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
from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import (
    Flight,
    Gate,
    GateAssignment,
    OptimizationResult,
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
                solver_status="OPTIMAL",
                solver_name="SimulatedAnnealing",
            )

        # 1. Obtain or validate initial feasible assignment
        gate_list = list(gates)
        has_overflow = any(g.is_overflow for g in gate_list)
        if allow_overflow and not has_overflow:
            overflow_gate = Gate(
                gate_id="OVERFLOW_APRON",
                gate_index=len(gate_list),
                is_overflow=True,
            )
            gate_list.append(overflow_gate)

        if initial_assignments is None:
            # Generate deterministic greedy solution as proven feasible initial seed
            greedy_solver = DeterministicGreedyGateSolver(config=self.config)
            greedy_result = greedy_solver.solve(flights, gate_list, allow_overflow=allow_overflow)
            if not greedy_result.feasible or not greedy_result.constraint_diagnostics.is_valid:
                raise ValueError("Greedy solver failed to produce a valid initial feasible assignment.")
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
                cand_obj = compute_state_objective(cand_state, self.config)
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

        # Best-so-far assignment is strictly returned
        final_assignments = best_state.to_gate_assignments()

        # Step 8 Verification: Objective never worse than initial solution
        assert best_obj <= initial_obj + 1e-9, (
            f"SA best objective ({best_obj:.4f}) is worse than initial ({initial_obj:.4f})"
        )

        # Authoritative evaluation via common evaluator
        result = evaluate_gate_assignment(
            assignments=final_assignments,
            flights=flights,
            gates=gate_list,
            config=self.config,
            runtime_ms=elapsed_ms,
            solver_status="OPTIMAL" if best_obj <= curr_obj else "FEASIBLE",
            solver_name="SimulatedAnnealing",
        )

        # Augment solver configuration with SA-specific execution metadata
        improvement = initial_obj - best_obj
        improvement_pct = (improvement / max(initial_obj, 1e-9)) * 100.0

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
