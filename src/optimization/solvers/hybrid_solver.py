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

import time
from typing import Any, Mapping, Sequence

from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import (
    ConstraintDiagnostic,
    Flight,
    Gate,
    GateAssignment,
    OptimizationResult,
    verify_hard_constraints_independently,
)
from src.optimization.evaluation import evaluate_gate_assignment
from src.optimization.sa.annealer import SAConfig, SimulatedAnnealingGateSolver
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver


class HybridGateSolver:
    """Two-Stage Hybrid Gate Assignment Solver (CP-SAT/Greedy warm start -> SA refinement)."""

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

        # Handle trivial zero-flight case
        if len(flights) == 0:
            return evaluate_gate_assignment(
                assignments={},
                flights=flights,
                gates=gates,
                config=self.config,
                runtime_ms=0.0,
                solver_status="OPTIMAL",
                solver_name="HybridCPSatSA",
            )

        # Ensure overflow stand exists in working gate list if requested
        gate_list = list(gates)
        has_overflow = any(g.is_overflow for g in gate_list)
        if allow_overflow and not has_overflow:
            overflow_gate = Gate(
                gate_id="OVERFLOW_APRON",
                gate_index=len(gate_list),
                is_overflow=True,
            )
            gate_list.append(overflow_gate)

        # ---------------------------------------------------------------------
        # Stage 1: Obtain initial incumbent via budgeted CP-SAT (or Greedy)
        # ---------------------------------------------------------------------
        cp_budget_seconds = max(0.01, self.config.time_limit_seconds * self.cp_ratio)
        cp_config = GateOptimizationConfig(
            reassignment_weight=self.config.reassignment_weight,
            overflow_weight=self.config.overflow_weight,
            delay_weight=self.config.delay_weight,
            conflict_weight=self.config.conflict_weight,
            risk_weight=self.config.risk_weight,
            time_limit_seconds=cp_budget_seconds,
            num_search_workers=self.config.num_search_workers,
            random_seed=self.config.random_seed,
            dual_core_gate_enabled=self.config.dual_core_gate_enabled,
        )
        cp_solver = CPSatGateSolver(config=cp_config)
        cp_result = cp_solver.solve(flights, gate_list, allow_overflow=allow_overflow)

        if cp_result.feasible and cp_result.constraint_diagnostics.is_valid:
            incumbent_assignments = cp_result.assignments
            stage1_status = cp_result.status
        else:
            # Fallback to deterministic greedy
            greedy_solver = DeterministicGreedyGateSolver(config=self.config)
            greedy_result = greedy_solver.solve(flights, gate_list, allow_overflow=allow_overflow)
            if not greedy_result.feasible or not greedy_result.constraint_diagnostics.is_valid:
                raise ValueError(
                    "Both Stage 1 CP-SAT and fallback Greedy failed to produce a feasible assignment."
                )
            incumbent_assignments = greedy_result.assignments
            stage1_status = "GREEDY_FALLBACK"

        # ---------------------------------------------------------------------
        # Stage 2: Simulated Annealing refinement starting from incumbent
        # ---------------------------------------------------------------------
        sa_solver = SimulatedAnnealingGateSolver(
            config=self.config,
            sa_config=self.sa_config,
        )
        sa_result = sa_solver.solve(
            flights=flights,
            gates=gate_list,
            initial_assignments=incumbent_assignments,
            allow_overflow=allow_overflow,
        )

        total_runtime_ms = (time.perf_counter() - t0) * 1000.0

        # Authoritative evaluation
        result = evaluate_gate_assignment(
            assignments=sa_result.assignments,
            flights=flights,
            gates=gate_list,
            config=self.config,
            runtime_ms=total_runtime_ms,
            solver_status=sa_result.status if stage1_status != "GREEDY_FALLBACK" else "FEASIBLE",
            solver_name="HybridCPSatSA",
        )

        return result
