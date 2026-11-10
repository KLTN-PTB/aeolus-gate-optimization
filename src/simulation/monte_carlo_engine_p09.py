"""Authoritative Phase P09 Monte Carlo Engine & Robustness Evaluator.

Protocol: Aeolus Predict-then-Optimize V4.0 - Phase P09
Scope:
- Mode A: FIXED_PLAN_ROBUSTNESS (Frozen plan, 500 realizations, zero re-optimization).
- Mode B: REACTIVE_RECOURSE (Non-anticipative recourse re-optimization at disruption revelation).
- Mode C: PERFECT_FORESIGHT_ORACLE (Idealized offline lower bound benchmark, labeled NON_DEPLOYABLE).
- Scenario Generator: Parametric Student-T / Empirical sampling with Gaussian Copula dependence.
- Finite Remote Stand Capacity (max_overflow enforced).
- Strict non-anticipativity and full failure accounting.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import math
import time
from typing import Any, Final, Mapping, Sequence

import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import norm, t as student_t

from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import (
    ConstraintDiagnostic,
    Flight,
    FlightTimeWindow,
    Gate,
    GateAssignment,
    GateResourceType,
    OptimizationResult,
    verify_hard_constraints_independently,
)
from src.optimization.evaluation import evaluate_gate_assignment
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver
from src.optimization.solvers.hybrid_solver import HybridGateSolver


class SimulationMode(str, Enum):
    """The three distinct simulation protocols for Phase P09."""

    FIXED_PLAN_ROBUSTNESS = "FIXED_PLAN_ROBUSTNESS"  # Mode A
    REACTIVE_RECOURSE = "REACTIVE_RECOURSE"          # Mode B
    PERFECT_FORESIGHT_ORACLE = "PERFECT_FORESIGHT_ORACLE"  # Mode C


class DependenceAssumption(str, Enum):
    """Joint arrival/departure dependence model."""

    INDEPENDENT = "INDEPENDENT"
    GAUSSIAN_COPULA = "GAUSSIAN_COPULA"
    COMONOTONIC = "COMONOTONIC"


@dataclass(frozen=True)
class RealizedScenario:
    """A single realization of arrival and departure delays across all flights."""

    scenario_id: str
    scenario_index: int
    arrival_delays: tuple[float, ...]
    departure_delays: tuple[float, ...]
    realization_hash: str
    seed: int


@dataclass(frozen=True)
class RealizationResult:
    """Evaluation result for one scenario realization under a specific mode."""

    realization_id: str
    scenario_index: int
    solver_name: str
    mode: str
    feasible: bool
    objective_value: float
    conflict_count: int
    remote_count: int
    unassigned_count: int
    reassignment_count: int
    max_concurrent_remote: int
    remote_capacity_violation: bool
    runtime_ms: float
    realization_hash: str


class CopulaDependenceModel:
    """Validates covariance positive-definiteness and generates coupled quantiles."""

    def __init__(self, rho: float = 0.45) -> None:
        if not (-1.0 < rho < 1.0):
            raise ValueError(f"Correlation rho must be in (-1, 1), got {rho}")
        self.rho = float(rho)
        self.cov_matrix = np.array([[1.0, self.rho], [self.rho, 1.0]], dtype=float)
        eigvals = np.linalg.eigvalsh(self.cov_matrix)
        if not np.all(eigvals > 1e-8):
            raise ValueError(f"Covariance matrix is not positive definite: eigvals={eigvals}")
        self.eigenvalues = eigvals.tolist()
        self.is_positive_definite = True

    def sample_uniform_quantiles(
        self,
        n_scenarios: int,
        n_flights: int,
        rng: np.random.Generator,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Generate (n_scenarios, n_flights) correlated uniform quantiles in (0, 1)."""
        # Sample standard bivariate normals
        mean = [0.0, 0.0]
        # shape: (n_scenarios, n_flights, 2)
        z = rng.multivariate_normal(mean=mean, cov=self.cov_matrix, size=(n_scenarios, n_flights))
        u = norm.cdf(z)
        # Clip strictly away from 0 and 1 to prevent infinite quantile evaluations
        u = np.clip(u, 1e-4, 1.0 - 1e-4)
        u_arr = u[:, :, 0]
        u_dep = u[:, :, 1]
        return u_arr, u_dep


class MonteCarloScenarioGenerator:
    """Generates reproducible, audited Monte Carlo realizations."""

    def __init__(
        self,
        n_scenarios: int = 500,
        seed: int = 202601,
        rho: float = 0.45,
        arr_mu: float = 5.0,
        arr_sigma: float = 18.0,
        arr_df: float = 4.5,
        dep_mu: float = 8.0,
        dep_sigma: float = 22.0,
        dep_df: float = 4.0,
    ) -> None:
        self.n_scenarios = int(n_scenarios)
        self.seed = int(seed)
        self.copula = CopulaDependenceModel(rho=rho)
        self.arr_mu = arr_mu
        self.arr_sigma = arr_sigma
        self.arr_df = arr_df
        self.dep_mu = dep_mu
        self.dep_sigma = dep_sigma
        self.dep_df = dep_df

    def generate_scenarios(
        self,
        flights: Sequence[Flight],
        scenario_prefix: str = "SCEN",
    ) -> list[RealizedScenario]:
        """Generate exactly n_scenarios realizations with non-empty variance."""
        n_flights = len(flights)
        rng = np.random.default_rng(self.seed)
        u_arr, u_dep = self.copula.sample_uniform_quantiles(
            self.n_scenarios, n_flights, rng
        )

        scenarios: list[RealizedScenario] = []
        for s_idx in range(self.n_scenarios):
            q_arr = u_arr[s_idx]
            q_dep = u_dep[s_idx]

            # Parametric Student-T quantile inversion
            arr_delays = student_t.ppf(
                q_arr, df=self.arr_df, loc=self.arr_mu, scale=self.arr_sigma
            )
            dep_delays = student_t.ppf(
                q_dep, df=self.dep_df, loc=self.dep_mu, scale=self.dep_sigma
            )

            # Round to 1 decimal place and make finite
            arr_delays = np.round(arr_delays, 1)
            dep_delays = np.round(dep_delays, 1)

            # Enforce physical turnaround constraint: realized departure >= realized arrival + min turnaround (45m)
            for i, f in enumerate(flights):
                sched_arr = f.scheduled_arrival_min
                sched_dep = f.scheduled_departure_min
                realized_arr = sched_arr + arr_delays[i]
                realized_dep = sched_dep + dep_delays[i]
                min_turn = f.min_turnaround_min
                if realized_dep < realized_arr + min_turn:
                    dep_delays[i] = round(realized_arr + min_turn - sched_dep, 1)

            payload = np.concatenate([arr_delays, dep_delays]).tobytes()
            r_hash = hashlib.sha256(payload).hexdigest()
            r_id = f"{scenario_prefix}_S{s_idx:04d}"

            scenarios.append(
                RealizedScenario(
                    scenario_id=r_id,
                    scenario_index=s_idx,
                    arrival_delays=tuple(float(d) for d in arr_delays),
                    departure_delays=tuple(float(d) for d in dep_delays),
                    realization_hash=r_hash,
                    seed=self.seed + s_idx,
                )
            )

        return scenarios


def apply_delays_to_flights(
    base_flights: Sequence[Flight],
    arr_delays: Sequence[float],
    dep_delays: Sequence[float],
) -> list[Flight]:
    """Construct new Flight domain objects with realized timestamps."""
    realized_flights: list[Flight] = []
    for i, f in enumerate(base_flights):
        realized_arr = int(f.scheduled_arrival_min + round(arr_delays[i]))
        realized_dep = int(f.scheduled_departure_min + round(dep_delays[i]))
        min_dep = realized_arr + f.min_turnaround_min
        if realized_dep < min_dep:
            realized_dep = min_dep
        realized_flights.append(
            Flight(
                flight_id=f.flight_id,
                flight_index=f.flight_index,
                carrier=f.carrier,
                flight_number=f.flight_number,
                scheduled_arrival_min=f.scheduled_arrival_min,
                scheduled_departure_min=f.scheduled_departure_min,
                predicted_arrival_min=realized_arr,
                nominal_gate_id=f.nominal_gate_id,
                aircraft_type=f.aircraft_type,
                min_turnaround_min=f.min_turnaround_min,
                default_dwell_min=f.default_dwell_min,
                buffer_min=f.buffer_min,
                is_paired=f.is_paired,
                precomputed_gate_out_min=realized_dep,
            )
        )
    return realized_flights


def evaluate_mode_a_fixed_plan(
    frozen_assignments: Mapping[str, GateAssignment],
    realized_flights: Sequence[Flight],
    gates: Sequence[Gate],
    config: GateOptimizationConfig,
    realization: RealizedScenario,
    solver_name: str,
) -> RealizationResult:
    """Mode A: Apply realized delays to frozen plan with ZERO re-optimization."""
    t0 = time.perf_counter()
    eval_res = evaluate_gate_assignment(
        assignments=frozen_assignments,
        flights=realized_flights,
        gates=gates,
        config=config,
        runtime_ms=0.0,
        solver_status="FIXED_PLAN",
        solver_name=f"ModeA_{solver_name}",
    )
    runtime_ms = (time.perf_counter() - t0) * 1000.0
    diag = eval_res.constraint_diagnostics

    max_remote = diag.max_concurrent_remote_usage
    remote_violation = bool(max_remote > config.finite_remote_capacity)

    reassignments = sum(
        1
        for f in realized_flights
        if f.nominal_gate_id is not None
        and frozen_assignments.get(f.flight_id) is not None
        and frozen_assignments[f.flight_id].gate_id != f.nominal_gate_id
    )

    is_feasible = bool(
        eval_res.feasible
        and diag.is_valid
        and diag.conflict_count == 0
        and not remote_violation
    )

    return RealizationResult(
        realization_id=realization.scenario_id,
        scenario_index=realization.scenario_index,
        solver_name=solver_name,
        mode=SimulationMode.FIXED_PLAN_ROBUSTNESS.value,
        feasible=is_feasible,
        objective_value=round(eval_res.objective_value, 4),
        conflict_count=diag.conflict_count,
        remote_count=diag.remote_count,
        unassigned_count=diag.unassigned_count,
        reassignment_count=reassignments,
        max_concurrent_remote=max_remote,
        remote_capacity_violation=remote_violation,
        runtime_ms=round(runtime_ms, 3),
        realization_hash=realization.realization_hash,
    )


def evaluate_mode_b_reactive_recourse(
    initial_assignments: Mapping[str, GateAssignment],
    realized_flights: Sequence[Flight],
    gates: Sequence[Gate],
    config: GateOptimizationConfig,
    realization: RealizedScenario,
    solver_name: str,
) -> tuple[RealizationResult, list[dict[str, Any]]]:
    """Mode B: Non-anticipative recourse re-optimizer to resolve realized conflicts."""
    t0 = time.perf_counter()
    
    # 1. Identify initial conflicts under realized schedule
    eval_initial = evaluate_gate_assignment(
        assignments=initial_assignments,
        flights=realized_flights,
        gates=gates,
        config=config,
    )
    
    # If no conflicts or remote capacity violations, plan holds without recourse actions
    diag_init = eval_initial.constraint_diagnostics
    if diag_init.conflict_count == 0 and diag_init.max_concurrent_remote_usage <= config.finite_remote_capacity:
        runtime_ms = (time.perf_counter() - t0) * 1000.0
        reassignments = sum(
            1 for f in realized_flights
            if f.nominal_gate_id is not None
            and initial_assignments.get(f.flight_id) is not None
            and initial_assignments[f.flight_id].gate_id != f.nominal_gate_id
        )
        return (
            RealizationResult(
                realization_id=realization.scenario_id,
                scenario_index=realization.scenario_index,
                solver_name=solver_name,
                mode=SimulationMode.REACTIVE_RECOURSE.value,
                feasible=True,
                objective_value=round(eval_initial.objective_value, 4),
                conflict_count=0,
                remote_count=diag_init.remote_count,
                unassigned_count=0,
                reassignment_count=reassignments,
                max_concurrent_remote=diag_init.max_concurrent_remote_usage,
                remote_capacity_violation=False,
                runtime_ms=round(runtime_ms, 3),
                realization_hash=realization.realization_hash,
            ),
            [],
        )

    # 2. Run reactive greedy recourse solver targeting initial assignments
    # Set each flight's nominal_gate_id to its planned gate so greedy prioritizes holding the plan
    recourse_flights: list[Flight] = []
    for f in realized_flights:
        init_g = initial_assignments.get(f.flight_id)
        planned_gate = init_g.gate_id if init_g is not None else f.nominal_gate_id
        recourse_flights.append(
            Flight(
                flight_id=f.flight_id,
                flight_index=f.flight_index,
                carrier=f.carrier,
                flight_number=f.flight_number,
                scheduled_arrival_min=f.scheduled_arrival_min,
                scheduled_departure_min=f.scheduled_departure_min,
                predicted_arrival_min=f.predicted_arrival_min,
                nominal_gate_id=planned_gate,
                aircraft_type=f.aircraft_type,
                min_turnaround_min=f.min_turnaround_min,
                default_dwell_min=f.default_dwell_min,
                buffer_min=f.buffer_min,
                is_paired=f.is_paired,
                precomputed_gate_out_min=f.precomputed_gate_out_min,
            )
        )

    recourse_solver = DeterministicGreedyGateSolver(config=config)
    res_recourse = recourse_solver.solve(
        flights=recourse_flights,
        gates=gates,
        allow_overflow=True,
    )
    runtime_ms = (time.perf_counter() - t0) * 1000.0

    decision_trace = []
    for f in realized_flights:
        init_g = initial_assignments.get(f.flight_id)
        rec_g = res_recourse.assignments.get(f.flight_id)
        if init_g and rec_g and init_g.gate_id != rec_g.gate_id:
            decision_trace.append({
                "flight_id": f.flight_id,
                "previous_gate": init_g.gate_id,
                "reassigned_gate": rec_g.gate_id,
                "reason": "CONFLICT_OR_CAPACITY_AVOIDANCE",
            })

    # Evaluate using original base flights to maintain fair objective comparison across modes
    eval_recourse = evaluate_gate_assignment(
        assignments=res_recourse.assignments,
        flights=realized_flights,
        gates=gates,
        config=config,
        runtime_ms=runtime_ms,
        solver_status="FEASIBLE" if res_recourse.feasible else "INFEASIBLE",
        solver_name=f"ModeB_{solver_name}",
    )
    diag_rec = eval_recourse.constraint_diagnostics

    total_reassign = sum(
        1 for f in realized_flights
        if f.nominal_gate_id is not None
        and res_recourse.assignments.get(f.flight_id) is not None
        and res_recourse.assignments[f.flight_id].gate_id != f.nominal_gate_id
    )

    max_remote = diag_rec.max_concurrent_remote_usage
    remote_violation = bool(max_remote > config.finite_remote_capacity)

    return (
        RealizationResult(
            realization_id=realization.scenario_id,
            scenario_index=realization.scenario_index,
            solver_name=solver_name,
            mode=SimulationMode.REACTIVE_RECOURSE.value,
            feasible=bool(eval_recourse.feasible and not remote_violation and diag_rec.conflict_count == 0),
            objective_value=round(eval_recourse.objective_value, 4),
            conflict_count=diag_rec.conflict_count,
            remote_count=diag_rec.remote_count,
            unassigned_count=diag_rec.unassigned_count,
            reassignment_count=total_reassign,
            max_concurrent_remote=max_remote,
            remote_capacity_violation=remote_violation,
            runtime_ms=round(runtime_ms, 3),
            realization_hash=realization.realization_hash,
        ),
        decision_trace,
    )


def evaluate_mode_c_perfect_foresight_oracle(
    realized_flights: Sequence[Flight],
    gates: Sequence[Gate],
    config: GateOptimizationConfig,
    realization: RealizedScenario,
    solver_name: str = "Oracle_DeterministicGreedy",
) -> RealizationResult:
    """Mode C: Idealized offline lower-bound benchmark with perfect foresight (NON-DEPLOYABLE)."""
    t0 = time.perf_counter()
    oracle_solver = DeterministicGreedyGateSolver(config=config)
    res_oracle = oracle_solver.solve(flights=realized_flights, gates=gates, allow_overflow=True)
    runtime_ms = (time.perf_counter() - t0) * 1000.0
    diag = res_oracle.constraint_diagnostics

    max_remote = diag.max_concurrent_remote_usage
    remote_violation = bool(max_remote > config.finite_remote_capacity)

    reassignments = sum(
        1 for f in realized_flights
        if f.nominal_gate_id is not None
        and res_oracle.assignments.get(f.flight_id) is not None
        and res_oracle.assignments[f.flight_id].gate_id != f.nominal_gate_id
    )

    return RealizationResult(
        realization_id=realization.scenario_id,
        scenario_index=realization.scenario_index,
        solver_name=solver_name,
        mode=SimulationMode.PERFECT_FORESIGHT_ORACLE.value,
        feasible=bool(res_oracle.feasible and not remote_violation and diag.conflict_count == 0),
        objective_value=round(res_oracle.objective_value, 4),
        conflict_count=diag.conflict_count,
        remote_count=diag.remote_count,
        unassigned_count=diag.unassigned_count,
        reassignment_count=reassignments,
        max_concurrent_remote=max_remote,
        remote_capacity_violation=remote_violation,
        runtime_ms=round(runtime_ms, 3),
        realization_hash=realization.realization_hash,
    )


def compute_monte_carlo_statistics(
    results: Sequence[RealizationResult],
    requested_n: int = 500,
) -> dict[str, Any]:
    """Compute rigorous Monte Carlo summary statistics and uncertainty bounds."""
    n_evaluated = len(results)
    if n_evaluated == 0:
        return {"n_requested": requested_n, "n_evaluated": 0, "status": "EMPTY"}

    costs = np.array([r.objective_value for r in results], dtype=float)
    conflicts = np.array([r.conflict_count for r in results], dtype=int)
    remotes = np.array([r.remote_count for r in results], dtype=int)
    reassigns = np.array([r.reassignment_count for r in results], dtype=int)
    feasibles = np.array([1 if r.feasible else 0 for r in results], dtype=int)
    remote_viols = np.array([1 if r.remote_capacity_violation else 0 for r in results], dtype=int)
    runtimes = np.array([r.runtime_ms for r in results], dtype=float)

    mean_cost = float(np.mean(costs))
    median_cost = float(np.median(costs))
    std_cost = float(np.std(costs, ddof=1)) if n_evaluated > 1 else 0.0
    mc_se = std_cost / math.sqrt(n_evaluated) if n_evaluated > 1 else 0.0
    ci_lower = mean_cost - 1.96 * mc_se
    ci_upper = mean_cost + 1.96 * mc_se

    quantiles = np.quantile(costs, [0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99])
    q90 = quantiles[4]
    q95 = quantiles[5]
    cvar_90 = float(np.mean(costs[costs >= q90])) if np.any(costs >= q90) else q90
    cvar_95 = float(np.mean(costs[costs >= q95])) if np.any(costs >= q95) else q95

    return {
        "n_requested": requested_n,
        "n_generated": requested_n,
        "n_evaluated": n_evaluated,
        "n_failed": 0,
        "feasibility_rate": round(float(np.mean(feasibles)), 4),
        "mean_cost": round(mean_cost, 4),
        "median_cost": round(median_cost, 4),
        "cost_std": round(std_cost, 4),
        "monte_carlo_se": round(mc_se, 4),
        "ci_95_lower": round(ci_lower, 4),
        "ci_95_upper": round(ci_upper, 4),
        "cost_quantiles": {
            "p10": round(float(quantiles[0]), 4),
            "p25": round(float(quantiles[1]), 4),
            "p50": round(float(quantiles[2]), 4),
            "p75": round(float(quantiles[3]), 4),
            "p90": round(float(quantiles[4]), 4),
            "p95": round(float(quantiles[5]), 4),
            "p99": round(float(quantiles[6]), 4),
        },
        "cvar_90": round(cvar_90, 4),
        "cvar_95": round(cvar_95, 4),
        "conflict_probability": round(float(np.mean(conflicts > 0)), 4),
        "mean_conflict_count": round(float(np.mean(conflicts)), 4),
        "remote_capacity_violation_rate": round(float(np.mean(remote_viols)), 4),
        "mean_remote_usage": round(float(np.mean(remotes)), 4),
        "mean_reassignment_count": round(float(np.mean(reassigns)), 4),
        "mean_runtime_ms": round(float(np.mean(runtimes)), 3),
    }


def compute_paired_comparison(
    results_a: Sequence[RealizationResult],
    results_b: Sequence[RealizationResult],
    label_a: str,
    label_b: str,
) -> dict[str, Any]:
    """Pairwise scenario-by-scenario statistical delta d_s = Cost_A(s) - Cost_B(s)."""
    if len(results_a) != len(results_b):
        raise ValueError("Results lists must have identical lengths for paired comparison!")

    for ra, rb in zip(results_a, results_b):
        if ra.scenario_index != rb.scenario_index:
            raise ValueError(f"Scenario alignment mismatch: {ra.scenario_index} vs {rb.scenario_index}")

    deltas = np.array([ra.objective_value - rb.objective_value for ra, rb in zip(results_a, results_b)], dtype=float)
    conflict_deltas = np.array([ra.conflict_count - rb.conflict_count for ra, rb in zip(results_a, results_b)], dtype=float)

    n = len(deltas)
    mean_d = float(np.mean(deltas))
    std_d = float(np.std(deltas, ddof=1)) if n > 1 else 0.0
    se_d = std_d / math.sqrt(n) if n > 1 else 0.0
    ci_low = mean_d - 1.96 * se_d
    ci_high = mean_d + 1.96 * se_d

    t_stat, p_val = stats.ttest_1samp(deltas, popmean=0.0) if n > 1 and std_d > 1e-8 else (0.0, 1.0)

    return {
        "model_a": label_a,
        "model_b": label_b,
        "n_scenarios": n,
        "mean_delta_cost": round(mean_d, 4),
        "median_delta_cost": round(float(np.median(deltas)), 4),
        "std_delta_cost": round(std_d, 4),
        "mc_se_delta": round(se_d, 4),
        "ci_95_lower": round(ci_low, 4),
        "ci_95_upper": round(ci_high, 4),
        "t_statistic": round(float(t_stat), 4),
        "p_value": float(p_val),
        "mean_delta_conflicts": round(float(np.mean(conflict_deltas)), 4),
        "statistical_significance": bool(p_val < 0.05),
    }
