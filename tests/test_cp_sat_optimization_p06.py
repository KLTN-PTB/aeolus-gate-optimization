"""Comprehensive Verification Test Suite for Phase P06: CP-SAT Optimization & Scalability.

Protocol: docs/remediation/06_cp_sat_scalability_report.md
Audited & Hardened: Phase P06 Independent Verification Protocol

Verifies all required specifications:
- CP01: Exhaustive oracle parity (canonical & randomized small instances)
- CP02: Sparse candidate set correctness
- CP03: Exactly-one assignment
- CP04: Contact no-overlap
- CP05: Finite remote capacity (Cap 1 overlap/non-overlap, Cap 2 concurrent/exceeded)
- CP06: Gate compatibility
- CP07: Gate availability windows
- CP08: Infeasible case handling
- CP09: Solver status & incumbent handling (OPTIMAL, FEASIBLE, INFEASIBLE, UNKNOWN)
- CP10: Warm-start validation
- CP11: Model objective/evaluator parity
- CP12: Integer scaling boundaries
- CP13: Zero eligible gate
- CP14: Cross-midnight occupancy
- CP15: Adjacent intervals
- CP16: Large overlap clique
- CP17: No-overlap sparse scenario
- CP18: Symmetry-breaking design policy (NOT_APPLICABLE / NOT_IMPLEMENTED by design)
- CP19: Deadline enforcement (construction wall-clock budget exceeded)
- CP20: Memory budget monitoring behavior (Process RSS vs Python heap)
- CP21: Fallback provenance forced without conditional assertions
- CP22: No false OPTIMAL under fallback
- CP23: Small deterministic reproducibility
- CP24: Full regression against validated baseline
"""

from __future__ import annotations

import math
import os
from dataclasses import replace
from unittest.mock import patch

import numpy as np
import psutil
import pytest
import tracemalloc
from ortools.sat.python import cp_model

from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import (
    Flight,
    FlightTimeWindow,
    Gate,
    GateAssignment,
    GateResourceType,
    SolverStatus,
    TerminationReason,
    verify_hard_constraints_independently,
)
from src.optimization.evaluation import evaluate_gate_assignment
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
from src.optimization.solvers.exhaustive_oracle import solve_exhaustive_oracle
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver


# =============================================================================
# FIXTURES & CANONICAL DATA
# =============================================================================

@pytest.fixture
def small_oracle_problem() -> tuple[list[Flight], list[Gate]]:
    """Small 4-flight, 3-gate problem suitable for exhaustive enumeration."""
    gates = [
        Gate(gate_id="G1", gate_index=0, resource_type=GateResourceType.CONTACT_GATE, capacity=1),
        Gate(gate_id="G2", gate_index=1, resource_type=GateResourceType.CONTACT_GATE, capacity=1),
        Gate(gate_id="REMOTE_01", gate_index=2, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=1),
        Gate(gate_id="APRON", gate_index=3, resource_type=GateResourceType.UNBOUNDED_OVERFLOW_APRON, capacity=math.inf, is_overflow=True),
    ]
    flights = [
        Flight(
            flight_id="F1",
            flight_index=0,
            carrier="DL",
            flight_number="101",
            scheduled_arrival_min=100,
            scheduled_departure_min=160,
            predicted_arrival_min=100,
            nominal_gate_id="G1",
        ),
        Flight(
            flight_id="F2",
            flight_index=1,
            carrier="DL",
            flight_number="102",
            scheduled_arrival_min=120,
            scheduled_departure_min=180,
            predicted_arrival_min=120,
            nominal_gate_id="G1",
        ),
        Flight(
            flight_id="F3",
            flight_index=2,
            carrier="AA",
            flight_number="103",
            scheduled_arrival_min=200,
            scheduled_departure_min=260,
            predicted_arrival_min=200,
            nominal_gate_id="G2",
        ),
        Flight(
            flight_id="F4",
            flight_index=3,
            carrier="AA",
            flight_number="104",
            scheduled_arrival_min=220,
            scheduled_departure_min=280,
            predicted_arrival_min=220,
            nominal_gate_id="G2",
        ),
    ]
    return flights, gates


CANONICAL_PARITY_CASES = [
    # Case 1: tight overlap feasible
    (
        "tight_overlap_feasible",
        [
            Flight("F1", 0, "VN", "101", 100, 160, 45, "G1", 100, 160),
            Flight("F2", 1, "VN", "102", 120, 180, 45, "G1", 120, 180),
            Flight("F3", 2, "VN", "103", 200, 260, 45, "G2", 200, 260),
        ],
        [
            Gate("G1", 0, is_overflow=False, resource_type=GateResourceType.CONTACT_GATE, capacity=1),
            Gate("G2", 1, is_overflow=False, resource_type=GateResourceType.CONTACT_GATE, capacity=1),
        ],
        True,
    ),
    # Case 2: overlap infeasible without overflow
    (
        "overlap_infeasible_without_overflow",
        [
            Flight("F1", 0, "VN", "101", 100, 160, 45, "G1", 100, 160),
            Flight("F2", 1, "VN", "102", 120, 180, 45, "G1", 120, 180),
        ],
        [
            Gate("G1", 0, is_overflow=False, resource_type=GateResourceType.CONTACT_GATE, capacity=1),
        ],
        False,
    ),
    # Case 3: contact plus finite remote
    (
        "contact_plus_finite_remote",
        [
            Flight("F1", 0, "VN", "101", 100, 160, 45, "G1", 100, 160),
            Flight("F2", 1, "VN", "102", 120, 180, 45, "G1", 120, 180),
            Flight("F3", 2, "VN", "103", 200, 260, 45, "G2", 200, 260),
        ],
        [
            Gate("G1", 0, is_overflow=False, resource_type=GateResourceType.CONTACT_GATE, capacity=1),
            Gate("R1", 1, is_overflow=True, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=1),
        ],
        True,
    ),
    # Case 4: carrier restricted multigate
    (
        "carrier_restricted_multigate",
        [
            Flight("F1", 0, "VN", "101", 100, 160, 45, "G1", 100, 160),
            Flight("F2", 1, "VJ", "102", 100, 160, 45, "G2", 100, 160),
            Flight("F3", 2, "QH", "103", 100, 160, 45, "G1", 100, 160),
            Flight("F4", 3, "VN", "104", 170, 230, 45, "G1", 170, 230),
        ],
        [
            Gate("G1", 0, is_overflow=False, resource_type=GateResourceType.CONTACT_GATE, capacity=1, allowed_carriers=["VN"]),
            Gate("G2", 1, is_overflow=False, resource_type=GateResourceType.CONTACT_GATE, capacity=1, allowed_carriers=["VJ"]),
            Gate("R1", 2, is_overflow=True, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=1),
        ],
        True,
    ),
    # Case 5: contact plus pooled remote (capacity=2)
    (
        "contact_plus_pooled_remote_cap2",
        [
            Flight("F1", 0, "VN", "101", 100, 160, 45, "G1", 100, 160),
            Flight("F2", 1, "VJ", "102", 100, 160, 45, "G2", 100, 160),
            Flight("F3", 2, "QH", "103", 100, 160, 45, "G1", 100, 160),
            Flight("F4", 3, "VN", "104", 170, 230, 45, "G1", 170, 230),
        ],
        [
            Gate("G1", 0, is_overflow=False, resource_type=GateResourceType.CONTACT_GATE, capacity=1),
            Gate("R_POOL", 1, is_overflow=True, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=2),
        ],
        True,
    ),
    # Case 6: cross-midnight overlap
    (
        "cross_midnight_overlap",
        [
            Flight("F1", 0, "VN", "101", 1400, 60, 45, "G1", 1400, 60),
            Flight("F2", 1, "VN", "102", 1420, 120, 45, "G2", 1420, 120),
            Flight("F3", 2, "VN", "103", 100, 200, 45, "G1", 100, 200),
        ],
        [
            Gate("G1", 0, is_overflow=False, resource_type=GateResourceType.CONTACT_GATE, capacity=1),
            Gate("G2", 1, is_overflow=False, resource_type=GateResourceType.CONTACT_GATE, capacity=1),
        ],
        True,
    ),
    # Case 7: 5 flights, 3 gates tight
    (
        "5flights_3gates_tight",
        [
            Flight("F1", 0, "VN", "101", 100, 150, 45, "G1", 100, 150),
            Flight("F2", 1, "VN", "102", 120, 170, 45, "G2", 120, 170),
            Flight("F3", 2, "VN", "103", 140, 190, 45, "G1", 140, 190),
            Flight("F4", 3, "VN", "104", 160, 210, 45, "G2", 160, 210),
            Flight("F5", 4, "VN", "105", 180, 230, 45, "G1", 180, 230),
        ],
        [
            Gate("G1", 0, is_overflow=False, resource_type=GateResourceType.CONTACT_GATE, capacity=1),
            Gate("G2", 1, is_overflow=False, resource_type=GateResourceType.CONTACT_GATE, capacity=1),
            Gate("R1", 2, is_overflow=True, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=1),
        ],
        True,
    ),
]


# =============================================================================
# CP01: EXHAUSTIVE COMBINATORIAL ORACLE PARITY
# =============================================================================

def test_cp01_exhaustive_oracle_parity(small_oracle_problem) -> None:
    """CP01: CP-SAT achieves exact mathematical objective and feasibility parity with exhaustive oracle."""
    flights, gates = small_oracle_problem
    cfg = GateOptimizationConfig(reassignment_weight=10.0, overflow_weight=200.0, scale_factor=100)

    # 1. Oracle ground-truth
    oracle_res = solve_exhaustive_oracle(flights, gates, config=cfg)
    assert oracle_res.is_feasible is True
    assert oracle_res.optimal_objective is not None

    # 2. CP-SAT Sparse Interval (Default)
    solver_interval = CPSatGateSolver(config=replace(cfg, cp_sat_formulation="sparse_interval"))
    res_interval = solver_interval.solve(flights, gates)
    assert res_interval.feasible is True
    assert res_interval.status == SolverStatus.OPTIMAL.value
    assert abs(res_interval.objective_value - oracle_res.optimal_objective) < 1e-4

    # 3. CP-SAT Sparse Pairwise
    solver_pairwise = CPSatGateSolver(config=replace(cfg, cp_sat_formulation="sparse_pairwise"))
    res_pairwise = solver_pairwise.solve(flights, gates)
    assert res_pairwise.feasible is True
    assert res_pairwise.status == SolverStatus.OPTIMAL.value
    assert abs(res_pairwise.objective_value - oracle_res.optimal_objective) < 1e-4


@pytest.mark.parametrize("case_name,flights,gates,allow_overflow", CANONICAL_PARITY_CASES)
def test_cp01_canonical_parity_scenarios(
    case_name: str, flights: list[Flight], gates: list[Gate], allow_overflow: bool
) -> None:
    """CP01 Parametrized: Evaluates all 7 canonical parity scenarios against combinatorial oracle."""
    cfg = GateOptimizationConfig(scale_factor=100, num_search_workers=1)
    oracle_res = solve_exhaustive_oracle(flights, gates, config=cfg, allow_overflow=allow_overflow)

    for form in ("sparse_interval", "sparse_pairwise"):
        solver = CPSatGateSolver(config=replace(cfg, cp_sat_formulation=form))
        sol_res = solver.solve(flights, gates, allow_overflow=allow_overflow)

        if oracle_res.is_feasible:
            assert sol_res.feasible is True, f"Failed on {case_name} with {form}"
            assert sol_res.status == SolverStatus.OPTIMAL.value
            assert abs(sol_res.objective_value - oracle_res.optimal_objective) < 1e-4
        else:
            assert sol_res.feasible is False, f"Expected infeasible on {case_name} with {form}"
            assert sol_res.status == SolverStatus.INFEASIBLE.value


@pytest.mark.parametrize("seed", [42, 101, 2026])
def test_cp01_randomized_small_instances(seed: int) -> None:
    """CP01 Randomized: Checks parity on randomly generated small topologies (3 flights, 2 gates).

    Note: Exhaustive oracle equivalence across tested finite instances confirms formulation
    correctness on those topologies, but is an empirical parity proof, not an inductive proof for arbitrary N.
    """
    rng = np.random.default_rng(seed)
    gates = [
        Gate("G1", 0, is_overflow=False, resource_type=GateResourceType.CONTACT_GATE, capacity=1),
        Gate("G2", 1, is_overflow=False, resource_type=GateResourceType.CONTACT_GATE, capacity=1),
    ]
    flights = []
    for i in range(3):
        start = int(rng.integers(100, 300))
        dur = int(rng.integers(40, 80))
        flights.append(
            Flight(
                flight_id=f"RF_{i}",
                flight_index=i,
                carrier="VN",
                flight_number=f"{100+i}",
                scheduled_arrival_min=start,
                scheduled_departure_min=start + dur,
                min_turnaround_min=45,
                nominal_gate_id="G1" if i == 0 else "G2",
                predicted_arrival_min=start,
            )
        )

    cfg = GateOptimizationConfig(scale_factor=100, num_search_workers=1)
    oracle_res = solve_exhaustive_oracle(flights, gates, config=cfg, allow_overflow=True)

    solver = CPSatGateSolver(config=replace(cfg, cp_sat_formulation="sparse_interval"))
    sol_res = solver.solve(flights, gates, allow_overflow=True)

    assert sol_res.feasible == oracle_res.is_feasible
    if oracle_res.is_feasible:
        assert sol_res.status == SolverStatus.OPTIMAL.value
        assert abs(sol_res.objective_value - oracle_res.optimal_objective) < 1e-4


# =============================================================================
# CP02 - CP04: BASIC CONSTRAINTS & SPARSE VARIABLES
# =============================================================================

def test_cp02_sparse_candidate_set_correctness() -> None:
    """CP02: Only eligible pairs receive decision variables; no valid candidate is omitted."""
    g1 = Gate(gate_id="G1", gate_index=0, allowed_carriers=frozenset({"DL"}))
    g2 = Gate(gate_id="G2", gate_index=1, allowed_carriers=frozenset({"AA"}))
    fl = Flight(
        flight_id="F1",
        flight_index=0,
        carrier="DL",
        flight_number="101",
        scheduled_arrival_min=100,
        scheduled_departure_min=160,
        predicted_arrival_min=100,
    )

    solver = CPSatGateSolver(config=GateOptimizationConfig(cp_sat_formulation="sparse_interval"))
    res = solver.solve([fl], [g1, g2], allow_overflow=False)
    assert res.feasible is True
    assert res.assignments["F1"].gate_id == "G1"
    assert res.solver_configuration["n_variables"] == 1


def test_cp03_exactly_one_assignment(small_oracle_problem) -> None:
    """CP03: Every flight receives exactly one gate assignment."""
    flights, gates = small_oracle_problem
    solver = CPSatGateSolver()
    res = solver.solve(flights, gates)
    assert res.feasible is True
    assert len(res.assignments) == len(flights)
    assigned_flight_ids = set(res.assignments.keys())
    expected_ids = {f.flight_id for f in flights}
    assert assigned_flight_ids == expected_ids


def test_cp04_contact_no_overlap() -> None:
    """CP04: Contact gates strictly prohibit overlapping flight occupancy intervals."""
    g_contact = Gate(gate_id="C01", gate_index=0, resource_type=GateResourceType.CONTACT_GATE, capacity=1)
    g_ovf = Gate(gate_id="OVF", gate_index=1, resource_type=GateResourceType.UNBOUNDED_OVERFLOW_APRON, is_overflow=True)
    f1 = Flight(flight_id="F1", flight_index=0, carrier="DL", flight_number="1", scheduled_arrival_min=100, scheduled_departure_min=160, predicted_arrival_min=100)
    f2 = Flight(flight_id="F2", flight_index=1, carrier="DL", flight_number="2", scheduled_arrival_min=120, scheduled_departure_min=180, predicted_arrival_min=120)

    solver = CPSatGateSolver()
    res = solver.solve([f1, f2], [g_contact, g_ovf])
    assert res.feasible is True
    gates_assigned = [res.assignments["F1"].gate_id, res.assignments["F2"].gate_id]
    assert not (gates_assigned[0] == "C01" and gates_assigned[1] == "C01")


# =============================================================================
# CP05: FINITE REMOTE CAPACITY
# =============================================================================

def test_cp05_remote_capacity_1_overlap_rejected() -> None:
    """CP05-1: Capacity 1 finite remote stand rejects two overlapping flights."""
    r_stand = Gate(gate_id="R1", gate_index=0, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=1)
    f1 = Flight(flight_id="F1", flight_index=0, carrier="DL", flight_number="1", scheduled_arrival_min=100, scheduled_departure_min=160, predicted_arrival_min=100, nominal_gate_id="R1")
    f2 = Flight(flight_id="F2", flight_index=1, carrier="DL", flight_number="2", scheduled_arrival_min=120, scheduled_departure_min=180, predicted_arrival_min=120, nominal_gate_id="R1")

    solver = CPSatGateSolver()
    res = solver.solve([f1, f2], [r_stand], allow_overflow=False)
    assert res.feasible is False
    assert res.status == SolverStatus.INFEASIBLE.value

    # Independent verifier must also verify violation if forcefully assigned
    forced_assignments = {
        "F1": GateAssignment(
            flight_id="F1",
            gate_id="R1",
            flight_index=0,
            gate_index=0,
            is_overflow=True,
            is_reassignment=False,
            occupancy_start_min=f1.occupancy_start_min,
            occupancy_end_min=f1.occupancy_end_min,
        ),
        "F2": GateAssignment(
            flight_id="F2",
            gate_id="R1",
            flight_index=1,
            gate_index=0,
            is_overflow=True,
            is_reassignment=False,
            occupancy_start_min=f2.occupancy_start_min,
            occupancy_end_min=f2.occupancy_end_min,
        ),
    }
    diag = verify_hard_constraints_independently([f1, f2], [r_stand], forced_assignments)
    assert diag.is_valid is False
    assert diag.planned_remote_violations > 0 or diag.hard_constraint_violations_count > 0


def test_cp05_remote_capacity_1_non_overlap_permitted() -> None:
    """CP05-2: Capacity 1 finite remote stand permits two non-overlapping flights."""
    r_stand = Gate(gate_id="R1", gate_index=0, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=1)
    # F1 occupies [100, 175). F2 occupies [200, 275) (no overlap)
    f1 = Flight(flight_id="F1", flight_index=0, carrier="DL", flight_number="1", scheduled_arrival_min=100, scheduled_departure_min=160, predicted_arrival_min=100, nominal_gate_id="R1", buffer_min=15)
    f2 = Flight(flight_id="F2", flight_index=1, carrier="DL", flight_number="2", scheduled_arrival_min=200, scheduled_departure_min=260, predicted_arrival_min=200, nominal_gate_id="R1", buffer_min=15)

    solver = CPSatGateSolver()
    res = solver.solve([f1, f2], [r_stand], allow_overflow=False)
    assert res.feasible is True
    assert res.status == SolverStatus.OPTIMAL.value
    assert res.assignments["F1"].gate_id == "R1"
    assert res.assignments["F2"].gate_id == "R1"

    diag = verify_hard_constraints_independently([f1, f2], [r_stand], res.assignments)
    assert diag.is_valid is True


def test_cp05_remote_capacity_2_concurrent_permitted() -> None:
    """CP05-3: Capacity 2 finite remote stand permits two concurrent flights."""
    r_stand = Gate(gate_id="R_POOL", gate_index=0, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=2)
    f1 = Flight(flight_id="F1", flight_index=0, carrier="DL", flight_number="1", scheduled_arrival_min=100, scheduled_departure_min=160, predicted_arrival_min=100, nominal_gate_id="R_POOL")
    f2 = Flight(flight_id="F2", flight_index=1, carrier="DL", flight_number="2", scheduled_arrival_min=100, scheduled_departure_min=160, predicted_arrival_min=100, nominal_gate_id="R_POOL")

    solver = CPSatGateSolver()
    res = solver.solve([f1, f2], [r_stand], allow_overflow=False)
    assert res.feasible is True
    assert res.status == SolverStatus.OPTIMAL.value

    diag = verify_hard_constraints_independently([f1, f2], [r_stand], res.assignments)
    assert diag.is_valid is True
    assert diag.max_concurrent_remote_usage == 2


def test_cp05_remote_capacity_2_three_concurrent_rejected() -> None:
    """CP05-4: Capacity 2 finite remote stand rejects three concurrent flights without other resources."""
    r_stand = Gate(gate_id="R_POOL", gate_index=0, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=2)
    f1 = Flight(flight_id="F1", flight_index=0, carrier="DL", flight_number="1", scheduled_arrival_min=100, scheduled_departure_min=160, predicted_arrival_min=100, nominal_gate_id="R_POOL")
    f2 = Flight(flight_id="F2", flight_index=1, carrier="DL", flight_number="2", scheduled_arrival_min=100, scheduled_departure_min=160, predicted_arrival_min=100, nominal_gate_id="R_POOL")
    f3 = Flight(flight_id="F3", flight_index=2, carrier="DL", flight_number="3", scheduled_arrival_min=100, scheduled_departure_min=160, predicted_arrival_min=100, nominal_gate_id="R_POOL")

    solver = CPSatGateSolver()
    res = solver.solve([f1, f2, f3], [r_stand], allow_overflow=False)
    assert res.feasible is False
    assert res.status == SolverStatus.INFEASIBLE.value


# =============================================================================
# CP06 - CP08: COMPATIBILITY, AVAILABILITY, INFEASIBILITY
# =============================================================================

def test_cp06_gate_compatibility() -> None:
    """CP06: Carrier and aircraft type incompatibilities are strictly respected."""
    g_dl = Gate(gate_id="G_DL", gate_index=0, allowed_carriers=frozenset({"DL"}), allowed_aircraft_types=frozenset({"A320"}))
    f_aa = Flight(flight_id="F_AA", flight_index=0, carrier="AA", flight_number="1", scheduled_arrival_min=100, scheduled_departure_min=160, predicted_arrival_min=100, aircraft_type="A320")
    f_b737 = Flight(flight_id="F_B737", flight_index=1, carrier="DL", flight_number="2", scheduled_arrival_min=100, scheduled_departure_min=160, predicted_arrival_min=100, aircraft_type="B737")

    solver = CPSatGateSolver()
    res = solver.solve([f_aa], [g_dl], allow_overflow=False)
    assert res.feasible is False
    res2 = solver.solve([f_b737], [g_dl], allow_overflow=False)
    assert res2.feasible is False


def test_cp07_gate_availability_windows() -> None:
    """CP07: Gates unavailable during flight window are never assigned."""
    g_avail = Gate(gate_id="G1", gate_index=0, available_windows=((0, 100), (200, 300)))
    f = Flight(flight_id="F1", flight_index=0, carrier="DL", flight_number="1", scheduled_arrival_min=120, scheduled_departure_min=180, predicted_arrival_min=120)

    solver = CPSatGateSolver()
    res = solver.solve([f], [g_avail], allow_overflow=False)
    assert res.feasible is False
    assert res.status == SolverStatus.INFEASIBLE.value


def test_cp08_infeasible_case_handling() -> None:
    """CP08: Severe congestion with disallowed overflow returns certified INFEASIBLE."""
    g1 = Gate(gate_id="G1", gate_index=0, capacity=1)
    f1 = Flight(flight_id="F1", flight_index=0, carrier="DL", flight_number="1", scheduled_arrival_min=100, scheduled_departure_min=160, predicted_arrival_min=100)
    f2 = Flight(flight_id="F2", flight_index=1, carrier="DL", flight_number="2", scheduled_arrival_min=105, scheduled_departure_min=165, predicted_arrival_min=105)

    solver = CPSatGateSolver()
    res = solver.solve([f1, f2], [g1], allow_overflow=False)
    assert res.feasible is False
    assert res.status == SolverStatus.INFEASIBLE.value
    assert res.objective_value is None
    assert res.termination_reason == TerminationReason.PROVEN_INFEASIBLE


# =============================================================================
# CP09: SOLVER STATUS & INCUMBENT HANDLING
# =============================================================================

def test_cp09_solver_status_normalization_and_incumbent(small_oracle_problem) -> None:
    """CP09: Tests normalization across OPTIMAL, FEASIBLE, INFEASIBLE, UNKNOWN reproducibly."""
    flights, gates = small_oracle_problem

    # 1. OPTIMAL (real OR-Tools execution)
    solver_opt = CPSatGateSolver(config=GateOptimizationConfig(time_limit_seconds=10.0))
    res_opt = solver_opt.solve(flights, gates)
    assert res_opt.status == SolverStatus.OPTIMAL.value
    assert res_opt.optimality_proven is True
    assert res_opt.optimality_gap == 0.0

    # 2. INFEASIBLE (real OR-Tools execution)
    res_inf = solver_opt.solve(flights, [gates[0]], allow_overflow=False)
    assert res_inf.status == SolverStatus.INFEASIBLE.value
    assert res_inf.feasible is False
    assert res_inf.objective_value is None

    # 3. Controlled FEASIBLE (when search returns cp_model.FEASIBLE with incumbent)
    with patch.object(cp_model.CpSolver, "Solve", return_value=cp_model.FEASIBLE), \
         patch.object(cp_model.CpSolver, "ObjectiveValue", return_value=25000), \
         patch.object(cp_model.CpSolver, "BestObjectiveBound", return_value=20000), \
         patch.object(cp_model.CpSolver, "BooleanValue", side_effect=lambda var: True):
        # When mock solver returns FEASIBLE, it must normalize to SolverStatus.FEASIBLE
        res_feas = solver_opt.solve(flights[:1], [gates[0]])
        assert res_feas.status == SolverStatus.FEASIBLE.value
        assert res_feas.optimality_proven is False
        assert res_feas.optimality_gap is not None

    # 4. Controlled UNKNOWN (when search returns cp_model.UNKNOWN with no incumbent and no fallback)
    cfg_no_fb = GateOptimizationConfig(cp_sat_fallback_to_greedy=False)
    solver_no_fb = CPSatGateSolver(config=cfg_no_fb)
    with patch.object(cp_model.CpSolver, "Solve", return_value=cp_model.UNKNOWN):
        res_unk = solver_no_fb.solve(flights, gates)
        assert res_unk.status == SolverStatus.UNKNOWN.value
        assert res_unk.feasible is False
        assert res_unk.objective_value is None
        assert res_unk.termination_reason == TerminationReason.TIME_LIMIT


# =============================================================================
# CP10 - CP17: PERFORMANCE, NUMERICS, CORNER CASES
# =============================================================================

def test_cp10_warm_start_validation(small_oracle_problem) -> None:
    """CP10: Warm-start hints from Greedy are validated, and provenance is tracked."""
    flights, gates = small_oracle_problem
    cfg = GateOptimizationConfig(cp_sat_use_warm_start=True)
    solver = CPSatGateSolver(config=cfg)
    res = solver.solve(flights, gates)
    assert res.feasible is True
    assert res.solver_configuration["warm_start_used"] is True
    assert res.solver_configuration["warm_start_time_ms"] > 0.0


def test_cp11_model_objective_evaluator_parity(small_oracle_problem) -> None:
    """CP11: Model integer scaled objective matches independent evaluator within tolerance."""
    flights, gates = small_oracle_problem
    cfg = GateOptimizationConfig(reassignment_weight=15.0, overflow_weight=250.0, scale_factor=100)
    solver = CPSatGateSolver(config=cfg)
    res = solver.solve(flights, gates)
    assert res.feasible is True
    eval_res = evaluate_gate_assignment(res.assignments, flights, gates, config=cfg)
    assert abs(res.objective_value - eval_res.objective_value) < 1e-4


def test_cp12_integer_scaling_boundaries() -> None:
    """CP12: Different scale factors maintain proportional objective values."""
    g = Gate(gate_id="G1", gate_index=0)
    fl = Flight(flight_id="F1", flight_index=0, carrier="DL", flight_number="1", scheduled_arrival_min=100, scheduled_departure_min=160, predicted_arrival_min=100, nominal_gate_id="OTHER")

    cfg10 = GateOptimizationConfig(reassignment_weight=10.0, scale_factor=10)
    cfg1000 = GateOptimizationConfig(reassignment_weight=10.0, scale_factor=1000)

    res10 = CPSatGateSolver(config=cfg10).solve([fl], [g], allow_overflow=False)
    res1000 = CPSatGateSolver(config=cfg1000).solve([fl], [g], allow_overflow=False)

    assert abs(res10.objective_value - res1000.objective_value) < 1e-3


def test_cp13_zero_eligible_gate() -> None:
    """CP13: Flights with zero compatible gates fail fast with certified INFEASIBLE (OPT-A)."""
    g = Gate(gate_id="G1", gate_index=0, allowed_carriers=frozenset({"AA"}))
    fl = Flight(flight_id="F1", flight_index=0, carrier="DL", flight_number="1", scheduled_arrival_min=100, scheduled_departure_min=160, predicted_arrival_min=100)

    solver = CPSatGateSolver()
    res = solver.solve([fl], [g], allow_overflow=False)
    assert res.feasible is False
    assert res.status == SolverStatus.INFEASIBLE.value


def test_cp14_cross_midnight_occupancy() -> None:
    """CP14: Interval extending past midnight correctly prevents overlaps on linear timeline."""
    g = Gate(gate_id="G1", gate_index=0, capacity=1)
    # F1 arrives at 1420 (23:40 Day 0) and releases at 1495 (00:55 Day 1 past midnight)
    f1 = Flight(
        flight_id="F1",
        flight_index=0,
        carrier="DL",
        flight_number="1",
        scheduled_arrival_min=1420,
        scheduled_departure_min=1480,
        predicted_arrival_min=1420,
        buffer_min=15,
    )
    # F2 arrives at 1450 (00:10 Day 1), overlapping with F1 during [1450, 1495)
    f2 = Flight(
        flight_id="F2",
        flight_index=1,
        carrier="DL",
        flight_number="2",
        scheduled_arrival_min=1450,
        scheduled_departure_min=1510,
        predicted_arrival_min=1450,
        buffer_min=15,
    )
    solver = CPSatGateSolver()
    res = solver.solve([f1, f2], [g], allow_overflow=False)
    assert res.feasible is False
    assert res.status == SolverStatus.INFEASIBLE.value


def test_cp15_adjacent_intervals() -> None:
    """CP15: Consecutive intervals respecting buffer time are permitted on the same gate."""
    g = Gate(gate_id="G1", gate_index=0, capacity=1)
    f1 = Flight(
        flight_id="F1",
        flight_index=0,
        carrier="DL",
        flight_number="1",
        scheduled_arrival_min=100,
        scheduled_departure_min=185,
        predicted_arrival_min=100,
        buffer_min=15,  # 185 + 15 = 200
    )
    f2 = Flight(
        flight_id="F2",
        flight_index=1,
        carrier="DL",
        flight_number="2",
        scheduled_arrival_min=200,
        scheduled_departure_min=260,
        predicted_arrival_min=200,
    )
    solver = CPSatGateSolver()
    res = solver.solve([f1, f2], [g], allow_overflow=False)
    assert res.feasible is True
    assert res.assignments["F1"].gate_id == "G1"
    assert res.assignments["F2"].gate_id == "G1"


def test_cp16_large_overlap_clique() -> None:
    """CP16: Multiple concurrent overlapping flights on single gate are solved without error."""
    g = Gate(gate_id="G1", gate_index=0, capacity=1)
    g_ovf = Gate(gate_id="OVF", gate_index=1, is_overflow=True)
    flights = [
        Flight(flight_id=f"F{i}", flight_index=i, carrier="DL", flight_number=f"{i}", scheduled_arrival_min=100, scheduled_departure_min=160, predicted_arrival_min=100)
        for i in range(8)
    ]
    solver = CPSatGateSolver()
    res = solver.solve(flights, [g, g_ovf])
    assert res.feasible is True
    g1_count = sum(1 for a in res.assignments.values() if a.gate_id == "G1")
    assert g1_count == 1


def test_cp17_no_overlap_sparse_scenario() -> None:
    """CP17: Widely spaced flights all receive nominal gates with zero penalty."""
    gates = [Gate(gate_id=f"G{i}", gate_index=i) for i in range(3)]
    flights = [
        Flight(
            flight_id=f"F{i}",
            flight_index=i,
            carrier="DL",
            flight_number=f"{i}",
            scheduled_arrival_min=i * 300,
            scheduled_departure_min=i * 300 + 60,
            predicted_arrival_min=i * 300,
            nominal_gate_id=f"G{i}",
        )
        for i in range(3)
    ]
    solver = CPSatGateSolver()
    res = solver.solve(flights, gates, allow_overflow=False)
    assert res.feasible is True
    assert res.status == SolverStatus.OPTIMAL.value
    assert res.objective_value == 0.0


# =============================================================================
# CP18: SYMMETRY-BREAKING DESIGN POLICY
# =============================================================================

def test_cp18_symmetry_breaking_design_policy(small_oracle_problem) -> None:
    """CP18: Confirms symmetry-breaking design decision (NOT_APPLICABLE / NOT_IMPLEMENTED).

    Architectural Rationale:
    In airport gate assignment, physical gates exhibit heterogeneous carrier, aircraft, and topology
    constraints. Imposing lexicographic symmetry breaking across arbitrary gate indices would artificially
    cut feasible candidate solutions when gates have non-identical eligibility rules.
    Therefore, symmetry breaking is deliberately omitted in production CPSatGateSolver.
    This test verifies that all identical gates remain available in the candidate pool without artificial pruning.
    """
    flights, _ = small_oracle_problem
    # Two identical contact gates
    g1 = Gate("GATE_A", 0, resource_type=GateResourceType.CONTACT_GATE, capacity=1)
    g2 = Gate("GATE_B", 1, resource_type=GateResourceType.CONTACT_GATE, capacity=1)

    solver = CPSatGateSolver(config=GateOptimizationConfig(cp_sat_formulation="sparse_interval"))
    res = solver.solve(flights[:2], [g1, g2], allow_overflow=False)

    assert res.feasible is True
    # Both gates are valid candidate assignments in variable count
    assert res.solver_configuration["n_variables"] == 4  # 2 flights x 2 gates


# =============================================================================
# CP19: DEADLINE ENFORCEMENT & TIMING ACCURACY
# =============================================================================

def test_cp19_deadline_reporting(small_oracle_problem) -> None:
    """CP19: Model construction, search, validation, and total wall clock are accurately reported."""
    flights, gates = small_oracle_problem
    solver = CPSatGateSolver()
    res = solver.solve(flights, gates)
    cfg = res.solver_configuration
    assert "model_construction_ms" in cfg
    assert "search_time_ms" in cfg
    assert "validation_time_ms" in cfg
    assert "total_wall_clock_ms" in cfg
    assert cfg["model_construction_ms"] >= 0.0
    assert cfg["search_time_ms"] >= 0.0
    # Total wall clock must encompass construction and search within small timer granularity
    assert cfg["total_wall_clock_ms"] >= (cfg["model_construction_ms"] + cfg["search_time_ms"]) * 0.95


def test_cp19_wall_clock_budget_exceeded_in_build(small_oracle_problem) -> None:
    """CP19-2: Total wall-clock budget exceeded during construction triggers clean TIMEOUT_NO_SOLUTION."""
    flights, gates = small_oracle_problem
    # Set impossible 10 microsecond budget (0.00001s)
    cfg = GateOptimizationConfig(total_wall_clock_budget_seconds=0.00001)
    solver = CPSatGateSolver(config=cfg)
    res = solver.solve(flights, gates)

    assert res.status == SolverStatus.TIMEOUT_NO_SOLUTION.value
    assert res.feasible is False
    assert res.termination_reason == TerminationReason.TIME_LIMIT
    assert res.objective_value is None
    assert res.assignments == {}


# =============================================================================
# CP20: MEMORY BUDGET MONITORING
# =============================================================================

def test_cp20_memory_monitoring_behavior(small_oracle_problem) -> None:
    """CP20: Verifies memory instrumentation distinguishing Python heap and Process RSS.

    Methodology:
    - tracemalloc: Tracks Python-level object allocations (heap).
    - psutil.Process().memory_info().rss: Captures total process resident memory, including
      native C++ allocations made by OR-Tools pybind11 wrappers.
    - Production Note: Memory enforcement in Python without OS-level cgroups is monitoring-only.
    """
    flights, gates = small_oracle_problem
    proc = psutil.Process(os.getpid())

    tracemalloc.start()
    rss_before_mb = proc.memory_info().rss / (1024 * 1024)

    solver = CPSatGateSolver()
    res = solver.solve(flights, gates)

    _, peak_traced_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    rss_after_mb = proc.memory_info().rss / (1024 * 1024)

    traced_mb = peak_traced_bytes / (1024 * 1024)
    assert res.feasible is True
    assert traced_mb >= 0.0
    assert rss_after_mb >= 0.0
    # Sanity: small instance memory should be well within bounds
    assert traced_mb < 50.0  # Python heap for 4 flights is well under 50 MB


# =============================================================================
# CP21 & CP22: GREEDY FALLBACK & PROVENANCE
# =============================================================================

def test_cp21_fallback_provenance_forced() -> None:
    """CP21: Forced fallback to Greedy when CP-SAT returns UNKNOWN accurately logs provenance metadata."""
    g = Gate(gate_id="G1", gate_index=0, capacity=1)
    g_ovf = Gate(gate_id="OVF", gate_index=1, is_overflow=True)
    flights = [
        Flight(flight_id=f"F{i}", flight_index=i, carrier="DL", flight_number=f"{i}", scheduled_arrival_min=100 + i*10, scheduled_departure_min=160 + i*10, predicted_arrival_min=100 + i*10)
        for i in range(5)
    ]
    cfg = GateOptimizationConfig(
        cp_sat_fallback_to_greedy=True,
    )
    solver = CPSatGateSolver(config=cfg)

    # Force CpSolver.Solve to return UNKNOWN without relying on hardware timing
    with patch.object(cp_model.CpSolver, "Solve", return_value=cp_model.UNKNOWN):
        res = solver.solve(flights, [g, g_ovf])

    # Unconditional assertions (no if-statements!)
    assert res.feasible is True
    assert res.solver_configuration["fallback_used"] is True
    assert res.solver_configuration["initial_solution_source"] == "GREEDY_FALLBACK"
    assert res.status == SolverStatus.FEASIBLE.value
    assert res.optimality_proven is False
    assert res.constraint_diagnostics.is_valid is True
    assert len(res.assignments) == 5


def test_cp21_fallback_failure_when_unsolvable() -> None:
    """CP21-2: When CP-SAT returns UNKNOWN and fallback Greedy also fails, returns certified UNKNOWN."""
    # 2 overlapping flights on 1 gate, allow_overflow=False
    g1 = Gate("G1", 0, capacity=1)
    f1 = Flight("F1", 0, "DL", "1", 100, 160, 45, "G1", 100, 160)
    f2 = Flight("F2", 1, "DL", "2", 100, 160, 45, "G1", 100, 160)

    cfg = GateOptimizationConfig(cp_sat_fallback_to_greedy=True)
    solver = CPSatGateSolver(config=cfg)

    with patch.object(cp_model.CpSolver, "Solve", return_value=cp_model.UNKNOWN):
        res = solver.solve([f1, f2], [g1], allow_overflow=False)

    assert res.feasible is False
    assert res.status == SolverStatus.UNKNOWN.value
    assert res.assignments == {}


def test_cp22_no_false_optimal_under_fallback() -> None:
    """CP22: Heuristic fallback solutions are NEVER certified as OPTIMAL."""
    g = Gate(gate_id="G1", gate_index=0, capacity=1)
    g_ovf = Gate(gate_id="OVF", gate_index=1, is_overflow=True)
    flights = [
        Flight(flight_id=f"F{i}", flight_index=i, carrier="DL", flight_number=f"{i}", scheduled_arrival_min=100, scheduled_departure_min=160, predicted_arrival_min=100)
        for i in range(3)
    ]
    cfg = GateOptimizationConfig(cp_sat_fallback_to_greedy=True)
    solver = CPSatGateSolver(config=cfg)

    with patch.object(cp_model.CpSolver, "Solve", return_value=cp_model.UNKNOWN):
        res = solver.solve(flights, [g, g_ovf])

    assert res.status != SolverStatus.OPTIMAL.value
    assert res.status == SolverStatus.FEASIBLE.value
    assert res.optimality_proven is False


# =============================================================================
# CP23 & CP24: REPRODUCIBILITY & BASELINE REGRESSION
# =============================================================================

def test_cp23_small_deterministic_reproducibility(small_oracle_problem) -> None:
    """CP23: Repeated solves with same seed produce identical assignments and objective."""
    flights, gates = small_oracle_problem
    cfg = GateOptimizationConfig(random_seed=202601)
    solver1 = CPSatGateSolver(config=cfg)
    solver2 = CPSatGateSolver(config=cfg)
    res1 = solver1.solve(flights, gates)
    res2 = solver2.solve(flights, gates)
    assert res1.objective_value == res2.objective_value
    assert res1.assignments == res2.assignments


def test_cp24_full_regression_against_validated_baseline(small_oracle_problem) -> None:
    """CP24: Legacy formulation and optimized formulation produce identical optimal objectives."""
    flights, gates = small_oracle_problem
    cfg_legacy = GateOptimizationConfig(cp_sat_formulation="dense_pairwise", random_seed=202601)
    cfg_opt = GateOptimizationConfig(cp_sat_formulation="sparse_interval", random_seed=202601)

    solver_legacy = CPSatGateSolver(config=cfg_legacy)
    solver_opt = CPSatGateSolver(config=cfg_opt)

    res_legacy = solver_legacy.solve(flights, gates)
    res_opt = solver_opt.solve(flights, gates)

    assert res_legacy.feasible is True
    assert res_opt.feasible is True
    assert abs(res_legacy.objective_value - res_opt.objective_value) < 1e-4
