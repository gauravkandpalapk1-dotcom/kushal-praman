from __future__ import annotations

from fastapi import APIRouter

from backend.app.api.deps import DB, AdminUser
from backend.app.schemas.misc import AgreementOut
from backend.app.services import agreement

router = APIRouter(tags=["agreement"])


@router.get("/agreement", response_model=AgreementOut,
            summary="Quadratic-weighted κ over double-scored decisions (null below threshold)")
def get_agreement(db: DB, _admin: AdminUser):
    return agreement.report(db)
