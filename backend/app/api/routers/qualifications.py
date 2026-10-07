from __future__ import annotations

from fastapi import APIRouter

from backend.app.api.deps import DB, AdminUser, CurrentUser
from backend.app.schemas.qualifications import (
    NOSIn,
    NOSOut,
    PCIn,
    PCOut,
    QualificationIn,
    QualificationListOut,
    QualificationOut,
    RubricIn,
    RubricOut,
    TreeOut,
)
from backend.app.services import presenters as P
from backend.app.services import qualifications as svc

router = APIRouter(tags=["qualifications"])


@router.get("/qualifications", response_model=list[QualificationListOut])
def list_qualifications(db: DB, _user: CurrentUser):
    return svc.list_out(db)


@router.get("/qualifications/{qid}/tree", response_model=TreeOut)
def tree(qid: int, db: DB, _user: CurrentUser):
    return P.tree_out(svc.get_qualification(db, qid))


@router.post("/qualifications", response_model=QualificationOut, status_code=201)
def create_qualification(body: QualificationIn, db: DB, admin: AdminUser):
    return P.qualification_out(svc.create_qualification(db, admin, body))


@router.post("/qualifications/{qid}/nos", response_model=NOSOut, status_code=201)
def create_nos(qid: int, body: NOSIn, db: DB, admin: AdminUser):
    n = svc.create_nos(db, admin, qid, body)
    return {"id": n.id, "code": n.code, "title": n.title, "version": n.version, "is_mandatory": n.is_mandatory, "pcs": []}


@router.post("/nos/{nos_id}/pcs", response_model=PCOut, status_code=201)
def create_pc(nos_id: int, body: PCIn, db: DB, admin: AdminUser):
    return P.pc_out(svc.create_pc(db, admin, nos_id, body))


@router.put("/pcs/{pc_id}/rubric", response_model=RubricOut, summary="Save a new rubric version for a PC")
def put_rubric(pc_id: int, body: RubricIn, db: DB, admin: AdminUser):
    return P.rubric_out(svc.put_rubric(db, admin, pc_id, body))
