from __future__ import annotations

from fastapi import APIRouter

from backend.app.api.deps import DB, AssessorUser
from backend.app.schemas.mapping import EditIn, MappingOut, RejectIn
from backend.app.services import mapping as svc

router = APIRouter(prefix="/mappings", tags=["mappings"])


@router.post("/{mapping_id}/confirm", response_model=MappingOut,
             summary="Confirm (409 until your initial score for this PC is locked)")
def confirm(mapping_id: int, db: DB, user: AssessorUser, body: dict | None = None):
    m = svc.confirm(db, svc.get(db, mapping_id), user)
    return svc.mapping_out(db, m, user)


@router.post("/{mapping_id}/reject", response_model=MappingOut, summary="Reject with a reason (required)")
def reject(mapping_id: int, body: RejectIn, db: DB, user: AssessorUser):
    m = svc.reject(db, svc.get(db, mapping_id), user, body.reason)
    return svc.mapping_out(db, m, user)


@router.post("/{mapping_id}/edit", response_model=MappingOut, summary="Edit PC and/or span; original kept in audit")
def edit(mapping_id: int, body: EditIn, db: DB, user: AssessorUser):
    m = svc.edit(db, svc.get(db, mapping_id), user, pc_id=body.pc_id, start_s=body.start_s, end_s=body.end_s,
                 reason=body.reason)
    return svc.mapping_out(db, m, user)
