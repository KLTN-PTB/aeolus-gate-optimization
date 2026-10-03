"""Unit tests for Stage 5 — Stability & Day-Block Bootstrap.

Verifies:
1. Seed ensemble predictive distribution construction (K=9 unified mixture).
2. Day-block bootstrap confidence interval calculation and threshold logic.
3. Algorithmic stability aggregations (mean +- SD).
4. Predictive consistency calculations across seeds.
5. Invariance of seed manifest and policy immutability.
"""

from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.models.probabilistic.stability import (
    compute_algorithmic_stability,
    compute_day_block_bootstrap_ci,
    compute_prediction_consistency,
    construct_seed_ensemble_mixture,
)


def test_construct_seed_ensemble_mixture():
    n = 20
    k = 3
    s = 3
    pi_list = [np.ones((n, k)) / k for _ in range(s)]
    mu_list = [np.random.normal(0, 10, (n, k)) for _ in range(s)]
    sigma_list = [np.random.uniform(2, 20, (n, k)) for _ in range(s)]

    pi_ens, mu_ens, sigma_ens = construct_seed_ensemble_mixture(pi_list, mu_list, sigma_list)

    assert pi_ens.shape == (n, s * k)
    assert mu_ens.shape == (n, s * k)
    assert sigma_ens.shape == (n, s * k)

    # Weights must sum to 1.0 across the 9 components
    assert np.allclose(np.sum(pi_ens, axis=1), np.ones(n), atol=1e-6)
    assert np.all(sigma_ens >= 2.0)

    # Error handling for mismatched lengths
    with pytest.raises(ValueError, match="identical sample length"):
        bad_pi = [np.ones((n, k)) / k, np.ones((n + 5, k)) / k]
        construct_seed_ensemble_mixture(bad_pi, mu_list[:2], sigma_list[:2])


def test_compute_day_block_bootstrap_ci():
    # Construct synthetic daily data with clear positive improvement (delta_crps < 0)
    rng = np.random.default_rng(42)
    n_days = 100
    dates = pd.date_range("2020-01-01", periods=n_days).astype(str)
    # delta_crps ~ Normal(-2.0, 0.5) (i.e. candidate is ~2.0 min better than baseline)
    deltas = rng.normal(-2.0, 0.5, size=n_days)
    counts = rng.integers(10, 50, size=n_days)

    df_daily = pd.DataFrame({
        "flight_date": dates,
        "delta_crps": deltas,
        "n_flights": counts,
    })

    res = compute_day_block_bootstrap_ci(
        df_daily,
        n_bootstraps=500,
        seed=42,
        delta_threshold=0.05,
    )

    # Basic invariants
    assert res.n_days == 100
    assert res.n_flights == int(np.sum(counts))
    assert res.point_estimate_delta_crps < -1.5
    assert res.point_estimate_improvement > 1.5

    # CI ordering
    assert res.ci_lower_delta_crps <= res.point_estimate_delta_crps <= res.ci_upper_delta_crps
    assert res.ci_lower_improvement <= res.point_estimate_improvement <= res.ci_upper_improvement
    assert res.ci_lower_improvement == pytest.approx(-res.ci_upper_delta_crps, abs=1e-5)

    # Improvement of ~2.0 min clearly exceeds delta=0.05 min
    assert res.lower_bound_exceeds_threshold is True


def test_compute_algorithmic_stability():
    seed_metrics = {
        "seed_1": {"crps": 13.5, "nll": 4.2, "nested": {"mae": 15.0}},
        "seed_2": {"crps": 13.7, "nll": 4.4, "nested": {"mae": 15.2}},
        "seed_3": {"crps": 13.6, "nll": 4.3, "nested": {"mae": 15.1}},
    }
    stab = compute_algorithmic_stability(seed_metrics)

    assert pytest.approx(stab["crps"]["mean"], 1e-4) == 13.6
    assert pytest.approx(stab["crps"]["min"], 1e-4) == 13.5
    assert pytest.approx(stab["crps"]["max"], 1e-4) == 13.7
    assert stab["crps"]["std"] > 0.0

    assert pytest.approx(stab["nested"]["mae"]["mean"], 1e-4) == 15.1


def test_compute_prediction_consistency():
    n = 100
    p1 = np.linspace(0, 50, n)
    p2 = p1 + np.random.normal(0, 0.5, n)
    p3 = p1 + np.random.normal(0, 1.0, n)

    preds_by_seed = {1: p1, 2: p2, 3: p3}
    quantiles_by_seed = {
        1: {"q_500": p1},
        2: {"q_500": p2},
        3: {"q_500": p3},
    }

    consistency = compute_prediction_consistency(preds_by_seed, quantiles_by_seed)

    assert consistency["mean_point_correlation"] > 0.99
    assert consistency["mean_point_mae"] < 1.0
    assert "q_500" in consistency["quantile_mean_mae"]


def test_seed_manifest_invariants():
    manifest_p = Path("artifacts/manifests/seed_manifest_v1.json")
    assert manifest_p.exists(), "seed_manifest_v1.json must exist"

    with open(manifest_p, "r", encoding="utf-8") as f:
        meta = json.load(f)

    assert meta["finalist_seeds"] == [202601, 202602, 202603]
    assert meta["predetermined_deployment_seed"] == 202601
    assert meta["policy"] == "evaluation_only_with_predetermined_deployment_seed"
    assert meta["registered_seed_ensemble_candidate"]["candidate_id"] == "seed_ensemble_3"
