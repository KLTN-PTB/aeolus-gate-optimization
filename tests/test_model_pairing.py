"""Tests for common random numbers (CRN) fairness and exact model pairing (Phase 9)."""

from __future__ import annotations

import numpy as np
import pytest

from src.evaluation.monte_carlo_comparison import (
    MonteCarloDelayTransformer,
    MonteCarloScenarioSpec,
    generate_common_latent_variables,
    run_monte_carlo_evaluation,
)
from tests.test_requested_n_is_evaluated import dummy_spec


def test_models_share_identical_latent_uniform_shocks(dummy_spec: MonteCarloScenarioSpec) -> None:
    """All models must receive the exact same latent uniform variable matrix U."""
    n_scen = 60
    n_flights = dummy_spec.n_flights

    # Common latent random variables generated ONCE
    latent_u = generate_common_latent_variables(n_scenarios=n_scen, n_flights=n_flights, seed=202601)

    base_delays = [15.0] * n_flights

    mat_linear = MonteCarloDelayTransformer.transform("arrival_linear_baseline_v1", latent_u, base_delays)
    mat_p4 = MonteCarloDelayTransformer.transform("P4_ngboost_student_t", latent_u, base_delays)
    mat_p5 = MonteCarloDelayTransformer.transform("P5_quantile_regression", latent_u, base_delays)

    # Invariants: shapes must be strictly identical
    assert mat_linear.shape == mat_p4.shape == mat_p5.shape == (n_scen, n_flights)

    # For any scenario s, the rank order of shocks across flights is correlated with U[s]
    # verifying that scenario s represents the exact same systemic shock
    for s in range(5):
        corr_linear_p4 = np.corrcoef(mat_linear[s], mat_p4[s])[0, 1]
        assert corr_linear_p4 > 0.90, "Model delay realizations under CRN must be strongly positively aligned"


def test_paired_scenario_evaluations_align_exactly(dummy_spec: MonteCarloScenarioSpec) -> None:
    """Evaluations across models must have 1-to-1 scenario alignment."""
    n_scen = 25
    latent_u = generate_common_latent_variables(n_scenarios=n_scen, n_flights=dummy_spec.n_flights, seed=202601)
    base_delays = [10.0] * dummy_spec.n_flights

    mat1 = MonteCarloDelayTransformer.transform("arrival_linear_baseline_v1", latent_u, base_delays)
    mat2 = MonteCarloDelayTransformer.transform("P4_ngboost_student_t", latent_u, base_delays)

    recs1 = run_monte_carlo_evaluation("arrival_linear_baseline_v1", dummy_spec, mat1, n_scen, seed=202601)
    recs2 = run_monte_carlo_evaluation("P4_ngboost_student_t", dummy_spec, mat2, n_scen, seed=202601)

    assert len(recs1) == len(recs2) == n_scen

    # Scenario index must match 1-to-1
    for i in range(n_scen):
        assert recs1[i].scenario_index == recs2[i].scenario_index == i
        assert recs1[i].requested_n == recs2[i].requested_n == n_scen
        # Delta is well-defined
        delta_obj = recs1[i].objective_value - recs2[i].objective_value
        assert np.isfinite(delta_obj)
