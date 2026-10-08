"""Simulated Annealing Gate Assignment Solver.

Protocol: docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md
          docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 19 (Stage 9)
Specification:
- Externalized configuration: T0, Tmin, cooling_rate, iterations, seed.
- Step logging: iteration, temperature, objective, accepted moves, best objective, feasibility status.
- Standard acceptance criterion: if delta <= 0 accept, else accept with prob exp(-delta / T).
- Guaranteed hard-feasibility: best-so-far solution is always hard-feasible.
- Objective monotonicity: best-so-far objective is never worse than initial solution.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import random
import time
from typing import Any, Mapping, Sequence

from src.models.probabilistic.contracts import PREDETERMINED_DEPLOYMENT_SEED
from src.optimization.config import GateOptimizationConfig, compute_improvement_pct
from src.optimization.domain import (
    Flight,
    Gate,
    GateAssignment,
    GateResourceType,
    OptimizationResult,
    TerminationReason,
    verify_hard_constraints_independently,
)
from src.optimization.evaluation import evaluate_gate_assignment
from src.optimization.sa.neighborhood import generate_neighbor
from src.optimization.sa.objective import compute_state_objective
from src.optimization.sa.state import SAState, create_initial_state
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver


@dataclass(frozen=True)
class SAConfig:
    """Externalized configuration parameters for Simulated Annealing.

    All parameters are externalized without hardcoding inside the solver.
    """

    T0: float = 100.0
    Tmin: float = 0.01
    cooling_rate: float = 0.95
    iterations: int = 1000
    seed: int = PREDETERMINED_DEPLOYMENT_SEED
    move_prob: float = 0.6
    max_neighbor_attempts: int = 50

    def __post_init__(self) -> None:
        if not math.isfinite(self.T0) or self.T0 <= 0:
            raise ValueError(f"T0 must be a positive finite float, got {self.T0}")
        if not math.isfinite(self.Tmin) or self.Tmin <= 0:
            raise ValueError(f"Tmin must be a positive finite float, got {self.Tmin}")
        if self.Tmin > self.T0:
            raise ValueError(f"Tmin ({self.Tmin}) cannot exceed T0 ({self.T0})")
        if not math.isfinite(self.cooling_rate) or not (0.0 < self.cooling_rate < 1.0):
            raise ValueError(f"cooling_rate must be in (0.0, 1.0), got {self.cooling_rate}")
        if self.iterations < 0:
            raise ValueError(f"iterations must be >= 0, got {self.iterations}")
        if not math.isfinite(self.move_prob) or not (0.0 <= self.move_prob <= 1.0):
            raise ValueError(f"move_prob must be in [0.0, 1.0], got {self.move_prob}")
        if self.max_neighbor_attempts < 1:
            raise ValueError(f"max_neighbor_attempts must be >= 1, got {self.max_neighbor_attempts}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SALogEntry:
    """Trace entry recorded at each iteration of Simulated Annealing."""

    iteration: int
    temperature: float
    objective: float
    accepted_moves: int
    best_objective: float
    feasibility_status: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SimulatedAnnealingGateSolver:
    """Simulated Annealing Gate Assignment Metaheuristic Solver."""

    def __init__(
        self,
        config: GateOptimizationConfig | None = None,
        sa_config: SAConfig | None = None,
    ) -> None:
        self.config = config or GateOptimizationConfig()
        self.sa_config = sa_config or SAConfig()

    def solve(
        self,
        flights: Sequence[Flight],
        gates: Sequence[Gate],
        *,
        initial_assignments: Mapping[str, GateAssignment] | None = None,
        allow_overflow: bool = True,
    ) -> OptimizationResult:
        """Execute Simulated Annealing starting from a validated feasible initial assignment.

        Args:
            flights: Sequence of Flight entities.
            gates: Sequence of Gate entities.
            initial_assignments: Optional pre-existing assignments. If None, generated via greedy.
            allow_overflow: Allow remote stand fallback.

        Returns:
            OptimizationResult evaluated by the authoritative common evaluator.
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
                solver_status="FEASIBLE",
                solver_name="SimulatedAnnealing",
                termination_reason=TerminationReason.FEASIBLE_FOUND,
            )

        # 1. Obtain or validate initial feasible assignment
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

        if initial_assignments is None:
            # Generate deterministic greedy solution as proven feasible initial seed
            greedy_solver = DeterministicGreedyGateSolver(config=self.config)
            greedy_result = greedy_solver.solve(flights, gate_list, allow_overflow=allow_overflow)
            if not greedy_result.feasible or not greedy_result.constraint_diagnostics.is_valid:
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                return OptimizationResult(
                    status="INFEASIBLE",
                    objective_value=float("inf"),
                    objective_breakdown=greedy_result.objective_breakdown,
                    feasible=False,
                    runtime_ms=elapsed_ms,
                    optimality_gap=None,
                    assignments={},
                    constraint_diagnostics=greedy_result.constraint_diagnostics,
                    solver_configuration={
                        **self.config.to_dict(),
                        "sa_config": self.sa_config.to_dict(),
                    },
                    termination_reason=TerminationReason.NO_FEASIBLE_SOLUTION,
                )
            init_assignments = greedy_result.assignments
        else:
            init_assignments = dict(initial_assignments)

        # Build validated feasible initial state
        curr_state = create_initial_state(
            flights=flights,
            gates=gate_list,
            initial_assignments=init_assignments,
        )

        initial_obj = compute_state_objective(curr_state, self.config)
        curr_obj = initial_obj
        best_state = curr_state.copy()
        best_obj = curr_obj

        rng = random.Random(self.sa_config.seed)
        accepted_moves = 0

        # Step 7: Record trace
        trace: list[SALogEntry] = [
            SALogEntry(
                iteration=0,
                temperature=self.sa_config.T0,
                objective=curr_obj,
                accepted_moves=0,
                best_objective=best_obj,
                feasibility_status=True,
            )
        ]

        # Simulated Annealing Loop
        for k in range(1, self.sa_config.iterations + 1):
            # Geometric cooling schedule
            temp = max(
                self.sa_config.Tmin,
                self.sa_config.T0 * (self.sa_config.cooling_rate ** (k - 1)),
            )

            # Generate candidate neighbor
            cand_state = generate_neighbor(
                curr_state,
                rng,
                move_prob=self.sa_config.move_prob,
                max_attempts=self.sa_config.max_neighbor_attempts,
            )

            if cand_state is not None:
                # Invariant I3: Accepted candidate must strictly satisfy hard constraints
                if not cand_state.is_feasible():
                    continue

                try:
                    cand_obj = compute_state_objective(cand_state, self.config)
                except Exception:
                    cand_obj = float("nan")

                # S07: Reject non-finite (NaN, inf) objective values
                if not math.isfinite(cand_obj):
                    accept = False
                else:
                    delta = cand_obj - curr_obj
                    # Step 5: Standard simulated annealing acceptance criterion
                    if delta <= 0:
                        accept = True
                    else:
                        if temp <= 1e-12:
                            prob = 0.0
                        else:
                            exponent = -delta / temp
                            prob = math.exp(exponent) if exponent > -700.0 else 0.0
                        accept = rng.random() < prob

                if accept:
                    curr_state = cand_state
                    curr_obj = cand_obj
                    accepted_moves += 1

                    if curr_obj < best_obj:
                        best_state = curr_state.copy()
                        best_obj = curr_obj

            trace.append(
                SALogEntry(
                    iteration=k,
                    temperature=temp,
                    objective=curr_obj,
                    accepted_moves=accepted_moves,
                    best_objective=best_obj,
                    feasibility_status=True,
                )
            )

        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        # Invariant I1: Best-so-far assignment is strictly verified
        assert best_state.is_feasible(), "Invariant I1: SA best_state must be hard-feasible"

        # Invariant I2: Objective never worse than initial solution
        assert best_obj <= initial_obj + 1e-9, (
            f"Invariant I2: SA best objective ({best_obj:.4f}) is worse than initial ({initial_obj:.4f})"
        )

        # Invariant I9: Recomputed objective matches stored best_obj
        recomputed_obj = compute_state_objective(best_state, self.config)
        assert abs(recomputed_obj - best_obj) < 1e-6, (
            f"Invariant I9: Recomputed objective ({recomputed_obj}) != stored best_obj ({best_obj})"
        )

        final_assignments = best_state.to_gate_assignments()

        # Authoritative evaluation via common evaluator
        # Invariants I10, S02, S22: SA is a metaheuristic and NEVER self-certifies OPTIMAL
        result = evaluate_gate_assignment(
            assignments=final_assignments,
            flights=flights,
            gates=gate_list,
            config=self.config,
            runtime_ms=elapsed_ms,
            solver_status="FEASIBLE",
            solver_name="SimulatedAnnealing",
            termination_reason=TerminationReason.ITERATION_LIMIT,
        )

        # Augment solver configuration with SA-specific execution metadata
        improvement = initial_obj - best_obj
        improvement_pct = compute_improvement_pct(initial_obj, best_obj)

        extra_metadata = {
            "sa_config": self.sa_config.to_dict(),
            "initial_objective": initial_obj,
            "best_objective": best_obj,
            "improvement": improvement,
            "improvement_pct": improvement_pct,
            "accepted_moves": accepted_moves,
            "trace_length": len(trace),
            "trace_sample": [trace[i].to_dict() for i in [0, len(trace) // 2, -1]] if trace else [],
        }

        # Store in solver configuration for transparent reporting
        result.solver_configuration.update(extra_metadata)
        return result
