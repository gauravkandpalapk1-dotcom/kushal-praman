from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import select

from backend.app.api.deps import DB, AdminUser, StaffUser
from backend.app.models import AuditLog
from backend.app.schemas.misc import AuditOut, AuditVerifyOut
from backend.app.services import audit

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=list[AuditOut], summary="Audit log, newest first")
def list_audit(db: DB, _admin: AdminUser, entity_type: str | None = None, entity_id: int | None = None,
               action: str | None = None, limit: Annotated[int, Query(ge=1, le=1000)] = 200):
    q = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    if entity_type:
        q = q.where(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        q = q.where(AuditLog.entity_id == entity_id)
    if action:
        q = q.where(AuditLog.action == action)
    return [audit.to_out(e) for e in db.scalars(q)]


@router.get("/verify", response_model=AuditVerifyOut, summary="Recompute the hash chain")
def verify(db: DB, _user: StaffUser):
    return audit.verify(db)
