"""Tests for Monte Carlo convergence statistics, standard errors, and CI (Phase 9)."""

from __future__ import annotations

import numpy as np
import pytest

from src.evaluation.monte_carlo_comparison import (
    AggregateMonteCarloMetrics,
    ScenarioEvaluationRecord,
    compute_convergence_analysis,
    compute_monte_carlo_aggregate,
)


def _make_dummy_records(model_id: str, n_scen: int, true_mean: float = 5000.0, true_std: float = 200.0) -> list[ScenarioEvaluationRecord]:
    rng = np.random.default_rng(42 + n_scen)
    objs = rng.normal(true_mean, true_std, size=n_scen)
    return [
        ScenarioEvaluationRecord(
            model_id=model_id,
            scenario_index=i,
            requested_n=n_scen,
            seed=202601,
            objective_value=float(objs[i]),
            reassignment_count=10,
            remote_count=5,
            unassigned_count=0,
            conflict_count=0,
            runtime_ms=1.5,
            hard_feasible=True,
        )
        for i in range(n_scen)
    ]


def test_mc_se_scales_as_one_over_sqrt_n() -> None:
    """Monte Carlo Standard Error must decrease strictly as O(1/sqrt(N))."""
    counts = [100, 400, 1600]
    aggs = {}

    for n in counts:
        recs = _make_dummy_records("test_model", n, true_mean=5000.0, true_std=200.0)
        aggs[n] = compute_monte_carlo_aggregate(recs)

    se_100 = aggs[100].mc_se_objective
    se_400 = aggs[400].mc_se_objective
    se_1600 = aggs[1600].mc_se_objective

    # Monotonic decrease
    assert se_100 > se_400 > se_1600

    # Rate check: se_400 / se_100 should be close to sqrt(100/400) = 0.5
    ratio_1 = se_400 / se_100
    assert 0.40 <= ratio_1 <= 0.60, f"Expected SE ratio ~0.50, got {ratio_1}"

    # Rate check: se_1600 / se_400 should be close to sqrt(400/1600) = 0.5
    ratio_2 = se_1600 / se_400
    assert 0.40 <= ratio_2 <= 0.60, f"Expected SE ratio ~0.50, got {ratio_2}"


def test_confidence_interval_contains_sample_mean() -> None:
    """95% Confidence Interval must surround sample mean symmetrically."""
    recs = _make_dummy_records("test_model", 500, true_mean=3500.0, true_std=150.0)
    agg = compute_monte_carlo_aggregate(recs)

    assert agg.ci_95_lower_objective < agg.mean_objective < agg.ci_95_upper_objective
    half_width = agg.ci_95_upper_objective - agg.mean_objective
    assert np.isclose(half_width, 1.95996 * agg.mc_se_objective, atol=1e-3)


def test_convergence_analysis_between_n_and_2n() -> None:
    """compute_convergence_analysis must correctly compute relative change between N and 2N."""
    aggs = {
        250: compute_monte_carlo_aggregate(_make_dummy_records("model_A", 250, true_mean=5000.0)),
        500: compute_monte_carlo_aggregate(_make_dummy_records("model_A", 500, true_mean=5000.0)),
        1000: compute_monte_carlo_aggregate(_make_dummy_records("model_A", 1000, true_mean=5000.0)),
    }

    pairs = compute_convergence_analysis(aggs, relative_change_threshold=0.03)
    assert len(pairs) == 2

    # Pair 1: 250 -> 500 (exact factor of 2)
    p1 = pairs[0]
    assert p1.n_base == 250
    assert p1.n_target == 500
    assert p1.relative_change < 0.03
    assert p1.is_converged

    # Pair 2: 500 -> 1000 (exact factor of 2)
    p2 = pairs[1]
    assert p2.n_base == 500
    assert p2.n_target == 1000
    assert p2.relative_change < 0.03
    assert p2.is_converged
