from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header

from backend.app.api.deps import DB, AdminUser
from backend.app.config import get_settings
from backend.app.errors import NotFound
from backend.app.schemas.misc import DemoResetIn, DemoResetOut
from backend.app.services import demo, media

router = APIRouter(prefix="/demo", tags=["demo"])


@router.get("/media/practical", summary="The synthetic demo practical video (demo mode only; Range supported)")
def demo_media(range_header: Annotated[str | None, Header(alias="Range")] = None):
    s = get_settings()
    if not s.is_demo_mode:
        raise NotFound("Demo media is only served in KP_MODE=demo.", "demo_mode_only")
    return media.file_response(s.DEMO_ASSET_PATH, "video/mp4", range_header, filename="practical_demo.mp4")


@router.post("/reset", response_model=DemoResetOut,
             summary="Wipe, re-seed and replay the demo story to a stage (admin, demo mode only; 409 otherwise)")
def reset(body: DemoResetIn, db: DB, _admin: AdminUser):
    return demo.reset(db, body.stage)
