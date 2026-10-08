"""Monte Carlo Robustness Evaluator for Gate Assignments.

Simulates synthetic realized operational delay scenarios across a fixed gate assignment
to measure conflict rate, recourse requirements, and operational robustness.

CRITICAL INVARIANT: Monte Carlo MUST NOT access the sealed 2024 Final Holdout.
All delays generated are strictly synthetic samples derived from ML prediction outputs.
"""

from __future__ import annotations

import logging
import random
from collections import defaultdict
from typing import Any

from src.optimization.contracts import ProblemInstance
from src.optimization.cp_sat_solver import occupancy_window

logger = logging.getLogger(__name__)


def sample_realized_delay(flight: Any, rng: random.Random) -> float:
    """Sample a synthetic realized delay for a flight scenario.

    Uses Bernoulli trial with p=flight.p_delay to determine if delay occurs,
    and truncated Gaussian with mean=flight.delay_est_min for magnitude.
    Does NOT reference 2024 holdout data.
    """
    if rng.random() < flight.p_delay:
        std_dev = max(5.0, flight.delay_est_min * 0.3)
        sample = rng.gauss(flight.delay_est_min, std_dev)
        return max(15.0, sample)
    return 0.0


def count_conflicts(
    instance: ProblemInstance,
    assignment: dict[str, str],
    realized_delays: dict[str, float],
) -> int:
    """Count realized gate occupancy overlap conflicts under a fixed assignment.

    Parameters
    ----------
    instance : ProblemInstance
        Data contract instance.
    assignment : dict[str, str]
        Fixed gate assignment mapping {flight_id: gate_id}.
    realized_delays : dict[str, float]
        Sampled realized delays per flight.

    Returns
    -------
    int
        Total number of conflicting flight pairs across all gates.
    """
    occ_by_gate: dict[str, list[tuple[int, int]]] = defaultdict(list)
    conflicts = 0

    for f in instance.flights:
        g_id = assignment.get(f.flight_id)
        if not g_id:
            continue

        delay = realized_delays.get(f.flight_id, 0.0)
        start_i, end_i = occupancy_window(
            f,
            buffer_time_min=instance.cost_params.buffer_time_min,
            mode="realized",
            realized_delay=delay,
        )

        for (s, e) in occ_by_gate[g_id]:
            if start_i < e and s < end_i:  # Overlap conflict
                conflicts += 1

        occ_by_gate[g_id].append((start_i, end_i))

    return conflicts


def run_monte_carlo(
    instance: ProblemInstance,
    assignment: dict[str, str],
    n_scenarios: int = 500,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Run Monte Carlo simulation across multiple synthetic delay scenarios.

    Parameters
    ----------
    instance : ProblemInstance
        Problem instance.
    assignment : dict[str, str]
        Fixed gate assignment strategy to evaluate.
    n_scenarios : int
        Number of scenarios to simulate (e.g. 500).
    seed : int
        RNG seed for deterministic reproducibility.

    Returns
    -------
    list[dict[str, Any]]
        Scenario evaluation records containing scenario index and conflict counts.
    """
    rng = random.Random(seed)
    results: list[dict[str, Any]] = []

    for s in range(n_scenarios):
        realized = {f.flight_id: sample_realized_delay(f, rng) for f in instance.flights}
        conflicts = count_conflicts(instance, assignment, realized)
        results.append(
            {
                "scenario": s,
                "conflicts": conflicts,
                "has_conflict": conflicts > 0,
            }
        )

    logger.info(
        "Monte Carlo evaluation completed (%d scenarios, avg_conflicts=%.2f)",
        n_scenarios,
        sum(r["conflicts"] for r in results) / max(1, n_scenarios),
    )
    return results
