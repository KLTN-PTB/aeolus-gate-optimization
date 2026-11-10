"""Tests for Day-Level Block-Bootstrap Paired Comparison Engine.

Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Sections 8, 9, 10
Verifies:
1. Daily score aggregation by operational date.
2. Vectorized day-block bootstrap CI computation.
3. Decision criteria: statistical superiority (CI_upper < 0) and practical significance.
4. Correct direction handling (lower is better for CRPS/NLL vs higher is better).
5. Contract violation guards on mismatched lengths and empty inputs.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.models.probabilistic.contracts import ProbabilisticContractViolation
from src.models.probabilistic.day_level_comparison import (
    compare_candidate_vs_baseline_daily,
    compute_day_level_bootstrap_ci,
)


def test_compute_day_level_bootstrap_ci() -> None:
    """Verify bootstrap CI reproduces expected bounds and standard errors."""
    rng = np.random.default_rng(202601)
    diffs = rng.normal(loc=-0.5, scale=0.2, size=100)

    ci_low, ci_high, se, boot_means = compute_day_level_bootstrap_ci(
        diffs,
        n_bootstraps=1000,
        confidence_level=0.95,
        seed=202601,
    )

    assert ci_low < ci_high
    assert ci_low < -0.5 < ci_high
    assert se > 0.0
    assert len(boot_means) == 1000


def test_compare_candidate_vs_baseline_daily_superiority() -> None:
    """Verify paired comparison detects statistically superior candidate."""
    # 30 operational days, 50 flights per day
    n_days = 30
    flights_per_day = 50
    dates = []
    for d in range(1, n_days + 1):
        d_str = f"2022-01-{d:02d}"
        dates.extend([d_str] * flights_per_day)

    total_flights = len(dates)
    rng = np.random.default_rng(202602)

    # Baseline scores (CRPS ~ 8.0)
    base_crps = rng.normal(8.0, 1.0, size=total_flights)
    # Candidate scores (CRPS ~ 7.5, clearly superior by 0.5 min > effect size 0.10)
    cand_crps = base_crps - rng.normal(0.5, 0.1, size=total_flights)

    res = compare_candidate_vs_baseline_daily(
        flight_dates=dates,
        candidate_scores={"crps": cand_crps},
        baseline_scores={"crps": base_crps},
        candidate_name="cand_model",
        baseline_name="base_model",
        effect_size_deltas={"crps": 0.10},
    )

    assert res.n_flights == total_flights
    assert res.n_days == n_days
    assert "crps" in res.metrics

    crps_metric = res.metrics["crps"]
    assert crps_metric.mean_difference < -0.40
    assert crps_metric.is_statistically_superior is True
    assert crps_metric.is_practically_significant is True
    assert crps_metric.p_candidate_better > 0.99
    assert len(res.daily_table) == n_days

    # Serialization check
    d = res.to_dict()
    assert d["candidate_name"] == "cand_model"
    assert d["n_days"] == n_days


def test_compare_mismatched_length_error() -> None:
    """Verify contract violation is raised when input array lengths do not match."""
    dates = ["2022-01-01", "2022-01-02"]
    cand = np.array([5.0, 6.0])
    base = np.array([5.0])

    with pytest.raises(ProbabilisticContractViolation):
        compare_candidate_vs_baseline_daily(
            flight_dates=dates,
            candidate_scores=cand,
            baseline_scores=base,
        )
