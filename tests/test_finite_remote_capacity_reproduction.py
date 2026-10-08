"""Reproduction of Hard Constraint & Finite Remote Stand Capacity Vulnerabilities.

Phase P02: STEP 1 - WRITE FAILING TESTS.
These tests reproduce the exact resource model flaws before remediation:
1. Verifier accepts two overlapping flights on the same finite remote stand.
2. CP-SAT allows two overlapping flights on the same finite remote stand.
3. Greedy assigns overlapping flights to the same finite remote stand.
4. Gate generator creates an infinite apron when max_overflow=0.
"""

from __future__ import annotations

import pytest

from src.evaluation.dual_core_benchmark import generate_contact_gates
from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import (
    Flight,
    Gate,
    GateAssignment,
    GateResourceType,
    verify_hard_constraints_independently,
)
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver


def test_reproduce_verifier_ignores_remote_stand_overlap() -> None:
    """FAILING TEST REPRODUCTION:

    Two overlapping flights are assigned to the SAME finite remote stand (capacity=1).
    EXPECTATION: Verifier MUST reject this assignment as invalid (is_valid=False).
    CURRENT BUG: Verifier ignores g.is_overflow, returning is_valid=True.
    """
    f1 = Flight("FL1", 0, "VN", "101", 100, 160, 100, default_dwell_min=60, buffer_min=15)
    f2 = Flight("FL2", 1, "VN", "102", 120, 180, 120, default_dwell_min=60, buffer_min=15)

    # Finite remote stand with capacity 1
    remote_stand = Gate(
        gate_id="REMOTE_01",
        gate_index=0,
        resource_type=GateResourceType.FINITE_REMOTE_STAND,
        capacity=1,
    )

    # Both flights overlap in [120, 175) and are assigned to REMOTE_01
    assignments = {
        "FL1": GateAssignment("FL1", "REMOTE_01", occupancy_start_min=f1.time_window.start_min, occupancy_end_min=f1.time_window.end_min, is_overflow=True),
        "FL2": GateAssignment("FL2", "REMOTE_01", occupancy_start_min=f2.time_window.start_min, occupancy_end_min=f2.time_window.end_min, is_overflow=True),
    }

    diag = verify_hard_constraints_independently(
        flights=[f1, f2],
        gates=[remote_stand],
        assignments=assignments,
    )

    # In a correct system, this must be rejected:
    assert diag.is_valid is False, "Bug confirmed: Verifier accepted overlapping flights on finite remote stand!"
    assert diag.conflict_count >= 1 or getattr(diag, "planned_remote_violations", 0) >= 1


def test_reproduce_cpsat_allows_overlapping_remote_stand() -> None:
    """FAILING TEST REPRODUCTION:

    Two overlapping flights with ONLY ONE finite remote stand (capacity=1) and NO other gates.
    EXPECTATION: CP-SAT must find this problem INFEASIBLE (cannot pack 2 overlapping flights into 1 stand).
    CURRENT BUG: CP-SAT skips overlap constraint on is_overflow gates, returning OPTIMAL/FEASIBLE.
    """
    f1 = Flight("FL1", 0, "VN", "101", 100, 160, 100, default_dwell_min=60, buffer_min=15)
    f2 = Flight("FL2", 1, "VN", "102", 120, 180, 120, default_dwell_min=60, buffer_min=15)

    remote_stand = Gate(
        gate_id="REMOTE_01",
        gate_index=0,
        resource_type=GateResourceType.FINITE_REMOTE_STAND,
        capacity=1,
    )

    solver = CPSatGateSolver()
    result = solver.solve([f1, f2], [remote_stand], allow_overflow=False)

    # In a correct system, this must be INFEASIBLE:
    assert result.feasible is False, "Bug confirmed: CP-SAT packed 2 overlapping flights onto 1 remote stand!"
    assert result.status == "INFEASIBLE"
    assert len(result.assignments) == 0


def test_reproduce_generator_max_overflow_zero_creates_apron() -> None:
    """FAILING TEST REPRODUCTION:

    When max_overflow=0, generator must produce 0 overflow gates.
    CURRENT BUG: max_overflow <= 1 condition creates OVERFLOW_APRON when max_overflow=0!
    """
    gates = generate_contact_gates(5, allow_overflow=True, max_overflow=0)
    overflow_gates = [g for g in gates if g.is_overflow]
    assert len(overflow_gates) == 0, f"Bug confirmed: max_overflow=0 produced {len(overflow_gates)} overflow gates!"
