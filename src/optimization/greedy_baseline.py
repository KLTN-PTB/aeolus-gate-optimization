"""Greedy Baseline Gate Assignment Strategy.

Sorts flights chronologically by scheduled departure/arrival time and assigns
the first compatible gate that becomes free. Used as a benchmark baseline.
"""

from __future__ import annotations

import logging
from src.optimization.contracts import ProblemInstance
from src.optimization.cp_sat_solver import occupancy_window

logger = logging.getLogger(__name__)


def greedy_assign(instance: ProblemInstance) -> dict[str, str]:
    """Assign gates greedily based on scheduled flight order.

    Parameters
    ----------
    instance : ProblemInstance
        Data contract container with flights, gates, and cost parameters.

    Returns
    -------
    dict[str, str]
        Assignment mapping {flight_id: gate_id}.
    """
    assignment: dict[str, str] = {}
    gate_free_until: dict[str, int] = {g.gate_id: 0 for g in instance.gates}

    sorted_flights = sorted(instance.flights, key=lambda fl: fl.sched_time_min)

    for f in sorted_flights:
        start_i, end_i = occupancy_window(f, instance.cost_params.buffer_time_min)
        candidates = [
            g
            for g in instance.gates
            if f.aircraft_type in g.compatible_types and gate_free_until[g.gate_id] <= start_i
        ]

        if not candidates:
            logger.error("Greedy baseline failed for flight %s: no free compatible gate", f.flight_id)
            raise RuntimeError(
                f"Greedy baseline failed at flight {f.flight_id}: no free compatible gate available at minute {start_i}"
            )

        # Pick candidate gate that was free earliest
        chosen = min(candidates, key=lambda g: gate_free_until[g.gate_id])
        assignment[f.flight_id] = chosen.gate_id
        gate_free_until[chosen.gate_id] = end_i

    logger.info("Greedy baseline completed successfully for %d flights", len(assignment))
    return assignment
