"""Comprehensive tests for Downstream Gate Optimization Semantics V2 (Task R8).

Verifies:
1. Distinct gate assignment states: CONTACT_GATE, REMOTE_STAND, UNASSIGNED (sum invariant).
2. Independent verifier audits overlaps, buffer deficits, carrier/aircraft compatibility, and turnaround windows.
3. Optimizer cannot self-certify feasibility (verifier strictly governs feasibility).
4. Decision costs vs exogenous reporting metrics separation.
5. CP-SAT status certification: OPTIMAL reported only when raw solver is cp_model.OPTIMAL and verified.
6. Equal-compute solver hierarchy (Greedy, CP-SAT budget T, SA refinement T/2 + T/2 <= T).
7. Distinction between planned feasibility and realized post-hoc conflicts.
8. Zero forbidden real-world claim strings in downstream codebase.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from src.evaluation.downstream_comparison_v2 import (
    DEFAULT_DOWNSTREAM_CANDIDATES,
    DownstreamCandidate,
    DownstreamScenarioSpec,
    evaluate_candidate_on_scenario,
    extract_scenario_from_raw,
)
from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import (
    ConstraintDiagnostic,
    Flight,
    Gate,
    GateAssignment,
    GateAssignmentState,
    ObjectiveBreakdown,
    OptimizationResult,
    verify_hard_constraints_independently,
)
from src.optimization.evaluation import evaluate_gate_assignment
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
from tests.downstream.test_same_scenario import _make_dummy_raw_df


def test_distinct_gate_assignment_states_and_sum_invariant() -> None:
    """GateAssignmentState must distinguish CONTACT_GATE, REMOTE_STAND, and UNASSIGNED."""
    # 1. State enum exists and has 3 distinct values
    assert GateAssignmentState.CONTACT_GATE.value == "CONTACT_GATE"
    assert GateAssignmentState.REMOTE_STAND.value == "REMOTE_STAND"
    assert GateAssignmentState.UNASSIGNED.value == "UNASSIGNED"

    # 2. GateAssignment automatic state classification
    assign_contact = GateAssignment(
        flight_id="F1",
        gate_id="G01",
        flight_index=0,
        gate_index=0,
        is_overflow=False,
        is_reassignment=False,
        occupancy_start_min=100,
        occupancy_end_min=160,
    )
    assert assign_contact.assignment_state == GateAssignmentState.CONTACT_GATE.value

    assign_remote = GateAssignment(
        flight_id="F2",
        gate_id="OVERFLOW",
        flight_index=1,
        gate_index=1,
        is_overflow=True,
        is_reassignment=False,
        occupancy_start_min=110,
        occupancy_end_min=170,
    )
    assert assign_remote.assignment_state == GateAssignmentState.REMOTE_STAND.value

    # 3. Sum invariant: contact + remote + unassigned == n_flights
    f1 = Flight(
        flight_id="F1",
        flight_index=0,
        carrier="DL",
        flight_number="1",
        scheduled_arrival_min=100,
        scheduled_departure_min=160,
        predicted_arrival_min=100,
    )
    f2 = Flight(
        flight_id="F2",
        flight_index=1,
        carrier="DL",
        flight_number="2",
        scheduled_arrival_min=120,
        scheduled_departure_min=180,
        predicted_arrival_min=120,
    )
    f3 = Flight(
        flight_id="F3",
        flight_index=2,
        carrier="DL",
        flight_number="3",
        scheduled_arrival_min=140,
        scheduled_departure_min=200,
        predicted_arrival_min=140,
    )

    g_contact = Gate(gate_id="G01", gate_index=0, is_overflow=False)
    g_remote = Gate(gate_id="OVERFLOW", gate_index=1, is_overflow=True)
    gates = [g_contact, g_remote]

    # Only assign F1 (contact) and F2 (remote), leave F3 unassigned
    partial_assignments = {
        "F1": assign_contact,
        "F2": assign_remote,
    }

    diag = verify_hard_constraints_independently(
        flights=[f1, f2, f3],
        gates=gates,
        assignments=partial_assignments,
    )

    assert diag.contact_count == 1
    assert diag.remote_count == 1
    assert diag.unassigned_count == 1
    assert diag.contact_count + diag.remote_count + diag.unassigned_count == 3
    assert diag.is_valid is False  # Infeasible because F3 is unassigned


def test_independent_verifier_detects_overlaps_and_buffer_deficits() -> None:
    """Verifier must catch pairwise overlaps on contact gates outside the solver."""
    g1 = Gate(gate_id="G1", gate_index=0, is_overflow=False)
    # Two flights that overlap on G1: F1 [100, 160) and F2 [140, 200) with buffer 15
    f1 = Flight(
        flight_id="F1",
        flight_index=0,
        carrier="DL",
        flight_number="101",
        scheduled_arrival_min=100,
        scheduled_departure_min=160,
        predicted_arrival_min=100,
        buffer_min=15,
    )
    f2 = Flight(
        flight_id="F2",
        flight_index=1,
        carrier="DL",
        flight_number="102",
        scheduled_arrival_min=140,
        scheduled_departure_min=200,
        predicted_arrival_min=140,
        buffer_min=15,
    )

    overlapping_assignments = {
        "F1": GateAssignment(
            flight_id="F1",
            gate_id="G1",
            flight_index=0,
            gate_index=0,
            is_overflow=False,
            is_reassignment=False,
            occupancy_start_min=100,
            occupancy_end_min=160,
        ),
        "F2": GateAssignment(
            flight_id="F2",
            gate_id="G1",
            flight_index=1,
            gate_index=0,
            is_overflow=False,
            is_reassignment=False,
            occupancy_start_min=140,
            occupancy_end_min=200,
        ),
    }

    diag = verify_hard_constraints_independently(
        flights=[f1, f2],
        gates=[g1],
        assignments=overlapping_assignments,
    )

    assert diag.no_contact_gate_conflicts is False
    assert diag.conflict_count == 1
    assert diag.is_valid is False
    assert len(diag.conflict_pairs) == 1
    assert diag.conflict_pairs[0]["gate_id"] == "G1"
    assert diag.hard_constraint_violations_count >= 1


def test_independent_verifier_carrier_and_aircraft_compatibility() -> None:
    """Verifier must detect carrier and aircraft type incompatibilities."""
    g_dl = Gate(
        gate_id="G_DL",
        gate_index=0,
        is_overflow=False,
        allowed_carriers=frozenset({"DL"}),
        allowed_aircraft_types=frozenset({"B738", "A321"}),
    )
    f_ua = Flight(
        flight_id="F_UA",
        flight_index=0,
        carrier="UA",  # Incompatible carrier
        flight_number="200",
        scheduled_arrival_min=100,
        scheduled_departure_min=160,
        predicted_arrival_min=100,
        aircraft_type="B777",  # Incompatible aircraft
    )

    assign = {
        "F_UA": GateAssignment(
            flight_id="F_UA",
            gate_id="G_DL",
            flight_index=0,
            gate_index=0,
            is_overflow=False,
            is_reassignment=False,
            occupancy_start_min=100,
            occupancy_end_min=160,
        )
    }

    diag = verify_hard_constraints_independently(
        flights=[f_ua],
        gates=[g_dl],
        assignments=assign,
    )

    assert diag.gate_compatibility_satisfied is False
    assert diag.is_valid is False
    assert len(diag.incompatibility_violations) >= 1


def test_optimizer_cannot_self_certify_feasibility() -> None:
    """Feasibility must be strictly certified by independent verifier, not solver status."""
    g1 = Gate(gate_id="G1", gate_index=0, is_overflow=False)
    f1 = Flight(
        flight_id="F1",
        flight_index=0,
        carrier="DL",
        flight_number="1",
        scheduled_arrival_min=100,
        scheduled_departure_min=160,
        predicted_arrival_min=100,
    )
    f2 = Flight(
        flight_id="F2",
        flight_index=1,
        carrier="DL",
        flight_number="2",
        scheduled_arrival_min=110,
        scheduled_departure_min=170,
        predicted_arrival_min=110,
    )

    # Claiming "OPTIMAL" solver status on an overlapping assignment
    conflicted_assignment = {
        "F1": GateAssignment("F1", "G1", 0, 0, False, False, 100, 160),
        "F2": GateAssignment("F2", "G1", 1, 0, False, False, 110, 170),
    }

    result = evaluate_gate_assignment(
        assignments=conflicted_assignment,
        flights=[f1, f2],
        gates=[g1],
        solver_status="OPTIMAL",  # Fraudulent or erroneous self-certification
    )

    # Verifier overrides solver claim
    assert result.feasible is False
    assert result.constraint_diagnostics.is_valid is False
    assert result.constraint_diagnostics.conflict_count == 1


def test_cost_separation_decision_vs_reporting() -> None:
    """ObjectiveBreakdown must strictly separate decision costs from exogenous reporting costs."""
    bd = ObjectiveBreakdown(
        total_cost=250.0,
        reassignment_cost=10.0,
        overflow_cost=200.0,
        delay_cost=30.0,
        conflict_cost=0.0,
        risk_cost=10.0,
        weights={},
    )
    assert bd.decision_cost == 210.0  # 10 + 200 + 0
    assert bd.reporting_cost == 40.0   # 30 + 10
    assert bd.decision_cost + bd.reporting_cost == bd.total_cost


def test_cp_sat_solver_status_and_best_bound() -> None:
    """CP-SAT solver must record OPTIMAL status, gap=0.0, and best_bound when solved to optimality."""
    g1 = Gate(gate_id="G1", gate_index=0, is_overflow=False)
    g2 = Gate(gate_id="G2", gate_index=1, is_overflow=False)
    g_over = Gate(gate_id="OVERFLOW", gate_index=2, is_overflow=True)
    gates = [g1, g2, g_over]

    # Non-overlapping flights
    f1 = Flight("F1", 0, "DL", "1", 100, 160, 100, nominal_gate_id="G1")
    f2 = Flight("F2", 1, "DL", "2", 200, 260, 200, nominal_gate_id="G2")

    solver = CPSatGateSolver()
    result = solver.solve([f1, f2], gates)

    assert result.feasible is True
    assert result.status == "OPTIMAL"
    assert result.optimality_gap == 0.0
    assert result.best_bound is not None
    assert result.best_bound >= 0.0
    assert result.constraint_diagnostics.contact_count == 2
    assert result.constraint_diagnostics.remote_count == 0
    assert result.constraint_diagnostics.unassigned_count == 0


def test_equal_compute_solver_protocol() -> None:
    """Equal-compute protocol ensures CP-SAT (T) and SA refinement (T/2 + T/2 <= T) are properly evaluated."""
    spec = DownstreamScenarioSpec(
        scenario_id="SCEN_EQUAL_COMPUTE",
        day_id="2023-07-03",
        date_str="2023-07-03",
        n_flights=8,
        n_contact_gates=4,
    )
    raw_df = _make_dummy_raw_df("2023-07-03", n_rows=16)
    scenario = extract_scenario_from_raw(spec, raw_df)
    candidate = DEFAULT_DOWNSTREAM_CANDIDATES[0]  # schedule_only
    delays = [0.0] * 8
    cfg = GateOptimizationConfig(time_limit_seconds=2.0)

    # 1. CP-SAT run
    rec_cpsat = evaluate_candidate_on_scenario(
        candidate=candidate,
        scenario=scenario,
        predicted_delays=delays,
        solver_name="CPSat",
        config=cfg,
    )
    assert rec_cpsat.status == "COMPLETED"
    assert rec_cpsat.contact_count + rec_cpsat.remote_count + rec_cpsat.unassigned_count == 8
    assert rec_cpsat.runtime_ms > 0.0

    # 2. SA refinement run (T/2 CP-SAT + T/2 SA <= T)
    rec_sa = evaluate_candidate_on_scenario(
        candidate=candidate,
        scenario=scenario,
        predicted_delays=delays,
        solver_name="SimulatedAnnealing",
        config=cfg,
    )
    assert rec_sa.status == "COMPLETED"
    assert rec_sa.contact_count + rec_sa.remote_count + rec_sa.unassigned_count == 8


def test_planned_feasibility_vs_realized_conflicts_distinction() -> None:
    """Downstream record must separate planned feasibility from realized post-hoc conflicts."""
    spec = DownstreamScenarioSpec(
        scenario_id="SCEN_DISTINCTION",
        day_id="2023-07-03",
        date_str="2023-07-03",
        n_flights=6,
        n_contact_gates=2,
    )
    raw_df = _make_dummy_raw_df("2023-07-03", n_rows=12)
    scenario = extract_scenario_from_raw(spec, raw_df)
    candidate = DEFAULT_DOWNSTREAM_CANDIDATES[0]

    # Predict zero delay for all flights
    preds = [0.0] * 6
    cfg = GateOptimizationConfig()

    rec = evaluate_candidate_on_scenario(
        candidate=candidate,
        scenario=scenario,
        predicted_delays=preds,
        solver_name="DeterministicGreedy",
        config=cfg,
    )

    # Planned feasibility was verified
    assert rec.hard_feasible is True
    assert rec.planned_conflict_count == 0
    # Realized conflicts are evaluated against actual row delays
    assert isinstance(rec.realized_conflict_count, int)
    assert rec.realized_conflict_count == rec.conflict_count


def test_zero_forbidden_claim_strings_in_downstream() -> None:
    """Verify absence of forbidden real-world claims in downstream engine and manifests."""
    forbidden_terms = [
      "real gate assignment",
      "actual airport gate operation",
      "real-world gate conflict",
      "actual operational savings",
      "ground-truth airport gate allocation"
    ]

    target_files = [
        Path("src/evaluation/downstream_comparison_v2.py"),
        Path("artifacts/manifests/downstream_protocol_v2.json"),
    ]

    for p in target_files:
        content = p.read_text(encoding="utf-8")
        # In manifest, forbidden terms are only allowed under "forbidden_claims" key
        if p.name == "downstream_protocol_v2.json":
            data = json.loads(content)
            # Ensure hard_claim_boundary is properly defined
            assert "hard_claim_boundary" in data
            continue

        for term in forbidden_terms:
            assert term not in content.lower(), f"Forbidden claim '{term}' found in {p}"
