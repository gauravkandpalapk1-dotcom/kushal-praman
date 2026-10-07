from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Response

from backend.app.api.deps import DB, AssessorUser, StaffUser
from backend.app.errors import Conflict
from backend.app.schemas.assessment import AISupportOut, AssessmentOut, FinalIn, InitialIn, OpenIn
from backend.app.schemas.misc import AuditOut
from backend.app.services import assessment as svc
from backend.app.services import audit, record

router = APIRouter(prefix="/assessments", tags=["assessments"])


@router.post("", response_model=AssessmentOut, status_code=201,
             responses={200: {"description": "This assessor already opened it: existing assessment"}})
def open_assessment(body: OpenIn, response: Response, db: DB, user: AssessorUser):
    a, created = svc.open_assessment(db, user, body.evidence_id, body.pc_id)
    if not created:
        response.status_code = 200
    return svc.assessment_out(db, a)


@router.get("", response_model=list[AssessmentOut])
def list_assessments(db: DB, user: StaffUser,
                     status: Literal["opened", "initial_locked", "ai_revealed", "finalized"] | None = None):
    return [svc.assessment_out(db, a) for a in svc.list_for(db, user, status)]


@router.get("/{assessment_id}", response_model=AssessmentOut)
def get_assessment(assessment_id: int, db: DB, user: StaffUser):
    a = svc.get(db, assessment_id)
    svc.check_view(a, user)
    return svc.assessment_out(db, a)


@router.post("/{assessment_id}/initial", response_model=AssessmentOut,
             summary="Lock the initial score (immutable; 409 if already locked)")
def initial(assessment_id: int, body: InitialIn, db: DB, user: AssessorUser):
    a = svc.lock_initial(db, svc.get(db, assessment_id), user, body.score, body.note)
    return svc.assessment_out(db, a)


@router.get("/{assessment_id}/ai-support", response_model=AISupportOut,
            summary="Interpretive AI output (409 initial_score_required until the initial score is locked)",
            responses={409: {"description": "initial_score_required"}})
def ai_support(assessment_id: int, db: DB, user: StaffUser):
    return svc.ai_support(db, svc.get(db, assessment_id), user)


@router.post("/{assessment_id}/final", response_model=AssessmentOut,
             summary="Final score (409 if not locked / already final; 422 if changed without rationale)")
def final(assessment_id: int, body: FinalIn, db: DB, user: AssessorUser):
    a = svc.finalize(db, svc.get(db, assessment_id), user, body.score, body.rationale)
    return svc.assessment_out(db, a)


@router.get("/{assessment_id}/audit", response_model=list[AuditOut])
def assessment_audit(assessment_id: int, db: DB, user: StaffUser):
    a = svc.get(db, assessment_id)
    svc.check_view(a, user)
    return [audit.to_out(e) for e in record.trail_entries(db, a)]


@router.get("/{assessment_id}/record.json", summary="Assessment record (JSON) — not a certificate")
def record_json(assessment_id: int, db: DB, user: StaffUser):
    a = svc.get(db, assessment_id)
    svc.check_view(a, user)
    rec = record.build(db, a)
    record.log_export(db, a, user, "json")
    return rec


@router.get("/{assessment_id}/record.pdf", response_class=Response,
            responses={200: {"content": {"application/pdf": {}}}},
            summary="Assessment record (PDF) — not a certificate")
def record_pdf(assessment_id: int, db: DB, user: StaffUser):
    a = svc.get(db, assessment_id)
    svc.check_view(a, user)
    try:
        pdf = record.render_pdf(record.build(db, a))
    except Exception as exc:  # noqa: BLE001
        raise Conflict("The PDF could not be generated.", "pdf_failed") from exc
    record.log_export(db, a, user, "pdf")
    fname = f"assessment-record-{a.evidence.display_number}-{a.pc.code}-{a.assessor.assessor_code}.pdf"
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{fname}"'})
