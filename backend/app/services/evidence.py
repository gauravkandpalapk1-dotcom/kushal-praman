"""Evidence intake: validation, content-addressed storage, server-side hashing, idempotency, numbering.

Upload rules (server-enforced):
  * size limit -> 413; MIME + extension allow-list + magic-byte sniffing -> 415
  * stored as storage/uploads/<sha256>.<ext>; the client filename is kept only as metadata
  * SHA-256 recomputed server-side and compared with meta.client_sha256 -> integrity_ok
  * idempotent on meta.local_id: a repeat returns the existing record (created=False)
  * display_number = reserved number if reserved for this candidate and unused, else next in sequence
"""
from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.errors import Conflict, Forbidden, NotFound, PayloadTooLarge, Unprocessable
from backend.app.models import (
    Assessment,
    Candidate,
    Evidence,
    EvidenceMetadata,
    EvidenceNumberReservation,
    PerformanceCriterion,
    Qualification,
    SyncQueue,
    User,
)
from backend.app.schemas.evidence import EvidenceMetaIn
from backend.app.security.file_validation import validate_upload
from backend.app.services import ai_runtime, audit, sequence
from backend.app.timeutil import to_naive_utc, utcnow

CHUNK = 1024 * 1024
SNIFF_BYTES = 64


def _human_size(n: int) -> str:
    return f"{n / (1024 * 1024):.1f} MB" if n >= 1024 * 1024 else f"{max(1, n // 1024)} KB"


def stored_path(e: Evidence) -> Path:
    return get_settings().uploads_dir / e.stored_filename


def _spool(src: BinaryIO, max_bytes: int) -> tuple[Path, str, int, bytes]:
    """Copy the upload to a temp file under storage/tmp while hashing; enforce the size limit."""
    s = get_settings()
    s.tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp = s.tmp_dir / f"upload-{uuid.uuid4().hex}.part"
    h = hashlib.sha256()
    size = 0
    head = b""
    try:
        with open(tmp, "wb") as out:
            while chunk := src.read(CHUNK):
                if len(head) < SNIFF_BYTES:
                    head += chunk[: SNIFF_BYTES - len(head)]
                size += len(chunk)
                if size > max_bytes:
                    raise PayloadTooLarge(f"File exceeds the {get_settings().MAX_UPLOAD_MB:g} MB limit.", "file_too_large")
                h.update(chunk)
                out.write(chunk)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return tmp, h.hexdigest(), size, head


def _allocate_number(db: Session, cand: Candidate, reserved: int | None) -> int:
    if reserved is not None:
        r = db.scalar(select(EvidenceNumberReservation).where(
            EvidenceNumberReservation.candidate_id == cand.id, EvidenceNumberReservation.number == reserved,
            EvidenceNumberReservation.used.is_(False)))
        taken = db.scalar(select(Evidence.id).where(Evidence.candidate_id == cand.id, Evidence.display_number == reserved))
        if r is not None and taken is None:
            r.used = True
            return reserved
    while True:
        n = sequence.take(db, cand)[0]
        taken = db.scalar(select(Evidence.id).where(Evidence.candidate_id == cand.id, Evidence.display_number == n))
        reserved_elsewhere = db.scalar(select(EvidenceNumberReservation.id).where(
            EvidenceNumberReservation.candidate_id == cand.id, EvidenceNumberReservation.number == n))
        if taken is None and reserved_elsewhere is None:
            return n


def ingest(db: Session, user: User, src: BinaryIO, *, filename: str | None, content_type: str | None,
           meta: EvidenceMetaIn) -> tuple[Evidence, bool]:
    """Receive one evidence file. Returns (evidence, created)."""
    s = get_settings()
    cand = user.candidate
    if user.role != "candidate" or cand is None:
        raise Forbidden("Only candidates can submit evidence, and only for themselves.", "candidate_only")

    existing = db.scalar(select(Evidence).where(Evidence.local_id == meta.local_id))
    if existing is not None:
        if existing.candidate_id != cand.id:
            raise Conflict("This local_id belongs to another submission.", "local_id_conflict")
        return existing, False

    qid = meta.qualification_id or cand.qualification_id
    if qid is None or db.get(Qualification, qid) is None:
        raise Unprocessable("Unknown qualification_id.", "unknown_qualification")
    if meta.pc_hint_id is not None and db.get(PerformanceCriterion, meta.pc_hint_id) is None:
        raise Unprocessable("Unknown pc_hint_id.", "unknown_pc")

    tmp, sha, size, head = _spool(src, s.max_upload_bytes)
    try:
        if size == 0:
            raise Unprocessable("Empty file.", "empty_file")
        vf = validate_upload(filename, content_type, head, kind=meta.kind, allowed=s.allowed_mime_types)
        s.uploads_dir.mkdir(parents=True, exist_ok=True)
        stored_name = f"{sha}.{vf.extension}"
        final = s.uploads_dir / stored_name
        if final.exists():
            tmp.unlink(missing_ok=True)
        else:
            os.replace(tmp, final)
    finally:
        tmp.unlink(missing_ok=True)

    integrity_ok = sha == meta.client_sha256
    is_demo = ai_runtime.is_demo_asset(sha)
    now = utcnow()
    safe_name = Path(filename or "").name[:255] or None

    try:
        with audit.write_lock():
            number = _allocate_number(db, cand, meta.reserved_number)
            ev = Evidence(
                candidate_id=cand.id, qualification_id=qid, pc_hint_id=meta.pc_hint_id, display_number=number,
                kind=meta.kind, original_filename=safe_name, stored_filename=stored_name, mime_type=vf.mime_type,
                size_bytes=size, sha256=sha, client_sha256=meta.client_sha256, integrity_ok=integrity_ok,
                local_id=meta.local_id, status="received", is_demo=is_demo, offline_captured=meta.offline_captured,
                encrypted_at_rest=meta.encrypted_at_rest, captured_at=to_naive_utc(meta.captured_at), synced_at=now,
                notes=meta.notes,
            )
            db.add(ev)
            db.flush()
            db.add(EvidenceMetadata(
                evidence_id=ev.id, latitude=meta.latitude, longitude=meta.longitude, accuracy_m=meta.accuracy_m,
                device=meta.device, language=meta.language or cand.preferred_language,
                queued_at=to_naive_utc(meta.queued_at), sync_attempts=meta.sync_attempts,
            ))
            sq = db.scalar(select(SyncQueue).where(SyncQueue.local_id == meta.local_id))
            if sq is None:
                sq = SyncQueue(candidate_id=cand.id, local_id=meta.local_id)
                db.add(sq)
            sq.evidence_id = ev.id
            sq.status = "synced"
            sq.attempts = max(sq.attempts or 0, meta.sync_attempts)
            sq.offline_captured = meta.offline_captured
            sq.is_demo = is_demo
            sq.queued_at = to_naive_utc(meta.queued_at)
            sq.synced_at = now
            flags = [meta.kind, _human_size(size)]
            if meta.offline_captured:
                flags.append("captured offline")
            if meta.sync_attempts > 1:
                flags.append(f"synced on attempt {meta.sync_attempts}")
            audit.log(db, actor=user, action="evidence.received", entity_type="evidence", entity_id=ev.id,
                      summary=f"{ev.label} received from {cand.candidate_code} ({', '.join(flags)})",
                      details={"display_number": number, "kind": meta.kind, "mime_type": vf.mime_type,
                               "size_bytes": size, "local_id": meta.local_id, "is_demo": is_demo,
                               "offline_captured": meta.offline_captured, "encrypted_at_rest": meta.encrypted_at_rest,
                               "sync_attempts": meta.sync_attempts, "reserved_number": meta.reserved_number,
                               "latitude": meta.latitude, "longitude": meta.longitude,
                               "captured_at": meta.captured_at.isoformat() if meta.captured_at else None})
    except IntegrityError:
        db.rollback()
        again = db.scalar(select(Evidence).where(Evidence.local_id == meta.local_id))
        if again is not None and again.candidate_id == cand.id:
            return again, False
        raise Conflict("Evidence could not be stored due to a concurrent submission; retry.", "concurrent_upload")

    if integrity_ok:
        audit.log(db, actor=user, action="evidence.integrity_verified", entity_type="evidence", entity_id=ev.id,
                  summary=f"{ev.label} received; SHA-256 verified ({sha[:8]}…{sha[-4:]})",
                  details={"sha256": sha, "client_sha256": meta.client_sha256, "match": True})
    else:
        audit.log(db, actor=user, action="evidence.integrity_failed", entity_type="evidence", entity_id=ev.id,
                  summary=f"{ev.label}: SHA-256 mismatch (client {meta.client_sha256[:8]}…, server {sha[:8]}…)",
                  details={"sha256": sha, "client_sha256": meta.client_sha256, "match": False})
    db.refresh(ev)
    return ev, True


def get_for_viewer(db: Session, evidence_id: int, user: User) -> Evidence:
    ev = db.get(Evidence, evidence_id)
    if ev is None:
        raise NotFound("Evidence not found.", "evidence_not_found")
    if user.role == "candidate" and (user.candidate is None or ev.candidate_id != user.candidate.id):
        raise Forbidden("You can only view your own evidence.", "not_owner")
    return ev


def list_for_viewer(db: Session, user: User, *, status: str | None, candidate_id: int | None) -> list[Evidence]:
    q = select(Evidence).order_by(Evidence.id.desc())
    if user.role == "candidate":
        q = q.where(Evidence.candidate_id == (user.candidate.id if user.candidate else -1))
    elif candidate_id is not None:
        q = q.where(Evidence.candidate_id == candidate_id)
    if status:
        q = q.where(Evidence.status == status)
    return list(db.scalars(q))


def assessor_has_locked(db: Session, assessor_id: int, evidence_id: int, pc_id: int) -> Assessment | None:
    a = db.scalar(select(Assessment).where(Assessment.assessor_id == assessor_id, Assessment.evidence_id == evidence_id,
                                           Assessment.pc_id == pc_id))
    return a if a is not None and a.is_locked else None
