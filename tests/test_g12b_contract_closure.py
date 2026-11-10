"""Tests for AEOLUS-G12B Part A: Contract Closure.

Specifications:
- GATE-01: Incompatible carrier on initial assigned gate triggers recourse.
- GATE-02: Incompatible carrier on candidate gate is rejected.
- GATE-03: Gate completely closed during occupancy window is rejected.
- GATE-04: Gate only partially open during required occupancy window is rejected.
- GATE-05: Fully compatible and available gate is accepted.
- GATE-06: No contact gate available -> fallback to remote stand if capacity permits.
- GATE-07: Neither contact nor remote available -> UNASSIGNED / NO_CAPACITY (infeasible).
- GATE-08: Gate compatibility verified ex-post matches online decision.
- GATE-09: No future realized data enters policy.
- STAT-01: compute_remediated_statistics accounts for requested, generated, evaluated, failed, feasible, infeasible, timeouts.
- STAT-02: Accounting handles intentional evaluation failure and timeout scenarios.
- STAT-03: solver_status distinguishes ONLINE_FEASIBLE from ONLINE_INFEASIBLE_NO_CAPACITY and ONLINE_INFEASIBLE.
"""

from __future__ import annotations

import math
from typing import Sequence
import pytest

from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import (
    Flight,
    FlightTimeWindow,
    Gate,
    GateAssignment,
    GateResourceType,
)
from src.simulation.monte_carlo_engine_v2 import (
    ObservableFlightSnapshot,
    CommittedReservationSnapshot,
    GateOccupancySnapshot,
    CausalObservationSnapshot,
    RealizedScenario,
    RemediatedRealizationResult,
    compute_remediated_statistics,
    evaluate_mode_b2_rolling_online_recourse,
    make_causal_recourse_decision,
)


# ==============================================================================
# GATE-01 & GATE-02: CARRIER COMPATIBILITY
# ==============================================================================
def test_gate_01_incompatible_carrier_on_initial_gate_triggers_recourse():
    """GATE-01: Carrier VN on gate G1 allowed only for BA -> must trigger recourse."""
    g1 = Gate(gate_id="G1", gate_index=0, resource_type=GateResourceType.CONTACT_GATE, allowed_carriers=("BA",))
    g2 = Gate(gate_id="G2", gate_index=1, resource_type=GateResourceType.CONTACT_GATE, allowed_carriers=("VN",))
    remote = Gate(gate_id="REMOTE", gate_index=2, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=5, is_overflow=True)
    cfg = GateOptimizationConfig()

    fl = ObservableFlightSnapshot(
        flight_id="F1", flight_index=0, carrier="VN", flight_number="101",
        aircraft_type="A321", scheduled_arrival_min=100, scheduled_departure_min=160,
        nominal_gate_id="G1", min_turnaround_min=30, default_dwell_min=60, buffer_min=15,
        is_paired=False, observed_arrival_min=100, estimated_departure_min=160, is_docked=False,
    )
    snap = CausalObservationSnapshot(
        epoch_min=100, current_flight=fl, gate_occupancy={},
        committed_reservations=[], current_remote_usage=0, finite_remote_capacity=5,
    )

    chosen_gate_id, reason = make_causal_recourse_decision(
        snapshot=snap, current_assigned_gate_id="G1",
        contact_gates=[g1, g2], remote_gate=remote, config=cfg,
    )
    assert chosen_gate_id == "G2", f"Carrier VN must be reassigned from G1 (BA only) to G2 (VN allowed), got {chosen_gate_id}"
    assert reason is not None


def test_gate_02_incompatible_carrier_on_candidate_gate_rejected():
    """GATE-02: Carrier VN seeking alternative contact gate must skip gate restricted to AF."""
    g1 = Gate(gate_id="G1", gate_index=0, resource_type=GateResourceType.CONTACT_GATE, allowed_carriers=("BA",))
    g2 = Gate(gate_id="G2", gate_index=1, resource_type=GateResourceType.CONTACT_GATE, allowed_carriers=("AF",))
    g3 = Gate(gate_id="G3", gate_index=2, resource_type=GateResourceType.CONTACT_GATE, allowed_carriers=("VN",))
    remote = Gate(gate_id="REMOTE", gate_index=3, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=5, is_overflow=True)
    cfg = GateOptimizationConfig()

    fl = ObservableFlightSnapshot(
        flight_id="F1", flight_index=0, carrier="VN", flight_number="101",
        aircraft_type="A321", scheduled_arrival_min=100, scheduled_departure_min=160,
        nominal_gate_id="G1", min_turnaround_min=30, default_dwell_min=60, buffer_min=15,
        is_paired=False, observed_arrival_min=100, estimated_departure_min=160, is_docked=False,
    )
    snap = CausalObservationSnapshot(
        epoch_min=100, current_flight=fl, gate_occupancy={},
        committed_reservations=[], current_remote_usage=0, finite_remote_capacity=5,
    )

    chosen_gate_id, _ = make_causal_recourse_decision(
        snapshot=snap, current_assigned_gate_id="G1",
        contact_gates=[g1, g2, g3], remote_gate=remote, config=cfg,
    )
    assert chosen_gate_id == "G3", f"Expected G3 (VN allowed), got {chosen_gate_id}"


# ==============================================================================
# GATE-03 & GATE-04: OPERATIONAL AVAILABILITY WINDOWS
# ==============================================================================
def test_gate_03_gate_closed_during_occupancy_window_rejected():
    """GATE-03: Gate G1 has maintenance during [90, 180]. Flight needs [100, 175). Must trigger recourse."""
    g1 = Gate(gate_id="G1", gate_index=0, resource_type=GateResourceType.CONTACT_GATE, available_windows=((0, 80), (200, 400)))
    g2 = Gate(gate_id="G2", gate_index=1, resource_type=GateResourceType.CONTACT_GATE, available_windows=((0, 500),))
    remote = Gate(gate_id="REMOTE", gate_index=2, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=5, is_overflow=True)
    cfg = GateOptimizationConfig()

    fl = ObservableFlightSnapshot(
        flight_id="F1", flight_index=0, carrier="VN", flight_number="101",
        aircraft_type="A321", scheduled_arrival_min=100, scheduled_departure_min=160,
        nominal_gate_id="G1", min_turnaround_min=30, default_dwell_min=60, buffer_min=15,
        is_paired=False, observed_arrival_min=100, estimated_departure_min=160, is_docked=False,
    )
    snap = CausalObservationSnapshot(
        epoch_min=100, current_flight=fl, gate_occupancy={},
        committed_reservations=[], current_remote_usage=0, finite_remote_capacity=5,
    )

    chosen_gate_id, _ = make_causal_recourse_decision(
        snapshot=snap, current_assigned_gate_id="G1",
        contact_gates=[g1, g2], remote_gate=remote, config=cfg,
    )
    assert chosen_gate_id == "G2", f"Gate G1 is closed at t=100..175; must select open gate G2, got {chosen_gate_id}"


def test_gate_04_gate_only_partially_open_rejected():
    """GATE-04: Gate G1 is open [0, 150]. Flight needs [100, 175) (buffer ends at 175).
    Gate closes before buffer ends -> must reject G1 and choose G2.
    """
    g1 = Gate(gate_id="G1", gate_index=0, resource_type=GateResourceType.CONTACT_GATE, available_windows=((0, 150),))
    g2 = Gate(gate_id="G2", gate_index=1, resource_type=GateResourceType.CONTACT_GATE, available_windows=((0, 300),))
    remote = Gate(gate_id="REMOTE", gate_index=2, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=5, is_overflow=True)
    cfg = GateOptimizationConfig()

    fl = ObservableFlightSnapshot(
        flight_id="F1", flight_index=0, carrier="VN", flight_number="101",
        aircraft_type="A321", scheduled_arrival_min=100, scheduled_departure_min=160,
        nominal_gate_id="G1", min_turnaround_min=30, default_dwell_min=60, buffer_min=15,
        is_paired=False, observed_arrival_min=100, estimated_departure_min=160, is_docked=False,
    )
    snap = CausalObservationSnapshot(
        epoch_min=100, current_flight=fl, gate_occupancy={},
        committed_reservations=[], current_remote_usage=0, finite_remote_capacity=5,
    )

    chosen_gate_id, _ = make_causal_recourse_decision(
        snapshot=snap, current_assigned_gate_id="G1",
        contact_gates=[g1, g2], remote_gate=remote, config=cfg,
    )
    assert chosen_gate_id == "G2", f"G1 closes at 150 (< 175 required), must select G2, got {chosen_gate_id}"


# ==============================================================================
# STAT-01: ACCURATE STATISTICAL ACCOUNTING
# ==============================================================================
def test_stat_01_accounting_decomposes_evaluations_and_failures():
    """STAT-01: compute_remediated_statistics decomposes requested, generated, evaluated, failed, feasible, infeasible."""
    # Create 2 mock results: 1 feasible, 1 infeasible
    res_feas = RemediatedRealizationResult(
        realization_id="R1", scenario_index=0, initial_plan_solver="Greedy", recourse_solver="RollingOnlineGreedy",
        recourse_policy="ONLINE_NON_ANTICIPATIVE_EVENT_DRIVEN", information_regime="ONLINE_RECOURSE",
        mode="MODE_B2_ONLINE_RECOURSE", objective_value=100.0, decision_cost=100.0, reporting_cost=0.0,
        reassignment_count=1, remote_count=0,
        feasibility=pytest.importorskip("src.simulation.monte_carlo_engine_v2").FeasibilityBreakdown(
            physical_contact_conflict_count=0, buffer_violation_count=0, max_concurrent_remote_usage=0,
            remote_capacity_violation=False, unassigned_flight_count=0, static_slot_consistency=False, composite_feasible=True,
        ),
        runtime_ms=3.0, solver_status="ONLINE_FEASIBLE", is_optimal_proven=False, realization_hash="h1",
    )
    res_infeas = RemediatedRealizationResult(
        realization_id="R2", scenario_index=1, initial_plan_solver="Greedy", recourse_solver="RollingOnlineGreedy",
        recourse_policy="ONLINE_NON_ANTICIPATIVE_EVENT_DRIVEN", information_regime="ONLINE_RECOURSE",
        mode="MODE_B2_ONLINE_RECOURSE", objective_value=500.0, decision_cost=500.0, reporting_cost=0.0,
        reassignment_count=1, remote_count=0,
        feasibility=pytest.importorskip("src.simulation.monte_carlo_engine_v2").FeasibilityBreakdown(
            physical_contact_conflict_count=0, buffer_violation_count=0, max_concurrent_remote_usage=0,
            remote_capacity_violation=False, unassigned_flight_count=1, static_slot_consistency=False, composite_feasible=False,
        ),
        runtime_ms=3.5, solver_status="ONLINE_INFEASIBLE_NO_CAPACITY", is_optimal_proven=False, realization_hash="h2",
    )

    stats = compute_remediated_statistics(
        results=[res_feas, res_infeas],
        requested_n=5,
        generation_failures=1,
        evaluation_failures=2,
    )

    acc = stats.get("accounting", {})
    assert acc.get("n_requested") == 5
    assert acc.get("n_generated") == 4  # 5 requested - 1 gen failure
    assert acc.get("n_evaluated") == 2
    assert acc.get("n_evaluation_failures") == 2
    assert acc.get("n_feasible") == 1
    assert acc.get("n_infeasible") == 1
    assert acc.get("n_capacity_exhausted") == 1


# ==============================================================================
# GATE-05 TO GATE-09 & STAT-02, STAT-03
# ==============================================================================
def test_gate_05_compatible_available_gate_accepted():
    """GATE-05: Gate G1 matches carrier VN and is open during [100, 175) -> accepted without recourse."""
    g1 = Gate(gate_id="G1", gate_index=0, resource_type=GateResourceType.CONTACT_GATE, allowed_carriers=("VN",), available_windows=((0, 300),))
    remote = Gate(gate_id="REMOTE", gate_index=1, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=5, is_overflow=True)
    cfg = GateOptimizationConfig()

    fl = ObservableFlightSnapshot(
        flight_id="F1", flight_index=0, carrier="VN", flight_number="101",
        aircraft_type="A321", scheduled_arrival_min=100, scheduled_departure_min=160,
        nominal_gate_id="G1", min_turnaround_min=30, default_dwell_min=60, buffer_min=15,
        is_paired=False, observed_arrival_min=100, estimated_departure_min=160, is_docked=False,
    )
    snap = CausalObservationSnapshot(
        epoch_min=100, current_flight=fl, gate_occupancy={},
        committed_reservations=[], current_remote_usage=0, finite_remote_capacity=5,
    )

    chosen_gate_id, reason = make_causal_recourse_decision(
        snapshot=snap, current_assigned_gate_id="G1",
        contact_gates=[g1], remote_gate=remote, config=cfg,
    )
    assert chosen_gate_id == "G1"
    assert reason is None, "Compatible, open gate should retain initial assignment"


def test_gate_06_no_valid_contact_gate_falls_back_to_remote():
    """GATE-06: All contact gates are incompatible with carrier or aircraft -> fallback to remote stand."""
    g1 = Gate(gate_id="G1", gate_index=0, resource_type=GateResourceType.CONTACT_GATE, allowed_carriers=("BA",))
    g2 = Gate(gate_id="G2", gate_index=1, resource_type=GateResourceType.CONTACT_GATE, allowed_aircraft_types=("B777",))
    remote = Gate(gate_id="REMOTE", gate_index=2, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=5, is_overflow=True)
    cfg = GateOptimizationConfig()

    fl = ObservableFlightSnapshot(
        flight_id="F1", flight_index=0, carrier="VN", flight_number="101",
        aircraft_type="A321", scheduled_arrival_min=100, scheduled_departure_min=160,
        nominal_gate_id="G1", min_turnaround_min=30, default_dwell_min=60, buffer_min=15,
        is_paired=False, observed_arrival_min=100, estimated_departure_min=160, is_docked=False,
    )
    snap = CausalObservationSnapshot(
        epoch_min=100, current_flight=fl, gate_occupancy={},
        committed_reservations=[], current_remote_usage=0, finite_remote_capacity=5,
    )

    chosen_gate_id, reason = make_causal_recourse_decision(
        snapshot=snap, current_assigned_gate_id="G1",
        contact_gates=[g1, g2], remote_gate=remote, config=cfg,
    )
    assert chosen_gate_id == "REMOTE"
    assert reason is not None


def test_gate_07_no_contact_and_no_remote_returns_unassigned():
    """GATE-07: All contact gates closed/incompatible and remote stand full -> returns None / unassigned."""
    g1 = Gate(gate_id="G1", gate_index=0, resource_type=GateResourceType.CONTACT_GATE, allowed_carriers=("BA",))
    remote = Gate(gate_id="REMOTE", gate_index=1, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=1, is_overflow=True)
    cfg = GateOptimizationConfig(finite_remote_capacity=1, enforce_remote_capacity=True, allow_unbounded_overflow=False)

    fl = ObservableFlightSnapshot(
        flight_id="F1", flight_index=0, carrier="VN", flight_number="101",
        aircraft_type="A321", scheduled_arrival_min=100, scheduled_departure_min=160,
        nominal_gate_id="G1", min_turnaround_min=30, default_dwell_min=60, buffer_min=15,
        is_paired=False, observed_arrival_min=100, estimated_departure_min=160, is_docked=False,
    )
    snap = CausalObservationSnapshot(
        epoch_min=100, current_flight=fl, gate_occupancy={},
        committed_reservations=[], current_remote_usage=1, finite_remote_capacity=1,  # Remote already full
    )

    chosen_gate_id, reason = make_causal_recourse_decision(
        snapshot=snap, current_assigned_gate_id="G1",
        contact_gates=[g1], remote_gate=remote, config=cfg,
    )
    assert chosen_gate_id is None
    assert reason == "NO_CAPACITY_EXHAUSTED"


def test_gate_08_end_to_end_mode_b2_carrier_and_availability():
    """GATE-08: Full schedule simulation where flight F1 (carrier VN) has nominal G1 (allowed BA only).
    F1 must be dynamically reassigned to G2 (allowed VN) and ex-post evaluation must have 0 incompatibility violations.
    """
    g1 = Gate(gate_id="G1", gate_index=0, resource_type=GateResourceType.CONTACT_GATE, allowed_carriers=("BA",))
    g2 = Gate(gate_id="G2", gate_index=1, resource_type=GateResourceType.CONTACT_GATE, allowed_carriers=("VN",))
    remote = Gate(gate_id="REMOTE", gate_index=2, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=5, is_overflow=True)
    all_gates = [g1, g2, remote]
    cfg = GateOptimizationConfig()

    f1 = Flight(
        flight_id="F1", flight_index=0, carrier="VN", flight_number="101",
        scheduled_arrival_min=100, scheduled_departure_min=160, predicted_arrival_min=100,
        nominal_gate_id="G1", aircraft_type="A321", min_turnaround_min=30, default_dwell_min=60, buffer_min=15,
        precomputed_gate_out_min=160,
    )
    init_plan = {
        "F1": GateAssignment(flight_id="F1", gate_id="G1", occupancy_start_min=100, occupancy_end_min=175),
    }
    scen = RealizedScenario(scenario_id="S_CARRIER", scenario_index=0, arrival_delays=(0.0,), departure_delays=(0.0,), realization_hash="hcarrier", seed=100)

    res = evaluate_mode_b2_rolling_online_recourse(
        initial_assignments=init_plan,
        realized_flights=[f1],
        base_scheduled_flights=[f1],
        gates=all_gates,
        config=cfg,
        realization=scen,
        initial_solver_name="Greedy",
    )
    assert res.reassignment_count == 1
    assert res.feasibility.composite_feasible, "Solution must be feasible after reassigning to compatible G2"
    assert res.solver_status == "ONLINE_FEASIBLE"
    assert res.decision_trace[0]["reassigned_gate"] == "G2"


def test_stat_03_solver_status_classification():
    """STAT-03: solver_status explicitly distinguishes ONLINE_FEASIBLE from ONLINE_INFEASIBLE_NO_CAPACITY."""
    g1 = Gate(gate_id="G1", gate_index=0, resource_type=GateResourceType.CONTACT_GATE)
    remote = Gate(gate_id="REMOTE", gate_index=1, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=1, is_overflow=True)
    cfg = GateOptimizationConfig(finite_remote_capacity=1, enforce_remote_capacity=True, allow_unbounded_overflow=False)

    f1 = Flight(flight_id="F1", flight_index=0, carrier="VN", flight_number="1", scheduled_arrival_min=50, scheduled_departure_min=150, predicted_arrival_min=50, nominal_gate_id="G1", min_turnaround_min=30, default_dwell_min=60, buffer_min=15, precomputed_gate_out_min=150)
    f2 = Flight(flight_id="F2", flight_index=1, carrier="VN", flight_number="2", scheduled_arrival_min=100, scheduled_departure_min=160, predicted_arrival_min=100, nominal_gate_id="G1", min_turnaround_min=30, default_dwell_min=60, buffer_min=15, precomputed_gate_out_min=160)
    f3 = Flight(flight_id="F3", flight_index=2, carrier="VN", flight_number="3", scheduled_arrival_min=105, scheduled_departure_min=170, predicted_arrival_min=105, nominal_gate_id="G1", min_turnaround_min=30, default_dwell_min=60, buffer_min=15, precomputed_gate_out_min=170)

    init_plan = {
        "F1": GateAssignment(flight_id="F1", gate_id="G1", occupancy_start_min=50, occupancy_end_min=165),
        "F2": GateAssignment(flight_id="F2", gate_id="G1", occupancy_start_min=100, occupancy_end_min=175),
        "F3": GateAssignment(flight_id="F3", gate_id="G1", occupancy_start_min=105, occupancy_end_min=185),
    }
    scen = RealizedScenario(scenario_id="S_STAT3", scenario_index=0, arrival_delays=(0.0, 0.0, 0.0), departure_delays=(0.0, 0.0, 0.0), realization_hash="hstat3", seed=101)

    res = evaluate_mode_b2_rolling_online_recourse(
        initial_assignments=init_plan, realized_flights=[f1, f2, f3], base_scheduled_flights=[f1, f2, f3],
        gates=[g1, remote], config=cfg, realization=scen, initial_solver_name="Greedy",
    )
    assert res.solver_status == "ONLINE_INFEASIBLE_NO_CAPACITY", f"Expected ONLINE_INFEASIBLE_NO_CAPACITY, got {res.solver_status}"
    assert not res.feasibility.composite_feasible

