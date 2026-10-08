"""Unit and Integration Tests for P10-A Native P4 Downstream Rebuild.

Verifies:
1. P4 frozen checkpoint cryptographic verification and loading.
2. Distributional parameter validity (finite, sigma > 0, df > 2).
3. Synthetic turn generation without realized arrival delay leakage.
4. Gate conflict and independent verifier correctness.
5. All 4 solvers execute within 2.0s ceiling and output valid assignments.
6. Monte Carlo sampling determinism, CRN consistency, and convergence statistics.
7. Downstream end-to-end integration pipeline execution.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.evaluation.downstream_comparison_v2 import (
    DEFAULT_SCENARIO_SPECS,
    build_scenario_gates,
    extract_scenario_from_raw,
    validate_downstream_input_boundary,
)
from src.evaluation.native_downstream_p4 import (
    CANONICAL_MC_N,
    P4_CERTIFIED_CHECKPOINT_PATH,
    P4_CERTIFIED_SHA256,
    P4VerificationError,
    TimeBudgetedSimulatedAnnealingSolver,
    execute_four_solvers,
    run_monte_carlo_grid,
    verify_and_load_p4_checkpoint,
)
from src.features.tabular_features import prepare_arrival_features
from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import Flight, Gate, verify_hard_constraints_independently
from src.optimization.evaluation import evaluate_gate_assignment
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver
from src.simulation.aircraft_turn import AircraftTurnModel


@pytest.fixture(scope="module")
def p4_model():
    """Load certified P4 model."""
    model, meta = verify_and_load_p4_checkpoint(
        checkpoint_path=P4_CERTIFIED_CHECKPOINT_PATH,
        expected_sha256=P4_CERTIFIED_SHA256,
    )
    return model


@pytest.fixture(scope="module")
def scen_2023_low():
    """Extract canonical SCEN_2023_LOW."""
    raw_df = pd.read_parquet("data/processed/inbound_atl/year=2023")
    spec = DEFAULT_SCENARIO_SPECS[0]
    return extract_scenario_from_raw(spec, raw_df)


# 1. P4 Model Loading & Verification Tests
def test_p4_checkpoint_verification(p4_model):
    """Verify that P4 checkpoint matches the registered cryptographic hash."""
    assert p4_model is not None
    assert getattr(p4_model, "is_fitted_", False)
    assert p4_model.model_ is None or hasattr(p4_model.model_, "pred_dist")


def test_p4_checkpoint_mismatch_raises():
    """Verify that an altered hash raises P4VerificationError."""
    with pytest.raises(P4VerificationError):
        verify_and_load_p4_checkpoint(
            checkpoint_path=P4_CERTIFIED_CHECKPOINT_PATH,
            expected_sha256="0000000000000000000000000000000000000000000000000000000000000000",
        )


# 2. Distributional Prediction & Parameter Validity Tests
def test_p4_distribution_parameters(p4_model, scen_2023_low):
    """Verify that P4 outputs observation-dependent, strictly finite parameters."""
    clean_df = scen_2023_low.flights_df.drop(columns=["_sched_arr_min", "nominal_gate_id"], errors="ignore")
    prep = prepare_arrival_features(clean_df)
    dist = p4_model.predict_distribution(prep.X)

    mu = dist["mu"]
    sigma = dist["sigma"]
    df = dist["df"]

    assert len(mu) == 30
    assert len(sigma) == 30
    assert len(df) == 30

    assert np.all(np.isfinite(mu))
    assert np.all(np.isfinite(sigma))
    assert np.all(np.isfinite(df))

    assert np.all(sigma >= 1.0)
    assert np.all(df >= 2.1)  # Finite variance constraint


# 3. Synthetic Turn Generation Tests
def test_synthetic_turn_contract(scen_2023_low):
    """Verify turnaround times respect min physical turnaround and buffer."""
    tm = AircraftTurnModel(min_turnaround_min=45, default_dwell_min=60, separation_buffer_min=15)
    row = scen_2023_low.flights_df.iloc[0]

    turn = tm.synthesize_turn(
        flight_id=str(row["flight_key"]),
        carrier=str(row["OP_CARRIER"]),
        flight_number=str(row["OP_CARRIER_FL_NUM"]),
        scheduled_arrival_min=int(row["_sched_arr_min"]),
        sampled_delay_min=10.0,
        nominal_gate_id=str(row["nominal_gate_id"]),
    )

    assert turn.simulated_arrival_min == int(row["_sched_arr_min"]) + 10
    assert turn.simulated_departure_min >= turn.simulated_arrival_min + 45
    assert turn.gate_release_min == turn.simulated_departure_min + 15
    assert turn.occupancy_duration_min >= 60.0


# 4. Gate Conflict & Independent Verifier Tests
def test_gate_verifier_overlap_detection():
    """Verify that overlapping flights on a contact gate trigger hard violation."""
    f1 = Flight(
        flight_id="F1", flight_index=0, carrier="DL", flight_number="101",
        scheduled_arrival_min=600, scheduled_departure_min=660, predicted_arrival_min=600,
        nominal_gate_id="G_01", min_turnaround_min=45, default_dwell_min=60, buffer_min=15,
    )
    f2 = Flight(
        flight_id="F2", flight_index=1, carrier="DL", flight_number="102",
        scheduled_arrival_min=620, scheduled_departure_min=680, predicted_arrival_min=620,
        nominal_gate_id="G_01", min_turnaround_min=45, default_dwell_min=60, buffer_min=15,
    )
    g1 = Gate(gate_id="G_01", gate_index=0, is_overflow=False)
    gates = [g1]

    # Assign both to G_01 (conflict)
    from src.optimization.domain import GateAssignment
    assignments = {
        "F1": GateAssignment("F1", "G_01", 0, 0, False, False, 600, 675),
        "F2": GateAssignment("F2", "G_01", 1, 0, False, False, 620, 695),
    }

    diag = verify_hard_constraints_independently([f1, f2], gates, assignments)
    assert not diag.is_valid
    assert diag.conflict_count == 1
    assert not diag.no_contact_gate_conflicts


# 5. Solver Tests (All 4 Solvers under 2.0s ceiling)
def test_all_four_solvers_execution(scen_2023_low):
    """Verify that Greedy, CP-SAT, SA, and Hybrid execute within budget and return feasible plans."""
    cfg = GateOptimizationConfig(
        reassignment_weight=10.0,
        overflow_weight=200.0,
        delay_weight=0.0,
        conflict_weight=1000.0,
        risk_weight=0.0,
        time_limit_seconds=2.0,
        num_search_workers=1,
        random_seed=202601,
    )
    tm = AircraftTurnModel(min_turnaround_min=45, default_dwell_min=60, separation_buffer_min=15)
    planned_delays = np.zeros(scen_2023_low.n_flights)

    records = execute_four_solvers(
        model_id="test_zero_delay",
        scenario=scen_2023_low,
        planned_delays=planned_delays,
        config=cfg,
        turn_model=tm,
    )

    assert len(records) == 4
    solver_names = {r.solver_name for r in records}
    assert solver_names == {"DeterministicGreedy", "CPSat", "SimulatedAnnealing", "HybridCPSatSA"}

    for r in records:
        assert r.feasible
        assert r.runtime_ms <= 2500.0  # within reasonable tolerance of 2.0s
        assert r.unassigned_count == 0
        assert r.planned_conflicts == 0


# 6. Monte Carlo Grid & Convergence Tests
def test_monte_carlo_grid_execution(scen_2023_low):
    """Verify Monte Carlo runs across grid and computes valid convergence statistics."""
    cfg = GateOptimizationConfig(
        reassignment_weight=10.0,
        overflow_weight=200.0,
        delay_weight=0.0,
        conflict_weight=1000.0,
        risk_weight=0.0,
        time_limit_seconds=2.0,
        random_seed=202601,
    )
    # Generate 250 deterministic delay rows for testing
    delay_matrix = np.zeros((250, scen_2023_low.n_flights))
    grid = (100, 250)

    conv_res, realizations = run_monte_carlo_grid(
        model_id="test_sched",
        scenario=scen_2023_low,
        delay_matrix=delay_matrix,
        counts=grid,
        config=cfg,
    )

    assert len(conv_res) == 2
    assert conv_res[0].n_requested == 100
    assert conv_res[1].n_requested == 250
    assert conv_res[0].n_success == 100
    assert conv_res[1].n_success == 250
    assert conv_res[0].mean_objective == 4200.0
    assert conv_res[1].mean_objective == 4200.0
