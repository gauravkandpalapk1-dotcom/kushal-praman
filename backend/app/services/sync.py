"""Offline sync support: evidence-number reservation and failed-attempt reporting."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.errors import Forbidden
from backend.app.models import EvidenceNumberReservation, SyncQueue, User
from backend.app.services import audit, sequence
from backend.app.timeutil import utcnow


def _candidate(user: User):
    if user.role != "candidate" or user.candidate is None:
        raise Forbidden("Only candidates use the sync queue.", "candidate_only")
    return user.candidate


def reserve(db: Session, user: User, count: int) -> list[int]:
    cand = _candidate(user)
    numbers = sequence.take(db, cand, count)
    for n in numbers:
        db.add(EvidenceNumberReservation(candidate_id=cand.id, number=n))
    label = f"#{numbers[0]}" if count == 1 else f"#{numbers[0]}–#{numbers[-1]}"
    audit.log(db, actor=user, action="sync.numbers_reserved", entity_type="candidate", entity_id=cand.id,
              summary=f"{cand.candidate_code} reserved evidence number(s) {label} for offline capture",
              details={"numbers": numbers})
    return numbers


def report_failure(db: Session, user: User, *, local_id: str, attempts: int, error: str | None,
                   offline_captured: bool) -> SyncQueue:
    cand = _candidate(user)
    row = db.scalar(select(SyncQueue).where(SyncQueue.local_id == local_id))
    if row is not None and row.candidate_id != cand.id:
        raise Forbidden("This local_id belongs to another candidate.", "not_owner")
    if row is not None and row.status == "synced":
        return row  # already synced: a late failure report does not downgrade it
    if row is None:
        row = SyncQueue(candidate_id=cand.id, local_id=local_id, status="failed", attempts=attempts,
                        offline_captured=offline_captured, is_demo=False)
        db.add(row)
    row.status, row.attempts, row.last_error = "failed", max(row.attempts or 0, attempts), (error or None)
    row.updated_at = utcnow()
    audit.log(db, actor=user, action="sync.failure_reported", entity_type="sync", entity_id=None,
              summary=f"{cand.candidate_code} reported a failed sync attempt ({attempts} so far)",
              details={"local_id": local_id, "attempts": attempts, "error": error})
    return row


def item_out(r: SyncQueue) -> dict[str, Any]:
    return {"local_id": r.local_id, "status": r.status, "attempts": r.attempts, "evidence_id": r.evidence_id,
            "last_error": r.last_error, "synced_at": r.synced_at, "updated_at": r.updated_at}


def mine(db: Session, user: User) -> list[SyncQueue]:
    cand = _candidate(user)
    return list(db.scalars(select(SyncQueue).where(SyncQueue.candidate_id == cand.id).order_by(SyncQueue.id.desc())))


def stats(db: Session) -> dict[str, Any]:
    rows = list(db.scalars(select(SyncQueue)))
    synced = sum(r.status == "synced" for r in rows)
    failed = sum(r.status == "failed" for r in rows)
    return {"items": len(rows), "synced": synced, "failed": failed,
            "success_rate": round(synced / (synced + failed), 4) if synced + failed else None}
