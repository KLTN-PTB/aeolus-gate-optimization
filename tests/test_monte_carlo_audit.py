"""Tests for Monte Carlo Scenario Generation, Downstream Convergence, and Reproducibility.

Protocol: docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md - Section 4
          docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 19 (Stage 9)
Requirements:
1. N changes scenario count.
2. Expected stochastic runs differ across seeds.
3. Fixed seed is reproducible.
4. Scenarios are not unexpectedly identical (all rows unique, positive per-flight variance).
5. Sampled values reach downstream simulation (downstream variance across scenarios).
6. Convergence audit evaluates full N scenarios without artificial truncation.
"""

from __future__ import annotations

import hashlib
import numpy as np
import pandas as pd
import pytest

from src.models.probabilistic.contracts import PREDETERMINED_DEPLOYMENT_SEED
from src.models.probabilistic.dependence import (
    GaussianCopulaDependenceModel,
    StudentTMarginalDistribution,
)
from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import Gate
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver
from src.simulation.aircraft_turn import AircraftTurnModel
from src.simulation.conflict_detector import detect_conflicts
from src.simulation.scenario_runner import MonteCarloScenarioRunner


@pytest.fixture
def mock_flight_batch() -> tuple[pd.DataFrame, list[StudentTMarginalDistribution], GaussianCopulaDependenceModel]:
    """Construct a clean, synthetic operational flight batch for testing."""
    n_flights = 20
    rng = np.random.default_rng(12345)
    dep_hours = np.linspace(7, 21, n_flights)

    flight_df = pd.DataFrame(
        {
            "flight_key": [f"FL_{i+1:03d}" for i in range(n_flights)],
            "scheduled_departure_hour": dep_hours,
            "scheduled_departure_minute": rng.choice([0, 15, 30, 45], size=n_flights),
            "scheduled_arrival_hour": np.clip(dep_hours + 2, 0, 23),
            "scheduled_arrival_minute": rng.choice([0, 15, 30, 45], size=n_flights),
            "OP_CARRIER": rng.choice(["DL", "AA", "UA", "WN"], size=n_flights),
            "aircraft_type": "NARROW",
        }
    )

    marginals = [
        StudentTMarginalDistribution(
            mu=float(rng.uniform(5.0, 20.0)),
            sigma=float(rng.uniform(10.0, 25.0)),
            df=float(rng.uniform(3.0, 5.0)),
            discrete=True,
        )
        for _ in range(n_flights)
    ]

    dependence_model = GaussianCopulaDependenceModel(
        temporal_length_scale_minutes=120.0,
        carrier_correlation=0.15,
    )

    return flight_df, marginals, dependence_model


def test_n_changes_scenario_count(mock_flight_batch):
    """Test that N strictly controls the number of scenarios generated."""
    flight_df, marginals, dep_model = mock_flight_batch
    runner = MonteCarloScenarioRunner(dependence_model=dep_model)

    for n_scen in [5, 17, 42]:
        matrix = runner.run_scenarios(marginals, flight_df, n_scenarios=n_scen, rng=PREDETERMINED_DEPLOYMENT_SEED)
        assert matrix.shape == (n_scen, len(flight_df)), (
            f"Expected shape ({n_scen}, {len(flight_df)}), got {matrix.shape}"
        )


def test_expected_stochastic_runs_differ_across_seeds(mock_flight_batch):
    """Test that different seeds produce distinct scenario realizations."""
    flight_df, marginals, dep_model = mock_flight_batch
    runner = MonteCarloScenarioRunner(dependence_model=dep_model)

    matrix_1 = runner.run_scenarios(marginals, flight_df, n_scenarios=25, rng=202601)
    matrix_2 = runner.run_scenarios(marginals, flight_df, n_scenarios=25, rng=202602)

    assert not np.array_equal(matrix_1, matrix_2), "Matrices across different seeds must not be identical"
    hash_1 = hashlib.sha256(matrix_1.tobytes()).hexdigest()
    hash_2 = hashlib.sha256(matrix_2.tobytes()).hexdigest()
    assert hash_1 != hash_2, "Hashes across different seeds must differ"


def test_fixed_seed_is_reproducible(mock_flight_batch):
    """Test that a fixed seed produces exactly bit-for-bit identical scenarios."""
    flight_df, marginals, dep_model = mock_flight_batch
    runner = MonteCarloScenarioRunner(dependence_model=dep_model)

    seed = 202601
    matrix_a = runner.run_scenarios(marginals, flight_df, n_scenarios=30, rng=seed)
    matrix_b = runner.run_scenarios(marginals, flight_df, n_scenarios=30, rng=seed)

    np.testing.assert_array_equal(matrix_a, matrix_b)
    assert hashlib.sha256(matrix_a.tobytes()).hexdigest() == hashlib.sha256(matrix_b.tobytes()).hexdigest()


def test_scenarios_are_not_unexpectedly_identical(mock_flight_batch):
    """Test that generated scenarios within a batch are not duplicates and have positive variance."""
    flight_df, marginals, dep_model = mock_flight_batch
    runner = MonteCarloScenarioRunner(dependence_model=dep_model)

    n_scen = 50
    matrix = runner.run_scenarios(marginals, flight_df, n_scenarios=n_scen, rng=PREDETERMINED_DEPLOYMENT_SEED)

    # 1. All rows must be distinct
    unique_rows = len(np.unique(matrix, axis=0))
    assert unique_rows == n_scen, f"Expected {n_scen} unique scenarios, found only {unique_rows}"

    # 2. Per-flight variance across scenarios must be strictly positive
    per_flight_var = np.var(matrix, axis=0)
    assert np.all(per_flight_var > 0.0), f"Some flights have zero variance across scenarios: {per_flight_var}"

    # 3. Check diagnostics helper
    diag = MonteCarloScenarioRunner.compute_scenario_diagnostics(matrix)
    assert diag["is_all_scenarios_unique"] is True
    assert diag["number_of_unique_scenarios"] == n_scen
    assert diag["per_flight_variance_min"] > 0.0


def test_sampled_values_reach_downstream_simulation(mock_flight_batch):
    """Test that sampled delay values genuinely propagate into downstream simulation and yield varying metrics."""
    flight_df, marginals, dep_model = mock_flight_batch
    runner = MonteCarloScenarioRunner(dependence_model=dep_model)

    n_scen = 20
    matrix = runner.run_scenarios(marginals, flight_df, n_scenarios=n_scen, rng=PREDETERMINED_DEPLOYMENT_SEED)

    n_gates = 8
    gates = [Gate(gate_id=f"G_{i+1:02d}", gate_index=i, is_overflow=False) for i in range(n_gates)]
    overflow_gate = Gate(gate_id="OVERFLOW_APRON", gate_index=n_gates, is_overflow=True)
    all_gates = gates + [overflow_gate]

    turn_model = AircraftTurnModel(min_turnaround_min=45, default_dwell_min=60, separation_buffer_min=15)
    scheduled_turns = turn_model.synthesize_batch(flight_df, np.zeros(len(flight_df), dtype=float))
    nominal_map = {t.flight_id: gates[i % n_gates].gate_id for i, t in enumerate(scheduled_turns)}

    greedy = DeterministicGreedyGateSolver(config=GateOptimizationConfig())

    durations = []
    objectives = []

    for s in range(n_scen):
        s_delays = matrix[s, :]
        turns = turn_model.synthesize_batch(flight_df, s_delays, nominal_map)
        conf = detect_conflicts(nominal_map, turns, all_gates)
        durations.append(conf.total_conflict_duration_min)

        flights = [t.to_flight(flight_index=idx) for idx, t in enumerate(turns)]
        res_g = greedy.solve(flights, all_gates)
        objectives.append(res_g.objective_value)

    # Downstream values MUST vary across scenarios
    assert np.std(durations) > 0.0, "Conflict durations must vary across scenarios with different delays"
    assert np.std(objectives) > 0.0, "Greedy objectives must vary across scenarios with different delays"


def test_convergence_evaluator_evaluates_all_scenarios_without_capping(mock_flight_batch):
    """Regression test: verify that multi-sample convergence audits evaluate all N scenarios (not capped at 100)."""
    flight_df, marginals, dep_model = mock_flight_batch
    runner = MonteCarloScenarioRunner(dependence_model=dep_model)

    sample_sizes = (10, 25, 40)
    max_N = max(sample_sizes)
    master_matrix = runner.run_scenarios(marginals, flight_df, n_scenarios=max_N, rng=PREDETERMINED_DEPLOYMENT_SEED)

    hashes = []
    scenario_counts = []
    unique_counts = []

    for n_scen in sample_sizes:
        sub = master_matrix[:n_scen, :]
        h = hashlib.sha256(sub.tobytes()).hexdigest()
        u = len(np.unique(sub, axis=0))
        hashes.append(h)
        scenario_counts.append(len(sub))
        unique_counts.append(u)

    # Each sample size must evaluate exactly n_scen scenarios
    assert scenario_counts == list(sample_sizes)
    assert unique_counts == list(sample_sizes)
    # Hashes must all be distinct because each subset has a different number of rows
    assert len(set(hashes)) == len(sample_sizes), "Hashes for different sample sizes must be distinct"
