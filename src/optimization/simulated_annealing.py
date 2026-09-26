"""Simulated Annealing Gate Optimization.

Takes an initial feasible assignment (from CP-SAT or Greedy) and optimizes multi-objective
soft costs (gate reassignment, delay risk, gate workload balance, remote stand penalties)
while guaranteeing zero hard constraint violations.
"""

from __future__ import annotations

import logging
import math
import random
from collections import defaultdict
from typing import Sequence

from src.optimization.contracts import ProblemInstance
from src.optimization.cp_sat_solver import occupancy_window

logger = logging.getLogger(__name__)


def soft_cost(
    assignment: dict[str, str],
    instance: ProblemInstance,
    weights: Sequence[float],
) -> float:
    """Calculate multi-objective soft cost for a valid gate assignment.

    Parameters
    ----------
    assignment : dict[str, str]
        Mapping {flight_id: gate_id}.
    instance : ProblemInstance
        Problem instance data contract.
    weights : Sequence[float]
        Tuple/list of (w1, w2, w3, w4) objective weights:
        - w1: Gate reassignment penalty
        - w2: Expected delay risk cost
        - w3: Gate workload balance variance penalty
        - w4: Remote stand penalty

    Returns
    -------
    float
        Total soft cost value.
    """
    w1, w2, w3, w4 = weights
    cost = 0.0
    gate_load: dict[str, float] = defaultdict(float)
    gate_map = {g.gate_id: g for g in instance.gates}

    for f in instance.flights:
        g_id = assignment[f.flight_id]
        gate = gate_map[g_id]

        # Cost 1: Gate reassignment penalty
        if f.current_gate is not None and g_id != f.current_gate:
            cost += w1 * instance.cost_params.reassignment_cost_default

        # Cost 2: Expected delay risk cost
        cost += w2 * f.p_delay * f.delay_est_min * instance.cost_params.delay_cost_weight

        # Cost 4: Remote gate penalty
        if not gate.is_contact_gate:
            cost += w4 * instance.cost_params.remote_gate_cost * f.priority_weight

        gate_load[g_id] += 1.0

    # Cost 3: Workload balance variance
    loads = list(gate_load.values()) or [0.0]
    mean_load = sum(loads) / len(loads)
    cost += w3 * sum((l - mean_load) ** 2 for l in loads)

    return cost


def is_feasible(assignment: dict[str, str], instance: ProblemInstance) -> bool:
    """Verify all hard constraints for a proposed candidate assignment.

    Parameters
    ----------
    assignment : dict[str, str]
        Candidate mapping {flight_id: gate_id}.
    instance : ProblemInstance
        Problem instance data contract.

    Returns
    -------
    bool
        True if all hard constraints are satisfied, False otherwise.
    """
    gate_map = {g.gate_id: g for g in instance.gates}
    occ_by_gate: dict[str, list[tuple[int, int]]] = defaultdict(list)

    for f in instance.flights:
        g_id = assignment.get(f.flight_id)
        if not g_id or g_id not in gate_map:
            return False

        gate = gate_map[g_id]

        # Constraint 1: Aircraft compatibility
        if f.aircraft_type not in gate.compatible_types:
            return False

        start_i, end_i = occupancy_window(f, instance.cost_params.buffer_time_min)

        # Constraint 2: Gate availability window
        if start_i < gate.available_from_min or end_i > gate.available_to_min:
            return False

        # Constraint 3: No time overlap at gate
        for (s, e) in occ_by_gate[g_id]:
            if start_i < e and s < end_i:  # Overlap detected
                return False

        occ_by_gate[g_id].append((start_i, end_i))

    return True


def neighbor(
    assignment: dict[str, str],
    instance: ProblemInstance,
    rng: random.Random,
) -> dict[str, str]:
    """Generate a candidate neighbor solution by mutating one flight's gate assignment."""
    new_assignment = dict(assignment)
    f = rng.choice(instance.flights)
    compatible_gates = [
        g.gate_id for g in instance.gates if f.aircraft_type in g.compatible_types
    ]
    if compatible_gates:
        new_assignment[f.flight_id] = rng.choice(compatible_gates)
    return new_assignment


def simulated_annealing(
    initial_assignment: dict[str, str],
    instance: ProblemInstance,
    weights: Sequence[float] = (1.0, 1.0, 0.5, 1.0),
    t0: float = 100.0,
    alpha: float = 0.95,
    iterations: int = 2000,
    seed: int = 42,
) -> tuple[dict[str, str], float]:
    """Perform Simulated Annealing metaheuristic starting from an initial feasible assignment.

    Parameters
    ----------
    initial_assignment : dict[str, str]
        Starting feasible gate assignment mapping.
    instance : ProblemInstance
        Problem instance data contract.
    weights : Sequence[float]
        Objective weights (w1, w2, w3, w4).
    t0 : float
        Initial temperature.
    alpha : float
        Cooling factor (0 < alpha < 1).
    iterations : int
        Number of SA iterations.
    seed : int
        RNG seed for reproducibility.

    Returns
    -------
    tuple[dict[str, str], float]
        (best_assignment, best_soft_cost)
    """
    if not is_feasible(initial_assignment, instance):
        raise ValueError("Initial assignment passed to Simulated Annealing is not feasible")

    rng = random.Random(seed)
    current = dict(initial_assignment)
    current_cost = soft_cost(current, instance, weights)
    best, best_cost = current, current_cost
    T = t0

    for _ in range(iterations):
        cand = neighbor(current, instance, rng)
        if not is_feasible(cand, instance):
            continue

        cand_cost = soft_cost(cand, instance, weights)
        delta = cand_cost - current_cost

        if delta < 0 or rng.random() < math.exp(-delta / max(T, 1e-6)):
            current, current_cost = cand, cand_cost
            if current_cost < best_cost:
                best, best_cost = current, current_cost

        T *= alpha

    logger.info(
        "Simulated Annealing completed: initial_cost=%.2f, best_cost=%.2f, iterations=%d",
        soft_cost(initial_assignment, instance, weights),
        best_cost,
        iterations,
    )
    return best, best_cost
