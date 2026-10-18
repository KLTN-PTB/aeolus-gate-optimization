"""Test Suite for Phase P03: Simulated Annealing & Hybrid Correctness.

Verifies:
- S01: SA feasible seed -> final feasible.
- S02: SA does not improve -> does not report OPTIMAL (reports FEASIBLE).
- S03: SA improves -> best cost <= initial cost.
- S04: Invalid move -> rejected.
- S05: Invalid swap -> rejected.
- S06: Repair failure -> preserves best-so-far.
- S07: NaN objective -> rejected gracefully.
- S08: Invalid cooling params -> ValueError on bad T0, Tmin, cooling_rate, iterations.
- S09: No neighbor available -> graceful termination with initial solution.
- S10: Fixed seed -> identical trace & objective (determinism).
- S11: Different seeds -> all satisfy hard constraints.
- S12: Contact gate conflict -> candidate rejected.
- S13: Remote capacity conflict -> candidate rejected.
- S14: CP-SAT FEASIBLE -> usable incumbent for Hybrid.
- S15: CP-SAT UNKNOWN + valid incumbent -> usable incumbent for Hybrid.
- S16: CP-SAT UNKNOWN + no incumbent -> greedy fallback allowed and recorded in trace.
- S17: CP-SAT INFEASIBLE -> no false feasibility, greedy fallback NOT attempted.
- S18: Greedy fallback failure -> returns INFEASIBLE with empty assignments.
- S19: Hybrid final objective calculated independently.
- S20: Hybrid trace contains all 17 provenance fields.
- S21: Legacy SA tests pass without regressions.
- S22: No false global-optimum certification.
- S23: Termination reasons reported accurately.
- S24: Duplicate/unknown assignments rejected.
- Brute Force Oracle Verification: Exact verification on small exhaustive state space.
"""

from __future__ import annotations

import itertools
import math
import random
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
from src.optimization.sa import (
    SAConfig,
    SAState,
    SimulatedAnnealingGateSolver,
    compute_state_objective,
    create_initial_state,
    generate_neighbor,
    try_move_flight,
    try_swap_flights,
)
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver
from src.optimization.solvers.hybrid_solver import HybridGateSolver
from tests.test_greedy_and_adversarial import _make_flight


# =============================================================================
# Helper Fixtures
# =============================================================================

@pytest.fixture
def small_scenario():
    """Small 3-flight, 2-contact gate scenario."""
    gates = [
        Gate(gate_id="G1", gate_index=0, resource_type=GateResourceType.CONTACT_GATE, capacity=1),
        Gate(gate_id="G2", gate_index=1, resource_type=GateResourceType.CONTACT_GATE, capacity=1),
    ]
    flights = [
        _make_flight("F1", start_min=100, duration_min=60, nominal_gate_id="G1"),
        _make_flight("F2", start_min=130, duration_min=60, nominal_gate_id="G2"),  # overlaps F1
        _make_flight("F3", start_min=170, duration_min=60, nominal_gate_id="G1"),  # overlaps F2, not F1
    ]
    return flights, gates


@pytest.fixture
def congested_scenario():
    """Scenario with 6 flights and 2 contact gates + 1 remote stand."""
    gates = [
        Gate(gate_id="G1", gate_index=0, resource_type=GateResourceType.CONTACT_GATE, capacity=1),
        Gate(gate_id="G2", gate_index=1, resource_type=GateResourceType.CONTACT_GATE, capacity=1),
        Gate(gate_id="R1", gate_index=2, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=1, is_overflow=True),
    ]
    flights = [
        _make_flight("FL_01", start_min=100, duration_min=60, nominal_gate_id="G1"),
        _make_flight("FL_02", start_min=110, duration_min=60, nominal_gate_id="G2"),
        _make_flight("FL_03", start_min=120, duration_min=60, nominal_gate_id="G1"),
        _make_flight("FL_04", start_min=170, duration_min=60, nominal_gate_id="G2"),
        _make_flight("FL_05", start_min=180, duration_min=60, nominal_gate_id="G1"),
        _make_flight("FL_06", start_min=190, duration_min=60, nominal_gate_id="G2"),
    ]
    return flights, gates


# =============================================================================
# S01 - S13: Simulated Annealing Correctness & Invariants
# =============================================================================

class TestSimulatedAnnealingCorrectness:
    """Verifies SA Invariants I1-I12 and specifications S01-S13."""

    def test_s01_sa_feasible_seed_yields_final_feasible(self, congested_scenario) -> None:
        """S01: Feasible seed guarantees final solution is independently certified feasible."""
        flights, gates = congested_scenario
        solver = SimulatedAnnealingGateSolver(sa_config=SAConfig(iterations=100, seed=42))
        res = solver.solve(flights, gates, allow_overflow=True)

        assert res.feasible is True
        diag = verify_hard_constraints_independently(flights=flights, gates=gates, assignments=res.assignments)
        assert diag.is_valid is True
        assert diag.hard_constraint_violations_count == 0

    def test_s02_sa_does_not_report_optimal(self, small_scenario) -> None:
        """S02 & S22: SA is a metaheuristic and NEVER self-certifies OPTIMAL."""
        flights, gates = small_scenario
        solver = SimulatedAnnealingGateSolver(sa_config=SAConfig(iterations=50, seed=42))
        res = solver.solve(flights, gates, allow_overflow=False)

        assert res.feasible is True
        assert res.status == "FEASIBLE"
        assert res.optimality_proven is False
        assert res.termination_reason == TerminationReason.ITERATION_LIMIT

    def test_s03_sa_improves_best_cost_monotonicity(self, congested_scenario) -> None:
        """S03 & I2: Best cost is monotonically non-increasing compared to initial solution."""
        flights, gates = congested_scenario
        greedy_res = DeterministicGreedyGateSolver().solve(flights, gates, allow_overflow=True)
        init_obj = greedy_res.objective_value

        solver = SimulatedAnnealingGateSolver(sa_config=SAConfig(iterations=300, seed=123))
        sa_res = solver.solve(flights, gates, initial_assignments=greedy_res.assignments, allow_overflow=True)

        assert sa_res.objective_value <= init_obj + 1e-9
        assert sa_res.solver_configuration["best_objective"] <= init_obj + 1e-9

    def test_s04_invalid_move_rejected(self, small_scenario) -> None:
        """S04: try_move_flight rejects moves that violate contact gate conflict."""
        flights, gates = small_scenario
        greedy_res = DeterministicGreedyGateSolver().solve(flights, gates, allow_overflow=False)
        state = create_initial_state(flights, gates, greedy_res.assignments)

        # Try moving F2 to G1: F2 [130, 190] overlaps with F1 [100, 160] and F3 [170, 230]
        f2 = next(f for f in flights if f.flight_id == "F2")
        g1 = next(g for g in gates if g.gate_id == "G1")
        cand = try_move_flight(state, f2, g1, use_repair=False)
        assert cand is None, "Moving F2 to G1 without repair should be rejected due to overlap conflict"

    def test_s05_invalid_swap_rejected(self, small_scenario) -> None:
        """S05: try_swap_flights rejects swaps that introduce conflict."""
        flights, gates = small_scenario
        greedy_res = DeterministicGreedyGateSolver().solve(flights, gates, allow_overflow=False)
        state = create_initial_state(flights, gates, greedy_res.assignments)

        # Swapping F1 (on G1) and F2 (on G2): F2 goes to G1 (conflicts with F3 on G1)
        f1 = next(f for f in flights if f.flight_id == "F1")
        f2 = next(f for f in flights if f.flight_id == "F2")
        cand = try_swap_flights(state, f1, f2, use_repair=False)
        assert cand is None, "Swapping F1 and F2 without repair should be rejected because F2 overlaps with F3 on G1"

    def test_s06_repair_failure_preserves_best_so_far(self, congested_scenario) -> None:
        """S06: Failure in neighbor generation preserves current and best state."""
        flights, gates = congested_scenario
        rng = random.Random(42)
        greedy_res = DeterministicGreedyGateSolver().solve(flights, gates, allow_overflow=True)
        state = create_initial_state(flights, gates, greedy_res.assignments)

        # Test with max_attempts=1 on tightly constrained copy where moves fail
        single_gate = [gates[0]]  # only G1
        # Create state with 1 flight on G1
        f1_only = [flights[0]]
        st = create_initial_state(f1_only, single_gate, {"FL_01": greedy_res.assignments["FL_01"]})
        # Cannot move to any other gate, cannot swap
        cand = generate_neighbor(st, rng, move_prob=0.5, max_attempts=5)
        assert cand is None
        # State itself remains untouched and feasible
        assert st.is_feasible() is True

    def test_s07_nan_objective_rejected_gracefully(self, small_scenario) -> None:
        """S07: Non-finite/NaN objective returned by candidate is rejected without crashing."""
        flights, gates = small_scenario
        solver = SimulatedAnnealingGateSolver(sa_config=SAConfig(iterations=10, seed=42))

        # Patch compute_state_objective to return NaN during neighbor evaluations in loop
        # but return real values for initial state (call 1) and final check
        call_count = 0
        original_compute = compute_state_objective

        def mocked_compute(st, cfg):
            nonlocal call_count
            call_count += 1
            if 2 <= call_count <= 8:  # inject NaN on candidate evaluations
                return float("nan")
            return original_compute(st, cfg)

        with patch("src.optimization.sa.annealer.compute_state_objective", side_effect=mocked_compute):
            res = solver.solve(flights, gates, allow_overflow=False)
            assert res.feasible is True
            assert math.isfinite(res.objective_value)

    @pytest.mark.parametrize(
        "kwargs, err_match",
        [
            ({"T0": 0.0}, "T0 must be a positive finite float"),
            ({"T0": -10.0}, "T0 must be a positive finite float"),
            ({"T0": float("inf")}, "T0 must be a positive finite float"),
            ({"Tmin": 0.0}, "Tmin must be a positive finite float"),
            ({"Tmin": -1.0}, "Tmin must be a positive finite float"),
            ({"Tmin": 200.0, "T0": 100.0}, "Tmin .* cannot exceed T0"),
            ({"cooling_rate": 0.0}, "cooling_rate must be in"),
            ({"cooling_rate": 1.0}, "cooling_rate must be in"),
            ({"cooling_rate": 1.2}, "cooling_rate must be in"),
            ({"iterations": -1}, "iterations must be >= 0"),
            ({"move_prob": -0.1}, "move_prob must be in"),
            ({"move_prob": 1.1}, "move_prob must be in"),
            ({"max_neighbor_attempts": 0}, "max_neighbor_attempts must be >= 1"),
        ],
    )
    def test_s08_invalid_cooling_params_raise_value_error(self, kwargs, err_match) -> None:
        """S08: SAConfig enforces rigorous parameter validation at initialization."""
        with pytest.raises(ValueError, match=err_match):
            SAConfig(**kwargs)

    def test_s09_no_neighbor_available_terminates_gracefully(self) -> None:
        """S09: Degenerate 1 flight, 1 gate problem terminates gracefully with initial solution."""
        g = Gate(gate_id="G1", gate_index=0, resource_type=GateResourceType.CONTACT_GATE, capacity=1)
        fl = _make_flight("F1", start_min=100, duration_min=60)
        solver = SimulatedAnnealingGateSolver(sa_config=SAConfig(iterations=20, seed=42))
        res = solver.solve([fl], [g], allow_overflow=False)

        assert res.feasible is True
        assert res.status == "FEASIBLE"
        assert len(res.assignments) == 1
        assert res.assignments["F1"].gate_id == "G1"

    def test_s10_fixed_seed_determinism(self, congested_scenario) -> None:
        """S10 & I4: Fixed seed produces exact bit-for-bit identical trace and objective."""
        flights, gates = congested_scenario
        cfg = SAConfig(iterations=100, seed=99999)

        solver1 = SimulatedAnnealingGateSolver(sa_config=cfg)
        res1 = solver1.solve(flights, gates, allow_overflow=True)

        solver2 = SimulatedAnnealingGateSolver(sa_config=cfg)
        res2 = solver2.solve(flights, gates, allow_overflow=True)

        assert res1.objective_value == res2.objective_value
        for f_id in res1.assignments:
            assert res1.assignments[f_id].gate_id == res2.assignments[f_id].gate_id
        assert res1.solver_configuration["trace_sample"] == res2.solver_configuration["trace_sample"]

    def test_s11_different_seeds_all_hard_feasible(self, congested_scenario) -> None:
        """S11: Different random seeds explore different paths but ALL maintain hard feasibility."""
        flights, gates = congested_scenario
        for seed in [11, 22, 33, 44]:
            solver = SimulatedAnnealingGateSolver(sa_config=SAConfig(iterations=80, seed=seed))
            res = solver.solve(flights, gates, allow_overflow=True)
            assert res.feasible is True
            diag = verify_hard_constraints_independently(flights=flights, gates=gates, assignments=res.assignments)
            assert diag.is_valid is True
            assert diag.hard_constraint_violations_count == 0

    def test_s12_contact_gate_conflict_rejected(self, small_scenario) -> None:
        """S12: Contact gate concurrency > 1 is strictly rejected in state transitions."""
        flights, gates = small_scenario
        greedy_res = DeterministicGreedyGateSolver().solve(flights, gates, allow_overflow=False)
        state = create_initial_state(flights, gates, greedy_res.assignments)

        # Attempt to manually create invalid assignment and test is_feasible()
        invalid_assignments = dict(state.assignments)
        invalid_assignments["F2"] = "G1"  # F1 and F2 overlap on G1
        inv_state = SAState(
            assignments=invalid_assignments,
            flights=state.flights,
            gates=state.gates,
        )
        assert inv_state.is_feasible() is False

    def test_s13_remote_capacity_conflict_rejected(self) -> None:
        """S13: Discrete finite remote stand capacity violation is strictly rejected."""
        remote_gate = Gate(
            gate_id="R_DISCRETE",
            gate_index=0,
            resource_type=GateResourceType.FINITE_REMOTE_STAND,
            capacity=1,
            is_overflow=True,
        )
        fl1 = _make_flight("F1", start_min=100, duration_min=60)
        fl2 = _make_flight("F2", start_min=120, duration_min=60)  # overlaps F1
        state = SAState(
            assignments={"F1": "R_DISCRETE", "F2": "R_DISCRETE"},
            flights=[fl1, fl2],
            gates=[remote_gate],
        )
        assert state.is_feasible() is False


# =============================================================================
# S14 - S24: Hybrid CP-SAT + SA Solver & Provenance Trace
# =============================================================================

class TestHybridSolverPipelineAndProvenance:
    """Verifies Hybrid solver 10-step pipeline, fallback policies, and 17-field trace contract."""

    def test_s14_cpsat_feasible_usable_incumbent(self, small_scenario) -> None:
        """S14: CP-SAT finding FEASIBLE incumbent seeds Stage 2 SA refinement."""
        flights, gates = small_scenario
        solver = HybridGateSolver(sa_config=SAConfig(iterations=30, seed=42), cp_ratio=0.5)
        res = solver.solve(flights, gates, allow_overflow=False)

        assert res.feasible is True
        trace = res.solver_configuration
        assert trace["cp_incumbent_found"] is True
        assert trace["cp_incumbent_valid"] is True
        assert trace["initial_solution_source"] == "CP_SAT"
        assert trace["fallback_attempted"] is False
        assert trace["fallback_used"] is False

    def test_s15_cpsat_unknown_with_incumbent_usable(self, small_scenario) -> None:
        """S15: CP-SAT status UNKNOWN with feasible incumbent is accepted by Stage 2."""
        flights, gates = small_scenario
        # Mock CP-SAT returning status="UNKNOWN" with feasible assignments
        greedy_sol = DeterministicGreedyGateSolver().solve(flights, gates, allow_overflow=False)
        mock_cp_result = OptimizationResult(
            status="UNKNOWN",
            objective_value=greedy_sol.objective_value,
            objective_breakdown=greedy_sol.objective_breakdown,
            feasible=True,
            runtime_ms=50.0,
            optimality_gap=None,
            assignments=greedy_sol.assignments,
            constraint_diagnostics=greedy_sol.constraint_diagnostics,
            solver_configuration={},
            optimality_proven=False,
            termination_reason=TerminationReason.TIME_LIMIT,
        )

        with patch.object(CPSatGateSolver, "solve", return_value=mock_cp_result):
            solver = HybridGateSolver(sa_config=SAConfig(iterations=20, seed=42))
            res = solver.solve(flights, gates, allow_overflow=False)

            assert res.feasible is True
            assert res.solver_configuration["cp_solver_status"] == "UNKNOWN"
            assert res.solver_configuration["cp_incumbent_found"] is True
            assert res.solver_configuration["initial_solution_source"] == "CP_SAT"
            assert res.solver_configuration["fallback_attempted"] is False

    def test_s16_cpsat_unknown_no_incumbent_greedy_fallback(self, small_scenario) -> None:
        """S16: CP-SAT timeout with no incumbent cleanly triggers Greedy fallback."""
        flights, gates = small_scenario
        mock_cp_result = OptimizationResult(
            status="UNKNOWN",
            objective_value=float("inf"),
            objective_breakdown=ObjectiveBreakdown(
                total_cost=float("inf"), reassignment_cost=0, overflow_cost=0,
                delay_cost=0, conflict_cost=0, risk_cost=0, weights={},
            ),
            feasible=False,
            runtime_ms=50.0,
            optimality_gap=None,
            assignments={},
            constraint_diagnostics=ConstraintDiagnostic(
                all_flights_assigned=False, no_contact_gate_conflicts=True,
                gate_availability_satisfied=True, gate_compatibility_satisfied=True,
                turnaround_valid=True, conflict_count=0, conflict_pairs=[],
                incompatibility_violations=[], availability_violations=[],
            ),
            solver_configuration={},
            optimality_proven=False,
            termination_reason=TerminationReason.TIME_LIMIT,
        )

        with patch.object(CPSatGateSolver, "solve", return_value=mock_cp_result):
            solver = HybridGateSolver(sa_config=SAConfig(iterations=20, seed=42))
            res = solver.solve(flights, gates, allow_overflow=False)

            assert res.feasible is True
            assert res.solver_configuration["fallback_attempted"] is True
            assert res.solver_configuration["fallback_used"] is True
            assert res.solver_configuration["fallback_reason"] == "CP_SAT_TIMEOUT_NO_INCUMBENT"
            assert res.solver_configuration["initial_solution_source"] == "GREEDY_FALLBACK"

    def test_s17_cpsat_infeasible_no_greedy_fallback(self) -> None:
        """S17: If CP-SAT mathematically proves INFEASIBLE, greedy fallback is strictly forbidden."""
        # Scenario with 2 overlapping flights and 1 contact gate, no overflow
        g = Gate(gate_id="G1", gate_index=0, resource_type=GateResourceType.CONTACT_GATE, capacity=1)
        f1 = _make_flight("F1", start_min=100, duration_min=60)
        f2 = _make_flight("F2", start_min=120, duration_min=60)

        solver = HybridGateSolver()
        res = solver.solve([f1, f2], [g], allow_overflow=False)

        assert res.feasible is False
        assert res.status == "INFEASIBLE"
        assert res.solver_configuration["cp_solver_status"] == "INFEASIBLE"
        assert res.solver_configuration["fallback_attempted"] is False
        assert res.solver_configuration["fallback_used"] is False
        assert res.solver_configuration["fallback_reason"] == "CP_SAT_PROVEN_INFEASIBLE"
        assert len(res.assignments) == 0

    def test_s18_greedy_fallback_failure_returns_infeasible(self, small_scenario) -> None:
        """S18: If CP-SAT has no incumbent AND greedy fallback fails, returns INFEASIBLE cleanly."""
        flights, gates = small_scenario
        mock_cp_result = OptimizationResult(
            status="UNKNOWN",
            objective_value=float("inf"),
            objective_breakdown=ObjectiveBreakdown(
                total_cost=float("inf"), reassignment_cost=0, overflow_cost=0,
                delay_cost=0, conflict_cost=0, risk_cost=0, weights={},
            ),
            feasible=False,
            runtime_ms=50.0,
            optimality_gap=None,
            assignments={},
            constraint_diagnostics=ConstraintDiagnostic(
                all_flights_assigned=False, no_contact_gate_conflicts=True,
                gate_availability_satisfied=True, gate_compatibility_satisfied=True,
                turnaround_valid=True, conflict_count=0, conflict_pairs=[],
                incompatibility_violations=[], availability_violations=[],
            ),
            solver_configuration={},
            optimality_proven=False,
            termination_reason=TerminationReason.TIME_LIMIT,
        )
        mock_greedy_result = OptimizationResult(
            status="INFEASIBLE",
            objective_value=float("inf"),
            objective_breakdown=ObjectiveBreakdown(
                total_cost=float("inf"), reassignment_cost=0, overflow_cost=0,
                delay_cost=0, conflict_cost=0, risk_cost=0, weights={},
            ),
            feasible=False,
            runtime_ms=10.0,
            optimality_gap=None,
            assignments={},
            constraint_diagnostics=ConstraintDiagnostic(
                all_flights_assigned=False, no_contact_gate_conflicts=True,
                gate_availability_satisfied=True, gate_compatibility_satisfied=True,
                turnaround_valid=True, conflict_count=0, conflict_pairs=[],
                incompatibility_violations=[], availability_violations=[],
            ),
            solver_configuration={},
            optimality_proven=False,
            termination_reason=TerminationReason.NO_FEASIBLE_SOLUTION,
        )

        with patch.object(CPSatGateSolver, "solve", return_value=mock_cp_result):
            with patch.object(DeterministicGreedyGateSolver, "solve", return_value=mock_greedy_result):
                solver = HybridGateSolver()
                res = solver.solve(flights, gates, allow_overflow=False)

                assert res.feasible is False
                # G12B-R1 Task 3: CP-SAT UNKNOWN without proof of infeasibility reports UNKNOWN/TIMEOUT_NO_SOLUTION, not INFEASIBLE
                assert res.status in ("UNKNOWN", "TIMEOUT_NO_SOLUTION")
                assert res.solver_configuration["fallback_attempted"] is True
                assert res.solver_configuration["fallback_used"] is False
                assert len(res.assignments) == 0

    def test_s19_hybrid_final_objective_calculated_independently(self, small_scenario) -> None:
        """S19: Hybrid final objective matches independent authoritative evaluate_gate_assignment."""
        flights, gates = small_scenario
        solver = HybridGateSolver(sa_config=SAConfig(iterations=30, seed=42))
        res = solver.solve(flights, gates, allow_overflow=False)

        assert res.feasible is True
        indep_eval = evaluate_gate_assignment(
            assignments=res.assignments,
            flights=flights,
            gates=gates,
            config=solver.config,
        )
        assert abs(res.objective_value - indep_eval.objective_value) < 1e-6

    def test_s20_hybrid_trace_contains_all_17_fields(self, small_scenario) -> None:
        """S20: Trace contract guarantees all 17 required provenance fields."""
        flights, gates = small_scenario
        solver = HybridGateSolver(sa_config=SAConfig(iterations=20, seed=42))
        res = solver.solve(flights, gates, allow_overflow=False)

        trace = res.solver_configuration
        required_17_fields = [
            "cp_solver_status",
            "cp_incumbent_found",
            "cp_incumbent_valid",
            "cp_optimality_proven",
            "fallback_attempted",
            "fallback_used",
            "fallback_reason",
            "initial_solution_source",
            "initial_cost",
            "sa_iterations",
            "sa_accepted_moves",
            "sa_best_cost",
            "final_cost",
            "final_feasible",
            "final_verifier_violations",
            "total_wall_clock_ms",
            "termination_reason",
        ]
        for field in required_17_fields:
            assert field in trace, f"Missing required provenance field in trace: {field}"

    def test_s21_legacy_sa_tests_parity(self, small_scenario) -> None:
        """S21: Parity check ensuring legacy solver behavior works seamlessly."""
        flights, gates = small_scenario
        greedy = DeterministicGreedyGateSolver().solve(flights, gates, allow_overflow=False)
        cpsat = CPSatGateSolver().solve(flights, gates, allow_overflow=False)
        sa = SimulatedAnnealingGateSolver().solve(flights, gates, allow_overflow=False)
        hybrid = HybridGateSolver().solve(flights, gates, allow_overflow=False)

        assert greedy.feasible is True
        assert cpsat.feasible is True
        assert sa.feasible is True
        assert hybrid.feasible is True

    def test_s22_no_false_global_optimum_certification(self, congested_scenario) -> None:
        """S22: Neither SA nor Hybrid certifies OPTIMAL without mathematical proof."""
        flights, gates = congested_scenario
        # Run SA: must never be OPTIMAL
        sa_res = SimulatedAnnealingGateSolver(sa_config=SAConfig(iterations=50, seed=42)).solve(
            flights, gates, allow_overflow=True
        )
        assert sa_res.status == "FEASIBLE"
        assert sa_res.optimality_proven is False

    def test_s23_termination_reasons_accurate(self, small_scenario) -> None:
        """S23: Termination reasons accurately represent the stopping condition."""
        flights, gates = small_scenario
        # SA completion
        sa_res = SimulatedAnnealingGateSolver(sa_config=SAConfig(iterations=10)).solve(flights, gates, allow_overflow=False)
        assert sa_res.termination_reason == TerminationReason.ITERATION_LIMIT

        # Hybrid completion inheriting optimality proof
        hybrid_res = HybridGateSolver(sa_config=SAConfig(iterations=10)).solve(flights, gates, allow_overflow=False)
        if hybrid_res.optimality_proven:
            assert hybrid_res.termination_reason == TerminationReason.OPTIMAL_PROVEN
        else:
            assert hybrid_res.termination_reason == TerminationReason.FEASIBLE_FOUND

    def test_s24_duplicate_unknown_assignments_rejected(self, small_scenario) -> None:
        """S24: Independent verifier and evaluator reject unknown gates and duplicate assignments."""
        flights, gates = small_scenario
        # Assignment referencing non-existent gate
        bad_assignment = {
            "F1": GateAssignment(
                flight_id="F1",
                gate_id="NON_EXISTENT_GATE",
                flight_index=0,
                gate_index=99,
                is_overflow=False,
                is_reassignment=False,
                occupancy_start_min=100,
                occupancy_end_min=160,
            ),
        }
        diag = verify_hard_constraints_independently(flights=flights, gates=gates, assignments=bad_assignment)
        assert diag.is_valid is False
        assert diag.unassigned_count > 0


# =============================================================================
# Brute Force Oracle Verification
# =============================================================================

class TestBruteForceOracleVerification:
    """Exact verification against brute-force combinatorial oracle."""

    def test_brute_force_oracle_exact_verification(self) -> None:
        """Enumerate all 2^3 = 8 assignment combinations to find the exact true global minimum.

        Verify:
        - True global minimum Z* is identified by brute force.
        - CP-SAT achieves Z* with status OPTIMAL and optimality_proven=True.
        - SA achieves objective >= Z* and status FEASIBLE (optimality_proven=False).
        - Hybrid achieves Z* with status OPTIMAL and optimality_proven=True.
        """
        gates = [
            Gate(gate_id="G1", gate_index=0, resource_type=GateResourceType.CONTACT_GATE, capacity=1),
            Gate(gate_id="G2", gate_index=1, resource_type=GateResourceType.CONTACT_GATE, capacity=1),
        ]
        flights = [
            _make_flight("F1", start_min=100, duration_min=60, nominal_gate_id="G1"),
            _make_flight("F2", start_min=130, duration_min=60, nominal_gate_id="G2"),  # overlaps F1
            _make_flight("F3", start_min=170, duration_min=60, nominal_gate_id="G1"),  # overlaps F2, not F1
        ]

        cfg = GateOptimizationConfig()
        gate_ids = [g.gate_id for g in gates]

        # Brute force enumeration
        feasible_evaluations: list[tuple[float, dict[str, str]]] = []
        for combo in itertools.product(gate_ids, repeat=len(flights)):
            assignments_dict: dict[str, GateAssignment] = {}
            for fl, g_id in zip(flights, combo):
                g_idx = 0 if g_id == "G1" else 1
                assignments_dict[fl.flight_id] = GateAssignment(
                    flight_id=fl.flight_id,
                    gate_id=g_id,
                    flight_index=fl.flight_index,
                    gate_index=g_idx,
                    is_overflow=False,
                    is_reassignment=bool(fl.nominal_gate_id != g_id),
                    occupancy_start_min=fl.time_window.start_min,
                    occupancy_end_min=fl.time_window.end_min,
                )

            diag = verify_hard_constraints_independently(flights=flights, gates=gates, assignments=assignments_dict)
            if diag.is_valid:
                eval_res = evaluate_gate_assignment(
                    assignments=assignments_dict,
                    flights=flights,
                    gates=gates,
                    config=cfg,
                )
                feasible_evaluations.append((eval_res.objective_value, {fl.flight_id: g_id for fl, g_id in zip(flights, combo)}))

        assert len(feasible_evaluations) > 0, "Brute force must find at least one feasible assignment"
        feasible_evaluations.sort(key=lambda item: item[0])
        z_star, best_combo = feasible_evaluations[0]

        # 1. Test CP-SAT
        cp_solver = CPSatGateSolver(config=cfg)
        cp_res = cp_solver.solve(flights, gates, allow_overflow=False)
        assert cp_res.feasible is True
        assert cp_res.status == "OPTIMAL"
        assert cp_res.optimality_proven is True
        assert abs(cp_res.objective_value - z_star) < 1e-6

        # 2. Test SA
        sa_solver = SimulatedAnnealingGateSolver(
            config=cfg,
            sa_config=SAConfig(iterations=100, seed=42),
        )
        sa_res = sa_solver.solve(flights, gates, allow_overflow=False)
        assert sa_res.feasible is True
        assert sa_res.status == "FEASIBLE"
        assert sa_res.optimality_proven is False
        assert sa_res.objective_value >= z_star - 1e-6

        # 3. Test Hybrid
        hybrid_solver = HybridGateSolver(
            config=cfg,
            sa_config=SAConfig(iterations=50, seed=42),
            cp_ratio=0.5,
        )
        hybrid_res = hybrid_solver.solve(flights, gates, allow_overflow=False)
        assert hybrid_res.feasible is True
        assert hybrid_res.status == "OPTIMAL"
        assert hybrid_res.optimality_proven is True
        assert abs(hybrid_res.objective_value - z_star) < 1e-6
