"""Assessor-first assessment state machine (server-enforced).

    opened -> initial_locked -> ai_revealed -> finalized

* The initial score is immutable (second submit -> 409 initial_already_locked; also DB-unique).
* Interpretive AI output (ai-support) -> 409 initial_score_required until the initial score is locked.
  The first successful reveal stamps ai_revealed_at and writes `ai.revealed`.
* Final: 409 if not locked / already finalized; 422 if score != initial without a rationale.
* Blind double-scoring: nothing here ever returns another assessor's scores.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.errors import Conflict, Forbidden, NotFound, Unprocessable
from backend.app.models import (
    NOS,
    Assessment,
    AssessmentScore,
    Evidence,
    EvidenceMapping,
    PerformanceCriterion,
    User,
)
from backend.app.services import audit, pipeline
from backend.app.services import presenters as P
from backend.app.timeutil import utcnow

DISCLAIMER = "AI output identifies and describes evidence. It does not assess competency. The assessor decides."
CONFIDENCE_NOTE = ("Confidence is an uncalibrated relevance score used for ranking evidence, not a probability "
                   "and not a judgement of the candidate.")


def _code(user: User) -> str:
    return user.assessor.assessor_code if user.assessor else user.full_name


def get(db: Session, assessment_id: int) -> Assessment:
    a = db.get(Assessment, assessment_id)
    if a is None:
        raise NotFound("Assessment not found.", "assessment_not_found")
    return a


def check_view(a: Assessment, user: User) -> None:
    if user.role == "admin":
        return
    if user.role == "assessor" and user.assessor and a.assessor_id == user.assessor.id:
        return
    raise Forbidden("Only the assessing assessor or an admin can view this assessment.", "not_owner")


def check_owner(a: Assessment, user: User) -> None:
    if not (user.role == "assessor" and user.assessor and a.assessor_id == user.assessor.id):
        raise Forbidden("Only the assessor who opened this assessment can act on it.", "not_owner")


def primary_mapping(db: Session, evidence_id: int, pc_id: int) -> EvidenceMapping | None:
    maps = list(db.scalars(select(EvidenceMapping).where(EvidenceMapping.evidence_id == evidence_id,
                                                         EvidenceMapping.pc_id == pc_id).order_by(EvidenceMapping.id)))
    live = [m for m in maps if m.status != "rejected"]
    return (live or maps or [None])[0]


def open_assessment(db: Session, user: User, evidence_id: int, pc_id: int) -> tuple[Assessment, bool]:
    if user.role != "assessor" or user.assessor is None:
        raise Forbidden("Only assessors can open assessments.", "assessor_only")
    ev = db.get(Evidence, evidence_id)
    if ev is None:
        raise NotFound("Evidence not found.", "evidence_not_found")
    pc = db.get(PerformanceCriterion, pc_id)
    if pc is None:
        raise NotFound("Performance criterion not found.", "pc_not_found")
    if pc.nos.qualification_id != ev.qualification_id:
        raise Unprocessable("This PC does not belong to the evidence's qualification.", "pc_not_in_qualification")
    assessor = user.assessor
    existing = db.scalar(select(Assessment).where(Assessment.evidence_id == ev.id, Assessment.pc_id == pc.id,
                                                  Assessment.assessor_id == assessor.id))
    if existing is not None:
        return existing, False
    other = db.scalar(select(Assessment.id).where(Assessment.evidence_id == ev.id, Assessment.pc_id == pc.id,
                                                  Assessment.assessor_id != assessor.id).limit(1))
    second = other is not None
    a = Assessment(evidence_id=ev.id, pc_id=pc.id, assessor_id=assessor.id, candidate_id=ev.candidate_id,
                   rubric_id=pc.current_rubric.id if pc.current_rubric else None, status="opened",
                   max_score=pc.max_marks, blind=second, is_second_assessor=second, is_demo=ev.is_demo,
                   opened_at=utcnow())
    try:
        with audit.write_lock():
            db.add(a)
            db.flush()
            audit.log(db, actor=user, action="assessment.opened", entity_type="assessment", entity_id=a.id,
                      summary=f"{assessor.assessor_code} opened {pc.code} on {ev.label}"
                              + (" (blind second assessment)" if second else ""),
                      details={"evidence_id": ev.id, "pc_id": pc.id, "pc_code": pc.code, "blind": second,
                               "rubric_id": a.rubric_id, "is_demo": ev.is_demo})
    except IntegrityError:
        db.rollback()
        again = db.scalar(select(Assessment).where(Assessment.evidence_id == ev.id, Assessment.pc_id == pc.id,
                                                   Assessment.assessor_id == assessor.id))
        if again is None:
            raise
        return again, False
    return a, True


def _check_score(a: Assessment, score: int) -> None:
    if not isinstance(score, int) or score < 0 or score > a.max_score:
        raise Unprocessable(f"Score must be an integer from 0 to {a.max_score}.", "score_out_of_range")


def lock_initial(db: Session, a: Assessment, user: User, score: int, note: str | None) -> Assessment:
    check_owner(a, user)
    if a.is_locked or a.status != "opened":
        raise Conflict("The initial score is already locked and cannot be changed.", "initial_already_locked")
    _check_score(a, score)
    now = utcnow()
    try:
        a.scores.append(AssessmentScore(phase="initial", score=score, max_score=a.max_score, created_at=now))
        a.status = "initial_locked"
        a.initial_locked_at = now
        a.initial_note = (note or "").strip() or None
        audit.log(db, actor=user, action="assessment.initial_locked", entity_type="assessment", entity_id=a.id,
                  summary=f"Initial score {score}/{a.max_score} locked for {a.pc.code}",
                  details={"score": score, "max_score": a.max_score, "note": a.initial_note,
                           "evidence_id": a.evidence_id, "pc_code": a.pc.code})
    except IntegrityError:
        db.rollback()
        raise Conflict("The initial score is already locked and cannot be changed.", "initial_already_locked")
    db.refresh(a)
    return a


def mark_revealed(db: Session, a: Assessment, user: User, via: str) -> None:
    """First reveal of interpretive AI output to the owning assessor (timestamp + audit)."""
    if a.ai_revealed_at is not None or not a.is_locked:
        return
    a.ai_revealed_at = utcnow()
    if a.status == "initial_locked":
        a.status = "ai_revealed"
    audit.log(db, actor=user, action="ai.revealed", entity_type="assessment", entity_id=a.id,
              summary=f"AI evidence revealed to {_code(user)} for {a.pc.code}",
              details={"via": via, "evidence_id": a.evidence_id, "pc_code": a.pc.code,
                       "initial_score": a.initial_score})


def ai_support(db: Session, a: Assessment, user: User) -> dict[str, Any]:
    check_view(a, user)
    if not a.is_locked:
        raise Conflict("Lock your initial score before AI interpretation is shown.", "initial_score_required")
    if user.role == "assessor":
        mark_revealed(db, a, user, via="ai-support")
    ev, pc = a.evidence, a.pc
    speech = pipeline.step_output(db, ev, "speech")
    lines = (speech.output or {}).get("segments", []) if speech and speech.status == "done" else []
    llm = pipeline.step_output(db, ev, "llm")
    summary = (llm.output or {}).get("summary") if llm and llm.status == "done" else None

    maps = list(db.scalars(select(EvidenceMapping).where(EvidenceMapping.evidence_id == ev.id,
                                                         EvidenceMapping.pc_id == pc.id).order_by(EvidenceMapping.id)))
    findings = []
    for m in maps:
        if m.status == "rejected":
            continue
        s0, s1 = m.segment.start_s, m.segment.end_s
        findings.append({
            "mapping_id": m.id, "start_s": s0, "end_s": s1, "statement": m.statement, "signal": m.signal,
            "confidence": m.confidence, "rationale": m.rationale, "tags": m.tags, "mode": m.mode, "status": m.status,
            "transcript": [{"start_s": t["start_s"], "end_s": t["end_s"], "text": t["text"],
                            "translation_en": t.get("translation_en")}
                           for t in lines if t["end_s"] > s0 and t["start_s"] < s1],
        })
    if not findings:
        findings.append({"mapping_id": None, "start_s": None, "end_s": None,
                         "statement": f"No potential evidence for {pc.code} was surfaced in {ev.label}.",
                         "signal": "not_found", "confidence": None, "rationale": None, "tags": [], "mode": None,
                         "status": None, "transcript": []})
    services = [{"service": r.key, "provider": r.provider, "model": r.model, "mode": r.mode, "status": r.status}
                for r in pipeline.run_rows(db, ev) if r.key in ("speech", "vision", "ocr", "llm", "mapping")]
    is_demo = any(f.get("mode") == "demo" for f in findings) or any(s["mode"] == "demo" for s in services)
    return {
        "assessment_id": a.id, "mode": "demo" if is_demo else "real",
        "pc": {"id": pc.id, "code": pc.code, "text": pc.text, "max_marks": pc.max_marks},
        "nos": P.nos_brief(pc.nos), "findings": findings, "summary": summary, "services": services,
        "confidence_note": CONFIDENCE_NOTE, "disclaimer": DISCLAIMER, "ai_revealed_at": a.ai_revealed_at,
    }


def finalize(db: Session, a: Assessment, user: User, score: int, rationale: str | None) -> Assessment:
    check_owner(a, user)
    if a.status == "finalized" or a.final_score is not None:
        raise Conflict("This assessment is already finalized.", "already_finalized")
    if not a.is_locked:
        raise Conflict("Lock the initial score before submitting a final score.", "initial_score_required")
    _check_score(a, score)
    rationale = (rationale or "").strip() or None
    initial = a.initial_score
    if score != initial and not rationale:
        raise Unprocessable("A rationale is required when the final score differs from the initial score.",
                            "rationale_required")
    now = utcnow()
    try:
        a.scores.append(AssessmentScore(phase="final", score=score, max_score=a.max_score, created_at=now))
        a.status = "finalized"
        a.finalized_at = now
        a.final_rationale = rationale
        change = "unchanged from initial" if score == initial else f"changed from {initial}/{a.max_score}; rationale recorded"
        audit.log(db, actor=user, action="assessment.finalized", entity_type="assessment", entity_id=a.id,
                  summary=f"Final score {score}/{a.max_score} submitted for {a.pc.code} ({change})",
                  details={"score": score, "initial_score": initial, "max_score": a.max_score,
                           "rationale": rationale, "ai_revealed": a.ai_revealed_at is not None,
                           "score_changed": score != initial, "evidence_id": a.evidence_id, "pc_code": a.pc.code})
    except IntegrityError:
        db.rollback()
        raise Conflict("This assessment is already finalized.", "already_finalized")
    db.refresh(a)
    return a


def assessment_out(db: Session, a: Assessment) -> dict[str, Any]:
    pc = a.pc
    nos: NOS = pc.nos
    m = primary_mapping(db, a.evidence_id, a.pc_id)
    initial, final = a.initial_score, a.final_score
    return {
        "id": a.id, "status": a.status, "max_score": a.max_score, "blind": a.blind,
        "is_second_assessor": a.is_second_assessor, "is_demo": a.is_demo,
        "evidence": P.evidence_out(a.evidence), "candidate": P.candidate_ref(a.candidate),
        "qualification": P.qualification_brief(nos.qualification), "nos": P.nos_brief(nos),
        "pc": P.pc_out(pc, a.rubric), "assessor": P.assessor_ref(a.assessor),
        "opened_at": a.opened_at, "initial_score": initial, "initial_note": a.initial_note,
        "initial_locked_at": a.initial_locked_at, "ai_revealed_at": a.ai_revealed_at, "final_score": final,
        "final_rationale": a.final_rationale, "finalized_at": a.finalized_at,
        "score_changed": (final != initial) if final is not None else None,
        "mapping": {"id": m.id, "status": m.status} if m else None,
    }


def list_for(db: Session, user: User, status: str | None) -> list[Assessment]:
    q = select(Assessment).order_by(Assessment.id.desc())
    if user.role == "assessor":
        q = q.where(Assessment.assessor_id == (user.assessor.id if user.assessor else -1))
    if status:
        q = q.where(Assessment.status == status)
    return list(db.scalars(q))
