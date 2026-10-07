"""Admin management of the QP -> NOS -> PC -> Rubric hierarchy."""
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.errors import Conflict, NotFound, Unprocessable
from backend.app.models import NOS, PerformanceCriterion, Qualification, Rubric, RubricLevel, User
from backend.app.services import audit
from backend.app.services import presenters as P


def get_qualification(db: Session, qid: int) -> Qualification:
    q = db.get(Qualification, qid)
    if q is None:
        raise NotFound("Qualification not found.", "qualification_not_found")
    return q


def list_out(db: Session) -> list[dict[str, Any]]:
    out = []
    for q in db.scalars(select(Qualification).order_by(Qualification.id)):
        pc_count = db.scalar(select(func.count(PerformanceCriterion.id)).join(NOS).where(NOS.qualification_id == q.id))
        out.append({**P.qualification_out(q), "nos_count": len(q.nos), "pc_count": pc_count or 0})
    return out


def create_qualification(db: Session, admin: User, data) -> Qualification:
    if db.scalar(select(Qualification.id).where(Qualification.nqr_code == data.nqr_code)) is not None:
        raise Conflict("A qualification with this NQR code exists.", "nqr_code_taken")
    with audit.write_lock():
        q = Qualification(**data.model_dump())
        db.add(q)
        db.flush()
        audit.log(db, actor=admin, action="admin.qualification_created", entity_type="qualification", entity_id=q.id,
                  summary=f"Qualification {q.title} ({q.nqr_code}) added", details=data.model_dump())
    return q


def create_nos(db: Session, admin: User, qid: int, data) -> NOS:
    q = get_qualification(db, qid)
    if db.scalar(select(NOS.id).where(NOS.qualification_id == q.id, NOS.code == data.code)) is not None:
        raise Conflict("This NOS code already exists in the qualification.", "nos_code_taken")
    with audit.write_lock():
        n = NOS(qualification_id=q.id, sort_order=len(q.nos), **data.model_dump())
        db.add(n)
        db.flush()
        audit.log(db, actor=admin, action="admin.nos_created", entity_type="nos", entity_id=n.id,
                  summary=f"NOS {n.code} added to {q.title}", details=data.model_dump())
    return n


def create_pc(db: Session, admin: User, nos_id: int, data) -> PerformanceCriterion:
    n = db.get(NOS, nos_id)
    if n is None:
        raise NotFound("NOS not found.", "nos_not_found")
    if db.scalar(select(PerformanceCriterion.id).where(PerformanceCriterion.nos_id == n.id,
                                                       PerformanceCriterion.code == data.code)) is not None:
        raise Conflict("This PC code already exists in the NOS.", "pc_code_taken")
    with audit.write_lock():
        pc = PerformanceCriterion(nos_id=n.id, **data.model_dump())
        db.add(pc)
        db.flush()
        audit.log(db, actor=admin, action="admin.pc_created", entity_type="pc", entity_id=pc.id,
                  summary=f"{pc.code} added to {n.code}", details=data.model_dump())
    return pc


def put_rubric(db: Session, admin: User, pc_id: int, data) -> Rubric:
    pc = db.get(PerformanceCriterion, pc_id)
    if pc is None:
        raise NotFound("Performance criterion not found.", "pc_not_found")
    scores = sorted(lv.score for lv in data.levels)
    if scores != list(range(pc.max_marks + 1)):
        raise Unprocessable(f"Rubric levels must cover each score 0..{pc.max_marks} exactly once.", "rubric_levels_invalid")
    version = (db.scalar(select(func.max(Rubric.version)).where(Rubric.pc_id == pc.id)) or 0) + 1
    with audit.write_lock():
        r = Rubric(pc_id=pc.id, version=version, status=data.status, author_note=data.author_note,
                   created_by_id=admin.id)
        db.add(r)
        db.flush()
        for lv in data.levels:
            db.add(RubricLevel(rubric_id=r.id, score=lv.score, descriptor=lv.descriptor, exemplar=lv.exemplar))
        audit.log(db, actor=admin, action="admin.rubric_versioned", entity_type="rubric", entity_id=r.id,
                  summary=f"Rubric v{version} ({data.status}) saved for {pc.code}",
                  details={"pc_id": pc.id, "version": version, "status": data.status})
    db.expire(pc, ["rubrics"])
    return r
