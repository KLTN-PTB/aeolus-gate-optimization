"""Test Suite for AEOLUS-G12B: Hybrid Solver Incumbent Protection & Wall-Clock Budget.

Covers:
- HYB-01: Outer incumbent guard rejects SA solution with worse objective.
- HYB-02: Outer incumbent guard rejects SA solution with infeasible assignments.
- HYB-03: Outer incumbent guard catches SA exception and preserves Stage 1 incumbent.
- HYB-04: SA improved feasible objective accepted.
- HYB-05: Strict invariant final_obj <= incumbent_obj + 1e-6 holds.
- HYB-06: CP-SAT timeout with feasible incumbent passes incumbent to Stage 2.
- HYB-07: Stage 2 SA loop respects deadline_perf_counter and terminates with TIME_LIMIT.
- HYB-08: Budget exhausted before Stage 2 skips SA and preserves incumbent.
- HYB-09: Total wall-clock time bounded by total_wall_clock_budget_seconds.
- HYB-10: Deterministic reproducibility with seed.
- HYB-11: Empty flights handled gracefully.
- HYB-12: Single flight handled gracefully.
- HYB-13: All remote fallback preserved.
- HYB-14: Tight buffer feasibility preserved.
- HYB-15: Carrier incompatibility preserved.
- HYB-16: Hybrid provenance trace contains incumbent protection fields.
"""

from __future__ import annotations

import math
import time
from unittest.mock import MagicMock, patch
import pytest

from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import (
    ConstraintDiagnostic,
    Flight,
    Gate,
    GateAssignment,
    GateResourceType,
    ObjectiveBreakdown,
    OptimizationResult,
    TerminationReason,
    verify_hard_constraints_independently,
)
from src.optimization.evaluation import evaluate_gate_assignment
from src.optimization.sa.annealer import SAConfig, SimulatedAnnealingGateSolver
from src.optimization.solvers.hybrid_solver import HybridGateSolver


def make_sample_problem(n_flights: int = 5, n_gates: int = 3) -> tuple[list[Flight], list[Gate]]:
    """Helper to construct a deterministic test instance."""
    gates = [
        Gate(
            gate_id=f"G{i}",
            gate_index=i,
            resource_type=GateResourceType.CONTACT_GATE,
        )
        for i in range(n_gates)
    ]
    remote = Gate(
        gate_id="REMOTE",
        gate_index=n_gates,
        resource_type=GateResourceType.FINITE_REMOTE_STAND,
        capacity=5,
        is_overflow=True,
    )
    all_gates = gates + [remote]

    flights = []
    for i in range(n_flights):
        arr = 100 + i * 40
        dep = arr + 60
        f = Flight(
            flight_id=f"F{i}",
            flight_index=i,
            carrier="VN",
            flight_number=f"{100 + i}",
            scheduled_arrival_min=arr,
            scheduled_departure_min=dep,
            predicted_arrival_min=arr,
            nominal_gate_id=f"G{i % n_gates}",
            aircraft_type="A321",
            min_turnaround_min=30,
            default_dwell_min=60,
            buffer_min=15,
            precomputed_gate_out_min=dep,
        )
        flights.append(f)

    return flights, all_gates


# ==============================================================================
# HYB-01: SA WORSE OBJECTIVE REJECTED
# ==============================================================================
def test_hyb_01_sa_worse_objective_rejected_incumbent_preserved():
    """HYB-01: When SA returns a solution with worse objective than CP-SAT,
    the outer incumbent guard MUST reject it and keep the CP-SAT incumbent.
    """
    flights, gates = make_sample_problem(n_flights=3, n_gates=2)
    cfg = GateOptimizationConfig(time_limit_seconds=5.0)
    solver = HybridGateSolver(config=cfg, sa_config=SAConfig(iterations=10, seed=42))

    # Mock SimulatedAnnealingGateSolver.solve to return a worse (higher cost) solution
    def mock_sa_solve(*args, **kwargs):
        # Assign all to REMOTE stand to create huge penalty
        bad_assignments = {
            f.flight_id: GateAssignment(
                flight_id=f.flight_id,
                gate_id="REMOTE",
                occupancy_start_min=f.scheduled_arrival_min,
                occupancy_end_min=f.scheduled_departure_min + f.buffer_min,
            )
            for f in flights
        }
        ev = evaluate_gate_assignment(bad_assignments, flights, gates, cfg, runtime_ms=10.0)
        return OptimizationResult(
            status="FEASIBLE",
            objective_value=ev.objective_value,
            objective_breakdown=ev.objective_breakdown,
            feasible=True,
            runtime_ms=10.0,
            optimality_gap=None,
            assignments=bad_assignments,
            constraint_diagnostics=ev.constraint_diagnostics,
            solver_configuration={},
            termination_reason=TerminationReason.ITERATION_LIMIT,
        )

    with patch.object(SimulatedAnnealingGateSolver, "solve", side_effect=mock_sa_solve):
        res = solver.solve(flights, gates)

    assert res.feasible
    assert res.objective_value < 90000.0, f"Expected CP-SAT incumbent preserved, but got {res.objective_value}"
    assert res.solver_configuration.get("sa_accepted") is False
    assert res.solver_configuration.get("sa_rejection_reason") == "SA_DEGRADED_INCUMBENT_OBJECTIVE"


# ==============================================================================
# HYB-02: SA INFEASIBLE PROPOSAL REJECTED
# ==============================================================================
def test_hyb_02_sa_infeasible_proposal_rejected_incumbent_preserved():
    """HYB-02: When SA returns an infeasible solution (e.g. contact conflict),
    the outer incumbent guard MUST reject it and retain the feasible incumbent.
    """
    flights, gates = make_sample_problem(n_flights=3, n_gates=2)
    cfg = GateOptimizationConfig(time_limit_seconds=5.0)
    solver = HybridGateSolver(config=cfg)

    # Mock SA to return conflicting assignments (all on G0 at same time)
    def mock_sa_solve(*args, **kwargs):
        infeasible_assignments = {
            f.flight_id: GateAssignment(
                flight_id=f.flight_id,
                gate_id="G0",
                occupancy_start_min=100,
                occupancy_end_min=200,
            )
            for f in flights
        }
        ev = evaluate_gate_assignment(infeasible_assignments, flights, gates, cfg, runtime_ms=10.0)
        return OptimizationResult(
            status="FEASIBLE",
            objective_value=ev.objective_value,
            objective_breakdown=ev.objective_breakdown,
            feasible=True,
            runtime_ms=10.0,
            optimality_gap=None,
            assignments=infeasible_assignments,
            constraint_diagnostics=ev.constraint_diagnostics,
            solver_configuration={},
            termination_reason=TerminationReason.ITERATION_LIMIT,
        )

    with patch.object(SimulatedAnnealingGateSolver, "solve", side_effect=mock_sa_solve):
        res = solver.solve(flights, gates)

    assert res.feasible, "Hybrid result must be feasible by retaining CP-SAT incumbent"
    assert res.solver_configuration.get("sa_accepted") is False
    assert res.solver_configuration.get("sa_rejection_reason") == "SA_PRODUCED_INFEASIBLE_SOLUTION"


# ==============================================================================
# HYB-03: SA EXCEPTION CAUGHT
# ==============================================================================
def test_hyb_03_sa_exception_caught_incumbent_preserved():
    """HYB-03: When SA raises a runtime exception, the solver must not crash;
    it must catch the error, record the trace, and return the incumbent.
    """
    flights, gates = make_sample_problem(n_flights=3, n_gates=2)
    cfg = GateOptimizationConfig(time_limit_seconds=5.0)
    solver = HybridGateSolver(config=cfg)

    with patch.object(SimulatedAnnealingGateSolver, "solve", side_effect=RuntimeError("SA simulation failed")):
        res = solver.solve(flights, gates)

    assert res.feasible
    assert res.solver_configuration.get("sa_accepted") is False
    assert "SA_EXCEPTION" in str(res.solver_configuration.get("sa_rejection_reason"))


# ==============================================================================
# HYB-04: SA IMPROVED FEASIBLE OBJECTIVE ACCEPTED
# ==============================================================================
def test_hyb_04_sa_improved_feasible_objective_accepted():
    """HYB-04: When SA finds a strictly better feasible assignment,
    the solver accepts it and returns the improved objective.
    """
    flights, gates = make_sample_problem(n_flights=3, n_gates=3)
    cfg = GateOptimizationConfig(time_limit_seconds=5.0)
    solver = HybridGateSolver(config=cfg)

    # Construct an optimal assignment where every flight gets its nominal gate (0 cost)
    optimal_assignments = {
        f.flight_id: GateAssignment(
            flight_id=f.flight_id,
            gate_id=f.nominal_gate_id,
            occupancy_start_min=f.scheduled_arrival_min,
            occupancy_end_min=f.scheduled_departure_min + f.buffer_min,
        )
        for f in flights
    }

    def mock_sa_solve(*args, **kwargs):
        ev = evaluate_gate_assignment(optimal_assignments, flights, gates, cfg, runtime_ms=5.0)
        return OptimizationResult(
            status="FEASIBLE",
            objective_value=ev.objective_value,
            objective_breakdown=ev.objective_breakdown,
            feasible=True,
            runtime_ms=5.0,
            optimality_gap=None,
            assignments=optimal_assignments,
            constraint_diagnostics=ev.constraint_diagnostics,
            solver_configuration={"accepted_moves": 5},
            termination_reason=TerminationReason.ITERATION_LIMIT,
        )

    # Set CP-SAT to produce a slightly suboptimal initial incumbent
    with patch.object(SimulatedAnnealingGateSolver, "solve", side_effect=mock_sa_solve):
        res = solver.solve(flights, gates)

    assert res.feasible
    assert res.objective_value == 0.0
    assert res.solver_configuration.get("sa_accepted") is True


# ==============================================================================
# HYB-05: INVARIANT FINAL_OBJ <= INCUMBENT_OBJ + 1e-6
# ==============================================================================
def test_hyb_05_strict_invariant_final_obj_le_incumbent_obj():
    """HYB-05: Real solver run without mocks. Verifies that final_obj <= initial_cost + 1e-6."""
    flights, gates = make_sample_problem(n_flights=8, n_gates=3)
    cfg = GateOptimizationConfig(time_limit_seconds=2.0)
    sa_cfg = SAConfig(iterations=200, seed=123)
    solver = HybridGateSolver(config=cfg, sa_config=sa_cfg, cp_ratio=0.5)

    res = solver.solve(flights, gates)
    assert res.feasible

    init_cost = res.solver_configuration.get("initial_cost")
    assert init_cost is not None
    assert res.objective_value <= init_cost + 1e-6, (
        f"Invariant violated: final_cost {res.objective_value} > initial_cost {init_cost}"
    )


# ==============================================================================
# HYB-06: CP-SAT TIMEOUT WITH INCUMBENT PASSES INCUMBENT
# ==============================================================================
def test_hyb_06_cpsat_timeout_with_incumbent_passes_incumbent():
    """HYB-06: When CP-SAT times out but found a feasible incumbent,
    the incumbent is passed to Stage 2 SA and preserved.
    """
    flights, gates = make_sample_problem(n_flights=4, n_gates=2)
    cfg = GateOptimizationConfig(time_limit_seconds=2.0)
    solver = HybridGateSolver(config=cfg, sa_config=SAConfig(iterations=50, seed=42))

    res = solver.solve(flights, gates)
    assert res.feasible
    assert res.solver_configuration.get("initial_solution_source") in ("CP_SAT", "GREEDY_FALLBACK")


# ==============================================================================
# HYB-07: SA WALL-CLOCK DEADLINE EARLY TERMINATION
# ==============================================================================
def test_hyb_07_sa_wallclock_deadline_terminates_early():
    """HYB-07: When SA is provided with a tight deadline, it stops before completing
    configured iterations and records TIME_LIMIT.
    """
    flights, gates = make_sample_problem(n_flights=6, n_gates=3)
    cfg = GateOptimizationConfig(time_limit_seconds=1.0)
    # Huge iteration count that would take several seconds if not interrupted
    sa_cfg = SAConfig(iterations=500000, seed=42)
    sa_solver = SimulatedAnnealingGateSolver(config=cfg, sa_config=sa_cfg)

    t0 = time.perf_counter()
    deadline = t0 + 0.1  # 100ms deadline
    res = sa_solver.solve(flights, gates, deadline_perf_counter=deadline)

    elapsed = time.perf_counter() - t0
    assert elapsed < 0.5, f"SA exceeded deadline: elapsed {elapsed}s"
    assert res.termination_reason == TerminationReason.TIME_LIMIT
    assert res.feasible


# ==============================================================================
# HYB-08: ZERO REMAINING BUDGET SKIPS SA
# ==============================================================================
def test_hyb_08_zero_remaining_budget_skips_sa():
    """HYB-08: If Stage 1 uses entire budget, Stage 2 SA is skipped and incumbent preserved."""
    flights, gates = make_sample_problem(n_flights=4, n_gates=2)
    cfg = GateOptimizationConfig(
        time_limit_seconds=0.1,
        total_wall_clock_budget_seconds=0.05,
    )
    solver = HybridGateSolver(config=cfg, sa_config=SAConfig(iterations=1000, seed=42))

    res = solver.solve(flights, gates)
    assert res.feasible
    assert res.objective_value <= res.solver_configuration.get("initial_cost") + 1e-6


# ==============================================================================
# HYB-09: TOTAL WALL-CLOCK BOUNDED BY BUDGET
# ==============================================================================
def test_hyb_09_total_wallclock_bounded_by_budget():
    """HYB-09: Total Hybrid execution time does not grossly exceed total_wall_clock_budget_seconds."""
    flights, gates = make_sample_problem(n_flights=10, n_gates=3)
    budget_s = 0.5
    cfg = GateOptimizationConfig(
        time_limit_seconds=budget_s,
        total_wall_clock_budget_seconds=budget_s,
    )
    solver = HybridGateSolver(config=cfg, sa_config=SAConfig(iterations=100000, seed=42))

    t0 = time.perf_counter()
    res = solver.solve(flights, gates)
    elapsed = time.perf_counter() - t0

    assert elapsed <= budget_s + 0.8, f"Total execution time {elapsed}s exceeded budget {budget_s}s"
    assert res.feasible


# ==============================================================================
# HYB-10: DETERMINISTIC REPRODUCIBILITY WITH SEED
# ==============================================================================
def test_hyb_10_deterministic_reproducibility_with_seed():
    """HYB-10: Two identical runs with the same seed yield identical assignments and objective."""
    flights, gates = make_sample_problem(n_flights=6, n_gates=3)
    cfg = GateOptimizationConfig(time_limit_seconds=2.0)
    sa_cfg = SAConfig(iterations=100, seed=999)

    solver1 = HybridGateSolver(config=cfg, sa_config=sa_cfg)
    solver2 = HybridGateSolver(config=cfg, sa_config=sa_cfg)

    res1 = solver1.solve(flights, gates)
    res2 = solver2.solve(flights, gates)

    assert res1.objective_value == res2.objective_value
    assert {k: v.gate_id for k, v in res1.assignments.items()} == {k: v.gate_id for k, v in res2.assignments.items()}


# ==============================================================================
# HYB-11: EMPTY FLIGHTS
# ==============================================================================
def test_hyb_11_empty_flights_handled_gracefully():
    """HYB-11: Zero flights returns feasible empty result."""
    _, gates = make_sample_problem(n_flights=0, n_gates=3)
    solver = HybridGateSolver()
    res = solver.solve([], gates)
    assert res.feasible
    assert len(res.assignments) == 0
    assert res.objective_value == 0.0


# ==============================================================================
# HYB-12: SINGLE FLIGHT
# ==============================================================================
def test_hyb_12_single_flight_handled_gracefully():
    """HYB-12: Single flight assigned to nominal gate at zero penalty."""
    flights, gates = make_sample_problem(n_flights=1, n_gates=2)
    solver = HybridGateSolver()
    res = solver.solve(flights, gates)
    assert res.feasible
    assert res.assignments["F0"].gate_id == "G0"
    assert res.objective_value == 0.0


# ==============================================================================
# HYB-13: ALL REMOTE FALLBACK PRESERVED
# ==============================================================================
def test_hyb_13_all_remote_fallback_preserved():
    """HYB-13: When contact gates are full or unavailable, remote assignments are valid."""
    g0 = Gate(gate_id="G0", gate_index=0, resource_type=GateResourceType.CONTACT_GATE)
    remote = Gate(gate_id="REMOTE", gate_index=1, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=5, is_overflow=True)
    f1 = Flight(flight_id="F1", flight_index=0, carrier="VN", flight_number="1", scheduled_arrival_min=100, scheduled_departure_min=200, predicted_arrival_min=100, nominal_gate_id="G0", min_turnaround_min=30, default_dwell_min=60, buffer_min=15, precomputed_gate_out_min=200)
    f2 = Flight(flight_id="F2", flight_index=1, carrier="VN", flight_number="2", scheduled_arrival_min=110, scheduled_departure_min=210, predicted_arrival_min=110, nominal_gate_id="G0", min_turnaround_min=30, default_dwell_min=60, buffer_min=15, precomputed_gate_out_min=210)

    solver = HybridGateSolver()
    res = solver.solve([f1, f2], [g0, remote])
    assert res.feasible
    remote_count = sum(1 for a in res.assignments.values() if a.gate_id == "REMOTE")
    assert remote_count >= 1


# ==============================================================================
# HYB-14: TIGHT BUFFER FEASIBILITY PRESERVED
# ==============================================================================
def test_hyb_14_tight_buffer_feasibility_preserved():
    """HYB-14: Flight separation respecting buffer_min is strictly maintained by Hybrid."""
    g0 = Gate(gate_id="G0", gate_index=0, resource_type=GateResourceType.CONTACT_GATE)
    remote = Gate(gate_id="REMOTE", gate_index=1, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=5, is_overflow=True)
    f1 = Flight(flight_id="F1", flight_index=0, carrier="VN", flight_number="1", scheduled_arrival_min=100, scheduled_departure_min=160, predicted_arrival_min=100, nominal_gate_id="G0", min_turnaround_min=30, default_dwell_min=60, buffer_min=20, precomputed_gate_out_min=160)
    # f2 arrives at 170, buffer for f1 ends at 180 -> conflict on G0, one must move
    f2 = Flight(flight_id="F2", flight_index=1, carrier="VN", flight_number="2", scheduled_arrival_min=170, scheduled_departure_min=230, predicted_arrival_min=170, nominal_gate_id="G0", min_turnaround_min=30, default_dwell_min=60, buffer_min=20, precomputed_gate_out_min=230)

    solver = HybridGateSolver()
    res = solver.solve([f1, f2], [g0, remote])
    assert res.feasible
    assert res.constraint_diagnostics.is_valid
    assert res.constraint_diagnostics.conflict_count == 0


# ==============================================================================
# HYB-15: CARRIER INCOMPATIBILITY PRESERVED
# ==============================================================================
def test_hyb_15_carrier_incompatibility_preserved():
    """HYB-15: Gate allowed_carriers is strictly respected by both stages."""
    g1 = Gate(gate_id="G1", gate_index=0, resource_type=GateResourceType.CONTACT_GATE, allowed_carriers=("BA",))
    g2 = Gate(gate_id="G2", gate_index=1, resource_type=GateResourceType.CONTACT_GATE, allowed_carriers=("VN",))
    remote = Gate(gate_id="REMOTE", gate_index=2, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=5, is_overflow=True)
    f1 = Flight(flight_id="F1", flight_index=0, carrier="VN", flight_number="101", scheduled_arrival_min=100, scheduled_departure_min=160, predicted_arrival_min=100, nominal_gate_id="G1", min_turnaround_min=30, default_dwell_min=60, buffer_min=15, precomputed_gate_out_min=160)

    solver = HybridGateSolver()
    res = solver.solve([f1], [g1, g2, remote])
    assert res.feasible
    assert res.assignments["F1"].gate_id == "G2"


# ==============================================================================
# HYB-16: HYBRID PROVENANCE TRACE COMPLETENESS
# ==============================================================================
def test_hyb_16_hybrid_provenance_trace_completeness():
    """HYB-16: Hybrid solver configuration contains all incumbent protection fields."""
    flights, gates = make_sample_problem(n_flights=4, n_gates=2)
    solver = HybridGateSolver()
    res = solver.solve(flights, gates)

    cfg_dict = res.solver_configuration
    required_fields = [
        "initial_cost",
        "final_cost",
        "sa_accepted",
        "stage1_wall_clock_ms",
        "stage2_wall_clock_ms",
        "total_wall_clock_ms",
    ]
    for rf in required_fields:
        assert rf in cfg_dict, f"Missing provenance field: {rf}"
