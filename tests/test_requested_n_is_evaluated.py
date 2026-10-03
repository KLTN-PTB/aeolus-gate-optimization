"""Tests that the exact requested Monte Carlo count N is always evaluated without truncation (Phase 9)."""

from __future__ import annotations

import pandas as pd
import pytest

from src.evaluation.monte_carlo_comparison import (
    MonteCarloDelayTransformer,
    MonteCarloScenarioSpec,
    generate_common_latent_variables,
    run_monte_carlo_evaluation,
)
from src.optimization.config import GateOptimizationConfig


@pytest.fixture
def dummy_spec() -> MonteCarloScenarioSpec:
    n_flights = 10
    df = pd.DataFrame({
        "flight_key": [f"FL_{i:03d}" for i in range(n_flights)],
        "OP_CARRIER": ["DL"] * n_flights,
        "OP_CARRIER_FL_NUM": [100 + i for i in range(n_flights)],
        "_sched_arr_min": [720 + i * 15 for i in range(n_flights)],
        "nominal_gate_id": [f"G_{(i % 4) + 1:02d}" for i in range(n_flights)],
        "ARR_DELAY": [10.0] * n_flights,
    })
    return MonteCarloScenarioSpec(
        scenario_id="SCEN_TEST",
        date_str="2023-11-23",
        n_flights=n_flights,
        n_contact_gates=4,
        flights_df=df,
        spec_hash="dummy_hash_123",
    )


def test_exact_requested_n_is_evaluated_without_truncation(dummy_spec: MonteCarloScenarioSpec) -> None:
    """Verify that every requested count N (including >100) is evaluated with zero truncation."""
    test_counts = [5, 20, 105, 150]
    base_delays = [5.0] * dummy_spec.n_flights

    for requested_n in test_counts:
        latent_u = generate_common_latent_variables(
            n_scenarios=requested_n,
            n_flights=dummy_spec.n_flights,
            seed=202601,
        )
        assert latent_u.shape == (requested_n, dummy_spec.n_flights)

        delay_matrix = MonteCarloDelayTransformer.transform(
            model_id="P4_ngboost_student_t",
            latent_u=latent_u,
            base_delays=base_delays,
        )
        assert delay_matrix.shape == (requested_n, dummy_spec.n_flights)

        records = run_monte_carlo_evaluation(
            model_id="P4_ngboost_student_t",
            spec=dummy_spec,
            delay_matrix=delay_matrix,
            requested_n=requested_n,
            seed=202601,
        )

        # Critical invariant: must evaluate ALL requested scenarios without capping at 100
        assert len(records) == requested_n, f"Truncation detected: {len(records)} != {requested_n}"
        assert records[-1].scenario_index == requested_n - 1


def test_mismatched_requested_n_fails_closed(dummy_spec: MonteCarloScenarioSpec) -> None:
    """Assert that passing a matrix whose row count != requested_n fails closed."""
    latent_u = generate_common_latent_variables(
        n_scenarios=50,
        n_flights=dummy_spec.n_flights,
    )
    delay_matrix = MonteCarloDelayTransformer.transform(
        model_id="schedule_only",
        latent_u=latent_u,
        base_delays=[0.0] * dummy_spec.n_flights,
    )

    with pytest.raises(ValueError, match="Safety Violation"):
        run_monte_carlo_evaluation(
            model_id="schedule_only",
            spec=dummy_spec,
            delay_matrix=delay_matrix,
            requested_n=100,  # Deliberate mismatch
        )
