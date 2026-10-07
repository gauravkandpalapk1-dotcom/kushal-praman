"""Inter-assessor agreement: weighted Cohen's kappa implemented from first principles (numpy).

    O_ij = observed proportion of pairs with (rater A = i, rater B = j)
    E_ij = row_i * col_j                      (chance agreement from the marginals)
    W_ij = (i - j)^2  (quadratic)  or  |i - j|  (linear)
    kappa_w = 1 - sum(W * O) / sum(W * E)

Categories are 0..max_marks (fixed, not just the observed values), matching
sklearn.metrics.cohen_kappa_score(y1, y2, labels=range(K+1), weights=...).

Edge case: when sum(W * E) == 0 (both raters used one single, identical category, i.e. zero
variance), kappa is mathematically undefined (0/0). We return None rather than inventing 1.0;
exact/adjacent agreement are still reported. (sklearn returns nan in this case.)
If only one rater has zero variance, E is non-zero and kappa is well defined (typically 0).

Pairs = the first two FINALIZED assessments by distinct assessors on the same (evidence, PC), by
finalized_at, using final scores. Below KAPPA_MIN_PAIRS nothing is reported (all values null).
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.models import Assessment


def weighted_kappa(a: Sequence[int], b: Sequence[int], n_categories: int, weights: str = "quadratic") -> float | None:
    if len(a) != len(b):
        raise ValueError("rating vectors must have equal length")
    if len(a) == 0:
        return None
    k = n_categories
    o = np.zeros((k, k), dtype=float)
    for x, y in zip(a, b):
        if not (0 <= x < k and 0 <= y < k):
            raise ValueError(f"rating outside 0..{k - 1}")
        o[int(x), int(y)] += 1
    o /= o.sum()
    e = np.outer(o.sum(axis=1), o.sum(axis=0))
    idx = np.arange(k)
    diff = np.abs(idx[:, None] - idx[None, :]).astype(float)
    if weights == "quadratic":
        w = diff ** 2
    elif weights == "linear":
        w = diff
    elif weights in ("none", "unweighted", None):
        w = (diff > 0).astype(float)
    else:
        raise ValueError(f"unknown weights: {weights}")
    expected = float((w * e).sum())
    if expected == 0.0:
        return None
    return float(1.0 - (w * o).sum() / expected)


def exact_agreement(a: Sequence[int], b: Sequence[int]) -> float | None:
    return float(np.mean(np.asarray(a) == np.asarray(b))) if len(a) else None


def adjacent_agreement(a: Sequence[int], b: Sequence[int]) -> float | None:
    return float(np.mean(np.abs(np.asarray(a) - np.asarray(b)) <= 1)) if len(a) else None


def collect_pairs(db: Session, *, is_demo: bool | None = None) -> list[dict[str, Any]]:
    q = select(Assessment).where(Assessment.status == "finalized").order_by(Assessment.finalized_at, Assessment.id)
    if is_demo is not None:
        q = q.where(Assessment.is_demo.is_(is_demo))
    groups: dict[tuple[int, int], list[Assessment]] = defaultdict(list)
    for a in db.scalars(q):
        groups[(a.evidence_id, a.pc_id)].append(a)
    pairs = []
    for (_ev, _pc), items in groups.items():
        first = items[0]
        second = next((x for x in items[1:] if x.assessor_id != first.assessor_id), None)
        if second is None:
            continue
        pairs.append({
            "evidence_label": first.evidence.label, "pc_code": first.pc.code,
            "candidate": first.candidate.user.full_name,
            "assessor_a": first.assessor.assessor_code, "score_a": first.final_score,
            "assessor_b": second.assessor.assessor_code, "score_b": second.final_score,
            "max_score": max(first.max_score, second.max_score),
            "is_demo": bool(first.is_demo or second.is_demo),
        })
    return pairs


def summarise(pairs: list[dict[str, Any]], threshold: int) -> dict[str, Any]:
    n = len(pairs)
    a = [p["score_a"] for p in pairs]
    b = [p["score_b"] for p in pairs]
    k = (max(p["max_score"] for p in pairs) + 1) if pairs else 5
    if n < threshold:
        return {"n_pairs": n, "status": "insufficient", "kappa": None, "kappa_linear": None,
                "exact_agreement": None, "adjacent_agreement": None,
                "message": f"Pilot measurement underway — {n} of {threshold} double-scored decisions collected."}
    kq = weighted_kappa(a, b, k, "quadratic")
    kl = weighted_kappa(a, b, k, "linear")
    msg = f"Quadratic-weighted κ computed on {n} double-scored decisions."
    if kq is None:
        msg += " κ is undefined because all scores fall in one category (no variance); exact agreement is reported."
    return {"n_pairs": n, "status": "reported", "kappa": None if kq is None else round(kq, 4),
            "kappa_linear": None if kl is None else round(kl, 4),
            "exact_agreement": round(exact_agreement(a, b), 4), "adjacent_agreement": round(adjacent_agreement(a, b), 4),
            "message": msg}


def report(db: Session) -> dict[str, Any]:
    threshold = get_settings().KAPPA_MIN_PAIRS
    pairs = collect_pairs(db)
    demo_flags = {p["is_demo"] for p in pairs}
    source = "none" if not pairs else ("mixed" if len(demo_flags) > 1 else ("demo" if True in demo_flags else "pilot"))
    out = {"threshold": threshold, "weighting": "quadratic", "data_source": source, **summarise(pairs, threshold)}
    out["pairs"] = [{k: v for k, v in p.items() if k != "max_score"} for p in pairs]
    return out
