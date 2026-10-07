"""Idempotent seed: agency, demo users, Assistant Electrician QP tree + rubric, research references.

Run:  .venv/Scripts/python -m backend.app.services.seed      (applies migrations first)

Demo credentials (DEMO ONLY — change or disable before any real deployment):
  ┌──────────────────────┬────────────────┬───────────┬─────────────────────────────────────────┐
  │ email                │ password       │ role      │ profile                                 │
  ├──────────────────────┼────────────────┼───────────┼─────────────────────────────────────────┤
  │ admin@kp.demo        │ Admin@2026     │ admin     │ Demo Administrator                      │
  │ raj@kp.demo          │ Candidate@2026 │ candidate │ Raj Kumar · CAND-0001 · hi · Dehradun   │
  │ a07@kp.demo          │ Assessor@2026  │ assessor  │ Demo Assessor A · A-07 · AA-DEMO        │
  │ a12@kp.demo          │ Assessor@2026  │ assessor  │ Demo Assessor B · A-12 · AA-DEMO        │
  └──────────────────────┴────────────────┴───────────┴─────────────────────────────────────────┘
Seed content is loaded from database/seed/*.json and is not rewritten here.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.config import ROOT
from backend.app.models import (
    NOS,
    AssessmentAgency,
    Assessor,
    Candidate,
    PerformanceCriterion,
    Qualification,
    ResearchReference,
    Rubric,
    RubricLevel,
    User,
)
from backend.app.security.passwords import hash_password

SEED_DIR = ROOT / "database" / "seed"
QUALIFICATION_FILE = SEED_DIR / "qualification_assistant_electrician.json"
RESEARCH_FILE = SEED_DIR / "research_references.json"

AGENCY = {"name": "Demo Assessment Agency", "code": "AA-DEMO"}
RAJ_NEXT_EVIDENCE_NUMBER = 17

DEMO_USERS: list[dict[str, Any]] = [
    {"email": "admin@kp.demo", "password": "Admin@2026", "role": "admin", "full_name": "Demo Administrator"},
    {"email": "raj@kp.demo", "password": "Candidate@2026", "role": "candidate", "full_name": "Raj Kumar",
     "candidate_code": "CAND-0001", "preferred_language": "hi", "district": "Dehradun"},
    {"email": "a07@kp.demo", "password": "Assessor@2026", "role": "assessor", "full_name": "Demo Assessor A",
     "assessor_code": "A-07"},
    {"email": "a12@kp.demo", "password": "Assessor@2026", "role": "assessor", "full_name": "Demo Assessor B",
     "assessor_code": "A-12"},
]


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def seed_qualification(db: Session, data: dict[str, Any]) -> Qualification:
    qd = data["qualification"]
    q = db.scalar(select(Qualification).where(Qualification.nqr_code == qd["nqr_code"]))
    if q is None:
        q = Qualification(**{k: qd.get(k) for k in (
            "title", "nqr_code", "nsqf_level", "sector_skill_council", "version", "assessment_mode", "source_ref")})
        db.add(q)
        db.flush()
    for order, nd in enumerate(data.get("nos", [])):
        n = db.scalar(select(NOS).where(NOS.qualification_id == q.id, NOS.code == nd["code"]))
        if n is None:
            n = NOS(qualification_id=q.id, code=nd["code"], title=nd["title"], version=nd.get("version"),
                    is_mandatory=nd.get("is_mandatory", True), sort_order=order)
            db.add(n)
            db.flush()
        for pd in nd.get("pcs", []):
            pc = db.scalar(select(PerformanceCriterion).where(
                PerformanceCriterion.nos_id == n.id, PerformanceCriterion.code == pd["code"]))
            if pc is None:
                pc = PerformanceCriterion(nos_id=n.id, code=pd["code"], text=pd["text"],
                                          max_marks=pd.get("max_marks", 4), is_verbatim=pd.get("is_verbatim", False),
                                          source_note=pd.get("source_note"), keywords=pd.get("keywords", []))
                db.add(pc)
                db.flush()
            rd = pd.get("rubric")
            if rd and db.scalar(select(Rubric).where(Rubric.pc_id == pc.id)) is None:
                r = Rubric(pc_id=pc.id, version=1, status=rd.get("status", "draft"), author_note=rd.get("author_note"))
                db.add(r)
                db.flush()
                for lv in rd.get("levels", []):
                    db.add(RubricLevel(rubric_id=r.id, score=lv["score"], descriptor=lv["descriptor"],
                                       exemplar=lv.get("exemplar")))
    db.flush()
    return q


def seed_research(db: Session, refs: list[dict[str, Any]]) -> None:
    for rd in refs:
        r = db.scalar(select(ResearchReference).where(ResearchReference.number == rd["number"]))
        fields = {k: rd.get(k) for k in ("short", "citation", "url", "doi", "category", "what_it_says",
                                         "design_decision", "where_in_product")}
        if r is None:
            db.add(ResearchReference(number=rd["number"], **fields))
        else:
            for k, v in fields.items():
                setattr(r, k, v)


def seed_users(db: Session, agency: AssessmentAgency, qualification: Qualification) -> None:
    for ud in DEMO_USERS:
        if db.scalar(select(User).where(User.email == ud["email"])) is not None:
            continue
        u = User(email=ud["email"], password_hash=hash_password(ud["password"]), full_name=ud["full_name"],
                 role=ud["role"], is_active=True)
        db.add(u)
        db.flush()
        if ud["role"] == "candidate":
            db.add(Candidate(user_id=u.id, candidate_code=ud["candidate_code"], qualification_id=qualification.id,
                             preferred_language=ud.get("preferred_language"), district=ud.get("district"),
                             next_evidence_number=RAJ_NEXT_EVIDENCE_NUMBER))
        elif ud["role"] == "assessor":
            db.add(Assessor(user_id=u.id, assessor_code=ud["assessor_code"], agency_id=agency.id))


def run(db: Session) -> None:
    agency = db.scalar(select(AssessmentAgency).where(AssessmentAgency.code == AGENCY["code"]))
    if agency is None:
        agency = AssessmentAgency(**AGENCY)
        db.add(agency)
        db.flush()
    q = seed_qualification(db, _load(QUALIFICATION_FILE))
    seed_research(db, _load(RESEARCH_FILE))
    seed_users(db, agency, q)
    db.commit()


def main() -> None:
    from backend.app.db import SessionLocal, run_migrations

    run_migrations()
    db = SessionLocal()
    try:
        run(db)
    finally:
        db.close()
    print("Seed complete: agency AA-DEMO, 4 demo users, Assistant Electrician tree, research references.")


if __name__ == "__main__":
    main()
