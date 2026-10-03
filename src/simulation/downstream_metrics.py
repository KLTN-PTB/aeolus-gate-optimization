"""Downstream Gate Simulation Utility and Risk Metrics Framework.

Protocol: docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md - Section 4
          docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 19 (Stage 9)

Computes:
1. Nominal plan conflict rates and duration.
2. Dynamic recourse metrics (overflow, reassignments, peak occupancy, utilization).
3. Downstream tail risk measures (VaR_95, CVaR_95).
4. Multi-regime comparative evaluation:
   - Schedule-Only (Zero delay nominal baseline)
   - Independent D0 Baseline
   - Gaussian Copula D2 Selected System
   - Historical Ground Truth (Oracle realized outcomes)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Sequence

import numpy as np

from src.simulation.gate_simulator import GateSimulationResult


def compute_var_cvar(values: Sequence[float] | np.ndarray, alpha: float = 0.95) -> tuple[float, float]:
    """Compute Value-at-Risk (VaR) and Conditional Value-at-Risk (CVaR / Expected Shortfall).

    Args:
        values: 1D array of non-negative cost or burden metrics (e.g. overflow, peak occupancy).
        alpha: Confidence level (default: 0.95).

    Returns:
        (var_alpha, cvar_alpha)
    """
    arr = np.asarray(values, dtype=float).ravel()
    if len(arr) == 0:
        return 0.0, 0.0

    var_val = float(np.percentile(arr, alpha * 100.0))
    tail_vals = arr[arr >= var_val - 1e-9]
    cvar_val = float(np.mean(tail_vals)) if len(tail_vals) > 0 else var_val
    return var_val, cvar_val


@dataclass
class DownstreamUtilitySummary:
    """Consolidated downstream gate utility metrics across operational days and scenarios."""

    regime_id: str
    total_days: int
    total_scenarios_evaluated: int
    total_flights: int

    # Conflict metrics under frozen nominal assignment (no recourse)
    conflict_scenario_rate: float
    mean_conflicts_per_day: float
    mean_conflict_duration_min: float
    p95_conflict_duration_min: float
    var95_conflicts: float
    cvar95_conflicts: float

    # Operational recourse metrics (dynamic greedy / MILP)
    mean_overflow_flights: float
    var95_overflow_flights: float
    cvar95_overflow_flights: float
    mean_reassignments_per_day: float
    mean_peak_occupancy: float
    var95_peak_occupancy: float
    cvar95_peak_occupancy: float
    mean_gate_utilization: float
    mean_solver_wall_sec: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def aggregate_simulation_results(
    regime_id: str,
    frozen_nominal_results: list[GateSimulationResult],
    recourse_results: list[GateSimulationResult],
    total_flights: int,
) -> DownstreamUtilitySummary:
    """Aggregate simulation results over all evaluated days and scenarios for one regime."""
    n_runs = len(frozen_nominal_results)
    if n_runs == 0:
        raise ValueError("Cannot aggregate empty simulation results")

    # Conflict metrics from frozen nominal plan
    conflict_counts = [r.total_conflict_count for r in frozen_nominal_results]
    conflict_durations = [r.total_conflict_duration_min for r in frozen_nominal_results]

    has_conflict_vec = [float(c > 0) for c in conflict_counts]
    conflict_rate = float(np.mean(has_conflict_vec))
    mean_conflicts = float(np.mean(conflict_counts))
    mean_duration = float(np.mean(conflict_durations))
    p95_duration = float(np.percentile(conflict_durations, 95.0))
    var95_conf, cvar95_conf = compute_var_cvar(conflict_counts, alpha=0.95)

    # Recourse metrics
    overflow_counts = [r.overflow_count for r in recourse_results]
    reassignments = [r.reassignments_count for r in recourse_results]
    peak_occs = [r.peak_concurrent_occupancy for r in recourse_results]
    utils = [r.gate_utilization_rate for r in recourse_results]
    solver_times = [r.wall_clock_time_sec for r in recourse_results]

    mean_overflow = float(np.mean(overflow_counts))
    var95_over, cvar95_over = compute_var_cvar(overflow_counts, alpha=0.95)
    mean_reassign = float(np.mean(reassignments))
    mean_peak = float(np.mean(peak_occs))
    var95_peak, cvar95_peak = compute_var_cvar(peak_occs, alpha=0.95)
    mean_util = float(np.mean(utils))
    mean_time = float(np.mean(solver_times))

    # Determine unique days if identifiable from scenario count
    return DownstreamUtilitySummary(
        regime_id=regime_id,
        total_days=len(set(r.scenario_id for r in frozen_nominal_results)),
        total_scenarios_evaluated=n_runs,
        total_flights=total_flights,
        conflict_scenario_rate=conflict_rate,
        mean_conflicts_per_day=mean_conflicts,
        mean_conflict_duration_min=mean_duration,
        p95_conflict_duration_min=p95_duration,
        var95_conflicts=var95_conf,
        cvar95_conflicts=cvar95_conf,
        mean_overflow_flights=mean_overflow,
        var95_overflow_flights=var95_over,
        cvar95_overflow_flights=cvar95_over,
        mean_reassignments_per_day=mean_reassign,
        mean_peak_occupancy=mean_peak,
        var95_peak_occupancy=var95_peak,
        cvar95_peak_occupancy=cvar95_peak,
        mean_gate_utilization=mean_util,
        mean_solver_wall_sec=mean_time,
    )
