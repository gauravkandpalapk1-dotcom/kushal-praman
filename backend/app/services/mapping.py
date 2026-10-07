"""Evidence mappings: tier-gated views and assessor decisions (confirm / edit / reject).

Tier rule (docs/API.md):
  admin     -> always sees interpretive fields (confidence, rationale, tags, signal)
  assessor  -> only for a PC where they hold an assessment whose initial score is locked
  candidate -> never
Decisions: assessor only, and only once that assessor's initial score for that (evidence, PC) is locked.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai import guardrails
from ai import mapper as lexmap
from backend.app.errors import Conflict, Forbidden, NotFound, Unprocessable
from backend.app.models import Assessment, Evidence, EvidenceMapping, EvidenceSegment, PerformanceCriterion, User
from backend.app.services import audit
from backend.app.services.assessment import mark_revealed
from backend.app.timeutil import utcnow

LOCK_ASSESSOR = "Revealed after your initial score is locked"
LOCK_CANDIDATE = "Interpretive AI output is shown to assessors only"


def get(db: Session, mapping_id: int) -> EvidenceMapping:
    m = db.get(EvidenceMapping, mapping_id)
    if m is None:
        raise NotFound("Mapping not found.", "mapping_not_found")
    return m


def _assessment_of(db: Session, user: User, evidence_id: int, pc_id: int) -> Assessment | None:
    if user.assessor is None:
        return None
    return db.scalar(select(Assessment).where(Assessment.assessor_id == user.assessor.id,
                                              Assessment.evidence_id == evidence_id, Assessment.pc_id == pc_id))


def mapping_out(db: Session, m: EvidenceMapping, user: User) -> dict[str, Any]:
    ev: Evidence = db.get(Evidence, m.evidence_id)
    pc = m.pc
    if user.role == "admin":
        locked, reason = False, None
    elif user.role == "assessor":
        a = _assessment_of(db, user, m.evidence_id, m.pc_id)
        locked = a is None or not a.is_locked
        reason = LOCK_ASSESSOR if locked else None
        if not locked:
            mark_revealed(db, a, user, via="mappings")
    else:
        locked, reason = True, LOCK_CANDIDATE
    q = ev.qualification
    return {
        "id": m.id, "evidence_id": m.evidence_id,
        "segment": {"id": m.segment.id, "start_s": m.segment.start_s, "end_s": m.segment.end_s},
        "pc": {"id": pc.id, "code": pc.code, "text": pc.text,
               "nos": {"id": pc.nos.id, "code": pc.nos.code, "title": pc.nos.title}},
        "qualification": {"id": q.id, "title": q.title, "nqr_code": q.nqr_code},
        "statement": m.statement, "status": m.status, "mode": m.mode,
        "decided_by": m.decided_by.assessor_code if m.decided_by else None, "decided_at": m.decided_at,
        "locked": locked, "lock_reason": reason,
        "confidence": None if locked else m.confidence,
        "rationale": None if locked else m.rationale,
        "tags": None if locked else (m.tags or []),
        "signal": None if locked else m.signal,
    }


def list_for_evidence(db: Session, ev: Evidence, user: User) -> list[dict[str, Any]]:
    maps = db.scalars(select(EvidenceMapping).where(EvidenceMapping.evidence_id == ev.id).order_by(EvidenceMapping.id))
    return [mapping_out(db, m, user) for m in maps]


def _require_decider(db: Session, m: EvidenceMapping, user: User) -> Assessment:
    if user.role != "assessor" or user.assessor is None:
        raise Forbidden("Only assessors decide on mappings.", "assessor_only")
    a = _assessment_of(db, user, m.evidence_id, m.pc_id)
    if a is None or not a.is_locked:
        raise Conflict("Lock your initial score for this PC before deciding on the AI mapping.",
                       "initial_score_required")
    return a


def _snapshot(m: EvidenceMapping) -> dict[str, Any]:
    return {"pc_id": m.pc_id, "pc_code": m.pc.code, "segment_id": m.segment_id, "start_s": m.segment.start_s,
            "end_s": m.segment.end_s, "statement": m.statement, "status": m.status}


def _span(m: EvidenceMapping) -> str:
    return f"{lexmap.format_ts(m.segment.start_s)}–{lexmap.format_ts(m.segment.end_s)}"


def confirm(db: Session, m: EvidenceMapping, user: User) -> EvidenceMapping:
    a = _require_decider(db, m, user)
    before = m.status
    m.status, m.decided_by_id, m.decided_at, m.decision_reason = "confirmed", user.assessor.id, utcnow(), None
    ev = db.get(Evidence, m.evidence_id)
    audit.log(db, actor=user, action="mapping.confirmed", entity_type="mapping", entity_id=m.id,
              summary=f"{user.assessor.assessor_code} confirmed mapping {ev.label} → {m.pc.code} ({_span(m)})",
              details={"assessment_id": a.id, "previous_status": before, **_snapshot(m)})
    return m


def reject(db: Session, m: EvidenceMapping, user: User, reason: str) -> EvidenceMapping:
    a = _require_decider(db, m, user)
    reason = (reason or "").strip()
    if not reason:
        raise Unprocessable("A reason is required to reject a mapping.", "reason_required")
    before = m.status
    m.status, m.decided_by_id, m.decided_at, m.decision_reason = "rejected", user.assessor.id, utcnow(), reason
    ev = db.get(Evidence, m.evidence_id)
    audit.log(db, actor=user, action="mapping.rejected", entity_type="mapping", entity_id=m.id,
              summary=f"{user.assessor.assessor_code} rejected mapping {ev.label} → {m.pc.code} ({_span(m)})",
              details={"assessment_id": a.id, "reason": reason, "previous_status": before, **_snapshot(m)})
    return m


def edit(db: Session, m: EvidenceMapping, user: User, *, pc_id: int | None, start_s: float | None,
         end_s: float | None, reason: str | None) -> EvidenceMapping:
    a = _require_decider(db, m, user)
    ev = db.get(Evidence, m.evidence_id)
    original = _snapshot(m)
    new_pc = m.pc
    if pc_id is not None and pc_id != m.pc_id:
        new_pc = db.get(PerformanceCriterion, pc_id)
        if new_pc is None or new_pc.nos.qualification_id != ev.qualification_id:
            raise Unprocessable("pc_id must be a PC of this evidence's qualification.", "pc_not_in_qualification")
    s0 = m.segment.start_s if start_s is None else float(start_s)
    s1 = m.segment.end_s if end_s is None else float(end_s)
    duration = ev.meta.duration_s if ev.meta else None
    if s1 < s0 or (s1 == s0 and ev.kind in ("video", "audio")) or (duration and s1 > duration + 0.5):
        raise Unprocessable("start_s/end_s must define a span inside the recording.", "invalid_span")
    with audit.write_lock():
        seg = db.scalar(select(EvidenceSegment).where(
            EvidenceSegment.evidence_id == ev.id, EvidenceSegment.start_s.between(s0 - 0.01, s0 + 0.01),
            EvidenceSegment.end_s.between(s1 - 0.01, s1 + 0.01)).limit(1))
        if seg is None:
            seg = EvidenceSegment(evidence_id=ev.id, run=ev.processing_run or 1, idx=999, start_s=s0, end_s=s1,
                                  label=f"Edited {lexmap.format_ts(s0)}–{lexmap.format_ts(s1)}", source="manual")
            db.add(seg)
            db.flush()
        m.segment_id = seg.id
        m.segment = seg
        m.pc_id, m.pc = new_pc.id, new_pc
        m.statement = guardrails.neutralise(lexmap.statement(new_pc.code, s0, s1)).text
        m.status, m.decided_by_id, m.decided_at = "edited", user.assessor.id, utcnow()
        m.decision_reason = (reason or "").strip() or None
        audit.log(db, actor=user, action="mapping.edited", entity_type="mapping", entity_id=m.id,
                  summary=(f"{user.assessor.assessor_code} edited mapping {ev.label}: {original['pc_code']} "
                           f"{lexmap.format_ts(original['start_s'])}–{lexmap.format_ts(original['end_s'])} → "
                           f"{new_pc.code} {lexmap.format_ts(s0)}–{lexmap.format_ts(s1)}"),
                  details={"assessment_id": a.id, "original": original, "new": _snapshot(m),
                           "reason": m.decision_reason})
    return m
