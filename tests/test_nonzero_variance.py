"""Tests for strictly positive variance across stochastic scenarios (Phase 9)."""

from __future__ import annotations

import numpy as np
import pytest

from src.evaluation.monte_carlo_comparison import (
    MonteCarloDelayTransformer,
    audit_monte_carlo_randomness,
    generate_common_latent_variables,
)


def test_stochastic_models_have_strictly_positive_variance() -> None:
    """Every stochastic model must exhibit strictly positive per-flight variance across scenarios."""
    n_scen = 150
    n_flights = 8
    latent_u = generate_common_latent_variables(n_scenarios=n_scen, n_flights=n_flights, seed=202601)
    base_delays = np.full(n_flights, 12.0)

    stochastic_models = [
        "arrival_linear_baseline_v1",
        "arrival_xgboost_baseline_v1",
        "P4_ngboost_student_t",
        "P5_quantile_regression",
    ]

    for model_id in stochastic_models:
        mat = MonteCarloDelayTransformer.transform(
            model_id=model_id,
            latent_u=latent_u,
            base_delays=base_delays,
        )
        audit = audit_monte_carlo_randomness(mat, requested_n=n_scen, model_id=model_id)

        assert audit.is_variance_positive, f"Model {model_id} failed positive variance check!"
        assert audit.per_flight_variance_min > 0.0
        assert audit.per_flight_variance_mean > 0.0


def test_schedule_only_has_zero_variance() -> None:
    """Schedule-only deterministic baseline has identically zero delay variance."""
    n_scen = 50
    n_flights = 8
    latent_u = generate_common_latent_variables(n_scenarios=n_scen, n_flights=n_flights, seed=202601)
    base_delays = np.zeros(n_flights)

    mat = MonteCarloDelayTransformer.transform(
        model_id="schedule_only",
        latent_u=latent_u,
        base_delays=base_delays,
    )
    np.testing.assert_array_equal(mat, 0.0)
    per_flight_var = np.var(mat, axis=0)
    np.testing.assert_array_equal(per_flight_var, 0.0)
