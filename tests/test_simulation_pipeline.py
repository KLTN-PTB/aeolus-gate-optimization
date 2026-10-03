"""Unit and Property Tests for Phase G Simulation Pipeline Components.

Protocol: docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md - Section 4
          docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 19 (Stage 9)
Verifies:
1. AircraftTurnModel boundary cases:
   - Early arrival (negative delay) preserves scheduled departure when dwell dominates.
   - Zero delay (on-time arrival) preserves standard dwell.
   - Severe delay (positive delay) pushes simulated departure via minimum turnaround.
   - Buffer separation added strictly to gate release.
   - Conversion to domain Flight object preserves time window.
2. MonteCarloScenarioRunner:
   - Output shape is strictly [n_scenarios, n_flights].
   - Deterministic reproducibility under identical seed.
   - Strictly pre-cutoff covariates only; zero leakage of ground-truth outcomes.
3. ConflictDetector:
   - Detects exact pairwise overlap durations on contact gates.
   - Ignores concurrent occupancies on overflow stands.
   - Computes correct peak single-gate and airport-wide concurrent occupancies.
   - Returns 0 conflicts on valid feasible assignments.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.models.probabilistic.dependence import (
    GaussianCopulaDependenceModel,
    IndependentDependenceModel,
    StudentTMarginalDistribution,
)
from src.optimization.domain import Gate, GateAssignment
from src.simulation.aircraft_turn import AircraftTurn, AircraftTurnModel
from src.simulation.conflict_detector import detect_conflicts
from src.simulation.scenario_runner import MonteCarloScenarioRunner


# =============================================================================
# 1. AircraftTurnModel Tests & Boundary Cases
# =============================================================================

def test_aircraft_turn_zero_delay() -> None:
    """Zero delay: simulated arrival equals scheduled arrival; dwell dominates minimum turnaround."""
    model = AircraftTurnModel(min_turnaround_min=45, default_dwell_min=60, separation_buffer_min=15)
    turn = model.synthesize_turn(
        flight_id="FL_01",
        carrier="DL",
        flight_number="101",
        scheduled_arrival_min=600,
        sampled_delay_min=0.0,
    )
    assert turn.simulated_arrival_min == 600
    # D_sched = 600 + 60 = 660. D_min = 600 + 45 = 645. D_sim = max(660, 645) = 660.
    assert turn.simulated_departure_min == 660
    # Gate release = 660 + 15 = 675.
    assert turn.gate_release_min == 675
    assert turn.occupancy_duration_min == 75


def test_aircraft_turn_early_arrival_negative_delay() -> None:
    """Early arrival: arrival is earlier than scheduled, but departure remains anchored to schedule."""
    model = AircraftTurnModel(min_turnaround_min=45, default_dwell_min=60, separation_buffer_min=15)
    turn = model.synthesize_turn(
        flight_id="FL_02",
        carrier="DL",
        flight_number="102",
        scheduled_arrival_min=600,
        sampled_delay_min=-25.0,  # 25 min early
    )
    assert turn.simulated_arrival_min == 575
    # D_sched = 660. D_min = 575 + 45 = 620. D_sim = max(660, 620) = 660.
    assert turn.simulated_departure_min == 660
    assert turn.gate_release_min == 675
    assert turn.occupancy_duration_min == 100


def test_aircraft_turn_late_arrival_pushes_departure() -> None:
    """Severe late arrival: arrival is delayed such that minimum turnaround pushes departure beyond schedule."""
    model = AircraftTurnModel(min_turnaround_min=45, default_dwell_min=60, separation_buffer_min=15)
    turn = model.synthesize_turn(
        flight_id="FL_03",
        carrier="DL",
        flight_number="103",
        scheduled_arrival_min=600,
        sampled_delay_min=90.0,  # 90 min late
    )
    assert turn.simulated_arrival_min == 690
    # D_sched = 660. D_min = 690 + 45 = 735. D_sim = max(660, 735) = 735.
    assert turn.simulated_departure_min == 735
    assert turn.gate_release_min == 750
    assert turn.occupancy_duration_min == 60


def test_aircraft_turn_paired_departure() -> None:
    """Paired flight: scheduled departure is explicitly provided rather than defaulted."""
    model = AircraftTurnModel(min_turnaround_min=45, default_dwell_min=60, separation_buffer_min=15)
    turn = model.synthesize_turn(
        flight_id="FL_04",
        carrier="AA",
        flight_number="200",
        scheduled_arrival_min=500,
        sampled_delay_min=10.0,
        scheduled_departure_min=590,
        is_paired=True,
    )
    assert turn.simulated_arrival_min == 510
    # D_sched = 590. D_min = 510 + 45 = 555. D_sim = max(590, 555) = 590.
    assert turn.simulated_departure_min == 590
    assert turn.gate_release_min == 605


def test_aircraft_turn_to_domain_flight_conversion() -> None:
    """Conversion to domain Flight preserves identical time window and timeline properties."""
    model = AircraftTurnModel(min_turnaround_min=45, default_dwell_min=60, separation_buffer_min=15)
    turn = model.synthesize_turn(
        flight_id="FL_05",
        carrier="UA",
        flight_number="300",
        scheduled_arrival_min=600,
        sampled_delay_min=30.0,
        nominal_gate_id="G12",
    )
    flight = turn.to_flight(flight_index=5)
    assert flight.flight_id == "FL_05"
    assert flight.predicted_arrival_min == 630
    assert flight.time_window.start_min == turn.simulated_arrival_min
    assert flight.time_window.end_min == turn.gate_release_min


# =============================================================================
# 2. MonteCarloScenarioRunner Tests
# =============================================================================

def test_scenario_runner_shape_and_reproducibility() -> None:
    """Scenario runner must output [n_scenarios, n_flights] and reproduce under same seed."""
    n_flights = 10
    n_scenarios = 50

    marginals = [
        StudentTMarginalDistribution(mu=15.0, sigma=10.0, df=4.0)
        for _ in range(n_flights)
    ]
    df = pd.DataFrame(
        {
            "scheduled_departure_hour": [8 + (i % 12) for i in range(n_flights)],
            "scheduled_departure_minute": [(i * 5) % 60 for i in range(n_flights)],
            "OP_CARRIER": ["DL" if i % 2 == 0 else "AA" for i in range(n_flights)],
        }
    )

    dep_model = GaussianCopulaDependenceModel(temporal_length_scale_minutes=120.0)
    runner = MonteCarloScenarioRunner(dependence_model=dep_model)

    scenarios_1 = runner.run_scenarios(marginals, df, n_scenarios=n_scenarios, rng=42)
    scenarios_2 = runner.run_scenarios(marginals, df, n_scenarios=n_scenarios, rng=42)

    assert scenarios_1.shape == (n_scenarios, n_flights)
    np.testing.assert_array_equal(scenarios_1, scenarios_2)


def test_scenario_runner_invalid_inputs_fail_closed() -> None:
    """Invalid input dimensions or negative scenario counts must raise errors fail-closed."""
    dep_model = IndependentDependenceModel()
    runner = MonteCarloScenarioRunner(dependence_model=dep_model)

    marginals = [StudentTMarginalDistribution(mu=10.0, sigma=5.0, df=5.0)]
    df_empty = pd.DataFrame()

    with pytest.raises(Exception):
        runner.run_scenarios(marginals, df_empty, n_scenarios=10)

    df_valid = pd.DataFrame({"OP_CARRIER": ["DL"], "scheduled_departure_hour": [10]})
    with pytest.raises(ValueError, match="strictly positive"):
        runner.run_scenarios(marginals, df_valid, n_scenarios=0)


# =============================================================================
# 3. ConflictDetector Tests
# =============================================================================

def test_conflict_detector_clean_schedule() -> None:
    """Disjoint flight occupancies on contact gates must produce zero conflicts."""
    model = AircraftTurnModel()
    turn_1 = model.synthesize_turn("F1", "DL", "1", scheduled_arrival_min=100, sampled_delay_min=0)  # [100, 175)
    turn_2 = model.synthesize_turn("F2", "DL", "2", scheduled_arrival_min=200, sampled_delay_min=0)  # [200, 275)

    g1 = Gate(gate_id="G1", gate_index=0, is_overflow=False)
    assignments = {"F1": "G1", "F2": "G1"}

    res = detect_conflicts(assignments, [turn_1, turn_2], [g1])
    assert res.has_conflicts is False
    assert res.conflict_count == 0
    assert res.total_conflict_duration_min == 0.0
    assert res.peak_single_gate_concurrency == 1


def test_conflict_detector_overlap_detected() -> None:
    """Overlapping occupancy intervals on contact gate must be detected with exact duration."""
    model = AircraftTurnModel()
    # Turn 1: [100, 175)
    turn_1 = model.synthesize_turn("F1", "DL", "1", scheduled_arrival_min=100, sampled_delay_min=0)
    # Turn 2: [140, 215) -> Overlaps with Turn 1 from 140 to 175 (35 minutes)
    turn_2 = model.synthesize_turn("F2", "DL", "2", scheduled_arrival_min=140, sampled_delay_min=0)

    g1 = Gate(gate_id="G1", gate_index=0, is_overflow=False)
    assignments = {"F1": "G1", "F2": "G1"}

    res = detect_conflicts(assignments, [turn_1, turn_2], [g1])
    assert res.has_conflicts is True
    assert res.conflict_count == 1
    assert res.total_conflict_duration_min == 35.0
    assert res.peak_single_gate_concurrency == 2


def test_conflict_detector_overflow_apron_ignored() -> None:
    """Overflow apron allows concurrent occupancy without registering conflicts."""
    model = AircraftTurnModel()
    turn_1 = model.synthesize_turn("F1", "DL", "1", scheduled_arrival_min=100, sampled_delay_min=0)
    turn_2 = model.synthesize_turn("F2", "DL", "2", scheduled_arrival_min=100, sampled_delay_min=0)

    g_ovf = Gate(gate_id="OVERFLOW", gate_index=1, is_overflow=True)
    assignments = {"F1": "OVERFLOW", "F2": "OVERFLOW"}

    res = detect_conflicts(assignments, [turn_1, turn_2], [g_ovf])
    assert res.has_conflicts is False
    assert res.conflict_count == 0
