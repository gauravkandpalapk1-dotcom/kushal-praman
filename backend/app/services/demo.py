"""Demo reset: wipe all data, re-seed, then replay the jury story through the REAL service functions.

Stages:
  fresh              nothing captured; Raj's next evidence number is 17
  processed          Evidence #17 = demo video uploaded by Raj (captured offline, encrypted queue, geotagged,
                     one failed sync attempt then success), pipeline run synchronously to done
  assessor_a_scored  A-07 opens PC10, locks 3/4, reveals AI support, confirms the mapping, finalises 3/4
  both_scored        A-12 scores blind: 3/4 -> 3/4
"""
from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.db import Base
from backend.app.errors import Conflict, NotFound
from backend.app.models import NOS, Evidence, PerformanceCriterion, User
from backend.app.schemas.evidence import EvidenceMetaIn
from backend.app.services import ai_runtime, audit, pipeline, seed
from backend.app.services import assessment as assess
from backend.app.services import evidence as evidence_svc
from backend.app.services import mapping as mapping_svc
from backend.app.services import sync as sync_svc
from backend.app.timeutil import utcnow

STAGES = ["fresh", "processed", "assessor_a_scored", "both_scored"]
DEMO_GEO = (30.3165, 78.0322)


def wipe(db: Session) -> None:
    with audit.write_lock():
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.commit()
    db.expunge_all()
    uploads = get_settings().uploads_dir
    if uploads.is_dir():
        for f in uploads.iterdir():
            if f.is_file():
                f.unlink(missing_ok=True)


def _user(db: Session, email: str) -> User:
    u = db.scalar(select(User).where(User.email == email))
    if u is None:
        raise NotFound(f"Seed user {email} missing.", "seed_missing")
    return u


def _pc10(db: Session) -> PerformanceCriterion:
    pc = db.scalar(select(PerformanceCriterion).join(NOS).where(NOS.code == "ISC/N1002",
                                                                PerformanceCriterion.code == "PC10"))
    if pc is None:
        raise NotFound("PC10 missing from seed.", "seed_missing")
    return pc


def _capture_and_process(db: Session) -> Evidence:
    demo = ai_runtime.demo_provider()
    if not demo.asset_available:
        raise Conflict("Demo video storage/demo/practical_demo.mp4 is missing.", "demo_asset_missing")
    raj, a07 = _user(db, "raj@kp.demo"), _user(db, "a07@kp.demo")
    pc = _pc10(db)
    numbers = sync_svc.reserve(db, raj, 3)
    local_id = f"demo-{uuid.uuid4().hex[:16]}"
    captured = utcnow() - timedelta(minutes=48)
    sync_svc.report_failure(db, raj, local_id=local_id, attempts=1, error="Network unavailable (device offline)",
                            offline_captured=True)
    meta = EvidenceMetaIn(
        local_id=local_id, kind="video", qualification_id=pc.nos.qualification_id, pc_hint_id=pc.id,
        client_sha256=demo.asset_sha256, captured_at=captured, latitude=DEMO_GEO[0], longitude=DEMO_GEO[1],
        accuracy_m=12, device="Android 14 · Chrome (field tablet)", language="hi", reserved_number=numbers[0],
        encrypted_at_rest=True, offline_captured=True, queued_at=captured + timedelta(minutes=1), sync_attempts=2,
    )
    with open(demo.asset_path, "rb") as f:
        ev, _ = evidence_svc.ingest(db, raj, f, filename="practical_demo.mp4", content_type="video/mp4", meta=meta)
    pipeline.start(db, ev, a07, background=False)
    db.expire_all()
    return db.get(Evidence, ev.id)


def _score(db: Session, email: str, ev: Evidence, initial: int, note: str, final: int, *,
           confirm_mapping: bool) -> int:
    user = _user(db, email)
    pc = _pc10(db)
    a, _ = assess.open_assessment(db, user, ev.id, pc.id)
    assess.lock_initial(db, a, user, initial, note)
    assess.ai_support(db, a, user)
    if confirm_mapping:
        m = assess.primary_mapping(db, ev.id, pc.id)
        if m is not None:
            mapping_svc.confirm(db, m, user)
    assess.finalize(db, a, user, final, None if final == initial else "Adjusted after reviewing the segment again.")
    return a.id


def reset(db: Session, stage: str) -> dict[str, Any]:
    if not get_settings().is_demo_mode:
        raise Conflict("Demo reset is only available in KP_MODE=demo.", "demo_mode_only")
    if stage not in STAGES:
        raise Conflict(f"Unknown stage '{stage}'.", "unknown_stage")
    wipe(db)
    seed.run(db)
    admin = _user(db, "admin@kp.demo")
    audit.log(db, actor=admin, action="demo.reset", entity_type="system", entity_id=None,
              summary=f"Demo reset to stage '{stage}' (data wiped, re-seeded, story replayed via service calls)",
              details={"stage": stage})
    level = STAGES.index(stage)
    ev_id: int | None = None
    assessment_ids: list[int] = []
    if level >= 1:
        ev = _capture_and_process(db)
        ev_id = ev.id
        if level >= 2:
            assessment_ids.append(_score(db, "a07@kp.demo", ev, 3,
                                         "Insulated stripper and crimping tool used correctly; lug re-seated once.",
                                         3, confirm_mapping=True))
        if level >= 3:
            assessment_ids.append(_score(db, "a12@kp.demo", ev, 3,
                                         "Correct, safe termination at the panel; minor rework observed.",
                                         3, confirm_mapping=False))
    chain = audit.verify(db)
    return {"ok": True, "stage": stage, "evidence_id": ev_id, "assessment_ids": assessment_ids,
            "audit_chain": chain, "message": f"Demo data reset to '{stage}'."}
