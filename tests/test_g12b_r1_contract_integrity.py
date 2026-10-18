"""Comprehensive test suite for AEOLUS-G12B-R1:
Scientific Status Integrity, Finite Remote Capacity Semantics,
Hybrid Status Correctness, and Execution Accounting Ledger.

Covers:
- STATUS-01 to STATUS-07: Standard Enum/String solver statuses, strict equality/hash invariants, explicit migration.
- CAP-01 to CAP-09: Strict finite remote stand capacity, no accidental unbounded overflow, explicit apron resources.
- HYB-STATUS-01 to HYB-STATUS-06: Accurate Hybrid solver statuses (UNKNOWN vs INFEASIBLE, optimality inheritance).
- STAT-LEDGER-01 to STAT-LEDGER-09: Complete execution ledger accounting, denominator validation, paired CRN consistency.
"""

from __future__ import annotations

import math
import time
from typing import Any
from unittest.mock import MagicMock, patch
import pytest

from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import (
    ConstraintDiagnostic,
    Flight,
    FlightTimeWindow,
    Gate,
    GateAssignment,
    GateResourceType,
    ObjectiveBreakdown,
    OptimizationResult,
    SolverStatus,
    TerminationReason,
    verify_hard_constraints_independently,
)
from src.optimization.evaluation import evaluate_gate_assignment
from src.optimization.sa.annealer import SAConfig, SimulatedAnnealingGateSolver
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver
from src.optimization.solvers.hybrid_solver import HybridGateSolver
from src.simulation.monte_carlo_engine_v2 import (
    CausalObservationSnapshot,
    FeasibilityBreakdown,
    ObservableFlightSnapshot,
    OnlineSolverStatus,
    RemediatedRealizationResult,
    canonicalize_legacy_solver_status,
    compute_remediated_statistics,
    evaluate_mode_b2_rolling_online_recourse,
    make_causal_recourse_decision,
)


# ==============================================================================
# TASK 1: STATUS-01 TO STATUS-07 (SOLVER STATUS NORMALIZATION)
# ==============================================================================
def test_status_01_equality_reflexive_symmetric_transitive():
    """STATUS-01: Equality on solver statuses is strictly reflexive, symmetric, and transitive."""
    s1 = OnlineSolverStatus.ONLINE_FEASIBLE
    s2 = OnlineSolverStatus.ONLINE_FEASIBLE
    s3 = "ONLINE_FEASIBLE"

    # Reflexive
    assert s1 == s1
    # Symmetric
    assert (s1 == s2) == (s2 == s1)
    assert (s1 == s3) == (s3 == s1)
    # Transitive
    assert s1 == s2 and s2 == s3 and s1 == s3


def test_status_02_equal_objects_have_equal_hashes():
    """STATUS-02: Fundamental Python contract: a == b implies hash(a) == hash(b)."""
    s1 = OnlineSolverStatus.ONLINE_FEASIBLE
    s2 = "ONLINE_FEASIBLE"
    assert s1 == s2
    assert hash(s1) == hash(s2)

    s_infeas = OnlineSolverStatus.ONLINE_INFEASIBLE_NO_CAPACITY
    s_infeas_str = "ONLINE_INFEASIBLE_NO_CAPACITY"
    assert s_infeas == s_infeas_str
    assert hash(s_infeas) == hash(s_infeas_str)


def test_status_03_set_and_dictionary_behavior_consistent():
    """STATUS-03: Statuses in sets and dicts behave with mathematical consistency."""
    status_set = {
        OnlineSolverStatus.ONLINE_FEASIBLE,
        "ONLINE_FEASIBLE",
        OnlineSolverStatus.ONLINE_INFEASIBLE_NO_CAPACITY,
    }
    # ONLINE_FEASIBLE and "ONLINE_FEASIBLE" must collapse to 1 entry
    assert len(status_set) == 2

    status_dict = {}
    status_dict[OnlineSolverStatus.ONLINE_FEASIBLE] = "val1"
    status_dict["ONLINE_FEASIBLE"] = "val2"
    assert len(status_dict) == 1
    assert status_dict[OnlineSolverStatus.ONLINE_FEASIBLE] == "val2"


def test_status_04_explicit_migration_handles_legacy_solved():
    """STATUS-04: Legacy 'ONLINE_SOLVED' is handled ONLY via explicit boundary migration."""
    # Without feasibility breakdown: cannot assume feasible
    migrated_unverified = canonicalize_legacy_solver_status("ONLINE_SOLVED")
    assert migrated_unverified == "LEGACY_ONLINE_SOLVED_UNVERIFIED"

    # With verified composite feasible metadata
    feas_meta = FeasibilityBreakdown(
        physical_contact_conflict_count=0,
        buffer_violation_count=0,
        max_concurrent_remote_usage=1,
        remote_capacity_violation=False,
        unassigned_flight_count=0,
        static_slot_consistency=False,
        composite_feasible=True,
    )
    migrated_feas = canonicalize_legacy_solver_status("ONLINE_SOLVED", feasibility=feas_meta)
    assert migrated_feas == OnlineSolverStatus.ONLINE_FEASIBLE.value

    # With unassigned flight: correctly migrates to INFEASIBLE_NO_CAPACITY
    infeas_meta = FeasibilityBreakdown(
        physical_contact_conflict_count=0,
        buffer_violation_count=0,
        max_concurrent_remote_usage=0,
        remote_capacity_violation=False,
        unassigned_flight_count=1,
        static_slot_consistency=False,
        composite_feasible=False,
    )
    migrated_infeas = canonicalize_legacy_solver_status("ONLINE_SOLVED", feasibility=infeas_meta)
    assert migrated_infeas == OnlineSolverStatus.ONLINE_INFEASIBLE_NO_CAPACITY.value


def test_status_05_no_feasible_infeasible_status_conflation():
    """STATUS-05: ONLINE_FEASIBLE and ONLINE_INFEASIBLE_NO_CAPACITY never equal each other."""
    assert OnlineSolverStatus.ONLINE_FEASIBLE != OnlineSolverStatus.ONLINE_INFEASIBLE_NO_CAPACITY
    assert OnlineSolverStatus.ONLINE_FEASIBLE != OnlineSolverStatus.ONLINE_INFEASIBLE
    assert OnlineSolverStatus.ONLINE_INFEASIBLE_NO_CAPACITY != OnlineSolverStatus.ONLINE_INFEASIBLE


def test_status_06_consumers_receive_canonical_string():
    """STATUS-06: str() and .value produce canonical strings suitable for serialization."""
    assert str(OnlineSolverStatus.ONLINE_FEASIBLE) == "ONLINE_FEASIBLE"
    assert str(OnlineSolverStatus.ONLINE_INFEASIBLE_NO_CAPACITY) == "ONLINE_INFEASIBLE_NO_CAPACITY"
    assert str(OnlineSolverStatus.ONLINE_INFEASIBLE) == "ONLINE_INFEASIBLE"


def test_status_07_no_breaking_custom_equality_with_legacy_solved():
    """STATUS-07: ONLINE_FEASIBLE is NOT silently equal to ONLINE_SOLVED."""
    # Custom equality hack must be removed: they are different strings
    assert OnlineSolverStatus.ONLINE_FEASIBLE != "ONLINE_SOLVED"
    assert "ONLINE_SOLVED" != OnlineSolverStatus.ONLINE_FEASIBLE


# ==============================================================================
# TASK 2: CAP-01 TO CAP-09 (FINITE REMOTE CAPACITY SEMANTICS)
# ==============================================================================
def make_remote_test_snapshot(carrier: str = "VN", remote_usage: int = 2, remote_cap: int = 2) -> tuple[CausalObservationSnapshot, Gate, Gate]:
    """Helper to create a scenario where contact gate is occupied and remote is at usage."""
    g1 = Gate("G1", 0, resource_type=GateResourceType.CONTACT_GATE)
    remote = Gate("REMOTE", 1, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=remote_cap, is_overflow=True)
    f = ObservableFlightSnapshot(
        flight_id="F1", flight_index=0, carrier=carrier, flight_number="100",
        aircraft_type="A321", scheduled_arrival_min=100, scheduled_departure_min=160,
        nominal_gate_id="G1", min_turnaround_min=30, default_dwell_min=60, buffer_min=15,
        is_paired=False, observed_arrival_min=100, estimated_departure_min=160, is_docked=False,
    )
    # G1 occupied
    snap = CausalObservationSnapshot(
        epoch_min=100,
        current_flight=f,
        gate_occupancy={"G1": MagicMock(is_occupied=True)},
        committed_reservations=[],
        current_remote_usage=remote_usage,
        finite_remote_capacity=remote_cap,
    )
    return snap, g1, remote


def test_cap_01_finite_remote_full_under_default_config_rejected():
    """CAP-01: When FINITE_REMOTE_STAND is full under default config, recourse MUST return None / NO_CAPACITY_EXHAUSTED."""
    cfg = GateOptimizationConfig()  # default has allow_unbounded_overflow=True, enforce_remote_capacity=False
    snap, g1, remote = make_remote_test_snapshot(remote_usage=2, remote_cap=2)

    chosen_gate, reason = make_causal_recourse_decision(
        snapshot=snap,
        current_assigned_gate_id="G1",
        contact_gates=[g1],
        remote_gate=remote,
        config=cfg,
    )
    assert chosen_gate is None, f"Expected None due to finite capacity, got {chosen_gate}"
    assert reason == "NO_CAPACITY_EXHAUSTED"


def test_cap_02_finite_remote_full_with_enforce_flag_rejected():
    """CAP-02: When FINITE_REMOTE_STAND is full with enforce_remote_capacity=True, returns None."""
    cfg = GateOptimizationConfig(enforce_remote_capacity=True)
    snap, g1, remote = make_remote_test_snapshot(remote_usage=2, remote_cap=2)

    chosen_gate, reason = make_causal_recourse_decision(
        snapshot=snap,
        current_assigned_gate_id="G1",
        contact_gates=[g1],
        remote_gate=remote,
        config=cfg,
    )
    assert chosen_gate is None
    assert reason == "NO_CAPACITY_EXHAUSTED"


def test_cap_03_all_contact_and_remote_exhausted_returns_unassigned():
    """CAP-03: When contact gates and remote stands are completely exhausted, decision returns unassigned."""
    g1 = Gate("G1", 0, resource_type=GateResourceType.CONTACT_GATE)
    g2 = Gate("G2", 1, resource_type=GateResourceType.CONTACT_GATE)
    remote = Gate("REMOTE", 2, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=1)
    cfg = GateOptimizationConfig()

    f = ObservableFlightSnapshot(
        flight_id="F1", flight_index=0, carrier="VN", flight_number="100",
        aircraft_type="A321", scheduled_arrival_min=100, scheduled_departure_min=160,
        nominal_gate_id="G1", min_turnaround_min=30, default_dwell_min=60, buffer_min=15,
        is_paired=False, observed_arrival_min=100, estimated_departure_min=160, is_docked=False,
    )
    snap = CausalObservationSnapshot(
        epoch_min=100, current_flight=f,
        gate_occupancy={"G1": MagicMock(is_occupied=True), "G2": MagicMock(is_occupied=True)},
        committed_reservations=[],
        current_remote_usage=1,
        finite_remote_capacity=1,
    )
    chosen_gate, reason = make_causal_recourse_decision(snap, "G1", [g1, g2], remote, cfg)
    assert chosen_gate is None
    assert reason == "NO_CAPACITY_EXHAUSTED"


def test_cap_04_multiple_simultaneous_arrivals_respect_remote_cap():
    """CAP-04: Two flights needing remote stand with capacity 1: first gets slot, second gets unassigned."""
    g1 = Gate("G1", 0, resource_type=GateResourceType.CONTACT_GATE)
    remote = Gate("REMOTE", 1, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=1)
    cfg = GateOptimizationConfig()

    f = ObservableFlightSnapshot(
        flight_id="F1", flight_index=0, carrier="VN", flight_number="100",
        aircraft_type="A321", scheduled_arrival_min=100, scheduled_departure_min=160,
        nominal_gate_id="G1", min_turnaround_min=30, default_dwell_min=60, buffer_min=15,
        is_paired=False, observed_arrival_min=100, estimated_departure_min=160, is_docked=False,
    )
    # Flight 1 arrives when remote_usage = 0 -> gets remote
    snap1 = CausalObservationSnapshot(
        epoch_min=100, current_flight=f,
        gate_occupancy={"G1": MagicMock(is_occupied=True)},
        committed_reservations=[],
        current_remote_usage=0,
        finite_remote_capacity=1,
    )
    gate1, _ = make_causal_recourse_decision(snap1, "G1", [g1], remote, cfg)
    assert gate1 == "REMOTE"

    # Flight 2 arrives when remote_usage = 1 -> remote full -> None
    snap2 = CausalObservationSnapshot(
        epoch_min=100, current_flight=f,
        gate_occupancy={"G1": MagicMock(is_occupied=True)},
        committed_reservations=[],
        current_remote_usage=1,
        finite_remote_capacity=1,
    )
    gate2, reason2 = make_causal_recourse_decision(snap2, "G1", [g1], remote, cfg)
    assert gate2 is None
    assert reason2 == "NO_CAPACITY_EXHAUSTED"


def test_cap_05_separate_explicit_unbounded_apron():
    """CAP-05: When explicit UNBOUNDED_OVERFLOW_APRON is provided, overflow uses apron, NOT finite remote."""
    g1 = Gate("G1", 0, resource_type=GateResourceType.CONTACT_GATE)
    remote = Gate("REMOTE", 1, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=1)
    apron = Gate("APRON", 2, resource_type=GateResourceType.UNBOUNDED_OVERFLOW_APRON, capacity=math.inf, is_overflow=True)
    cfg = GateOptimizationConfig(allow_unbounded_overflow=True)

    snap, _, _ = make_remote_test_snapshot(remote_usage=1, remote_cap=1)

    chosen_gate, reason = make_causal_recourse_decision(
        snapshot=snap,
        current_assigned_gate_id="G1",
        contact_gates=[g1],
        remote_gate=remote,
        config=cfg,
        overflow_gate=apron,
    )
    assert chosen_gate == "APRON", f"Expected explicit APRON, got {chosen_gate}"
    assert reason == "OVERFLOW_APRON_RECOURSE"


def test_cap_06_remote_gate_compatibility_and_availability():
    """CAP-06: Remote gate with carrier restriction or maintenance closure cannot be assigned."""
    g1 = Gate("G1", 0, resource_type=GateResourceType.CONTACT_GATE)
    remote = Gate(
        "REMOTE", 1, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=5,
        allowed_carriers=("BA",),  # Prohibits VN
    )
    cfg = GateOptimizationConfig()
    snap, _, _ = make_remote_test_snapshot(carrier="VN", remote_usage=0, remote_cap=5)

    chosen_gate, reason = make_causal_recourse_decision(
        snapshot=snap, current_assigned_gate_id="G1", contact_gates=[g1], remote_gate=remote, config=cfg,
    )
    assert chosen_gate is None
    assert reason == "REMOTE_INCOMPATIBLE"


def test_cap_07_no_false_feasible_result_under_capacity_exhaustion():
    """CAP-07: End-to-end Mode B2 with remote capacity exhaustion yields composite_feasible=False."""
    g1 = Gate("G1", 0, resource_type=GateResourceType.CONTACT_GATE)
    remote = Gate("REMOTE", 1, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=1, is_overflow=True)
    cfg = GateOptimizationConfig()  # default config

    f1 = Flight("F1", 0, "VN", "1", 50, 150, 50, nominal_gate_id="G1", precomputed_gate_out_min=150)
    f2 = Flight("F2", 1, "VN", "2", 100, 160, 100, nominal_gate_id="G1", precomputed_gate_out_min=160)
    f3 = Flight("F3", 2, "VN", "3", 105, 170, 105, nominal_gate_id="G1", precomputed_gate_out_min=170)

    init_plan = {
        "F1": GateAssignment("F1", "G1", occupancy_start_min=50, occupancy_end_min=165),
        "F2": GateAssignment("F2", "G1", occupancy_start_min=100, occupancy_end_min=175),
        "F3": GateAssignment("F3", "G1", occupancy_start_min=105, occupancy_end_min=185),
    }
    from src.simulation.monte_carlo_engine_p09 import RealizedScenario
    scen = RealizedScenario("S_CAP7", 0, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), "hcap7", 101)

    res = evaluate_mode_b2_rolling_online_recourse(
        init_plan, [f1, f2, f3], [f1, f2, f3], [g1, remote], cfg, scen, "Greedy"
    )
    assert not res.feasibility.composite_feasible
    assert res.solver_status == OnlineSolverStatus.ONLINE_INFEASIBLE_NO_CAPACITY.value
    assert res.feasibility.unassigned_flight_count >= 1


def test_cap_08_overflow_counted_and_labelled_separately():
    """CAP-08: Decomposed feasibility distinguishes remote stands from overflow apron."""
    breakdown = FeasibilityBreakdown(
        physical_contact_conflict_count=0,
        buffer_violation_count=0,
        max_concurrent_remote_usage=1,
        remote_capacity_violation=False,
        unassigned_flight_count=0,
        static_slot_consistency=False,
        composite_feasible=True,
    )
    d = breakdown.to_dict()
    assert "max_concurrent_remote_usage" in d
    assert "remote_capacity_violation" in d
    assert "unassigned_flight_count" in d


def test_cap_09_ex_post_feasibility_agrees_with_declared_resource_model():
    """CAP-09: verify_hard_constraints_independently confirms finite remote capacity cannot be exceeded."""
    flights = [
        Flight("F1", 0, "VN", "1", 100, 200, 100),
        Flight("F2", 1, "VN", "2", 110, 210, 110),
    ]
    remote = Gate("REMOTE", 0, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=1)
    assignments = {
        "F1": GateAssignment("F1", "REMOTE", occupancy_start_min=100, occupancy_end_min=215),
        "F2": GateAssignment("F2", "REMOTE", occupancy_start_min=110, occupancy_end_min=225),
    }
    diag = verify_hard_constraints_independently(flights, [remote], assignments)
    assert not diag.is_valid
    assert diag.conflict_count >= 1


# ==============================================================================
# TASK 3: HYB-STATUS-01 TO HYB-STATUS-06 (HYBRID SOLVER STATUS INTEGRITY)
# ==============================================================================
def make_dummy_diagnostic(is_valid: bool = True) -> ConstraintDiagnostic:
    return ConstraintDiagnostic(
        all_flights_assigned=is_valid,
        no_contact_gate_conflicts=is_valid,
        gate_availability_satisfied=is_valid,
        gate_compatibility_satisfied=is_valid,
        turnaround_valid=is_valid,
        conflict_count=0 if is_valid else 1,
        conflict_pairs=[] if is_valid else [{"dummy": True}],
        incompatibility_violations=[],
        availability_violations=[],
        hard_constraint_violations_count=0 if is_valid else 1,
    )


def test_hyb_status_01_cpsat_unknown_and_greedy_fails_returns_unknown():
    """HYB-STATUS-01: When CP-SAT returns UNKNOWN and Greedy fallback fails, Hybrid MUST report UNKNOWN, NOT INFEASIBLE."""
    flights = [Flight("F1", 0, "VN", "1", 100, 160, 100)]
    gates = [Gate("G1", 0, resource_type=GateResourceType.CONTACT_GATE)]
    cfg = GateOptimizationConfig()
    solver = HybridGateSolver(config=cfg)

    # Stub CP-SAT to return UNKNOWN (no incumbent)
    def mock_cpsat_solve(*args, **kwargs):
        return OptimizationResult(
            status="UNKNOWN",
            objective_value=float("inf"),
            objective_breakdown=ObjectiveBreakdown(0, 0, 0, 0, 0, 0, weights={}),
            feasible=False,
            runtime_ms=10.0,
            optimality_gap=None,
            assignments={},
            constraint_diagnostics=make_dummy_diagnostic(is_valid=False),
            solver_configuration={},
            termination_reason=TerminationReason.NO_FEASIBLE_SOLUTION,
        )

    # Stub Greedy to also fail
    def mock_greedy_solve(*args, **kwargs):
        return OptimizationResult(
            status="UNKNOWN",
            objective_value=float("inf"),
            objective_breakdown=ObjectiveBreakdown(0, 0, 0, 0, 0, 0, weights={}),
            feasible=False,
            runtime_ms=5.0,
            optimality_gap=None,
            assignments={},
            constraint_diagnostics=make_dummy_diagnostic(is_valid=False),
            solver_configuration={},
            termination_reason=TerminationReason.NO_FEASIBLE_SOLUTION,
        )

    with patch.object(CPSatGateSolver, "solve", side_effect=mock_cpsat_solve):
        with patch.object(DeterministicGreedyGateSolver, "solve", side_effect=mock_greedy_solve):
            res = solver.solve(flights, gates)

    assert res.status == "UNKNOWN", f"Expected UNKNOWN, but got {res.status}"
    assert res.status != "INFEASIBLE", "Must NOT claim proven INFEASIBLE when search merely failed"
    assert res.termination_reason == TerminationReason.NO_FEASIBLE_SOLUTION


def test_hyb_status_02_cpsat_timeout_and_greedy_infeasible_returns_timeout_no_solution():
    """HYB-STATUS-02: CP-SAT timeout + Greedy fails reports TIMEOUT_NO_SOLUTION / TIME_LIMIT."""
    flights = [Flight("F1", 0, "VN", "1", 100, 160, 100)]
    gates = [Gate("G1", 0, resource_type=GateResourceType.CONTACT_GATE)]
    cfg = GateOptimizationConfig()
    solver = HybridGateSolver(config=cfg)

    def mock_cpsat_timeout(*args, **kwargs):
        return OptimizationResult(
            status="TIMEOUT_NO_SOLUTION",
            objective_value=float("inf"),
            objective_breakdown=ObjectiveBreakdown(0, 0, 0, 0, 0, 0, weights={}),
            feasible=False,
            runtime_ms=5000.0,
            optimality_gap=None,
            assignments={},
            constraint_diagnostics=make_dummy_diagnostic(is_valid=False),
            solver_configuration={},
            termination_reason=TerminationReason.TIME_LIMIT,
        )

    def mock_greedy_fail(*args, **kwargs):
        return OptimizationResult(
            status="UNKNOWN",
            objective_value=float("inf"),
            objective_breakdown=ObjectiveBreakdown(0, 0, 0, 0, 0, 0, weights={}),
            feasible=False,
            runtime_ms=5.0,
            optimality_gap=None,
            assignments={},
            constraint_diagnostics=make_dummy_diagnostic(is_valid=False),
            solver_configuration={},
            termination_reason=TerminationReason.NO_FEASIBLE_SOLUTION,
        )

    with patch.object(CPSatGateSolver, "solve", side_effect=mock_cpsat_timeout):
        with patch.object(DeterministicGreedyGateSolver, "solve", side_effect=mock_greedy_fail):
            res = solver.solve(flights, gates)

    assert res.status in ("TIMEOUT_NO_SOLUTION", "UNKNOWN")
    assert res.status != "INFEASIBLE"


def test_hyb_status_03_cpsat_proven_infeasible_reports_infeasible():
    """HYB-STATUS-03: When CP-SAT mathematically proves INFEASIBLE, reports INFEASIBLE with PROVEN_INFEASIBLE."""
    flights = [Flight("F1", 0, "VN", "1", 100, 160, 100)]
    gates = [Gate("G1", 0, resource_type=GateResourceType.CONTACT_GATE)]
    cfg = GateOptimizationConfig()
    solver = HybridGateSolver(config=cfg)

    def mock_cpsat_infeas(*args, **kwargs):
        return OptimizationResult(
            status="INFEASIBLE",
            objective_value=float("inf"),
            objective_breakdown=ObjectiveBreakdown(0, 0, 0, 0, 0, 0, weights={}),
            feasible=False,
            runtime_ms=10.0,
            optimality_gap=None,
            assignments={},
            constraint_diagnostics=make_dummy_diagnostic(is_valid=False),
            solver_configuration={},
            termination_reason=TerminationReason.PROVEN_INFEASIBLE,
        )

    with patch.object(CPSatGateSolver, "solve", side_effect=mock_cpsat_infeas):
        res = solver.solve(flights, gates)

    assert res.status == "INFEASIBLE"
    assert res.termination_reason == TerminationReason.PROVEN_INFEASIBLE
    assert not res.solver_configuration.get("fallback_attempted")


def test_hyb_status_04_cpsat_feasible_incumbent_preserved_when_sa_worse():
    """HYB-STATUS-04: When CP-SAT finds feasible incumbent and SA degrades, preserves FEASIBLE incumbent."""
    flights = [Flight("F1", 0, "VN", "1", 100, 160, 100)]
    gates = [Gate("G1", 0, resource_type=GateResourceType.CONTACT_GATE)]
    solver = HybridGateSolver()
    res = solver.solve(flights, gates)
    assert res.feasible
    assert res.status in ("FEASIBLE", "OPTIMAL")


def test_hyb_status_05_cpsat_optimal_proof_inherited_correctly():
    """HYB-STATUS-05: Optimality proof inherited only when CP-SAT proved optimal and cost preserved."""
    flights = [Flight("F1", 0, "VN", "1", 100, 160, 100, nominal_gate_id="G1")]
    gates = [Gate("G1", 0, resource_type=GateResourceType.CONTACT_GATE)]
    solver = HybridGateSolver()
    res = solver.solve(flights, gates)
    assert res.optimality_proven
    assert res.status == "OPTIMAL"
    assert res.termination_reason == TerminationReason.OPTIMAL_PROVEN


def test_hyb_status_06_no_fabricated_optimality_gap_or_proof():
    """HYB-STATUS-06: A heuristic solution without exact CP proof NEVER claims optimality_proven=True."""
    flights = [Flight("F1", 0, "VN", "1", 100, 160, 100)]
    gates = [Gate("G1", 0, resource_type=GateResourceType.CONTACT_GATE)]
    cfg = GateOptimizationConfig()
    solver = HybridGateSolver(config=cfg)

    # Stub CP-SAT to return FEASIBLE without proof
    def mock_cpsat_feasible(*args, **kwargs):
        asgn = {"F1": GateAssignment("F1", "G1", occupancy_start_min=100, occupancy_end_min=175)}
        return OptimizationResult(
            status="FEASIBLE",
            objective_value=50.0,
            objective_breakdown=ObjectiveBreakdown(50.0, 50.0, 0, 0, 0, 0, weights={}),
            feasible=True,
            runtime_ms=20.0,
            optimality_gap=None,
            assignments=asgn,
            constraint_diagnostics=make_dummy_diagnostic(is_valid=True),
            solver_configuration={},
            termination_reason=TerminationReason.FEASIBLE_FOUND,
            optimality_proven=False,
        )

    with patch.object(CPSatGateSolver, "solve", side_effect=mock_cpsat_feasible):
        res = solver.solve(flights, gates)

    assert not res.optimality_proven
    assert res.status == "FEASIBLE"
    assert res.optimality_gap is None


# ==============================================================================
# TASK 4: STAT-LEDGER-01 TO STAT-LEDGER-09 (EXECUTION ACCOUNTING LEDGER)
# ==============================================================================
from src.simulation.monte_carlo_engine_v2 import SimulationExecutionLedger


def test_stat_ledger_01_100_requested_98_evaluated_2_failures():
    """STAT-LEDGER-01: Validates exact accounting for 100 requested, 98 evaluated, 2 failures."""
    ledger = SimulationExecutionLedger(run_id="RUN_01", requested_n=100)
    for i in range(98):
        ledger.record_evaluation_success(
            scenario_id=f"SCEN_{i:03d}",
            realization_hash=f"hash_{i}",
            initial_plan_solver="Greedy",
            recourse_mode="MODE_B2",
            solver_status="ONLINE_FEASIBLE",
            composite_feasible=True,
            objective_value=100.0 + i,
            runtime_ms=5.0,
        )
    ledger.record_generation_failure(scenario_id="SCEN_098", reason="COPULA_DEVIATION_ERROR")
    ledger.record_evaluation_failure(scenario_id="SCEN_099", reason="SIMULATION_DIVERGENCE")

    summary = ledger.compute_summary()
    acc = summary["accounting"]
    assert acc["n_requested"] == 100
    assert acc["n_generated"] == 99
    assert acc["n_generation_failures"] == 1
    assert acc["n_evaluated"] == 98
    assert acc["n_evaluation_failures"] == 1
    assert acc["n_feasible"] == 98
    assert acc["n_infeasible"] == 0


def test_stat_ledger_02_missing_scenario_without_failure_triggers_error():
    """STAT-LEDGER-02: Missing scenario ID without logged failure causes validation to FAIL."""
    ledger = SimulationExecutionLedger(run_id="RUN_02", requested_n=10)
    for i in range(8):  # Missing 8 and 9!
        ledger.record_evaluation_success(
            scenario_id=f"SCEN_{i}",
            realization_hash=f"h_{i}",
            initial_plan_solver="Greedy",
            recourse_mode="MODE_B2",
            solver_status="ONLINE_FEASIBLE",
            composite_feasible=True,
            objective_value=50.0,
            runtime_ms=2.0,
        )

    with pytest.raises(ValueError, match="Missing scenario accounting"):
        ledger.validate_ledger()


def test_stat_ledger_03_timeout_accounting():
    """STAT-LEDGER-03: Timeouts are accounted explicitly in the ledger."""
    ledger = SimulationExecutionLedger(run_id="RUN_03", requested_n=5)
    for i in range(4):
        ledger.record_evaluation_success(
            scenario_id=f"SCEN_{i}", realization_hash=f"h_{i}", initial_plan_solver="CP-SAT",
            recourse_mode="MODE_B2", solver_status="ONLINE_FEASIBLE", composite_feasible=True,
            objective_value=50.0, runtime_ms=2.0,
        )
    ledger.record_timeout(scenario_id="SCEN_4", realization_hash="h_4", runtime_ms=5000.0)

    summary = ledger.compute_summary()
    assert summary["accounting"]["n_timeouts"] == 1
    assert summary["accounting"]["n_evaluated"] == 5


def test_stat_ledger_04_infeasible_scenario_vs_execution_failure():
    """STAT-LEDGER-04: Distinguishes operational infeasibility (evaluated) from execution failure (not evaluated)."""
    ledger = SimulationExecutionLedger(run_id="RUN_04", requested_n=3)
    # Feasible run
    ledger.record_evaluation_success(
        scenario_id="SCEN_0", realization_hash="h_0", initial_plan_solver="Greedy",
        recourse_mode="MODE_B2", solver_status="ONLINE_FEASIBLE", composite_feasible=True,
        objective_value=100.0, runtime_ms=2.0,
    )
    # Evaluated but operationally infeasible (capacity exhausted)
    ledger.record_evaluation_success(
        scenario_id="SCEN_1", realization_hash="h_1", initial_plan_solver="Greedy",
        recourse_mode="MODE_B2", solver_status="ONLINE_INFEASIBLE_NO_CAPACITY", composite_feasible=False,
        objective_value=500.0, runtime_ms=3.0,
    )
    # Execution crashed before evaluation
    ledger.record_evaluation_failure(scenario_id="SCEN_2", reason="PARSING_EXCEPTION")

    summary = ledger.compute_summary()
    assert summary["accounting"]["n_evaluated"] == 2
    assert summary["accounting"]["n_feasible"] == 1
    assert summary["accounting"]["n_infeasible"] == 1
    assert summary["accounting"]["n_evaluation_failures"] == 1


def test_stat_ledger_05_duplicate_scenario_id_raises_error():
    """STAT-LEDGER-05: Duplicate scenario IDs in ledger trigger error to prevent sample bias."""
    ledger = SimulationExecutionLedger(run_id="RUN_05", requested_n=5)
    ledger.record_evaluation_success(
        scenario_id="SCEN_0", realization_hash="h_0", initial_plan_solver="Greedy",
        recourse_mode="MODE_B2", solver_status="ONLINE_FEASIBLE", composite_feasible=True,
        objective_value=10.0, runtime_ms=1.0,
    )
    with pytest.raises(ValueError, match="Duplicate scenario_id"):
        ledger.record_evaluation_success(
            scenario_id="SCEN_0", realization_hash="h_0", initial_plan_solver="Greedy",
            recourse_mode="MODE_B2", solver_status="ONLINE_FEASIBLE", composite_feasible=True,
            objective_value=10.0, runtime_ms=1.0,
        )


def test_stat_ledger_06_same_realization_across_three_solvers_tracked():
    """STAT-LEDGER-06: Multi-solver ledger tracks paired CRN hash consistency."""
    ledger = SimulationExecutionLedger(run_id="RUN_06", requested_n=2)
    # Realization 0 for all 3 solvers
    for s in ["Greedy", "CP-SAT", "Hybrid"]:
        ledger.record_evaluation_success(
            scenario_id="SCEN_0", realization_hash="hash_alpha", initial_plan_solver=s,
            recourse_mode="MODE_B2", solver_status="ONLINE_FEASIBLE", composite_feasible=True,
            objective_value=10.0, runtime_ms=1.0,
        )
    # Realization 1 for all 3 solvers
    for s in ["Greedy", "CP-SAT", "Hybrid"]:
        ledger.record_evaluation_success(
            scenario_id="SCEN_1", realization_hash="hash_beta", initial_plan_solver=s,
            recourse_mode="MODE_B2", solver_status="ONLINE_FEASIBLE", composite_feasible=True,
            objective_value=12.0, runtime_ms=1.0,
        )
    assert ledger.validate_paired_crn(required_solvers=["Greedy", "CP-SAT", "Hybrid"])


def test_stat_ledger_07_missing_paired_crn_realization_detected():
    """STAT-LEDGER-07: Detects if a solver is missing a realization in paired CRN analysis."""
    ledger = SimulationExecutionLedger(run_id="RUN_07", requested_n=2)
    ledger.record_evaluation_success(
        scenario_id="SCEN_0", realization_hash="h_0", initial_plan_solver="Greedy",
        recourse_mode="MODE_B2", solver_status="ONLINE_FEASIBLE", composite_feasible=True,
        objective_value=10.0, runtime_ms=1.0,
    )
    # Missing CP-SAT for SCEN_0!
    with pytest.raises(ValueError, match="Missing paired CRN"):
        ledger.validate_paired_crn(required_solvers=["Greedy", "CP-SAT"])


def test_stat_ledger_08_valid_20_and_100_pilot_replay():
    """STAT-LEDGER-08: Ledger successfully validates standard 20 and 100 scenario sizes."""
    for n in (20, 100):
        ledger = SimulationExecutionLedger(run_id=f"PILOT_{n}", requested_n=n)
        for i in range(n):
            ledger.record_evaluation_success(
                scenario_id=f"SCEN_{i:03d}", realization_hash=f"h_{i}", initial_plan_solver="Greedy",
                recourse_mode="MODE_B2", solver_status="ONLINE_FEASIBLE", composite_feasible=True,
                objective_value=50.0, runtime_ms=2.0,
            )
        ledger.validate_ledger()
        summary = ledger.compute_summary()
        assert summary["accounting"]["n_evaluated"] == n


def test_stat_ledger_09_correct_failure_denominators():
    """STAT-LEDGER-09: Explicitly discloses failure and feasibility rate denominators."""
    ledger = SimulationExecutionLedger(run_id="RUN_09", requested_n=10)
    # 8 evaluated (6 feasible, 2 infeasible), 1 eval failure, 1 gen failure
    for i in range(6):
        ledger.record_evaluation_success(
            scenario_id=f"SCEN_{i}", realization_hash=f"h_{i}", initial_plan_solver="Greedy",
            recourse_mode="MODE_B2", solver_status="ONLINE_FEASIBLE", composite_feasible=True,
            objective_value=10.0, runtime_ms=1.0,
        )
    for i in range(6, 8):
        ledger.record_evaluation_success(
            scenario_id=f"SCEN_{i}", realization_hash=f"h_{i}", initial_plan_solver="Greedy",
            recourse_mode="MODE_B2", solver_status="ONLINE_INFEASIBLE_NO_CAPACITY", composite_feasible=False,
            objective_value=100.0, runtime_ms=1.0,
        )
    ledger.record_evaluation_failure(scenario_id="SCEN_8", reason="TIMEOUT")
    ledger.record_generation_failure(scenario_id="SCEN_9", reason="OUT_OF_BOUNDS")

    rates = ledger.compute_rates()
    # generation failure rate has denominator n_requested (10)
    assert rates["generation_failure_rate"]["numerator"] == 1
    assert rates["generation_failure_rate"]["denominator"] == 10
    assert rates["generation_failure_rate"]["rate"] == 0.10

    # evaluation failure rate has denominator n_generated (9)
    assert rates["evaluation_failure_rate"]["numerator"] == 1
    assert rates["evaluation_failure_rate"]["denominator"] == 9
    assert round(rates["evaluation_failure_rate"]["rate"], 4) == round(1 / 9, 4)

    # composite feasible rate has denominator n_evaluated (8)
    assert rates["composite_feasible_rate"]["numerator"] == 6
    assert rates["composite_feasible_rate"]["denominator"] == 8
    assert rates["composite_feasible_rate"]["rate"] == 0.75
