"""Two-Stage Hybrid CP-SAT + Simulated Annealing Gate Assignment Solver.

Protocol: docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md
          Aeolus Dual Core Architecture Protocol V2 - Phase P8
Architecture:
1. Stage 1: Fast exact Constraint Programming via OR-Tools CP-SAT (budgeted to a fraction
   of total time limit) or deterministic Greedy fallback to obtain a guaranteed hard-feasible
   initial incumbent.
2. Stage 2: Metaheuristic soft-objective neighborhood search via Simulated Annealing
   starting from the Stage 1 incumbent.
3. Guaranteed Feasibility:
   - Solution is independently certified by verify_hard_constraints_independently.
   - Monotonicity: best objective is never worse than Stage 1 incumbent.
4. Deterministic Reproducibility:
   - Controlled via random_seed and single-worker CP-SAT search.
"""

from __future__ import annotations

from dataclasses import replace
import math
import time
from typing import Any, Mapping, Sequence

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
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver


class HybridGateSolver:
    """Two-Stage Hybrid Gate Assignment Solver (CP-SAT/Greedy warm start -> SA refinement).

    Protocol: Phase P03 Stage Pipeline:
    1. Validate scenario.
    2. Build CP-SAT model.
    3. Run CP-SAT within configured fraction of time budget.
    4. Validate CP-SAT incumbent if any.
    5. If no valid incumbent and CP-SAT did not prove infeasibility: try Greedy fallback.
    6. Validate fallback incumbent.
    7. Run SA refinement starting from incumbent.
    8. Validate final assignment independently.
    9. Compute objective independently.
    10. Return stage-level diagnostics & hybrid provenance trace.
    """

    def __init__(
        self,
        config: GateOptimizationConfig | None = None,
        sa_config: SAConfig | None = None,
        cp_ratio: float = 0.5,
    ) -> None:
        self.config = config or GateOptimizationConfig()
        self.sa_config = sa_config or SAConfig()
        if not (0.0 < cp_ratio < 1.0):
            raise ValueError(f"cp_ratio must be strictly between 0 and 1, got {cp_ratio}")
        self.cp_ratio = float(cp_ratio)

    def solve(
        self,
        flights: Sequence[Flight],
        gates: Sequence[Gate],
        *,
        allow_overflow: bool = True,
    ) -> OptimizationResult:
        """Solve gate assignment problem using two-stage CP-SAT + SA metaheuristic.

        Args:
            flights: Sequence of Flight domain entities.
            gates: Sequence of Gate domain entities.
            allow_overflow: Whether to allow fallback overflow apron stand.

        Returns:
            OptimizationResult evaluated by authoritative common evaluator.
        """
        t0 = time.perf_counter()

        # Step 1: Handle trivial zero-flight case
        if len(flights) == 0:
            return evaluate_gate_assignment(
                assignments={},
                flights=flights,
                gates=gates,
                config=self.config,
                runtime_ms=0.0,
                solver_status="OPTIMAL",
                solver_name="HybridCPSatSA",
                termination_reason=TerminationReason.OPTIMAL_PROVEN,
                optimality_proven=True,
            )

        # Prepare working gate list
        gate_list = list(gates)
        has_overflow = any(g.is_overflow for g in gate_list)
        if allow_overflow and not has_overflow:
            if getattr(self.config, "allow_unbounded_overflow", True):
                overflow_gate = Gate(
                    gate_id="OVERFLOW_APRON",
                    gate_index=len(gate_list),
                    resource_type=GateResourceType.UNBOUNDED_OVERFLOW_APRON,
                    capacity=math.inf,
                    is_overflow=True,
                )
                gate_list.append(overflow_gate)

        # ---------------------------------------------------------------------
        # Step 2 & 3: Run Stage 1 CP-SAT within configured budget
        # ---------------------------------------------------------------------
        cp_budget_seconds = max(0.01, self.config.time_limit_seconds * self.cp_ratio)
        cp_config = replace(self.config, time_limit_seconds=cp_budget_seconds)
        cp_solver = CPSatGateSolver(config=cp_config)
        t_cp0 = time.perf_counter()
        cp_result = cp_solver.solve(flights, gate_list, allow_overflow=allow_overflow)
        cp_wall_clock_ms = (time.perf_counter() - t_cp0) * 1000.0

        cp_solver_status = cp_result.status
        cp_incumbent_found = bool(cp_result.feasible and len(cp_result.assignments) == len(flights))
        cp_optimality_proven = bool(cp_result.optimality_proven)

        # Step 4: Validate CP-SAT incumbent if found
        cp_incumbent_valid = False
        if cp_incumbent_found:
            cp_diag = verify_hard_constraints_independently(
                flights=flights,
                gates=gate_list,
                assignments=cp_result.assignments,
            )
            cp_incumbent_valid = bool(cp_diag.is_valid)

        # Step 5 & 6: Determine incumbent or fallback policy
        fallback_attempted = False
        fallback_used = False
        fallback_reason: str | None = None
        initial_solution_source: str = "NONE"
        initial_cost: float = float("inf")
        incumbent_assignments: dict[str, GateAssignment] = {}

        if cp_incumbent_found and cp_incumbent_valid:
            incumbent_assignments = dict(cp_result.assignments)
            initial_solution_source = "CP_SAT"
            initial_cost = float(cp_result.objective_value)
        elif cp_solver_status == "INFEASIBLE":
            # Section VII Rule: If CP-SAT mathematically proved INFEASIBLE under same constraints,
            # do NOT attempt greedy fallback. The problem is definitively infeasible.
            fallback_attempted = False
            fallback_used = False
            fallback_reason = "CP_SAT_PROVEN_INFEASIBLE"
            total_wall_clock_ms = (time.perf_counter() - t0) * 1000.0
            hybrid_trace = {
                "cp_solver_status": cp_solver_status,
                "cp_incumbent_found": False,
                "cp_incumbent_valid": False,
                "cp_optimality_proven": False,
                "fallback_attempted": False,
                "fallback_used": False,
                "fallback_reason": fallback_reason,
                "initial_solution_source": "NONE",
                "initial_cost": float("inf"),
                "sa_iterations": 0,
                "sa_accepted_moves": 0,
                "sa_best_cost": float("inf"),
                "final_cost": float("inf"),
                "final_feasible": False,
                "final_verifier_violations": cp_result.constraint_diagnostics.hard_constraint_violations_count,
                "total_wall_clock_ms": total_wall_clock_ms,
                "stage1_wall_clock_ms": cp_wall_clock_ms,
                "stage2_wall_clock_ms": 0.0,
                "termination_reason": TerminationReason.PROVEN_INFEASIBLE.value,
            }
            return OptimizationResult(
                status="INFEASIBLE",
                objective_value=float("inf"),
                objective_breakdown=cp_result.objective_breakdown,
                feasible=False,
                runtime_ms=total_wall_clock_ms,
                optimality_gap=None,
                assignments={},
                constraint_diagnostics=cp_result.constraint_diagnostics,
                solver_configuration={
                    **self.config.to_dict(),
                    **hybrid_trace,
                },
                termination_reason=TerminationReason.PROVEN_INFEASIBLE,
            )
        else:
            # CP-SAT timed out or produced no valid incumbent -> attempt greedy fallback
            fallback_attempted = True
            fallback_reason = "CP_SAT_TIMEOUT_NO_INCUMBENT"
            greedy_solver = DeterministicGreedyGateSolver(config=self.config)
            greedy_result = greedy_solver.solve(flights, gate_list, allow_overflow=allow_overflow)

            if greedy_result.feasible:
                greedy_diag = verify_hard_constraints_independently(
                    flights=flights,
                    gates=gate_list,
                    assignments=greedy_result.assignments,
                )
                if greedy_diag.is_valid:
                    fallback_used = True
                    initial_solution_source = "GREEDY_FALLBACK"
                    incumbent_assignments = dict(greedy_result.assignments)
                    initial_cost = float(greedy_result.objective_value)
                    cp_optimality_proven = False

            if not fallback_used:
                # Both CP-SAT and fallback failed
                total_wall_clock_ms = (time.perf_counter() - t0) * 1000.0
                hybrid_trace = {
                    "cp_solver_status": cp_solver_status,
                    "cp_incumbent_found": False,
                    "cp_incumbent_valid": False,
                    "cp_optimality_proven": False,
                    "fallback_attempted": True,
                    "fallback_used": False,
                    "fallback_reason": fallback_reason,
                    "initial_solution_source": "NONE",
                    "initial_cost": float("inf"),
                    "sa_iterations": 0,
                    "sa_accepted_moves": 0,
                    "sa_best_cost": float("inf"),
                    "final_cost": float("inf"),
                    "final_feasible": False,
                    "final_verifier_violations": greedy_result.constraint_diagnostics.hard_constraint_violations_count,
                    "total_wall_clock_ms": total_wall_clock_ms,
                    "stage1_wall_clock_ms": cp_wall_clock_ms,
                    "stage2_wall_clock_ms": 0.0,
                    "termination_reason": TerminationReason.NO_FEASIBLE_SOLUTION.value,
                }
                return OptimizationResult(
                    status="INFEASIBLE",
                    objective_value=float("inf"),
                    objective_breakdown=greedy_result.objective_breakdown,
                    feasible=False,
                    runtime_ms=total_wall_clock_ms,
                    optimality_gap=None,
                    assignments={},
                    constraint_diagnostics=greedy_result.constraint_diagnostics,
                    solver_configuration={
                        **self.config.to_dict(),
                        **hybrid_trace,
                    },
                    termination_reason=TerminationReason.NO_FEASIBLE_SOLUTION,
                )

        # ---------------------------------------------------------------------
        # Step 7: Run SA refinement starting from validated incumbent
        # ---------------------------------------------------------------------
        sa_solver = SimulatedAnnealingGateSolver(
            config=self.config,
            sa_config=self.sa_config,
        )
        t_sa0 = time.perf_counter()
        sa_result = sa_solver.solve(
            flights=flights,
            gates=gate_list,
            initial_assignments=incumbent_assignments,
            allow_overflow=allow_overflow,
        )
        sa_wall_clock_ms = (time.perf_counter() - t_sa0) * 1000.0

        # Step 8: Validate final assignment independently
        final_diag = verify_hard_constraints_independently(
            flights=flights,
            gates=gate_list,
            assignments=sa_result.assignments,
        )
        final_feasible = bool(final_diag.is_valid and len(sa_result.assignments) == len(flights))

        total_wall_clock_ms = (time.perf_counter() - t0) * 1000.0

        # Step 9: Compute objective independently
        final_eval = evaluate_gate_assignment(
            assignments=sa_result.assignments,
            flights=flights,
            gates=gate_list,
            config=self.config,
            runtime_ms=total_wall_clock_ms,
            solver_status="FEASIBLE" if final_feasible else "INFEASIBLE",
            solver_name="HybridCPSatSA",
        )

        # Step 10: Determine status, optimality inheritance, and trace contract
        # Proof inheritance: ONLY if Stage 1 CP-SAT proved OPTIMAL and SA preserved the cost
        has_optimality_proof = (
            final_feasible
            and cp_optimality_proven
            and abs(final_eval.objective_value - initial_cost) < 1e-9
        )

        if has_optimality_proof:
            hybrid_status = "OPTIMAL"
            term_reason = TerminationReason.OPTIMAL_PROVEN
            opt_gap = 0.0
        elif final_feasible:
            hybrid_status = "FEASIBLE"
            term_reason = TerminationReason.FEASIBLE_FOUND
            opt_gap = None
        else:
            hybrid_status = "INFEASIBLE"
            term_reason = TerminationReason.NO_FEASIBLE_SOLUTION
            opt_gap = None

        hybrid_trace = {
            "cp_solver_status": cp_solver_status,
            "cp_incumbent_found": cp_incumbent_found,
            "cp_incumbent_valid": cp_incumbent_valid,
            "cp_optimality_proven": cp_optimality_proven,
            "fallback_attempted": fallback_attempted,
            "fallback_used": fallback_used,
            "fallback_reason": fallback_reason,
            "initial_solution_source": initial_solution_source,
            "initial_cost": initial_cost,
            "sa_iterations": self.sa_config.iterations,
            "sa_accepted_moves": sa_result.solver_configuration.get("accepted_moves", 0),
            "sa_best_cost": float(sa_result.objective_value),
            "final_cost": float(final_eval.objective_value),
            "final_feasible": final_feasible,
            "final_verifier_violations": final_diag.hard_constraint_violations_count,
            "total_wall_clock_ms": total_wall_clock_ms,
            "stage1_wall_clock_ms": cp_wall_clock_ms,
            "stage2_wall_clock_ms": sa_wall_clock_ms,
            "termination_reason": term_reason.value if hasattr(term_reason, "value") else str(term_reason),
        }

        return OptimizationResult(
            status=hybrid_status,
            objective_value=final_eval.objective_value,
            objective_breakdown=final_eval.objective_breakdown,
            feasible=final_feasible,
            runtime_ms=total_wall_clock_ms,
            optimality_gap=opt_gap,
            assignments=dict(sa_result.assignments),
            constraint_diagnostics=final_diag,
            solver_configuration={
                **self.config.to_dict(),
                "solver_name": "HybridCPSatSA",
                "sa_config": self.sa_config.to_dict(),
                **hybrid_trace,
            },
            raw_solver_status=cp_solver_status,
            optimality_proven=has_optimality_proof,
            termination_reason=term_reason,
        )
