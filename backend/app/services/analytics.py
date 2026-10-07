"""Impact analytics. Pilot (is_demo=false) and demo values are always reported separately.

The pilot value is null with status "insufficient" until its n reaches the minimum
(METRIC_MIN_N; KAPPA_MIN_PAIRS for kappa). No value is ever estimated or invented.
"""
from __future__ import annotations

from collections import defaultdict
from statistics import median
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.models import Assessment, Assessor, Candidate, Evidence, EvidenceMapping, SyncQueue
from backend.app.services import agreement


def _pilot(value: float | None, n: int, min_n: int) -> dict[str, Any]:
    ok = n >= min_n and value is not None
    return {"value": round(value, 2) if ok else None, "n": n, "status": "reported" if ok else "insufficient",
            "min_n": min_n}


def _demo(value: float | None, n: int) -> dict[str, Any]:
    return {"value": None if value is None else round(value, 2), "n": n}


def _finalized(db: Session, is_demo: bool) -> list[Assessment]:
    return list(db.scalars(select(Assessment).where(Assessment.status == "finalized",
                                                    Assessment.is_demo.is_(is_demo))))


def _linked_pct(db: Session, items: list[Assessment]) -> float | None:
    if not items:
        return None
    linked = 0
    for a in items:
        hit = db.scalar(select(EvidenceMapping.id).where(
            EvidenceMapping.evidence_id == a.evidence_id, EvidenceMapping.pc_id == a.pc_id,
            EvidenceMapping.status.in_(("confirmed", "edited"))).limit(1))
        linked += hit is not None
    return 100.0 * linked / len(items)


def _minutes_per_candidate(items: list[Assessment]) -> tuple[float | None, int]:
    per: dict[int, float] = defaultdict(float)
    for a in items:
        if a.finalized_at and a.opened_at:
            per[a.candidate_id] += (a.finalized_at - a.opened_at).total_seconds() / 60.0
    return (median(per.values()) if per else None), len(per)


def _sync(db: Session, is_demo: bool) -> tuple[float | None, int]:
    rows = list(db.scalars(select(SyncQueue).where(SyncQueue.is_demo.is_(is_demo))))
    synced = sum(r.status == "synced" for r in rows)
    failed = sum(r.status == "failed" for r in rows)
    total = synced + failed
    return (100.0 * synced / total if total else None), total


def impact(db: Session) -> dict[str, Any]:
    s = get_settings()
    min_n, kmin = s.METRIC_MIN_N, s.KAPPA_MIN_PAIRS
    pilot_f, demo_f = _finalized(db, False), _finalized(db, True)

    pilot_pairs = agreement.collect_pairs(db, is_demo=False)
    demo_pairs = agreement.collect_pairs(db, is_demo=True)
    pk = agreement.summarise(pilot_pairs, kmin)
    dk = agreement.summarise(demo_pairs, kmin)
    p_min, p_min_n = _minutes_per_candidate(pilot_f)
    d_min, d_min_n = _minutes_per_candidate(demo_f)
    p_sync, p_sync_n = _sync(db, False)
    d_sync, d_sync_n = _sync(db, True)

    metrics = [
        {"key": "evidence_linked_pct", "label": "% of scores linked to evidence", "unit": "%",
         "definition": "Finalized assessments with ≥1 confirmed/edited evidence mapping ÷ all finalized assessments",
         "pilot": _pilot(_linked_pct(db, pilot_f), len(pilot_f), min_n),
         "demo": _demo(_linked_pct(db, demo_f), len(demo_f)),
         "note": "A score counts as linked when the assessor confirmed or edited an evidence→PC mapping for it."},
        {"key": "weighted_kappa", "label": "Inter-assessor agreement (quadratic-weighted κ)", "unit": "κ",
         "definition": "Quadratic-weighted Cohen's κ over the first two finalized, blind scores per (evidence, PC)",
         "pilot": {"value": pk["kappa"], "n": pk["n_pairs"], "status": pk["status"], "min_n": kmin},
         "demo": {"value": dk["kappa"], "n": dk["n_pairs"]},
         "note": f"Reported only at n ≥ {kmin} double-scored decisions. {pk['message']}"},
        {"key": "minutes_per_candidate", "label": "Assessor minutes per candidate", "unit": "min",
         "definition": "Median over candidates of the summed (finalized_at − opened_at) minutes of their assessments",
         "pilot": _pilot(p_min, p_min_n, min_n), "demo": _demo(d_min, d_min_n),
         "note": "Measures time from opening an assessment to the final decision; demo replays are near-instant."},
        {"key": "offline_sync_success", "label": "Offline sync success", "unit": "%",
         "definition": "Items synced ÷ (items synced + items reported failed and never synced)",
         "pilot": _pilot(p_sync, p_sync_n, min_n), "demo": _demo(d_sync, d_sync_n),
         "note": "An item that failed and later synced counts as synced. Failure reports without a synced upload "
                 "are counted as pilot data."},
    ]

    revealed = [a for a in pilot_f + demo_f if a.ai_revealed_at is not None]
    changed = sum(a.final_score != a.initial_score for a in revealed)
    flags = {a.is_demo for a in revealed}
    ai_source = "none" if not revealed else ("mixed" if len(flags) > 1 else ("demo" if True in flags else "pilot"))

    counts = {
        "candidates": db.scalar(select(func.count(Candidate.id))) or 0,
        "assessors": db.scalar(select(func.count(Assessor.id))) or 0,
        "evidence": db.scalar(select(func.count(Evidence.id))) or 0,
        "assessments": db.scalar(select(func.count(Assessment.id))) or 0,
        "double_scored": len(pilot_pairs) + len(demo_pairs),
    }
    return {
        "metrics": metrics,
        "ai_influence": {
            "post_reveal_change_rate": round(changed / len(revealed), 4) if revealed else None,
            "n": len(revealed),
            "note": "Share of finalized decisions where the final score differs from the locked initial score "
                    "(decisions where AI support was revealed).",
            "data_source": ai_source,
        },
        "counts": counts,
    }
