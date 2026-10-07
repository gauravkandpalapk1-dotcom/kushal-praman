from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from sqlalchemy import select

from backend.app.api.deps import DB, AdminUser
from backend.app.models import AssessmentAgency, User
from backend.app.schemas.auth import AdminUserIn, AdminUserPatch, AgencyListOut, UserOut
from backend.app.services import presenters as P
from backend.app.services import users as user_svc

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserOut])
def list_users(db: DB, _admin: AdminUser, role: Literal["candidate", "assessor", "admin"] | None = None):
    q = select(User).order_by(User.id)
    if role:
        q = q.where(User.role == role)
    return [P.user_out(u) for u in db.scalars(q)]


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(body: AdminUserIn, db: DB, admin: AdminUser):
    u = user_svc.create_user(db, actor=admin, email=body.email, password=body.password, full_name=body.full_name,
                             role=body.role, assessor_code=body.assessor_code, qualification_id=body.qualification_id,
                             preferred_language=body.preferred_language, district=body.district,
                             action="admin.user_created")
    return P.user_out(u)


@router.patch("/users/{user_id}", response_model=UserOut)
def patch_user(user_id: int, body: AdminUserPatch, db: DB, admin: AdminUser):
    return P.user_out(user_svc.set_active(db, admin, user_id, body.is_active))


@router.get("/agencies", response_model=list[AgencyListOut])
def agencies(db: DB, _admin: AdminUser):
    return [{"id": a.id, "name": a.name, "code": a.code, "assessor_count": len(a.assessors)}
            for a in db.scalars(select(AssessmentAgency).order_by(AssessmentAgency.id))]
