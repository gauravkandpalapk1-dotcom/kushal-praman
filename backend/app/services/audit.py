"""Hash-chained, tamper-evident audit log.

    hash = sha256( prev_hash + canonical_json({ts, actor_id, action, entity_type, entity_id, summary, details}) )

canonical_json = sorted keys, compact separators, UTF-8. `ts` is rendered with microseconds.
The genesis prev_hash is 64 zeros. Appends are serialised by a process-wide lock that is held
until the transaction commits, so concurrent request/background-thread writes cannot fork the
chain. (Multi-process deployments would need a DB-level lock; this prototype runs one process.)

`log()` COMMITS the session: the business change and its audit entry land atomically.
"""
from __future__ import annotations

import hashlib
import json
import threading
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models import AuditLog, User
from backend.app.timeutil import iso_precise, utcnow

GENESIS = "0" * 64
_chain_lock = threading.RLock()


def write_lock() -> threading.RLock:
    """Hold this around a write unit that flushes BEFORE calling log() (e.g. to obtain new ids).

    With SQLite, a session that has flushed holds the database write lock; if it then waited for
    the chain lock while another thread held the chain lock and needed the DB write lock, both
    would stall. Taking the (re-entrant) chain lock first gives a single lock order.
    """
    return _chain_lock


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _normalise(details: dict[str, Any] | None) -> dict[str, Any]:
    """Round-trip through JSON so what we hash is exactly what the JSON column returns later."""
    return json.loads(canonical_json(details or {}))


def compute_hash(prev_hash: str, *, ts, actor_id, action, entity_type, entity_id, summary, details) -> str:
    payload = {
        "ts": iso_precise(ts), "actor_id": actor_id, "action": action, "entity_type": entity_type,
        "entity_id": entity_id, "summary": summary, "details": details,
    }
    return hashlib.sha256((prev_hash + canonical_json(payload)).encode("utf-8")).hexdigest()


def log(db: Session, *, actor: User | None, action: str, entity_type: str, entity_id: int | None,
        summary: str, details: dict[str, Any] | None = None, commit: bool = True) -> AuditLog:
    details_n = _normalise(details)
    with _chain_lock:
        try:
            db.flush()
            prev = db.scalar(select(AuditLog.hash).order_by(AuditLog.id.desc()).limit(1)) or GENESIS
            ts = utcnow()
            actor_id = actor.id if actor else None
            entry = AuditLog(
                ts=ts, actor_id=actor_id, action=action, entity_type=entity_type, entity_id=entity_id,
                summary=summary, details=details_n, prev_hash=prev,
                hash=compute_hash(prev, ts=ts, actor_id=actor_id, action=action, entity_type=entity_type,
                                  entity_id=entity_id, summary=summary, details=details_n),
            )
            db.add(entry)
            if commit:
                db.commit()
            else:
                db.flush()
        except Exception:
            db.rollback()
            raise
    return entry


def verify(db: Session) -> dict[str, Any]:
    """Recompute the whole chain. broken_at = id of the first entry that does not verify."""
    prev = GENESIS
    count = 0
    head = None
    for e in db.scalars(select(AuditLog).order_by(AuditLog.id)).yield_per(500):
        count += 1
        if e.prev_hash != prev:
            return {"ok": False, "entries": _count(db), "head_hash": _head(db), "broken_at": e.id,
                    "reason": "prev_hash does not match the previous entry's hash (entry removed or reordered)"}
        expected = compute_hash(prev, ts=e.ts, actor_id=e.actor_id, action=e.action, entity_type=e.entity_type,
                                entity_id=e.entity_id, summary=e.summary, details=e.details or {})
        if expected != e.hash:
            return {"ok": False, "entries": _count(db), "head_hash": _head(db), "broken_at": e.id,
                    "reason": "content does not match its hash (entry modified)"}
        prev = head = e.hash
    return {"ok": True, "entries": count, "head_hash": head, "broken_at": None, "reason": None}


def _count(db: Session) -> int:
    return db.scalar(select(func.count(AuditLog.id))) or 0


def _head(db: Session) -> str | None:
    return db.scalar(select(AuditLog.hash).order_by(AuditLog.id.desc()).limit(1))


def actor_view(e: AuditLog) -> dict[str, Any]:
    u = e.actor
    if u is None:
        name = "Processing pipeline" if e.action.startswith(("processing.", "mapping.proposed")) else "System"
        return {"id": None, "name": name, "role": "system", "code": None}
    code = None
    if u.assessor:
        code = u.assessor.assessor_code
    elif u.candidate:
        code = u.candidate.candidate_code
    return {"id": u.id, "name": u.full_name, "role": u.role, "code": code}


def to_out(e: AuditLog) -> dict[str, Any]:
    return {
        "id": e.id, "ts": e.ts, "actor": actor_view(e), "action": e.action, "entity_type": e.entity_type,
        "entity_id": e.entity_id, "summary": e.summary, "details": e.details or {}, "prev_hash": e.prev_hash,
        "hash": e.hash,
    }
