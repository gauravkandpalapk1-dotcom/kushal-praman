from __future__ import annotations

from fastapi import APIRouter

from backend.app.api.deps import DB, AdminUser
from backend.app.schemas.misc import ImpactOut
from backend.app.services import analytics

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/impact", response_model=ImpactOut, summary="Impact metrics: pilot vs demo, never invented")
def impact(db: DB, _admin: AdminUser):
    return analytics.impact(db)
