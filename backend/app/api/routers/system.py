from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from sqlalchemy import text

from ai.segmentation import ffmpeg_info
from backend.app.api.deps import DB
from backend.app.config import APP_VERSION, get_settings
from backend.app.db import engine_name
from backend.app.services import ai_runtime, audit
from backend.app.timeutil import iso, utcnow

router = APIRouter(tags=["system"])


@router.get("/health", summary="System health: DB, storage, ffmpeg, AI services, audit chain (public)")
def health(db: DB) -> dict[str, Any]:
    s = get_settings()
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:  # noqa: BLE001
        db_ok = False
    storage_ok = True
    try:
        s.uploads_dir.mkdir(parents=True, exist_ok=True)
        probe = s.uploads_dir / ".health"
        probe.write_bytes(b"ok")
        probe.unlink()
    except OSError:
        storage_ok = False
    chain = audit.verify(db) if db_ok else {"ok": False, "entries": 0, "broken_at": None}
    ff = ffmpeg_info()
    demo_p = ai_runtime.demo_provider()
    status = "ok" if db_ok and storage_ok and ff["available"] and chain["ok"] else "degraded"
    return {
        "status": status, "mode": s.KP_MODE, "version": APP_VERSION, "time": iso(utcnow()),
        "db": {"ok": db_ok, "engine": engine_name()},
        "storage": {"ok": storage_ok},
        "ffmpeg": {"available": ff["available"], "version": ff["version"], "ffprobe": ff["ffprobe"]},
        "audit_chain": {"ok": chain["ok"], "entries": chain["entries"], "broken_at": chain.get("broken_at")},
        "demo_asset": {"available": demo_p.asset_available,
                       "sha256": demo_p.asset_sha256 if demo_p.asset_available else None},
        "services": [svc.to_dict() for svc in ai_runtime.registry().services_status()],
    }
