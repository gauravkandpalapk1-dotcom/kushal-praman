from __future__ import annotations

from fastapi import APIRouter

from backend.app.api.deps import DB, AdminUser, CandidateUser
from backend.app.schemas.misc import ReserveIn, ReserveOut, SyncItemOut, SyncReportIn, SyncStatsOut
from backend.app.services import sync as svc

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/reserve", response_model=ReserveOut, summary="Reserve evidence numbers for offline capture")
def reserve(body: ReserveIn, db: DB, user: CandidateUser):
    return {"numbers": svc.reserve(db, user, body.count)}


@router.post("/report", response_model=SyncItemOut, summary="Report a failed sync attempt")
def report(body: SyncReportIn, db: DB, user: CandidateUser):
    row = svc.report_failure(db, user, local_id=body.local_id, attempts=body.attempts, error=body.error,
                             offline_captured=body.offline_captured)
    return svc.item_out(row)


@router.get("/status", response_model=list[SyncItemOut], summary="My sync queue items (server view)")
def status(db: DB, user: CandidateUser):
    return [svc.item_out(r) for r in svc.mine(db, user)]


@router.get("/stats", response_model=SyncStatsOut)
def stats(db: DB, _admin: AdminUser):
    return svc.stats(db)
