"""Tests for Monte Carlo scenario uniqueness and absence of duplicates (Phase 9)."""

from __future__ import annotations

import numpy as np
import pytest

from src.evaluation.monte_carlo_comparison import (
    MonteCarloDelayTransformer,
    audit_monte_carlo_randomness,
    generate_common_latent_variables,
)


def test_stochastic_scenarios_are_all_unique() -> None:
    """Stochastic models must produce 100% unique scenario realizations (no duplicate rows)."""
    n_scen = 200
    n_flights = 15
    latent_u = generate_common_latent_variables(n_scenarios=n_scen, n_flights=n_flights, seed=202601)
    base_delays = np.linspace(5.0, 25.0, n_flights)

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
        assert mat.shape == (n_scen, n_flights)

        audit = audit_monte_carlo_randomness(mat, requested_n=n_scen, model_id=model_id)
        assert audit.is_all_scenarios_unique, f"Model {model_id} has duplicate scenarios!"
        assert audit.number_of_unique_scenarios == n_scen


def test_latent_u_is_all_unique() -> None:
    """Common latent uniform matrix U must have 100% unique rows."""
    latent_u = generate_common_latent_variables(n_scenarios=300, n_flights=12, seed=202601)
    unique_rows = len(np.unique(latent_u, axis=0))
    assert unique_rows == 300
