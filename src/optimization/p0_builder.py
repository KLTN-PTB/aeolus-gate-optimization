"""P0 Initial Gate Schedule Builder for Turnaround Sessions.

Generates a deterministic initial gate schedule (P0) strictly using scheduled time windows (sched_*).
Guarantees:
- Zero dependency on ML predictions (pred_*, p_delay*, delay_est*) or ground truth labels (actual_*).
- Deterministic behavior using Greedy earliest_free (spread / worst-fit) strategy.
- Serves as the single shared baseline P0 for Greedy reassignment, CP-SAT, and Simulated Annealing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from src.optimization.contracts import ProblemInstance
from src.optimization.cp_sat_solver import dataframe_to_problem_instance
from src.optimization.greedy_baseline import greedy_assign

logger = logging.getLogger(__name__)


@dataclass
class P0Result:
    """Result container for initial gate schedule P0."""

    assignment: dict[str, str]
    status: str
    solve_time_sec: float
    unassigned_count: int
    gates_used: int
    unassigned_flights: list[str] = field(default_factory=list)


def build_initial_gate_schedule(
    df_sessions: pd.DataFrame,
    num_gates: int,
    buffer_time_min: int = 15,
    policy: str = "earliest_free",
) -> P0Result:
    """Build a deterministic initial gate schedule (P0) based strictly on scheduled times.

    Parameters
    ----------
    df_sessions : pd.DataFrame
        DataFrame of turnaround sessions containing sched_start_min, sched_end_min, sched_duration_min.
    num_gates : int
        Number of available gates.
    buffer_time_min : int
        Safety buffer in minutes (default 15).
    policy : str
        Greedy policy (default 'earliest_free').

    Returns
    -------
    P0Result
        Result containing the assignment mapping {session_id: gate_id} and execution stats.
    """
    # Defensive copy with ONLY scheduled fields to mathematically guarantee no leakage
    sched_cols = [
        "session_id",
        "session_type",
        "aircraft_type",
        "sched_start_min",
        "sched_end_min",
        "sched_duration_min",
    ]
    available_cols = [c for c in sched_cols if c in df_sessions.columns]
    df_sched_only = df_sessions[available_cols].copy()

    sched_instance = dataframe_to_problem_instance(
        df_sched_only,
        num_gates=num_gates,
        buffer_time_min=buffer_time_min,
        time_basis="sched",
    )

    greedy_res = greedy_assign(
        sched_instance,
        mode="fixed",
        policy=policy,
        allow_unassigned=True,
    )

    assignment = dict(greedy_res.assignment)
    gates_used = len(set(assignment.values()))
    unassigned = list(greedy_res.unassigned_flights)

    logger.info(
        "P0 built: %d assigned, %d unassigned, %d gates used, status=%s in %.3fs",
        len(assignment),
        len(unassigned),
        gates_used,
        greedy_res.status,
        greedy_res.solve_time_sec,
    )

    return P0Result(
        assignment=assignment,
        status=greedy_res.status,
        solve_time_sec=greedy_res.solve_time_sec,
        unassigned_count=len(unassigned),
        gates_used=gates_used,
        unassigned_flights=unassigned,
    )


def attach_initial_gate(
    df_sessions: pd.DataFrame,
    p0_result: P0Result,
) -> pd.DataFrame:
    """Attach the P0 initial gate assignments to a DataFrame copy.

    Does NOT modify the input DataFrame in place.
    """
    df_out = df_sessions.copy()
    df_out["initial_gate"] = df_out["session_id"].map(p0_result.assignment)
    return df_out
