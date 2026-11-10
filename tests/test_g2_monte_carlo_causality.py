"""Test Suite for Phase G2: Monte Carlo Scientific Correctness & Causality Remediation.

Covers verification specifications MC-CAUSAL-01 through MC-CAUSAL-09 and Feasibility Decomposition:
- MC-CAUSAL-01: Same history, different future -> strictly identical current action.
- MC-CAUSAL-02: Future delay mutation does not alter past decisions.
- MC-CAUSAL-03: Observed past event permitted to change future action.
- MC-CAUSAL-04: Cannot move already docked or completed flights.
- MC-CAUSAL-05: Cannot retroactively change gate of docked flight.
- MC-CAUSAL-06: Timezone and midnight crossover (>1440 min) handled correctly.
- MC-CAUSAL-07: Missing or invalid decision timestamp handled fail-closed.
- MC-CAUSAL-08: Decision trace contains explicit decision_epoch_min and rationale.
- MC-CAUSAL-09: Identical scenario and seed produce bit-exact deterministic replay.
- FEAS-01: Feasibility decomposition separates physical contact conflict from static slot consistency.
- MODE-01: Mode B1 explicitly identified as FULL_INFORMATION_RETROSPECTIVE.
- MODE-02: Mode B2 explicitly identified as ONLINE_NON_ANTICIPATIVE.
- MODE-03: Mode C1 labeled HEURISTIC baseline vs Mode C2 labeled PROVEN_OPTIMAL_ORACLE.
- STAT-01: Paired comparison verifies CRN alignment and tracks improved/worsened/tied rates.
"""

from __future__ import annotations

import math
import pytest
import numpy as np

from src.contracts.provenance import InformationRegime
from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import (
    Flight,
    Gate,
    GateAssignment,
    GateResourceType,
)
from src.simulation.monte_carlo_engine_p09 import (
    RealizedScenario,
)
from src.simulation.monte_carlo_engine_v2 import (
    FeasibilityBreakdown,
    RemediatedRealizationResult,
    RemediatedSimulationMode,
    compute_remediated_paired_comparison,
    compute_remediated_statistics,
    evaluate_mode_a_fixed_plan_v2,
    evaluate_mode_b1_retrospective_recourse,
    evaluate_mode_b2_rolling_online_recourse,
    evaluate_mode_c_greedy_foresight,
    evaluate_mode_c_optimal_foresight,
)


@pytest.fixture
def base_config() -> GateOptimizationConfig:
    return GateOptimizationConfig(
        separation_buffer_minutes=15,
        overflow_weight=500.0,
        reassignment_weight=100.0,
        conflict_weight=10000.0,
        finite_remote_capacity=5,
        enforce_remote_capacity=True,
    )


@pytest.fixture
def simple_gates() -> list[Gate]:
    return [
        Gate(gate_id="G1", gate_index=0, resource_type=GateResourceType.CONTACT_GATE, capacity=1),
        Gate(gate_id="G2", gate_index=1, resource_type=GateResourceType.CONTACT_GATE, capacity=1),
        Gate(gate_id="REMOTE1", gate_index=2, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=5, is_overflow=True),
    ]


@pytest.fixture
def four_flights() -> list[Flight]:
    """Four flights across the operational day:
    F1: [100, 160], nominal G1
    F2: [200, 260], nominal G1 (planned 40 min after F1)
    F3: [500, 560], nominal G2
    F4: [600, 660], nominal G2 (planned 40 min after F3)
    """
    return [
        Flight(
            flight_id="F1", flight_index=0, carrier="DL", flight_number="101",
            scheduled_arrival_min=100, scheduled_departure_min=160, predicted_arrival_min=100,
            nominal_gate_id="G1", min_turnaround_min=30, default_dwell_min=60, buffer_min=15,
            precomputed_gate_out_min=160,
        ),
        Flight(
            flight_id="F2", flight_index=1, carrier="DL", flight_number="102",
            scheduled_arrival_min=200, scheduled_departure_min=260, predicted_arrival_min=200,
            nominal_gate_id="G1", min_turnaround_min=30, default_dwell_min=60, buffer_min=15,
            precomputed_gate_out_min=260,
        ),
        Flight(
            flight_id="F3", flight_index=2, carrier="AA", flight_number="201",
            scheduled_arrival_min=500, scheduled_departure_min=560, predicted_arrival_min=500,
            nominal_gate_id="G2", min_turnaround_min=30, default_dwell_min=60, buffer_min=15,
            precomputed_gate_out_min=560,
        ),
        Flight(
            flight_id="F4", flight_index=3, carrier="AA", flight_number="202",
            scheduled_arrival_min=600, scheduled_departure_min=660, predicted_arrival_min=600,
            nominal_gate_id="G2", min_turnaround_min=30, default_dwell_min=60, buffer_min=15,
            precomputed_gate_out_min=660,
        ),
    ]


@pytest.fixture
def initial_plan(four_flights: list[Flight]) -> dict[str, GateAssignment]:
    return {
        f.flight_id: GateAssignment(
            flight_id=f.flight_id,
            gate_id=f.nominal_gate_id,
            occupancy_start_min=f.scheduled_arrival_min,
            occupancy_end_min=f.scheduled_departure_min + f.buffer_min,
        )
        for f in four_flights
    }


# ==============================================================================
# MC-CAUSAL-01 & MC-CAUSAL-02: NON-ANTICIPATIVITY & FUTURE MUTATION INVARIANCE
# ==============================================================================

def test_mc_causal_01_same_history_different_future_same_current_action(
    four_flights: list[Flight],
    simple_gates: list[Gate],
    base_config: GateOptimizationConfig,
    initial_plan: dict[str, GateAssignment],
):
    """MC-CAUSAL-01: Two realizations identical up to epoch T=250 min must produce
    identical actions for all flights arriving <= 250 min, even if future delays diverge wildly.
    """
    # Scenario A: F1 delayed departure to 230 (conflicts with F2 at G1).
    # Future F3 on time, F4 on time.
    realized_flights_a = [
        Flight(
            flight_id="F1", flight_index=0, carrier="DL", flight_number="101",
            scheduled_arrival_min=100, scheduled_departure_min=160, predicted_arrival_min=100,
            nominal_gate_id="G1", default_dwell_min=130, buffer_min=15, precomputed_gate_out_min=230,
        ),
        Flight(
            flight_id="F2", flight_index=1, carrier="DL", flight_number="102",
            scheduled_arrival_min=200, scheduled_departure_min=260, predicted_arrival_min=200,
            nominal_gate_id="G1", default_dwell_min=60, buffer_min=15, precomputed_gate_out_min=260,
        ),
        four_flights[2],  # F3 at 500
        four_flights[3],  # F4 at 600
    ]
    scen_a = RealizedScenario(
        scenario_id="SCEN_A", scenario_index=0,
        arrival_delays=(0.0, 0.0, 0.0, 0.0), departure_delays=(70.0, 0.0, 0.0, 0.0),
        realization_hash="hash_a", seed=1,
    )

    # Scenario B: Exactly identical F1 and F2 history. But future F3 and F4 have huge delays (e.g. +300 min).
    realized_flights_b = [
        realized_flights_a[0],
        realized_flights_a[1],
        Flight(
            flight_id="F3", flight_index=2, carrier="AA", flight_number="201",
            scheduled_arrival_min=500, scheduled_departure_min=560, predicted_arrival_min=800,
            nominal_gate_id="G2", default_dwell_min=120, buffer_min=15, precomputed_gate_out_min=920,
        ),
        Flight(
            flight_id="F4", flight_index=3, carrier="AA", flight_number="202",
            scheduled_arrival_min=600, scheduled_departure_min=660, predicted_arrival_min=950,
            nominal_gate_id="G2", default_dwell_min=120, buffer_min=15, precomputed_gate_out_min=1070,
        ),
    ]
    scen_b = RealizedScenario(
        scenario_id="SCEN_B", scenario_index=1,
        arrival_delays=(0.0, 0.0, 300.0, 350.0), departure_delays=(70.0, 0.0, 360.0, 410.0),
        realization_hash="hash_b", seed=2,
    )

    res_a = evaluate_mode_b2_rolling_online_recourse(
        initial_assignments=initial_plan,
        realized_flights=realized_flights_a,
        base_scheduled_flights=four_flights,
        gates=simple_gates,
        config=base_config,
        realization=scen_a,
        initial_solver_name="Greedy",
    )

    res_b = evaluate_mode_b2_rolling_online_recourse(
        initial_assignments=initial_plan,
        realized_flights=realized_flights_b,
        base_scheduled_flights=four_flights,
        gates=simple_gates,
        config=base_config,
        realization=scen_b,
        initial_solver_name="Greedy",
    )

    # Filter traces for epoch <= 250 min
    trace_a_past = [t for t in res_a.decision_trace if t["decision_epoch_min"] <= 250]
    trace_b_past = [t for t in res_b.decision_trace if t["decision_epoch_min"] <= 250]

    assert len(trace_a_past) == len(trace_b_past), "Past decision counts must match exactly"
    for da, db in zip(trace_a_past, trace_b_past):
        assert da["flight_id"] == db["flight_id"]
        assert da["reassigned_gate"] == db["reassigned_gate"]
        assert da["decision_epoch_min"] == db["decision_epoch_min"]


def test_mc_causal_02_future_delay_mutation_does_not_alter_past_decisions(
    four_flights: list[Flight],
    simple_gates: list[Gate],
    base_config: GateOptimizationConfig,
    initial_plan: dict[str, GateAssignment],
):
    """MC-CAUSAL-02: Mutating the delay of flight F4 must not change the decision for F1 or F2."""
    realized_base = list(four_flights)
    # F1 delayed departure to 210 -> conflicts with F2 at 200
    realized_base[0] = Flight(
        flight_id="F1", flight_index=0, carrier="DL", flight_number="101",
        scheduled_arrival_min=100, scheduled_departure_min=160, predicted_arrival_min=100,
        nominal_gate_id="G1", default_dwell_min=110, buffer_min=15, precomputed_gate_out_min=210,
    )

    scen_1 = RealizedScenario(
        scenario_id="S1", scenario_index=0,
        arrival_delays=(0.0, 0.0, 0.0, 0.0), departure_delays=(50.0, 0.0, 0.0, 0.0),
        realization_hash="h1", seed=10,
    )
    # Now mutate F4 delay drastically
    realized_mutated = list(realized_base)
    realized_mutated[3] = Flight(
        flight_id="F4", flight_index=3, carrier="AA", flight_number="202",
        scheduled_arrival_min=600, scheduled_departure_min=660, predicted_arrival_min=900,
        nominal_gate_id="G2", default_dwell_min=60, buffer_min=15, precomputed_gate_out_min=960,
    )
    scen_2 = RealizedScenario(
        scenario_id="S2", scenario_index=1,
        arrival_delays=(0.0, 0.0, 0.0, 300.0), departure_delays=(50.0, 0.0, 0.0, 300.0),
        realization_hash="h2", seed=20,
    )

    r1 = evaluate_mode_b2_rolling_online_recourse(
        initial_assignments=initial_plan, realized_flights=realized_base,
        base_scheduled_flights=four_flights, gates=simple_gates, config=base_config,
        realization=scen_1, initial_solver_name="Greedy",
    )
    r2 = evaluate_mode_b2_rolling_online_recourse(
        initial_assignments=initial_plan, realized_flights=realized_mutated,
        base_scheduled_flights=four_flights, gates=simple_gates, config=base_config,
        realization=scen_2, initial_solver_name="Greedy",
    )

    t1_f2 = next((t for t in r1.decision_trace if t["flight_id"] == "F2"), None)
    t2_f2 = next((t for t in r2.decision_trace if t["flight_id"] == "F2"), None)
    assert t1_f2 is not None and t2_f2 is not None
    assert t1_f2["reassigned_gate"] == t2_f2["reassigned_gate"]


# ==============================================================================
# MC-CAUSAL-03, MC-CAUSAL-04, MC-CAUSAL-05: DOCKED IMMUTABILITY & REASSIGNMENT
# ==============================================================================

def test_mc_causal_03_observed_past_event_changes_future_action(
    four_flights: list[Flight],
    simple_gates: list[Gate],
    base_config: GateOptimizationConfig,
    initial_plan: dict[str, GateAssignment],
):
    """MC-CAUSAL-03: When F1 delays its departure, future flight F2 arriving at G1 is reassigned."""
    realized = [
        Flight(
            flight_id="F1", flight_index=0, carrier="DL", flight_number="101",
            scheduled_arrival_min=100, scheduled_departure_min=160, predicted_arrival_min=100,
            nominal_gate_id="G1", default_dwell_min=120, buffer_min=15, precomputed_gate_out_min=220,
        ),
        four_flights[1],  # F2 arrives at 200
        four_flights[2],
        four_flights[3],
    ]
    scen = RealizedScenario(
        scenario_id="S3", scenario_index=0,
        arrival_delays=(0.0, 0.0, 0.0, 0.0), departure_delays=(60.0, 0.0, 0.0, 0.0),
        realization_hash="h3", seed=30,
    )
    res = evaluate_mode_b2_rolling_online_recourse(
        initial_assignments=initial_plan, realized_flights=realized,
        base_scheduled_flights=four_flights, gates=simple_gates, config=base_config,
        realization=scen, initial_solver_name="Greedy",
    )

    f2_trace = [t for t in res.decision_trace if t["flight_id"] == "F2"]
    assert len(f2_trace) == 1
    assert f2_trace[0]["previous_gate"] == "G1"
    # F2 should be reassigned to G2 (contact gate free at 200)
    assert f2_trace[0]["reassigned_gate"] == "G2"


def test_mc_causal_04_and_05_cannot_move_already_docked_flight(
    four_flights: list[Flight],
    simple_gates: list[Gate],
    base_config: GateOptimizationConfig,
    initial_plan: dict[str, GateAssignment],
):
    """MC-CAUSAL-04 & MC-CAUSAL-05: F1 arrived at t=100 and docked at G1.
    Even when F1's delay creates an impending conflict with F2, F1 CANNOT be reassigned
    to another gate because it is already docked at G1.
    """
    realized = [
        Flight(
            flight_id="F1", flight_index=0, carrier="DL", flight_number="101",
            scheduled_arrival_min=100, scheduled_departure_min=160, predicted_arrival_min=100,
            nominal_gate_id="G1", default_dwell_min=120, buffer_min=15, precomputed_gate_out_min=220,
        ),
        four_flights[1],  # F2 arrives at 200
        four_flights[2],
        four_flights[3],
    ]
    scen = RealizedScenario(
        scenario_id="S4", scenario_index=0,
        arrival_delays=(0.0, 0.0, 0.0, 0.0), departure_delays=(60.0, 0.0, 0.0, 0.0),
        realization_hash="h4", seed=40,
    )
    res = evaluate_mode_b2_rolling_online_recourse(
        initial_assignments=initial_plan, realized_flights=realized,
        base_scheduled_flights=four_flights, gates=simple_gates, config=base_config,
        realization=scen, initial_solver_name="Greedy",
    )

    # Verify F1 is never in decision_trace (its gate was not changed)
    f1_trace = [t for t in res.decision_trace if t["flight_id"] == "F1"]
    assert len(f1_trace) == 0, "Docked flight F1 must NEVER be moved!"


# ==============================================================================
# MC-CAUSAL-06 & MC-CAUSAL-07: TIMEZONE / MIDNIGHT CROSSOVER & FAIL-CLOSED
# ==============================================================================

def test_mc_causal_06_midnight_crossover_handled_monotonically(
    simple_gates: list[Gate],
    base_config: GateOptimizationConfig,
):
    """MC-CAUSAL-06: Flights crossing midnight (> 1440 min) preserve proper chronological ordering."""
    flights = [
        Flight(
            flight_id="LATE1", flight_index=0, carrier="DL", flight_number="999",
            scheduled_arrival_min=1400, scheduled_departure_min=1480, predicted_arrival_min=1400,
            nominal_gate_id="G1", default_dwell_min=80, buffer_min=15, precomputed_gate_out_min=1480,
        ),
        Flight(
            flight_id="EARLY2", flight_index=1, carrier="DL", flight_number="1000",
            scheduled_arrival_min=1460, scheduled_departure_min=1540, predicted_arrival_min=1460,
            nominal_gate_id="G1", default_dwell_min=80, buffer_min=15, precomputed_gate_out_min=1540,
        ),
    ]
    plan = {
        f.flight_id: GateAssignment(
            flight_id=f.flight_id, gate_id=f.nominal_gate_id,
            occupancy_start_min=f.scheduled_arrival_min, occupancy_end_min=f.scheduled_departure_min + 15,
        )
        for f in flights
    }
    scen = RealizedScenario(
        scenario_id="S_MIDNIGHT", scenario_index=0,
        arrival_delays=(0.0, 0.0), departure_delays=(0.0, 0.0),
        realization_hash="h_mid", seed=50,
    )
    res = evaluate_mode_b2_rolling_online_recourse(
        initial_assignments=plan, realized_flights=flights,
        base_scheduled_flights=flights, gates=simple_gates, config=base_config,
        realization=scen, initial_solver_name="Greedy",
    )
    # At 1460, LATE1 is still docked at G1 (occupancy until 1480+15=1495). EARLY2 must be reassigned.
    e2_trace = [t for t in res.decision_trace if t["flight_id"] == "EARLY2"]
    assert len(e2_trace) == 1
    assert e2_trace[0]["reassigned_gate"] != "G1"


def test_mc_causal_07_missing_decision_timestamp_handled_fail_closed():
    """MC-CAUSAL-07: Missing or non-finite timestamp raises fail-closed ValueError."""
    with pytest.raises(ValueError, match="must be finite numeric"):
        Flight(
            flight_id="CORRUPT", flight_index=0, carrier="DL", flight_number="999",
            scheduled_arrival_min=100, scheduled_departure_min=160,
            predicted_arrival_min=float("nan"),  # Missing / NaN timestamp
            nominal_gate_id="G1",
        )


def test_mc_causal_08_decision_trace_contains_epoch_and_reason(
    four_flights: list[Flight],
    simple_gates: list[Gate],
    base_config: GateOptimizationConfig,
    initial_plan: dict[str, GateAssignment],
):
    """MC-CAUSAL-08: Decision trace captures decision_epoch_min, flight_id, previous_gate, reassigned_gate, and reason."""
    realized = [
        Flight(
            flight_id="F1", flight_index=0, carrier="DL", flight_number="101",
            scheduled_arrival_min=100, scheduled_departure_min=160, predicted_arrival_min=100,
            nominal_gate_id="G1", default_dwell_min=120, buffer_min=15, precomputed_gate_out_min=220,
        ),
        four_flights[1],
        four_flights[2],
        four_flights[3],
    ]
    scen = RealizedScenario(
        scenario_id="S8", scenario_index=0,
        arrival_delays=(0.0, 0.0, 0.0, 0.0), departure_delays=(60.0, 0.0, 0.0, 0.0),
        realization_hash="h8", seed=80,
    )
    res = evaluate_mode_b2_rolling_online_recourse(
        initial_assignments=initial_plan, realized_flights=realized,
        base_scheduled_flights=four_flights, gates=simple_gates, config=base_config,
        realization=scen, initial_solver_name="Greedy",
    )
    for record in res.decision_trace:
        assert "decision_epoch_min" in record
        assert "flight_id" in record
        assert "previous_gate" in record
        assert "reassigned_gate" in record
        assert "reason" in record
        assert record["reason"] == "ONLINE_NON_ANTICIPATIVE_RECOURSE"


def test_mc_causal_09_deterministic_replay(
    four_flights: list[Flight],
    simple_gates: list[Gate],
    base_config: GateOptimizationConfig,
    initial_plan: dict[str, GateAssignment],
):
    """MC-CAUSAL-09: Replaying identical scenario with identical inputs produces identical hash and costs."""
    scen = RealizedScenario(
        scenario_id="S9", scenario_index=0,
        arrival_delays=(10.0, 20.0, 0.0, 5.0), departure_delays=(15.0, 25.0, 0.0, 10.0),
        realization_hash="h9", seed=90,
    )
    res1 = evaluate_mode_b2_rolling_online_recourse(
        initial_assignments=initial_plan, realized_flights=four_flights,
        base_scheduled_flights=four_flights, gates=simple_gates, config=base_config,
        realization=scen, initial_solver_name="Greedy",
    )
    res2 = evaluate_mode_b2_rolling_online_recourse(
        initial_assignments=initial_plan, realized_flights=four_flights,
        base_scheduled_flights=four_flights, gates=simple_gates, config=base_config,
        realization=scen, initial_solver_name="Greedy",
    )
    assert res1.objective_value == res2.objective_value
    assert res1.reassignment_count == res2.reassignment_count
    assert res1.realization_hash == res2.realization_hash


# ==============================================================================
# FEASIBILITY DECOMPOSITION: PHYSICAL CONFLICT VS STATIC CONSISTENCY
# ==============================================================================

def test_feas_01_decomposition_separates_physical_conflict_from_static_consistency(
    four_flights: list[Flight],
    simple_gates: list[Gate],
    base_config: GateOptimizationConfig,
    initial_plan: dict[str, GateAssignment],
):
    """FEAS-01: Delaying F3 by 10 min alters operational schedule (static consistency=False),
    but creates NO physical conflict because F3 and F4 have ample buffer.
    Composite feasibility remains TRUE while static consistency is FALSE.
    """
    # Delay F3 arrival by 10 min (510 min), departure by 10 min (570 min).
    # F4 arrives at 600 min, so at gate G2 there is NO overlap (570 + 15 = 585 <= 600).
    realized_no_conflict = list(four_flights)
    realized_no_conflict[2] = Flight(
        flight_id="F3", flight_index=2, carrier="AA", flight_number="201",
        scheduled_arrival_min=500, scheduled_departure_min=560, predicted_arrival_min=510,
        nominal_gate_id="G2", default_dwell_min=60, buffer_min=15, precomputed_gate_out_min=570,
    )
    scen = RealizedScenario(
        scenario_id="S_FEAS1", scenario_index=0,
        arrival_delays=(0.0, 0.0, 10.0, 0.0), departure_delays=(0.0, 0.0, 10.0, 0.0),
        realization_hash="h_feas1", seed=100,
    )
    res = evaluate_mode_a_fixed_plan_v2(
        frozen_assignments=initial_plan,
        realized_flights=realized_no_conflict,
        gates=simple_gates,
        config=base_config,
        realization=scen,
        solver_name="Greedy",
    )

    # Static slot consistency is FALSE because F3 arrived at 510, not 500
    assert res.feasibility.static_slot_consistency is False
    # But physical contact conflict count is 0!
    assert res.feasibility.physical_contact_conflict_count == 0
    # Composite operational feasibility is TRUE!
    assert res.feasibility.composite_feasible is True


def test_feas_02_physical_conflict_causes_composite_infeasible(
    four_flights: list[Flight],
    simple_gates: list[Gate],
    base_config: GateOptimizationConfig,
    initial_plan: dict[str, GateAssignment],
):
    """FEAS-02: Severe delay causing overlap results in physical conflict > 0 and composite_feasible = False."""
    realized_conflict = list(four_flights)
    # F1 delayed departure to 220, overlaps F2 arriving at 200 at G1
    realized_conflict[0] = Flight(
        flight_id="F1", flight_index=0, carrier="DL", flight_number="101",
        scheduled_arrival_min=100, scheduled_departure_min=160, predicted_arrival_min=100,
        nominal_gate_id="G1", default_dwell_min=120, buffer_min=15, precomputed_gate_out_min=220,
    )
    scen = RealizedScenario(
        scenario_id="S_FEAS2", scenario_index=0,
        arrival_delays=(0.0, 0.0, 0.0, 0.0), departure_delays=(60.0, 0.0, 0.0, 0.0),
        realization_hash="h_feas2", seed=101,
    )
    res = evaluate_mode_a_fixed_plan_v2(
        frozen_assignments=initial_plan,
        realized_flights=realized_conflict,
        gates=simple_gates,
        config=base_config,
        realization=scen,
        solver_name="Greedy",
    )
    assert res.feasibility.physical_contact_conflict_count > 0
    assert res.feasibility.composite_feasible is False


# ==============================================================================
# MODES & STATISTICAL COMPARISON AUDIT
# ==============================================================================

def test_mode_01_mode_b1_retrospective_regime(
    four_flights: list[Flight],
    simple_gates: list[Gate],
    base_config: GateOptimizationConfig,
    initial_plan: dict[str, GateAssignment],
):
    """MODE-01: Mode B1 must explicitly record RETROSPECTIVE information regime."""
    scen = RealizedScenario(
        scenario_id="S_B1", scenario_index=0,
        arrival_delays=(0.0, 0.0, 0.0, 0.0), departure_delays=(0.0, 0.0, 0.0, 0.0),
        realization_hash="h_b1", seed=110,
    )
    res = evaluate_mode_b1_retrospective_recourse(
        initial_assignments=initial_plan, realized_flights=four_flights,
        gates=simple_gates, config=base_config, realization=scen,
        initial_solver_name="Greedy", recourse_solver_name="DeterministicGreedy",
    )
    assert res.information_regime == InformationRegime.RETROSPECTIVE.value
    assert res.recourse_policy == "FULL_INFORMATION_RETROSPECTIVE"


def test_mode_02_mode_b2_online_regime(
    four_flights: list[Flight],
    simple_gates: list[Gate],
    base_config: GateOptimizationConfig,
    initial_plan: dict[str, GateAssignment],
):
    """MODE-02: Mode B2 must explicitly record ONLINE_RECOURSE information regime."""
    scen = RealizedScenario(
        scenario_id="S_B2", scenario_index=0,
        arrival_delays=(0.0, 0.0, 0.0, 0.0), departure_delays=(0.0, 0.0, 0.0, 0.0),
        realization_hash="h_b2", seed=120,
    )
    res = evaluate_mode_b2_rolling_online_recourse(
        initial_assignments=initial_plan, realized_flights=four_flights,
        base_scheduled_flights=four_flights, gates=simple_gates, config=base_config,
        realization=scen, initial_solver_name="Greedy",
    )
    assert res.information_regime == InformationRegime.ONLINE_RECOURSE.value
    assert res.recourse_policy == "ONLINE_NON_ANTICIPATIVE_EVENT_DRIVEN"


def test_mode_03_mode_c1_vs_c2_optimality_flag(
    four_flights: list[Flight],
    simple_gates: list[Gate],
    base_config: GateOptimizationConfig,
):
    """MODE-03: Mode C1 (Greedy) is NEVER optimal proven, Mode C2 (CP-SAT) is optimal proven."""
    scen = RealizedScenario(
        scenario_id="S_C", scenario_index=0,
        arrival_delays=(0.0, 0.0, 0.0, 0.0), departure_delays=(0.0, 0.0, 0.0, 0.0),
        realization_hash="h_c", seed=130,
    )
    res_c1 = evaluate_mode_c_greedy_foresight(
        realized_flights=four_flights, gates=simple_gates, config=base_config, realization=scen,
    )
    assert res_c1.is_optimal_proven is False
    assert res_c1.recourse_policy == "HEURISTIC_FULL_FORESIGHT_BENCHMARK"

    res_c2 = evaluate_mode_c_optimal_foresight(
        realized_flights=four_flights, gates=simple_gates, config=base_config, realization=scen,
    )
    assert res_c2.is_optimal_proven is True
    assert res_c2.recourse_policy == "PROVEN_MATHEMATICAL_OPTIMAL_FORESIGHT"


def test_stat_01_crn_paired_comparison_metrics():
    """STAT-01: compute_remediated_paired_comparison accurately calculates paired deltas, SE, and proportions."""
    r_a = [
        RemediatedRealizationResult(
            realization_id=f"R{i}", scenario_index=i, initial_plan_solver="SolA", recourse_solver="NONE",
            recourse_policy="P", information_regime="I", mode="M",
            objective_value=100.0 + i * 10, decision_cost=0, reporting_cost=0, reassignment_count=0, remote_count=0,
            feasibility=FeasibilityBreakdown(0, 0, 0, False, 0, True, True), runtime_ms=1.0,
            solver_status="OPTIMAL", is_optimal_proven=True, realization_hash=f"h{i}",
        )
        for i in range(10)
    ]
    r_b = [
        RemediatedRealizationResult(
            realization_id=f"R{i}", scenario_index=i, initial_plan_solver="SolB", recourse_solver="NONE",
            recourse_policy="P", information_regime="I", mode="M",
            objective_value=80.0 + i * 10, decision_cost=0, reporting_cost=0, reassignment_count=0, remote_count=0,
            feasibility=FeasibilityBreakdown(0, 0, 0, False, 0, True, True), runtime_ms=1.0,
            solver_status="OPTIMAL", is_optimal_proven=True, realization_hash=f"h{i}",
        )
        for i in range(10)
    ]
    paired = compute_remediated_paired_comparison(r_a, r_b, "ModelA", "ModelB")
    assert paired["mean_delta_cost"] == 20.0
    assert paired["std_delta_cost"] == 0.0
    assert paired["counts"]["improved"] == 10
    assert paired["proportions"]["improved_pct"] == 100.0
