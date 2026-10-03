"""Unit tests for Stage 9 — Monte Carlo / Gate Simulation + Downstream Utility.

Protocol: docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md - Section 4
          docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 19 (Stage 9)
"""

from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.models.probabilistic.contracts import PROBABILISTIC_PREDICTOR_COLUMNS
from src.models.probabilistic.dependence import (
    GaussianCopulaDependenceModel,
    IndependentDependenceModel,
    StudentTMarginalDistribution,
)
from src.models.probabilistic.dependence_interface import DayFlightBatch
from src.simulation.downstream_metrics import (
    aggregate_simulation_results,
    compute_var_cvar,
)
from src.simulation.gate_simulator import (
    GateConflict,
    GateSimulationResult,
    GateSimulator,
)
from src.simulation.turn_synthesis import (
    SyntheticTurn,
    SyntheticTurnSynthesizer,
)

ROOT = Path(__file__).resolve().parents[1]


def _make_dummy_flight_batch(n_flights: int = 10, base_hour: int = 10) -> DayFlightBatch:
    """Helper creating synthetic flight batch strictly with pre-cutoff features."""
    data = {
        "scheduled_departure_hour": [base_hour + (i % 4) for i in range(n_flights)],
        "scheduled_departure_minute": [(i * 15) % 60 for i in range(n_flights)],
        "CRS_ELAPSED_TIME": [120.0 + (i * 10) for i in range(n_flights)],
        "calendar_year": [2023] * n_flights,
        "calendar_month": [5] * n_flights,
        "calendar_day_of_month": [15] * n_flights,
        "calendar_day_of_week": [2] * n_flights,
        "is_weekend": [0] * n_flights,
        "OP_CARRIER": ["DL" if i % 2 == 0 else "AA" for i in range(n_flights)],
        "ORIGIN": (["BOS", "ORD", "MCO", "LGA", "DFW"] * (n_flights // 5 + 1))[:n_flights],
        "OP_CARRIER_FL_NUM": [str(100 + i) for i in range(n_flights)],
    }
    df = pd.DataFrame(data)
    df.index = pd.Index([f"FL_{20230515}_{i:03d}" for i in range(n_flights)])
    return DayFlightBatch(flight_date="2023-05-15", flight_features=df[list(PROBABILISTIC_PREDICTOR_COLUMNS)])


# =============================================================================
# 1. Joint Sampler Validation Tests
# =============================================================================

def test_joint_sampler_validation_marginal_preservation():
    """Verify that joint copula sampler preserves flight marginal distributions."""
    batch = _make_dummy_flight_batch(n_flights=8)
    marginals = [
        StudentTMarginalDistribution(mu=10.0, sigma=15.0, df=4.5, discrete=True)
        for _ in range(batch.n_flights)
    ]
    copula = GaussianCopulaDependenceModel(temporal_length_scale_minutes=120.0, carrier_correlation=0.15)

    rng = np.random.default_rng(202601)
    y_sim = copula.sample_joint(marginals, batch.flight_features, n_samples=2000, rng=rng)

    assert y_sim.shape == (2000, 8)
    # Check sample mean is close to theoretical location (mu = 10.0)
    col_means = np.mean(y_sim, axis=0)
    np.testing.assert_allclose(col_means, 10.0, atol=2.0)


def test_joint_sampler_validation_daily_n_variation():
    """Verify that joint sampler correctly handles varying daily flight counts."""
    copula = GaussianCopulaDependenceModel()
    rng = np.random.default_rng(202601)

    for n in [3, 9, 21]:
        b = _make_dummy_flight_batch(n_flights=n)
        m = [StudentTMarginalDistribution(mu=5.0, sigma=12.0, df=4.0) for _ in range(n)]
        y = copula.sample_joint(m, b.flight_features, n_samples=50, rng=rng)
        assert y.shape == (50, n)


def test_joint_sampler_validation_psd_guarantee():
    """Verify that copula correlation matrices are strictly positive semi-definite."""
    copula = GaussianCopulaDependenceModel(temporal_length_scale_minutes=90.0, carrier_correlation=0.20)
    batch = _make_dummy_flight_batch(n_flights=15)
    corr = copula.construct_correlation_matrix(batch.flight_features)

    min_eig = np.min(np.linalg.eigvalsh(corr))
    assert min_eig >= 1e-6 - 1e-9
    assert np.allclose(np.diag(corr), 1.0)


def test_joint_sampler_validation_reproducibility():
    """Verify that sampling is strictly reproducible under registered seeds."""
    batch = _make_dummy_flight_batch(n_flights=6)
    marginals = [StudentTMarginalDistribution(mu=0.0, sigma=10.0, df=5.0) for _ in range(6)]
    copula = GaussianCopulaDependenceModel()

    y1 = copula.sample_joint(marginals, batch.flight_features, n_samples=100, rng=np.random.default_rng(202601))
    y2 = copula.sample_joint(marginals, batch.flight_features, n_samples=100, rng=np.random.default_rng(202601))
    np.testing.assert_array_equal(y1, y2)


# =============================================================================
# 2. Synthetic Aircraft Turn Model Tests
# =============================================================================

def test_synthetic_aircraft_turn_physics():
    """Verify that turn synthesis enforces physical turnaround lower bounds."""
    batch = _make_dummy_flight_batch(n_flights=3)
    synthesizer = SyntheticTurnSynthesizer(min_turnaround_minutes=45.0, default_dwell_minutes=60.0)

    # Simulated delay of 90 minutes
    delays = np.array([90.0, 0.0, -15.0])
    turns = synthesizer.synthesize_turns(batch.flight_features, delays)

    assert len(turns) == 3
    t0 = turns[0]
    # Check arrival prediction
    assert t0.simulated_arrival_min == t0.scheduled_arrival_min + 90.0
    # Earliest departure must respect min turnaround (45 min)
    assert t0.gate_release_min >= t0.gate_arrival_min + 45.0
    # Realized turnaround duration must be >= 45 min
    assert t0.occupancy_duration_min >= 45.0


# =============================================================================
# 3. Gate Simulation & Optimization Tests
# =============================================================================

def test_nominal_schedule_planning_and_conflict_detection():
    """Verify nominal schedule planning is conflict-free, but flags conflicts under delays."""
    batch = _make_dummy_flight_batch(n_flights=6)
    synthesizer = SyntheticTurnSynthesizer()

    # Zero delay nominal schedule
    zero_delays = np.zeros(6)
    turns_nom = synthesizer.synthesize_turns(batch.flight_features, zero_delays)

    simulator = GateSimulator(n_contact_gates=5)
    nom_plan = simulator.build_nominal_schedule_plan(turns_nom)

    # Check nominal plan has zero conflicts under zero delay
    res_nom = simulator.evaluate_nominal_plan_under_delays(turns_nom, nom_plan)
    assert res_nom.total_conflict_count == 0

    # Delay flight 0 by 180 min so it overlaps later flights assigned to the same gate
    conflict_delays = np.array([180.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    turns_delayed = synthesizer.synthesize_turns(batch.flight_features, conflict_delays)
    tight_simulator = GateSimulator(n_contact_gates=2)
    tight_nom = tight_simulator.build_nominal_schedule_plan(turns_nom)
    res_delayed = tight_simulator.evaluate_nominal_plan_under_delays(turns_delayed, tight_nom)
    assert res_delayed.total_conflict_count >= 1
    assert res_delayed.total_conflict_duration_min > 0.0


def test_dynamic_greedy_and_exact_milp_solvers():
    """Verify both dynamic greedy and exact MILP allocate gates without conflicts."""
    batch = _make_dummy_flight_batch(n_flights=8)
    synthesizer = SyntheticTurnSynthesizer()
    delays = np.array([25.0, 45.0, 60.0, 10.0, 80.0, 15.0, 30.0, 50.0])
    turns = synthesizer.synthesize_turns(batch.flight_features, delays)

    simulator = GateSimulator(n_contact_gates=4)
    nom_plan = simulator.build_nominal_schedule_plan(turns)

    # 1. Dynamic greedy recourse
    res_greedy = simulator.solve_dynamic_greedy(turns, nom_plan)
    assert res_greedy.total_conflict_count == 0
    assert len(res_greedy.assignments) == 8

    # 2. Exact MILP optimizer
    res_milp = simulator.solve_milp_assignment(turns, nom_plan)
    assert res_milp.total_conflict_count == 0
    assert len(res_milp.assignments) == 8


# =============================================================================
# 4. Downstream Risk Metrics Tests
# =============================================================================

def test_var_and_cvar_computation():
    """Verify VaR and CVaR calculations on known distribution."""
    # Data: 0 to 99 (100 values)
    vals = np.arange(100, dtype=float)
    var95, cvar95 = compute_var_cvar(vals, alpha=0.95)
    # 95th percentile of 0..99 is 95.0
    assert var95 == pytest.approx(94.05, abs=1.0)
    # Tail values are 95..99, mean is 97.0
    assert cvar95 > var95
    assert cvar95 == pytest.approx(97.0, abs=1.0)


def test_aggregate_simulation_results():
    """Verify aggregate_simulation_results compiles downstream utility summary."""
    dummy_nominal = [
        GateSimulationResult(
            scenario_id=i,
            n_flights=10,
            n_contact_gates=5,
            solver_mode="nominal_frozen",
            assignments={"FL_0": 0},
            conflicts=[],
            total_conflict_count=1 if i % 2 == 0 else 0,
            total_conflict_duration_min=15.0 if i % 2 == 0 else 0.0,
            overflow_count=0,
            reassignments_count=0,
            peak_concurrent_occupancy=4,
            gate_utilization_rate=0.65,
            wall_clock_time_sec=0.001,
        )
        for i in range(10)
    ]
    dummy_recourse = [
        GateSimulationResult(
            scenario_id=i,
            n_flights=10,
            n_contact_gates=5,
            solver_mode="dynamic_greedy",
            assignments={"FL_0": 0},
            conflicts=[],
            total_conflict_count=0,
            total_conflict_duration_min=0.0,
            overflow_count=1 if i % 3 == 0 else 0,
            reassignments_count=2,
            peak_concurrent_occupancy=4,
            gate_utilization_rate=0.65,
            wall_clock_time_sec=0.001,
        )
        for i in range(10)
    ]

    summary = aggregate_simulation_results("test_regime", dummy_nominal, dummy_recourse, total_flights=100)
    assert summary.regime_id == "test_regime"
    assert summary.conflict_scenario_rate == pytest.approx(0.50)
    assert summary.total_scenarios_evaluated == 10
    assert summary.mean_reassignments_per_day == pytest.approx(2.0)
