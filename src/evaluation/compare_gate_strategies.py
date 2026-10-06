"""Gate Optimization Strategy Evaluation and Benchmark Script.

Compares three gate assignment strategies on identical ProblemInstances:
1. Greedy Baseline
2. CP-SAT Exact Solver
3. CP-SAT + Simulated Annealing (CP-SAT+SA)

Evaluates soft costs, solve runtime, gate utilization, and robust performance
under Monte Carlo synthetic delay simulation.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from src.optimization.contracts import ProblemInstance
from src.optimization.cp_sat_solver import solve_gate_assignment
from src.optimization.greedy_baseline import greedy_assign
from src.optimization.simulated_annealing import simulated_annealing, soft_cost
from src.simulation.monte_carlo import run_monte_carlo

logger = logging.getLogger(__name__)


def evaluate_strategies(
    instance: ProblemInstance,
    weights: tuple[float, float, float, float] = (1.0, 1.0, 0.5, 1.0),
    n_scenarios: int = 200,
    seed: int = 42,
) -> dict[str, dict[str, Any]]:
    """Compare Greedy, CP-SAT, and CP-SAT+SA on a single ProblemInstance.

    Parameters
    ----------
    instance : ProblemInstance
        Data contract container with flights, gates, and parameters.
    weights : tuple[float, float, float, float]
        Soft cost weights (w1, w2, w3, w4).
    n_scenarios : int
        Number of Monte Carlo scenarios for robustness testing.
    seed : int
        RNG seed.

    Returns
    -------
    dict[str, dict[str, Any]]
        Metrics breakdown by strategy name.
    """
    results: dict[str, dict[str, Any]] = {}

    # 1. Greedy Baseline
    t0 = time.perf_counter()
    try:
        greedy_solution = greedy_assign(instance)
        greedy_time = time.perf_counter() - t0
        greedy_cost = soft_cost(greedy_solution, instance, weights)
        greedy_mc = run_monte_carlo(instance, greedy_solution, n_scenarios=n_scenarios, seed=seed)
        greedy_conflicts = [r["conflicts"] for r in greedy_mc]
        results["Greedy"] = {
            "feasible": True,
            "soft_cost": greedy_cost,
            "solve_time_sec": greedy_time,
            "mean_conflicts": sum(greedy_conflicts) / max(1, len(greedy_conflicts)),
            "conflict_rate": sum(1 for c in greedy_conflicts if c > 0) / max(1, len(greedy_conflicts)),
            "assignment": greedy_solution,
        }
    except Exception as err:
        logger.warning("Greedy baseline failed: %s", err)
        results["Greedy"] = {
            "feasible": False,
            "error": str(err),
        }

    # 2. CP-SAT Solver
    t0 = time.perf_counter()
    try:
        cpsat_solution, status, cpsat_wall_time = solve_gate_assignment(instance)
        cpsat_cost = soft_cost(cpsat_solution, instance, weights)
        cpsat_mc = run_monte_carlo(instance, cpsat_solution, n_scenarios=n_scenarios, seed=seed)
        cpsat_conflicts = [r["conflicts"] for r in cpsat_mc]
        results["CP-SAT"] = {
            "feasible": True,
            "status": status,
            "soft_cost": cpsat_cost,
            "solve_time_sec": cpsat_wall_time,
            "mean_conflicts": sum(cpsat_conflicts) / max(1, len(cpsat_conflicts)),
            "conflict_rate": sum(1 for c in cpsat_conflicts if c > 0) / max(1, len(cpsat_conflicts)),
            "assignment": cpsat_solution,
        }
    except Exception as err:
        logger.error("CP-SAT solver failed: %s", err)
        results["CP-SAT"] = {
            "feasible": False,
            "error": str(err),
        }

    # 3. CP-SAT + Simulated Annealing
    if results.get("CP-SAT", {}).get("feasible"):
        t0 = time.perf_counter()
        init_assign = results["CP-SAT"]["assignment"]
        sa_solution, sa_cost = simulated_annealing(
            init_assign,
            instance,
            weights=weights,
            seed=seed,
        )
        sa_time = time.perf_counter() - t0
        sa_mc = run_monte_carlo(instance, sa_solution, n_scenarios=n_scenarios, seed=seed)
        sa_conflicts = [r["conflicts"] for r in sa_mc]
        results["CP-SAT+SA"] = {
            "feasible": True,
            "soft_cost": sa_cost,
            "solve_time_sec": results["CP-SAT"]["solve_time_sec"] + sa_time,
            "mean_conflicts": sum(sa_conflicts) / max(1, len(sa_conflicts)),
            "conflict_rate": sum(1 for c in sa_conflicts if c > 0) / max(1, len(sa_conflicts)),
            "assignment": sa_solution,
        }

    return results


def print_comparison_table(metrics: dict[str, dict[str, Any]]) -> None:
    """Print formatted comparative table of strategy results."""
    print("=========================================================================")
    print("                GATE ASSIGNMENT STRATEGY COMPARISON                     ")
    print("=========================================================================")
    print(f"{'Strategy':<15} | {'Feasible':<10} | {'Soft Cost':<12} | {'Solve Time (s)':<15} | {'Mean Conflicts':<15}")
    print("-" * 77)
    for strategy, m in metrics.items():
        if m.get("feasible"):
            print(
                f"{strategy:<15} | {'YES':<10} | {m['soft_cost']:<12.2f} | {m['solve_time_sec']:<15.4f} | {m['mean_conflicts']:<15.2f}"
            )
        else:
            print(f"{strategy:<15} | {'NO':<10} | {'N/A':<12} | {'N/A':<15} | {'N/A':<15}")
    print("=========================================================================")
