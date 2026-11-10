"""Comprehensive Test Suite for Phase P02: Hard Constraint Correctness & Finite Remote Capacity.

Verifies all 24 formal specifications R01–R24 plus differential oracle tests:
- R01: Verifier detects overlap on FINITE_REMOTE_STAND with capacity=1.
- R02: Verifier detects exceeding K on pooled remote resource.
- R03: UNBOUNDED_OVERFLOW_APRON allows concurrency only when explicitly unbounded.
- R04: Greedy does not place 2 overlapping flights on same FINITE_REMOTE_STAND.
- R05: Greedy respects capacity K of pooled remote resource.
- R06: CP-SAT generates no-overlap constraint for all FINITE_REMOTE_STAND with capacity=1.
- R07: CP-SAT generates capacity <= K constraint for pooled remote resource.
- R08: Simulated Annealing treats 2 overlapping flights on finite remote stand as hard constraint violation.
- R09: SA neighborhood operator does not create/keep moves leading to overlap on finite remote stands.
- R10: Hybrid solver passes correct capacity semantics from CP-SAT to SA.
- R11: Hybrid incumbent is re-verified before transfer.
- R12: Generator max_overflow=0 produces no overflow stand/apron.
- R13: Generator max_overflow=K produces exactly K finite stands separately or 1 pooled resource.
- R14: No solver silently turns finite remote stand into unbounded apron when allow_unbounded_overflow=False.
- R15: Evaluation report clearly separates planned/realized violations for contact gate vs remote stand.
- R16: Diagnostic contains max_concurrent_remote_usage.
- R17: Reassignment cost calculated correctly for finite remote stand.
- R18: Overflow cost not mistakenly applied to contact gate and vice versa.
- R19: Time window with buffer_min applied uniformly.
- R20: Zero-capacity gate rejected by validation (ValueError).
- R21: Duplicate gate_id rejected by verifier (is_valid=False).
- R22: Negative capacity rejected by validation (ValueError).
- R23: Unknown resource type rejected by validation (ValueError).
- R24: Backward compatibility for legacy tests with unbounded apron.
- Oracle Differential Test: Verifies agreement across solvers on small canonical instances.
"""

from __future__ import annotations

import math
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
from src.optimization.evaluation import evaluate_gate_assignment
from src.optimization.sa import SAConfig, SimulatedAnnealingGateSolver
from src.optimization.sa.neighborhood import is_gate_feasible_for_flight, try_move_flight
from src.optimization.sa.state import create_initial_state
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver
from src.optimization.solvers.hybrid_solver import HybridGateSolver


def _make_flight(
    fid: str,
    idx: int,
    start: int,
    end: int,
    nominal: str | None = None,
    carrier: str = "VN",
) -> Flight:
    return Flight(
        flight_id=fid,
        flight_index=idx,
        carrier=carrier,
        flight_number=f"10{idx}",
        scheduled_arrival_min=start,
        scheduled_departure_min=end - 15,
        predicted_arrival_min=start,
        nominal_gate_id=nominal,
        min_turnaround_min=30,
        default_dwell_min=end - 15 - start,
        buffer_min=15,
    )


# ---------------------------------------------------------------------------
# R01: Verifier detects overlap on FINITE_REMOTE_STAND with capacity=1
# ---------------------------------------------------------------------------
def test_r01_verifier_detects_overlap_on_finite_remote_stand() -> None:
    f1 = _make_flight("FL1", 0, 100, 160)
    f2 = _make_flight("FL2", 1, 120, 180)
    stand = Gate("REMOTE_01", 0, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=1)

    assignments = {
        "FL1": GateAssignment("FL1", "REMOTE_01", 0, 0, True, False, 100, 160),
        "FL2": GateAssignment("FL2", "REMOTE_01", 1, 0, True, False, 120, 180),
    }
    diag = verify_hard_constraints_independently([f1, f2], [stand], assignments)
    assert diag.is_valid is False
    assert diag.planned_remote_violations >= 1
    assert diag.planned_contact_violations == 0
    assert diag.conflict_count >= 1


# ---------------------------------------------------------------------------
# R02: Verifier detects exceeding K on pooled remote resource
# ---------------------------------------------------------------------------
def test_r02_verifier_detects_exceeding_k_on_pooled_remote() -> None:
    f1 = _make_flight("FL1", 0, 100, 160)
    f2 = _make_flight("FL2", 1, 110, 170)
    f3 = _make_flight("FL3", 2, 120, 180)
    pool = Gate("REMOTE_POOL", 0, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=2)

    assignments = {
        "FL1": GateAssignment("FL1", "REMOTE_POOL", 0, 0, True, False, 100, 160),
        "FL2": GateAssignment("FL2", "REMOTE_POOL", 1, 0, True, False, 110, 170),
        "FL3": GateAssignment("FL3", "REMOTE_POOL", 2, 0, True, False, 120, 180),
    }
    diag = verify_hard_constraints_independently([f1, f2, f3], [pool], assignments)
    assert diag.is_valid is False
    assert diag.planned_remote_violations >= 1
    assert diag.max_concurrent_remote_usage == 3


# ---------------------------------------------------------------------------
# R03: UNBOUNDED_OVERFLOW_APRON allows concurrency only when explicitly unbounded
# ---------------------------------------------------------------------------
def test_r03_unbounded_apron_allows_concurrency() -> None:
    f1 = _make_flight("FL1", 0, 100, 160)
    f2 = _make_flight("FL2", 1, 110, 170)
    f3 = _make_flight("FL3", 2, 120, 180)
    apron = Gate("OVERFLOW_APRON", 0, resource_type=GateResourceType.UNBOUNDED_OVERFLOW_APRON, capacity=math.inf)

    assignments = {
        "FL1": GateAssignment("FL1", "OVERFLOW_APRON", 0, 0, True, False, 100, 160),
        "FL2": GateAssignment("FL2", "OVERFLOW_APRON", 1, 0, True, False, 110, 170),
        "FL3": GateAssignment("FL3", "OVERFLOW_APRON", 2, 0, True, False, 120, 180),
    }
    diag = verify_hard_constraints_independently([f1, f2, f3], [apron], assignments)
    assert diag.is_valid is True
    assert diag.conflict_count == 0
    assert diag.planned_remote_violations == 0
    assert diag.max_concurrent_remote_usage == 3


# ---------------------------------------------------------------------------
# R04: Greedy does not place 2 overlapping flights on same FINITE_REMOTE_STAND
# ---------------------------------------------------------------------------
def test_r04_greedy_does_not_place_overlapping_flights_on_same_finite_stand() -> None:
    f1 = _make_flight("FL1", 0, 100, 160)
    f2 = _make_flight("FL2", 1, 120, 180)
    stand = Gate("REMOTE_01", 0, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=1)

    solver = DeterministicGreedyGateSolver()
    result = solver.solve([f1, f2], [stand], allow_overflow=False)
    # Greedy must not assign both to REMOTE_01 because capacity is 1
    assert result.feasible is False
    assert result.status == "INFEASIBLE"
    # At most 1 flight assigned to REMOTE_01
    assigned_to_stand = [fid for fid, a in result.assignments.items() if a.gate_id == "REMOTE_01"]
    assert len(assigned_to_stand) <= 1


# ---------------------------------------------------------------------------
# R05: Greedy respects capacity K of pooled remote resource
# ---------------------------------------------------------------------------
def test_r05_greedy_respects_capacity_k_of_pooled_remote() -> None:
    f1 = _make_flight("FL1", 0, 100, 160)
    f2 = _make_flight("FL2", 1, 110, 170)
    f3 = _make_flight("FL3", 2, 120, 180)
    pool = Gate("REMOTE_POOL", 0, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=2)

    solver = DeterministicGreedyGateSolver()
    result = solver.solve([f1, f2, f3], [pool], allow_overflow=False)
    assert result.feasible is False
    assigned_to_pool = [fid for fid, a in result.assignments.items() if a.gate_id == "REMOTE_POOL"]
    assert len(assigned_to_pool) == 2  # exactly 2 accommodated, 3rd unassigned


# ---------------------------------------------------------------------------
# R06: CP-SAT generates no-overlap constraint for all FINITE_REMOTE_STAND with capacity=1
# ---------------------------------------------------------------------------
def test_r06_cpsat_enforces_no_overlap_on_finite_remote_stand() -> None:
    f1 = _make_flight("FL1", 0, 100, 160)
    f2 = _make_flight("FL2", 1, 120, 180)
    stand = Gate("REMOTE_01", 0, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=1)

    solver = CPSatGateSolver()
    result = solver.solve([f1, f2], [stand], allow_overflow=False)
    assert result.feasible is False
    assert result.status == "INFEASIBLE"
    assert result.solver_configuration.get("raw_solver_status") == "INFEASIBLE"
    assert len(result.assignments) == 0


# ---------------------------------------------------------------------------
# R07: CP-SAT generates capacity <= K constraint for pooled remote resource
# ---------------------------------------------------------------------------
def test_r07_cpsat_enforces_capacity_k_pooled_remote() -> None:
    f1 = _make_flight("FL1", 0, 100, 160)
    f2 = _make_flight("FL2", 1, 110, 170)
    pool_cap2 = Gate("REMOTE_POOL", 0, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=2)

    solver = CPSatGateSolver()
    # 2 flights on cap 2: OPTIMAL
    res2 = solver.solve([f1, f2], [pool_cap2], allow_overflow=False)
    assert res2.feasible is True
    assert res2.status == "OPTIMAL"

    # 3 flights on cap 2: INFEASIBLE
    f3 = _make_flight("FL3", 2, 120, 180)
    res3 = solver.solve([f1, f2, f3], [pool_cap2], allow_overflow=False)
    assert res3.feasible is False
    assert res3.status == "INFEASIBLE"


# ---------------------------------------------------------------------------
# R08: Simulated Annealing treats 2 overlapping flights on finite remote stand as hard constraint violation
# ---------------------------------------------------------------------------
def test_r08_sa_treats_remote_stand_overlap_as_infeasible() -> None:
    f1 = _make_flight("FL1", 0, 100, 160)
    f2 = _make_flight("FL2", 1, 120, 180)
    stand = Gate("REMOTE_01", 0, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=1)

    solver = SimulatedAnnealingGateSolver()
    result = solver.solve([f1, f2], [stand], allow_overflow=False)
    assert result.feasible is False
    assert result.status == "INFEASIBLE"


# ---------------------------------------------------------------------------
# R09: SA neighborhood operator does not create/keep moves leading to overlap on finite remote stands
# ---------------------------------------------------------------------------
def test_r09_sa_neighborhood_rejects_remote_stand_overlap() -> None:
    f1 = _make_flight("FL1", 0, 100, 160)
    f2 = _make_flight("FL2", 1, 120, 180)
    stand = Gate("REMOTE_01", 0, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=1)

    # is_gate_feasible_for_flight must return False for f2 when f1 is on stand
    assert is_gate_feasible_for_flight(stand, f2, [f1]) is False
    # But True if f1 does not overlap
    f_non_overlap = _make_flight("FL3", 2, 200, 260)
    assert is_gate_feasible_for_flight(stand, f_non_overlap, [f1]) is True


# ---------------------------------------------------------------------------
# R10: Hybrid solver passes correct capacity semantics from CP-SAT to SA
# ---------------------------------------------------------------------------
def test_r10_hybrid_solver_preserves_capacity_semantics() -> None:
    f1 = _make_flight("FL1", 0, 100, 160)
    f2 = _make_flight("FL2", 1, 120, 180)
    stand = Gate("REMOTE_01", 0, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=1)

    solver = HybridGateSolver()
    result = solver.solve([f1, f2], [stand], allow_overflow=False)
    assert result.feasible is False
    assert result.status == "INFEASIBLE"


# ---------------------------------------------------------------------------
# R11: Hybrid incumbent is re-verified before transfer
# ---------------------------------------------------------------------------
def test_r11_hybrid_incumbent_reverified_before_transfer() -> None:
    f1 = _make_flight("FL1", 0, 100, 160)
    f2 = _make_flight("FL2", 1, 200, 260)
    stand = Gate("REMOTE_01", 0, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=1)

    solver = HybridGateSolver()
    result = solver.solve([f1, f2], [stand], allow_overflow=False)
    assert result.feasible is True
    assert result.constraint_diagnostics.is_valid is True
    assert result.constraint_diagnostics.planned_remote_violations == 0


# ---------------------------------------------------------------------------
# R12: Generator max_overflow=0 produces no overflow stand/apron
# ---------------------------------------------------------------------------
def test_r12_generator_max_overflow_zero_creates_no_overflow() -> None:
    gates = generate_contact_gates(5, allow_overflow=True, max_overflow=0)
    assert len(gates) == 5
    assert all(not g.is_overflow for g in gates)
    assert all(g.resource_type == GateResourceType.CONTACT_GATE for g in gates)


# ---------------------------------------------------------------------------
# R13: Generator max_overflow=K produces exactly K finite stands separately or 1 pooled resource
# ---------------------------------------------------------------------------
def test_r13_generator_max_overflow_k_discrete_and_pooled() -> None:
    # Discrete stands
    gates_disc = generate_contact_gates(5, allow_overflow=True, max_overflow=3, pooled_remote=False)
    assert len(gates_disc) == 8
    remote_stands = [g for g in gates_disc if g.is_overflow]
    assert len(remote_stands) == 3
    assert all(g.resource_type == GateResourceType.FINITE_REMOTE_STAND for g in remote_stands)
    assert all(g.capacity == 1 for g in remote_stands)

    # Pooled stand
    gates_pool = generate_contact_gates(5, allow_overflow=True, max_overflow=3, pooled_remote=True)
    assert len(gates_pool) == 6
    pools = [g for g in gates_pool if g.is_overflow]
    assert len(pools) == 1
    assert pools[0].resource_type == GateResourceType.FINITE_REMOTE_STAND
    assert pools[0].capacity == 3


# ---------------------------------------------------------------------------
# R14: No solver silently turns finite remote stand into unbounded apron when allow_unbounded_overflow=False
# ---------------------------------------------------------------------------
def test_r14_no_silent_unbounded_fallback_when_forbidden() -> None:
    f1 = _make_flight("FL1", 0, 100, 160)
    f2 = _make_flight("FL2", 1, 120, 180)
    stand = Gate("REMOTE_01", 0, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=1)

    cfg = GateOptimizationConfig(allow_unbounded_overflow=False)
    cpsat = CPSatGateSolver(config=cfg)
    res_cp = cpsat.solve([f1, f2], [stand], allow_overflow=True)
    assert res_cp.feasible is False
    assert res_cp.status == "INFEASIBLE"

    greedy = DeterministicGreedyGateSolver(config=cfg)
    res_gr = greedy.solve([f1, f2], [stand], allow_overflow=True)
    assert res_gr.feasible is False


# ---------------------------------------------------------------------------
# R15: Evaluation report clearly separates planned/realized violations for contact gate vs remote stand
# ---------------------------------------------------------------------------
def test_r15_diagnostic_separates_contact_and_remote_violations() -> None:
    f1 = _make_flight("FL1", 0, 100, 160)
    f2 = _make_flight("FL2", 1, 120, 180)
    g_contact = Gate("G01", 0, resource_type=GateResourceType.CONTACT_GATE, capacity=1)
    g_remote = Gate("REMOTE_01", 1, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=1)

    # Case A: conflict on contact gate
    assign_contact = {
        "FL1": GateAssignment("FL1", "G01", 0, 0, False, False, 100, 160),
        "FL2": GateAssignment("FL2", "G01", 1, 0, False, False, 120, 180),
    }
    diag_c = verify_hard_constraints_independently([f1, f2], [g_contact, g_remote], assign_contact)
    assert diag_c.planned_contact_violations == 1
    assert diag_c.planned_remote_violations == 0

    # Case B: conflict on remote stand
    assign_remote = {
        "FL1": GateAssignment("FL1", "REMOTE_01", 0, 1, True, False, 100, 160),
        "FL2": GateAssignment("FL2", "REMOTE_01", 1, 1, True, False, 120, 180),
    }
    diag_r = verify_hard_constraints_independently([f1, f2], [g_contact, g_remote], assign_remote)
    assert diag_r.planned_contact_violations == 0
    assert diag_r.planned_remote_violations == 1


# ---------------------------------------------------------------------------
# R16: Diagnostic contains max_concurrent_remote_usage
# ---------------------------------------------------------------------------
def test_r16_diagnostic_contains_max_concurrent_remote_usage() -> None:
    f1 = _make_flight("FL1", 0, 100, 160)
    f2 = _make_flight("FL2", 1, 120, 180)
    f3 = _make_flight("FL3", 2, 200, 260)
    r1 = Gate("REMOTE_01", 0, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=1)
    r2 = Gate("REMOTE_02", 1, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=1)

    assignments = {
        "FL1": GateAssignment("FL1", "REMOTE_01", 0, 0, True, False, 100, 160),
        "FL2": GateAssignment("FL2", "REMOTE_02", 1, 1, True, False, 120, 180),
        "FL3": GateAssignment("FL3", "REMOTE_01", 2, 0, True, False, 200, 260),
    }
    diag = verify_hard_constraints_independently([f1, f2, f3], [r1, r2], assignments)
    assert diag.is_valid is True
    # At t in [120, 160), FL1 is on REMOTE_01 and FL2 is on REMOTE_02: concurrent = 2
    assert diag.max_concurrent_remote_usage == 2


# ---------------------------------------------------------------------------
# R17: Reassignment cost calculated correctly for finite remote stand
# ---------------------------------------------------------------------------
def test_r17_reassignment_cost_calculated_correctly_for_remote_stand() -> None:
    f = _make_flight("FL1", 0, 100, 160, nominal="G01")
    stand = Gate("REMOTE_01", 0, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=1)

    cfg = GateOptimizationConfig(reassignment_weight=50.0, overflow_weight=200.0)
    assign = {"FL1": GateAssignment("FL1", "REMOTE_01", 0, 0, True, True, 100, 160)}

    res = evaluate_gate_assignment(assign, [f], [stand], cfg)
    assert res.objective_breakdown.reassignment_cost == 50.0
    assert res.objective_breakdown.overflow_cost == 200.0


# ---------------------------------------------------------------------------
# R18: Overflow cost not mistakenly applied to contact gate and vice versa
# ---------------------------------------------------------------------------
def test_r18_overflow_cost_separation() -> None:
    f = _make_flight("FL1", 0, 100, 160, nominal="G01")
    g_contact = Gate("G01", 0, resource_type=GateResourceType.CONTACT_GATE, capacity=1)

    cfg = GateOptimizationConfig(reassignment_weight=50.0, overflow_weight=200.0)
    assign = {"FL1": GateAssignment("FL1", "G01", 0, 0, False, False, 100, 160)}

    res = evaluate_gate_assignment(assign, [f], [g_contact], cfg)
    assert res.objective_breakdown.overflow_cost == 0.0
    assert res.objective_breakdown.reassignment_cost == 0.0


# ---------------------------------------------------------------------------
# R19: Time window with buffer_min applied uniformly
# ---------------------------------------------------------------------------
def test_r19_time_window_with_buffer_min_applied_uniformly() -> None:
    f1 = Flight("FL1", 0, "VN", "101", 100, 160, 100, min_turnaround_min=30, default_dwell_min=60, buffer_min=15)
    f2 = Flight("FL2", 1, "VN", "102", 170, 230, 170, min_turnaround_min=30, default_dwell_min=60, buffer_min=15)

    # f1 window: [100, 160 + 15) = [100, 175)
    # f2 window: [170, 230 + 15) = [170, 245)
    # They overlap in [170, 175) because of the 15 min buffer!
    assert f1.time_window.overlaps(f2.time_window) is True

    g = Gate("G01", 0, resource_type=GateResourceType.CONTACT_GATE, capacity=1)
    assign = {
        "FL1": GateAssignment("FL1", "G01", 0, 0, False, False, 100, 175),
        "FL2": GateAssignment("FL2", "G01", 1, 0, False, False, 170, 245),
    }
    diag = verify_hard_constraints_independently([f1, f2], [g], assign)
    assert diag.is_valid is False
    assert diag.planned_contact_violations == 1


# ---------------------------------------------------------------------------
# R20: Zero-capacity gate rejected by validation (ValueError)
# ---------------------------------------------------------------------------
def test_r20_zero_capacity_gate_rejected() -> None:
    with pytest.raises(ValueError, match="Gate.capacity must be >= 1"):
        Gate("G0", 0, capacity=0)


# ---------------------------------------------------------------------------
# R21: Duplicate gate_id rejected by verifier (is_valid=False)
# ---------------------------------------------------------------------------
def test_r21_duplicate_gate_id_rejected() -> None:
    f = _make_flight("FL1", 0, 100, 160)
    g1 = Gate("G01", 0)
    g2 = Gate("G01", 1)  # duplicate ID

    assign = {"FL1": GateAssignment("FL1", "G01", 0, 0, False, False, 100, 160)}
    diag = verify_hard_constraints_independently([f], [g1, g2], assign)
    assert diag.is_valid is False
    assert len(diag.duplicate_gate_violations) >= 1


# ---------------------------------------------------------------------------
# R22: Negative capacity rejected by validation (ValueError)
# ---------------------------------------------------------------------------
def test_r22_negative_capacity_gate_rejected() -> None:
    with pytest.raises(ValueError, match="Gate.capacity must be >= 1"):
        Gate("G0", 0, capacity=-5)


# ---------------------------------------------------------------------------
# R23: Unknown resource type rejected by validation (ValueError)
# ---------------------------------------------------------------------------
def test_r23_unknown_resource_type_rejected() -> None:
    with pytest.raises(ValueError):
        Gate("G0", 0, resource_type="UNSUPPORTED_TYPE")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# R24: Backward compatibility for legacy tests with unbounded apron
# ---------------------------------------------------------------------------
def test_r24_backward_compatibility_unbounded_apron() -> None:
    f1 = _make_flight("FL1", 0, 100, 160)
    f2 = _make_flight("FL2", 1, 120, 180)
    legacy_gate = Gate("OVERFLOW_APRON", 0, is_overflow=True)
    assert legacy_gate.resource_type == GateResourceType.UNBOUNDED_OVERFLOW_APRON
    assert legacy_gate.is_unbounded is True

    assign = {
        "FL1": GateAssignment("FL1", "OVERFLOW_APRON", 0, 0, True, False, 100, 160),
        "FL2": GateAssignment("FL2", "OVERFLOW_APRON", 1, 0, True, False, 120, 180),
    }
    diag = verify_hard_constraints_independently([f1, f2], [legacy_gate], assign)
    assert diag.is_valid is True
    assert diag.conflict_count == 0


# ---------------------------------------------------------------------------
# Differential Oracle Test: Greedy vs CP-SAT vs SA Agreement
# ---------------------------------------------------------------------------
def test_differential_oracle_solvers_agree_on_finite_remote_feasibility() -> None:
    """Differential oracle test: on a 3-flight instance with 1 contact gate and 1 finite remote stand (cap=1),
    all solvers must agree on feasibility or infeasibility.
    """
    # Two overlapping flights FL1 [100, 160), FL2 [120, 180), and FL3 [130, 190).
    # All 3 overlap in [130, 160).
    # With only 1 contact gate and 1 finite remote stand, max concurrency = 2 < 3.
    # Therefore, all 3 solvers MUST find this problem INFEASIBLE.
    f1 = _make_flight("FL1", 0, 100, 160)
    f2 = _make_flight("FL2", 1, 120, 180)
    f3 = _make_flight("FL3", 2, 130, 190)

    g_contact = Gate("G01", 0, resource_type=GateResourceType.CONTACT_GATE, capacity=1)
    g_stand = Gate("REMOTE_01", 1, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=1)
    gates = [g_contact, g_stand]

    cfg = GateOptimizationConfig(allow_unbounded_overflow=False)
    gr_res = DeterministicGreedyGateSolver(config=cfg).solve([f1, f2, f3], gates, allow_overflow=False)
    cp_res = CPSatGateSolver(config=cfg).solve([f1, f2, f3], gates, allow_overflow=False)
    sa_res = SimulatedAnnealingGateSolver(config=cfg).solve([f1, f2, f3], gates, allow_overflow=False)

    assert gr_res.feasible is False, "Greedy must find 3 overlapping flights on 2 capacity-1 gates infeasible"
    assert cp_res.feasible is False, "CP-SAT must find 3 overlapping flights on 2 capacity-1 gates infeasible"
    assert sa_res.feasible is False, "SA must find 3 overlapping flights on 2 capacity-1 gates infeasible"
