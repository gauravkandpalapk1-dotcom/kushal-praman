"""Weighted kappa: cross-checked against scikit-learn, plus edge cases."""
from __future__ import annotations

import math
import random

import pytest
from sklearn.metrics import cohen_kappa_score

from backend.app.services.agreement import (
    adjacent_agreement,
    exact_agreement,
    summarise,
    weighted_kappa,
)

LABELS = list(range(5))


@pytest.mark.parametrize("seed", range(12))
@pytest.mark.parametrize("weights", ["quadratic", "linear"])
def test_matches_sklearn_on_random_vectors(seed, weights):
    rng = random.Random(seed)
    n = rng.randint(5, 200)
    a = [rng.randint(0, 4) for _ in range(n)]
    # correlated second rater
    b = [min(4, max(0, x + rng.choice([-2, -1, 0, 0, 0, 1, 1]))) for x in a]
    ours = weighted_kappa(a, b, 5, weights)
    ref = cohen_kappa_score(a, b, labels=LABELS, weights=weights)
    assert ours == pytest.approx(ref, abs=1e-12)


def test_matches_sklearn_unweighted():
    a = [0, 1, 2, 3, 4, 4, 3, 2]
    b = [0, 1, 1, 3, 4, 3, 3, 2]
    assert weighted_kappa(a, b, 5, "none") == pytest.approx(cohen_kappa_score(a, b, labels=LABELS))


def test_perfect_agreement_is_one():
    a = [0, 1, 2, 3, 4, 2]
    assert weighted_kappa(a, a, 5) == pytest.approx(1.0)


def test_all_identical_single_category_is_undefined():
    # Zero variance for both raters: expected disagreement is 0 -> kappa = 0/0. We return None.
    a = b = [3, 3, 3, 3]
    assert weighted_kappa(a, b, 5) is None
    ref = cohen_kappa_score(a, b, labels=LABELS, weights="quadratic")
    assert math.isnan(ref)  # sklearn agrees it is undefined
    assert exact_agreement(a, b) == 1.0


def test_one_rater_zero_variance_matches_sklearn():
    a = [2, 2, 2, 2, 2]
    b = [1, 2, 3, 2, 4]
    ours = weighted_kappa(a, b, 5)
    assert ours == pytest.approx(cohen_kappa_score(a, b, labels=LABELS, weights="quadratic"))
    assert ours == pytest.approx(0.0)


def test_agreement_rates():
    a, b = [0, 1, 2, 3], [0, 2, 4, 3]
    assert exact_agreement(a, b) == 0.5
    assert adjacent_agreement(a, b) == 0.75


def test_summarise_below_threshold_reports_nothing():
    pairs = [{"score_a": 3, "score_b": 3, "max_score": 4}]
    s = summarise(pairs, 30)
    assert s["status"] == "insufficient"
    assert s["kappa"] is None and s["kappa_linear"] is None
    assert s["exact_agreement"] is None and s["adjacent_agreement"] is None
    assert s["message"] == "Pilot measurement underway — 1 of 30 double-scored decisions collected."


def test_summarise_at_threshold_reports():
    rng = random.Random(7)
    pairs = []
    for _ in range(30):
        x = rng.randint(0, 4)
        pairs.append({"score_a": x, "score_b": min(4, x + rng.choice([0, 0, 1])), "max_score": 4})
    s = summarise(pairs, 30)
    assert s["status"] == "reported"
    ref = cohen_kappa_score([p["score_a"] for p in pairs], [p["score_b"] for p in pairs], labels=LABELS,
                            weights="quadratic")
    assert s["kappa"] == pytest.approx(round(ref, 4))
