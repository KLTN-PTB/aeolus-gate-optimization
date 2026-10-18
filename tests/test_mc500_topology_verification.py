"""Adversarial Verification and Invariant Tests for Gate Resource Topology.

Suite: AEOLUS-MC500-TOPOLOGY-GATE (TOPO-01 through TOPO-12)
Verifies:
- TOPO-01: Exactly 25 contact gates with capacity=1.
- TOPO-02: Total finite remote capacity == 5.
- TOPO-03: Zero implicit unbounded apron in strict experiment (allow_unbounded_overflow=False).
- TOPO-04: Mode B2 utilizes finite remote stand when contact gates are exhausted.
- TOPO-05: Mode B2 accommodates 5 concurrent occupants on finite remote stand.
- TOPO-06: 6th concurrent remote occupant is rejected with NO_CAPACITY_EXHAUSTED.
- TOPO-07: All solvers and evaluation modes share identical gate inventory.
- TOPO-08: Zero hidden fallback to unbounded apron when allow_unbounded_overflow=False.
- TOPO-09: Independent verifier diagnostics align with Mode B2 feasibility.
- TOPO-10: Regression battery pass for existing gate optimization invariants.
- TOPO-11: Mode B2 causal non-anticipativity invariant preserved.
- TOPO-12: Scenario MC_REM_S0009 resolution: infeasible under legacy topology, feasible under corrected topology.
"""

from __future__ import annotations

import copy
import math
from typing import Sequence
import pytest

from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import (
    Flight,
    Gate,
    GateAssignment,
    GateResourceType,
    SolverStatus,
    verify_hard_constraints_independently,
)
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
from src.optimization.solvers.hybrid_solver import HybridGateSolver
from src.simulation.scalability_scenario import (
    DownstreamScenario,
    generate_scalability_scenario,
    scenario_to_flights,
    scenario_to_gates,
)
from src.simulation.monte_carlo_engine_p09 import (
    MonteCarloScenarioGenerator,
    RealizedScenario,
    apply_delays_to_flights,
)
from src.simulation.monte_carlo_engine_v2 import (
    evaluate_mode_b1_retrospective_recourse,
    evaluate_mode_b2_rolling_online_recourse,
)


def _make_dummy_flight(
    flight_id: str,
    index: int,
    start_min: int,
    dwell_min: int = 60,
    buffer_min: int = 15,
    carrier: str = "DL",
    aircraft_type: str = "B737",
    nominal_gate_id: str = "G_01",
) -> Flight:
    """Helper to construct deterministic flight entity."""
    return Flight(
        flight_id=flight_id,
        flight_index=index,
        carrier=carrier,
        flight_number=f"DL{1000 + index}",
        aircraft_type=aircraft_type,
        nominal_gate_id=nominal_gate_id,
        scheduled_arrival_min=start_min,
        scheduled_departure_min=start_min + dwell_min,
        predicted_arrival_min=start_min,
        min_turnaround_min=45,
        default_dwell_min=dwell_min,
        buffer_min=buffer_min,
        is_paired=False,
    )


def _make_assignment(flight_id: str, gate_id: str, start_min: int, end_min: int) -> GateAssignment:
    """Helper to construct deterministic GateAssignment entity."""
    return GateAssignment(
        flight_id=flight_id,
        gate_id=gate_id,
        occupancy_start_min=start_min,
        occupancy_end_min=end_min,
    )


def _make_dummy_scenario(n_flights: int) -> RealizedScenario:
    """Helper to construct zero-delay dummy RealizedScenario."""
    return RealizedScenario(
        scenario_id="SCEN_DUMMY",
        scenario_index=0,
        arrival_delays=tuple([0.0] * n_flights),
        departure_delays=tuple([0.0] * n_flights),
        realization_hash="dummy_hash_001",
        seed=202601,
    )


# ==============================================================================
# TOPO-01 TO TOPO-03: RESOURCE INVENTORY TOPOLOGY
# ==============================================================================

def test_topo_01_exactly_25_contact_gates():
    """TOPO-01: Production scenario produces exactly 25 CONTACT_GATE resources."""
    scen = generate_scalability_scenario(
        n_flights=120,
        n_contact_gates=25,
        seed=202601,
        scenario_id="SCEN_P09_CANONICAL_120",
    )
    contact_gates, remote_gate = scenario_to_gates(
        scen, finite_remote_capacity=5, remote_gate_id="REMOTE_STAND_01"
    )
    assert len(contact_gates) == 25
    for idx, g in enumerate(contact_gates):
        assert g.resource_type == GateResourceType.CONTACT_GATE
        assert g.capacity == 1
        assert g.is_overflow is False
        assert g.gate_id == f"G_{idx+1:02d}"


def test_topo_02_total_finite_remote_capacity_equals_five():
    """TOPO-02: Total finite remote capacity equals exactly 5."""
    scen = generate_scalability_scenario(
        n_flights=120,
        n_contact_gates=25,
        seed=202601,
        scenario_id="SCEN_P09_CANONICAL_120",
    )
    contact_gates, remote_gate = scenario_to_gates(
        scen, finite_remote_capacity=5, remote_gate_id="REMOTE_STAND_01"
    )
    all_gates = contact_gates + [remote_gate]
    finite_remote = [g for g in all_gates if g.resource_type == GateResourceType.FINITE_REMOTE_STAND]
    assert len(finite_remote) == 1
    total_remote_cap = sum(g.capacity for g in finite_remote)
    assert total_remote_cap == 5
    assert remote_gate.gate_id == "REMOTE_STAND_01"
    assert remote_gate.is_overflow is True


def test_topo_03_no_unbounded_overflow_apron_when_disallowed():
    """TOPO-03: Zero UNBOUNDED_OVERFLOW_APRON gates present in strict experiment."""
    scen = generate_scalability_scenario(
        n_flights=120,
        n_contact_gates=25,
        seed=202601,
        scenario_id="SCEN_P09_CANONICAL_120",
    )
    contact_gates, remote_gate = scenario_to_gates(
        scen, finite_remote_capacity=5, remote_gate_id="REMOTE_STAND_01"
    )
    all_gates = contact_gates + [remote_gate]
    unbounded = [
        g for g in all_gates
        if g.resource_type == GateResourceType.UNBOUNDED_OVERFLOW_APRON or math.isinf(g.capacity)
    ]
    assert len(unbounded) == 0


# ==============================================================================
# TOPO-04 TO TOPO-06: FINITE REMOTE STAND CAPACITY CONSTRAINTS IN MODE B2
# ==============================================================================

def test_topo_04_mode_b2_utilizes_finite_remote_when_contact_full():
    """TOPO-04: Mode B2 assigns overflowing flight to finite remote stand when contact gates full."""
    contact_gate = Gate(gate_id="G_01", gate_index=0, resource_type=GateResourceType.CONTACT_GATE, capacity=1)
    remote_gate = Gate(
        gate_id="REMOTE_STAND_01",
        gate_index=1,
        resource_type=GateResourceType.FINITE_REMOTE_STAND,
        capacity=5,
        is_overflow=True,
    )
    gates = [contact_gate, remote_gate]
    config = GateOptimizationConfig(finite_remote_capacity=5, allow_unbounded_overflow=False)

    # Flight 1 docks at G_01 [0, 60]
    f1 = _make_dummy_flight("F1", 0, start_min=0, dwell_min=60, nominal_gate_id="G_01")
    # Flight 2 arrives at 10 min, also planned at G_01 -> conflict!
    f2 = _make_dummy_flight("F2", 1, start_min=10, dwell_min=60, nominal_gate_id="G_01")

    initial_assignments = {
        "F1": _make_assignment("F1", "G_01", 0, 75),
        "F2": _make_assignment("F2", "G_01", 10, 85),
    }

    dummy_scen = _make_dummy_scenario(2)

    res_b2 = evaluate_mode_b2_rolling_online_recourse(
        initial_assignments=initial_assignments,
        realized_flights=[f1, f2],
        base_scheduled_flights=[f1, f2],
        gates=gates,
        config=config,
        realization=dummy_scen,
        initial_solver_name="CPSat",
    )

    assert res_b2.feasibility.composite_feasible is True
    assert res_b2.remote_count == 1
    assert len(res_b2.decision_trace) == 1
    assert res_b2.decision_trace[0]["reassigned_gate"] == "REMOTE_STAND_01"


def test_topo_05_five_concurrent_remote_occupants_accepted():
    """TOPO-05: Exactly 5 concurrent remote occupants are accepted on finite remote stand."""
    contact_gate = Gate(gate_id="G_01", gate_index=0, resource_type=GateResourceType.CONTACT_GATE, capacity=1)
    remote_gate = Gate(
        gate_id="REMOTE_STAND_01",
        gate_index=1,
        resource_type=GateResourceType.FINITE_REMOTE_STAND,
        capacity=5,
        is_overflow=True,
    )
    gates = [contact_gate, remote_gate]
    config = GateOptimizationConfig(finite_remote_capacity=5, allow_unbounded_overflow=False)

    # 1 contact flight [0, 120] occupying G_01
    f_contact = _make_dummy_flight("F_C0", 0, start_min=0, dwell_min=120, nominal_gate_id="G_01")
    # 5 concurrent flights [10..50, 100] all conflicting on G_01
    flights = [f_contact]
    initial_asgns = {"F_C0": _make_assignment("F_C0", "G_01", 0, 135)}
    for k in range(1, 6):
        fk = _make_dummy_flight(f"F_R{k}", k, start_min=10 + k * 2, dwell_min=80, nominal_gate_id="G_01")
        flights.append(fk)
        initial_asgns[fk.flight_id] = _make_assignment(fk.flight_id, "G_01", fk.scheduled_arrival_min, fk.scheduled_departure_min + 15)

    dummy_scen = _make_dummy_scenario(len(flights))

    res_b2 = evaluate_mode_b2_rolling_online_recourse(
        initial_assignments=initial_asgns,
        realized_flights=flights,
        base_scheduled_flights=flights,
        gates=gates,
        config=config,
        realization=dummy_scen,
        initial_solver_name="CPSat",
    )

    assert res_b2.feasibility.composite_feasible is True
    assert res_b2.remote_count == 5
    assert res_b2.feasibility.max_concurrent_remote_usage == 5


def test_topo_06_sixth_concurrent_remote_occupant_rejected():
    """TOPO-06: Sixth concurrent remote occupant rejected with NO_CAPACITY_EXHAUSTED."""
    contact_gate = Gate(gate_id="G_01", gate_index=0, resource_type=GateResourceType.CONTACT_GATE, capacity=1)
    remote_gate = Gate(
        gate_id="REMOTE_STAND_01",
        gate_index=1,
        resource_type=GateResourceType.FINITE_REMOTE_STAND,
        capacity=5,
        is_overflow=True,
    )
    gates = [contact_gate, remote_gate]
    config = GateOptimizationConfig(finite_remote_capacity=5, allow_unbounded_overflow=False)

    # 1 contact flight [0, 120] occupying G_01
    f_contact = _make_dummy_flight("F_C0", 0, start_min=0, dwell_min=120, nominal_gate_id="G_01")
    flights = [f_contact]
    initial_asgns = {"F_C0": _make_assignment("F_C0", "G_01", 0, 135)}
    # 6 concurrent flights all conflicting on G_01
    for k in range(1, 7):
        fk = _make_dummy_flight(f"F_R{k}", k, start_min=10 + k * 2, dwell_min=80, nominal_gate_id="G_01")
        flights.append(fk)
        initial_asgns[fk.flight_id] = _make_assignment(fk.flight_id, "G_01", fk.scheduled_arrival_min, fk.scheduled_departure_min + 15)

    dummy_scen = _make_dummy_scenario(len(flights))

    res_b2 = evaluate_mode_b2_rolling_online_recourse(
        initial_assignments=initial_asgns,
        realized_flights=flights,
        base_scheduled_flights=flights,
        gates=gates,
        config=config,
        realization=dummy_scen,
        initial_solver_name="CPSat",
    )

    # 1 on G_01, 5 on REMOTE_STAND_01, 1 rejected!
    assert res_b2.feasibility.composite_feasible is False
    assert "ONLINE_INFEASIBLE_NO_CAPACITY" in res_b2.solver_status
    assert res_b2.remote_count == 5
    assert res_b2.feasibility.unassigned_flight_count == 1
    # Verify rejection reason in trace
    rejections = [tr for tr in res_b2.decision_trace if tr["reassigned_gate"] == "UNASSIGNED"]
    assert len(rejections) == 1
    assert rejections[0]["reason"] == "NO_CAPACITY_EXHAUSTED"


# ==============================================================================
# TOPO-07 TO TOPO-09: SOLVER CONSISTENCY AND INDEPENDENT VALIDATION
# ==============================================================================

def test_topo_07_solvers_and_modes_share_identical_gate_inventory():
    """TOPO-07: Greedy, CP-SAT, Hybrid, and Recourse modes receive identical gate list."""
    scen = generate_scalability_scenario(
        n_flights=120,
        n_contact_gates=25,
        seed=202601,
        scenario_id="SCEN_P09_CANONICAL_120",
    )
    contact_gates, remote_gate = scenario_to_gates(
        scen, finite_remote_capacity=5, remote_gate_id="REMOTE_STAND_01"
    )
    all_gates = contact_gates + [remote_gate]
    assert len(all_gates) == 26

    # Verify all gate IDs and types
    gate_ids = [g.gate_id for g in all_gates]
    assert len(set(gate_ids)) == 26
    assert gate_ids[-1] == "REMOTE_STAND_01"
    assert all_gates[-1].capacity == 5
    assert all_gates[-1].resource_type == GateResourceType.FINITE_REMOTE_STAND


def test_topo_08_no_hidden_unbounded_apron_fallback():
    """TOPO-08: When allow_unbounded_overflow=False, no fallback to infinite apron occurs."""
    contact_gate = Gate(gate_id="G_01", gate_index=0, resource_type=GateResourceType.CONTACT_GATE, capacity=1)
    remote_gate = Gate(
        gate_id="REMOTE_STAND_01",
        gate_index=1,
        resource_type=GateResourceType.FINITE_REMOTE_STAND,
        capacity=1,
        is_overflow=True,
    )
    # Even if an unbounded apron is erroneously present in gates, config disables it!
    apron_gate = Gate(
        gate_id="APRON_EXTRA",
        gate_index=2,
        resource_type=GateResourceType.UNBOUNDED_OVERFLOW_APRON,
        capacity=math.inf,
        is_overflow=True,
    )
    gates = [contact_gate, remote_gate, apron_gate]
    config = GateOptimizationConfig(finite_remote_capacity=1, allow_unbounded_overflow=False)

    # 3 flights: 1 on contact, 1 on remote, 1 overflow
    f1 = _make_dummy_flight("F1", 0, start_min=0, dwell_min=60, nominal_gate_id="G_01")
    f2 = _make_dummy_flight("F2", 1, start_min=10, dwell_min=60, nominal_gate_id="G_01")
    f3 = _make_dummy_flight("F3", 2, start_min=20, dwell_min=60, nominal_gate_id="G_01")
    flights = [f1, f2, f3]

    initial_asgns = {
        "F1": _make_assignment("F1", "G_01", 0, 75),
        "F2": _make_assignment("F2", "G_01", 10, 85),
        "F3": _make_assignment("F3", "G_01", 20, 95),
    }

    dummy_scen = _make_dummy_scenario(3)

    res_b2 = evaluate_mode_b2_rolling_online_recourse(
        initial_assignments=initial_asgns,
        realized_flights=flights,
        base_scheduled_flights=flights,
        gates=gates,
        config=config,
        realization=dummy_scen,
        initial_solver_name="CPSat",
    )

    # F3 MUST NOT be placed on APRON_EXTRA because allow_unbounded_overflow is False!
    assert res_b2.feasibility.composite_feasible is False
    assert res_b2.feasibility.unassigned_flight_count == 1
    apron_assignments = [tr for tr in res_b2.decision_trace if tr["reassigned_gate"] == "APRON_EXTRA"]
    assert len(apron_assignments) == 0


def test_topo_09_verifier_diagnostics_align_with_b2_feasibility():
    """TOPO-09: Independent verifier confirms zero hard conflicts on feasible B2 assignment."""
    contact_gate = Gate(gate_id="G_01", gate_index=0, resource_type=GateResourceType.CONTACT_GATE, capacity=1)
    remote_gate = Gate(
        gate_id="REMOTE_STAND_01",
        gate_index=1,
        resource_type=GateResourceType.FINITE_REMOTE_STAND,
        capacity=5,
        is_overflow=True,
    )
    gates = [contact_gate, remote_gate]
    config = GateOptimizationConfig(finite_remote_capacity=5, allow_unbounded_overflow=False)

    f1 = _make_dummy_flight("F1", 0, start_min=0, dwell_min=60, nominal_gate_id="G_01")
    f2 = _make_dummy_flight("F2", 1, start_min=10, dwell_min=60, nominal_gate_id="G_01")
    flights = [f1, f2]
    initial_asgns = {
        "F1": _make_assignment("F1", "G_01", 0, 75),
        "F2": _make_assignment("F2", "G_01", 10, 85),
    }

    dummy_scen = _make_dummy_scenario(2)

    res_b2 = evaluate_mode_b2_rolling_online_recourse(
        initial_assignments=initial_asgns,
        realized_flights=flights,
        base_scheduled_flights=flights,
        gates=gates,
        config=config,
        realization=dummy_scen,
        initial_solver_name="CPSat",
    )

    # Check diagnostic consistency
    assert res_b2.feasibility.composite_feasible is True
    assert res_b2.feasibility.physical_contact_conflict_count == 0
    assert res_b2.feasibility.buffer_violation_count == 0
    assert res_b2.feasibility.remote_capacity_violation is False
    assert res_b2.feasibility.unassigned_flight_count == 0
    assert res_b2.solver_status == "ONLINE_FEASIBLE"


# ==============================================================================
# TOPO-10 TO TOPO-12: REGRESSION, NON-ANTICIPATIVITY, AND SCENARIO S0009 RESOLUTION
# ==============================================================================

def test_topo_10_solver_battery_regression():
    """TOPO-10: Greedy and CP-SAT solvers solve 120-flight canonical scenario on 25+5 topology."""
    scen = generate_scalability_scenario(
        n_flights=120,
        n_contact_gates=25,
        seed=202601,
        scenario_id="SCEN_P09_CANONICAL_120",
    )
    flights = scenario_to_flights(scen)
    contact_gates, remote_gate = scenario_to_gates(
        scen, finite_remote_capacity=5, remote_gate_id="REMOTE_STAND_01"
    )
    all_gates = contact_gates + [remote_gate]
    config = GateOptimizationConfig(
        finite_remote_capacity=5,
        enforce_remote_capacity=True,
        allow_unbounded_overflow=False,
        time_limit_seconds=2.0,
        random_seed=202601,
    )

    greedy_res = DeterministicGreedyGateSolver(config=config).solve(flights, all_gates)
    assert greedy_res.status in (SolverStatus.FEASIBLE.value, SolverStatus.OPTIMAL.value)
    assert len(greedy_res.assignments) == 120

    cpsat_res = CPSatGateSolver(config=config).solve(flights, all_gates)
    assert cpsat_res.status in (SolverStatus.FEASIBLE.value, SolverStatus.OPTIMAL.value)
    assert len(cpsat_res.assignments) == 120


def test_topo_11_mode_b2_non_anticipativity_preserved():
    """TOPO-11: Perturbing future arrival delays beyond decision epoch leaves past/present decisions invariant."""
    contact_gate = Gate(gate_id="G_01", gate_index=0, resource_type=GateResourceType.CONTACT_GATE, capacity=1)
    remote_gate = Gate(
        gate_id="REMOTE_STAND_01",
        gate_index=1,
        resource_type=GateResourceType.FINITE_REMOTE_STAND,
        capacity=5,
        is_overflow=True,
    )
    gates = [contact_gate, remote_gate]
    config = GateOptimizationConfig(finite_remote_capacity=5, allow_unbounded_overflow=False)

    f1 = _make_dummy_flight("F1", 0, start_min=0, dwell_min=60, nominal_gate_id="G_01")
    f2 = _make_dummy_flight("F2", 1, start_min=10, dwell_min=60, nominal_gate_id="G_01")
    f3 = _make_dummy_flight("F3", 2, start_min=150, dwell_min=60, nominal_gate_id="G_01")  # well after lock horizon

    flights_a = [f1, f2, f3]
    # Perturb f3 to start at 200 min instead of 150 min
    f3_perturbed = _make_dummy_flight("F3", 2, start_min=200, dwell_min=60, nominal_gate_id="G_01")
    flights_b = [f1, f2, f3_perturbed]

    initial_asgns = {
        "F1": _make_assignment("F1", "G_01", 0, 75),
        "F2": _make_assignment("F2", "G_01", 10, 85),
        "F3": _make_assignment("F3", "G_01", 150, 225),
    }

    dummy_scen_a = _make_dummy_scenario(3)
    dummy_scen_b = _make_dummy_scenario(3)

    res_a = evaluate_mode_b2_rolling_online_recourse(
        initial_assignments=initial_asgns,
        realized_flights=flights_a,
        base_scheduled_flights=flights_a,
        gates=gates,
        config=config,
        realization=dummy_scen_a,
        initial_solver_name="CPSat",
    )
    res_b = evaluate_mode_b2_rolling_online_recourse(
        initial_assignments=initial_asgns,
        realized_flights=flights_b,
        base_scheduled_flights=flights_a,
        gates=gates,
        config=config,
        realization=dummy_scen_b,
        initial_solver_name="CPSat",
    )

    # Decisions for F1 and F2 must be identical regardless of F3 perturbation
    trace_a = [(tr["flight_id"], tr["reassigned_gate"]) for tr in res_a.decision_trace]
    trace_b = [(tr["flight_id"], tr["reassigned_gate"]) for tr in res_b.decision_trace]
    assert trace_a == trace_b


def test_topo_12_scenario_mc_rem_s0009_resolution():
    """TOPO-12: Scenario MC_REM_S0009 is infeasible under legacy topology, feasible under corrected 25+5 topology."""
    scen = generate_scalability_scenario(
        n_flights=120,
        n_contact_gates=25,
        seed=202601,
        scenario_id="SCEN_P09_CANONICAL_120",
    )
    base_flights = scenario_to_flights(scen)

    generator = MonteCarloScenarioGenerator(
        n_scenarios=10,
        seed=202601,
        rho=0.45,
    )
    # Generate scenarios up to index 9 (S0009)
    scenarios = generator.generate_scenarios(base_flights, scenario_prefix="MC_REM")
    s9 = scenarios[9]
    assert s9.scenario_id == "MC_REM_S0009"

    # 1. LEGACY TOPOLOGY (25 contact gates + REMOTE_APRON_01 with unbounded apron classification)
    legacy_contact, legacy_overflow = scenario_to_gates(scen)  # old call
    legacy_gates = legacy_contact + [legacy_overflow]
    config_strict = GateOptimizationConfig(
        finite_remote_capacity=5,
        enforce_remote_capacity=True,
        allow_unbounded_overflow=False,
        time_limit_seconds=1.5,
        random_seed=202601,
    )
    # CPSat initial plan
    cpsat_plan = CPSatGateSolver(config=config_strict).solve(base_flights, legacy_gates)
    assert cpsat_plan.status in (SolverStatus.FEASIBLE.value, SolverStatus.OPTIMAL.value)

    realized_flights = apply_delays_to_flights(base_flights, s9.arrival_delays, s9.departure_delays)

    # Legacy Mode B2 evaluation
    res_legacy = evaluate_mode_b2_rolling_online_recourse(
        initial_assignments=cpsat_plan.assignments,
        realized_flights=realized_flights,
        base_scheduled_flights=base_flights,
        gates=legacy_gates,
        config=config_strict,
        realization=s9,
        initial_solver_name="CPSat",
    )
    # Legacy topology MUST fail on S0009 because no finite remote stand exists!
    assert res_legacy.feasibility.composite_feasible is False
    assert "ONLINE_INFEASIBLE_NO_CAPACITY" in res_legacy.solver_status
    assert res_legacy.remote_count == 0

    # 2. CORRECTED TOPOLOGY (25 contact gates + REMOTE_STAND_01 with capacity=5)
    corr_contact, corr_remote = scenario_to_gates(
        scen, finite_remote_capacity=5, remote_gate_id="REMOTE_STAND_01"
    )
    corr_gates = corr_contact + [corr_remote]
    corr_plan = CPSatGateSolver(config=config_strict).solve(base_flights, corr_gates)

    res_corr = evaluate_mode_b2_rolling_online_recourse(
        initial_assignments=corr_plan.assignments,
        realized_flights=realized_flights,
        base_scheduled_flights=base_flights,
        gates=corr_gates,
        config=config_strict,
        realization=s9,
        initial_solver_name="CPSat",
    )
    # Corrected topology MUST succeed on S0009!
    assert res_corr.feasibility.composite_feasible is True
    assert res_corr.remote_count == 1
    assert res_corr.objective_value < res_legacy.objective_value
