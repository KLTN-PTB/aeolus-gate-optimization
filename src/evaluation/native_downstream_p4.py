"""Native P4 Downstream Evaluation Engine (P10-A Rebuild).

Protocol Governance:
1. Native P4 Checkpoint:
   - Certified checkpoint: artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib
   - Cryptographic verification: SHA-256 == e7e7462f17b65b276ebdee9c7beced15e090f69b088a18896d5a91aaa8cb062f
   - Model identity: P4_ngboost_student_t (B5NGBoostStudentT).
   - Output: Observation-dependent mu(x), sigma(x), df(x).
   - Stochastic representation: Y_i = mu(x_i) + sigma(x_i) * T_{df(x_i)}.
2. Strictly Prohibits P5 in Downstream Simulation:
   - P5 is Role B (Marginal Quantile Forecast Champion) only.
   - P5 is NOT fit, NOT reconstructed, and NOT converted to stochastic density.
3. Canonical Scenario Population:
   - SCEN_2023_LOW: 2023-11-23, n_flights=30, n_contact_gates=10, seed=202601.
4. Input Boundary Isolation:
   - Strictly 11 Core Arrival predictors (DEST=ATL, cutoff=CRS_DEP_TIME-2h).
   - Zero actual delay leakage into planned arrivals.
   - Zero Weather, zero auxiliary Departure delay.
5. Solver Parity:
   - Solvers: DeterministicGreedy, CPSat, SimulatedAnnealing, HybridCPSatSA.
   - Budget: 2.0 seconds total wall-clock ceiling.
   - Seed: 202601.
   - One shared verifier: evaluate_gate_assignment().
   - Objective penalties: reassignment=10.0, remote=200.0, unassigned=1000.0, delay_risk=0.0.
6. Monte Carlo Evaluation:
   - Registered grid: N in [100, 250, 500, 1000, 2500].
   - Canonical N: 500.
   - CRN: TRUE with RNG numpy.random.default_rng(202601).uniform(0.001, 0.999).
7. Output Namespace:
   - artifacts/native_downstream_v1/
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import logging
import math
from pathlib import Path
import random
import time
from typing import Any, Final, Mapping, Sequence

import joblib
import numpy as np
import pandas as pd
from scipy.stats import norm, t as student_t
from sklearn.linear_model import Ridge

from src.data.access_guard import assert_data_access_allowed
from src.data.preprocessing import build_linear_preprocessor
from src.data.stratified_loader import load_stratified_fold_data
from src.evaluation.downstream_comparison_v2 import (
    DEFAULT_SCENARIO_SPECS,
    DownstreamScenario,
    DownstreamScenarioSpec,
    build_scenario_gates,
    extract_scenario_from_raw,
    validate_downstream_input_boundary,
)
from src.evaluation.mc_convergence import (
    MCFailureType,
    ScenarioRealizationMeta,
    generate_crn_latent_matrix,
)
from src.features.tabular_features import prepare_arrival_features
from src.models.probabilistic.baselines import B5NGBoostStudentT
from src.models.probabilistic.contracts import PREDETERMINED_DEPLOYMENT_SEED
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
from src.optimization.sa.neighborhood import generate_neighbor
from src.optimization.sa.objective import compute_state_objective
from src.optimization.sa.state import SAState, create_initial_state
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver
from src.simulation.aircraft_turn import AircraftTurn, AircraftTurnModel
from src.simulation.conflict_detector import detect_conflicts

LOGGER = logging.getLogger("native_downstream_p4")

P4_CERTIFIED_CHECKPOINT_PATH: Final = Path("artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib")
P4_CERTIFIED_SHA256: Final = "e7e7462f17b65b276ebdee9c7beced15e090f69b088a18896d5a91aaa8cb062f"
NATIVE_DOWNSTREAM_DIR: Final = Path("artifacts/native_downstream_v1")
SOLVER_TIME_LIMIT_SECONDS: Final = 2.0
PREREGISTERED_MC_GRID: Final[tuple[int, ...]] = (100, 250, 500, 1000, 2500)
CANONICAL_MC_N: Final = 500


class P4VerificationError(RuntimeError):
    """Raised when frozen P4 checkpoint fails integrity or capability checks."""


class P5RoleViolationError(RuntimeError):
    """Raised when an attempt is made to use P5 in downstream simulation."""


def verify_and_load_p4_checkpoint(
    checkpoint_path: Path = P4_CERTIFIED_CHECKPOINT_PATH,
    expected_sha256: str = P4_CERTIFIED_SHA256,
) -> tuple[B5NGBoostStudentT, dict[str, Any]]:
    """Verify cryptographic hash and load frozen P4 checkpoint.

    Returns:
        Tuple of (loaded B5NGBoostStudentT model, verification metadata dict).
    """
    if not checkpoint_path.exists():
        raise P4VerificationError(f"P4 checkpoint file missing at: {checkpoint_path}")

    with open(checkpoint_path, "rb") as f:
        file_bytes = f.read()

    actual_sha256 = hashlib.sha256(file_bytes).hexdigest()
    if actual_sha256 != expected_sha256:
        raise P4VerificationError(
            f"P4 checkpoint SHA-256 mismatch! Expected {expected_sha256}, got {actual_sha256}"
        )

    model = joblib.load(checkpoint_path)
    if not isinstance(model, B5NGBoostStudentT):
        raise P4VerificationError(
            f"Loaded model is of type {type(model)}, expected B5NGBoostStudentT"
        )

    if not getattr(model, "is_fitted_", False) or model.model_ is None:
        raise P4VerificationError("P4 model is not marked as fitted or missing underlying booster")

    metadata = {
        "checkpoint_path": str(checkpoint_path).replace("\\", "/"),
        "sha256": actual_sha256,
        "expected_sha256": expected_sha256,
        "file_size_bytes": len(file_bytes),
        "model_class": f"{model.__class__.__module__}.{model.__class__.__name__}",
        "n_estimators": model.n_estimators,
        "learning_rate": model.learning_rate,
        "seed": model.seed,
        "verification_status": "CERTIFIED_VALID",
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    return model, metadata


class TimeBudgetedSimulatedAnnealingSolver:
    """Time-bounded Simulated Annealing solver matching R26 specifications."""

    def __init__(
        self,
        config: GateOptimizationConfig,
        time_budget_seconds: float = SOLVER_TIME_LIMIT_SECONDS,
        seed: int = PREDETERMINED_DEPLOYMENT_SEED,
        T0: float = 100.0,
        Tmin: float = 0.01,
        move_prob: float = 0.7,
        max_attempts: int = 50,
    ) -> None:
        self.config = config
        self.time_budget_seconds = float(time_budget_seconds)
        self.seed = int(seed)
        self.T0 = float(T0)
        self.Tmin = float(Tmin)
        self.move_prob = float(move_prob)
        self.max_attempts = int(max_attempts)

    def solve(
        self,
        flights: Sequence[Flight],
        gates: Sequence[Gate],
        *,
        initial_assignments: Mapping[str, GateAssignment] | None = None,
        allow_overflow: bool = True,
    ) -> tuple[OptimizationResult, list[float], int]:
        t0 = time.perf_counter()
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
            greedy_solver = DeterministicGreedyGateSolver(config=self.config)
            greedy_res = greedy_solver.solve(flights, gate_list, allow_overflow=allow_overflow)
            if not greedy_res.feasible:
                raise ValueError("Greedy failed to produce initial feasible assignment.")
            init_assignments = greedy_res.assignments
        else:
            init_assignments = dict(initial_assignments)

        curr_state = create_initial_state(flights, gate_list, init_assignments)
        curr_obj = compute_state_objective(curr_state, self.config)
        best_state = curr_state.copy()
        best_obj = curr_obj

        best_so_far_trace: list[float] = [best_obj]
        rng = random.Random(self.seed)
        iterations = 0

        while True:
            elapsed = time.perf_counter() - t0
            if elapsed >= self.time_budget_seconds:
                break

            iterations += 1
            progress = min(1.0, elapsed / max(self.time_budget_seconds, 1e-6))
            temp = max(self.Tmin, self.T0 * ((self.Tmin / self.T0) ** progress))

            cand_state = generate_neighbor(
                curr_state,
                rng,
                move_prob=self.move_prob,
                max_attempts=self.max_attempts,
            )

            if cand_state is not None:
                cand_obj = compute_state_objective(cand_state, self.config)
                delta = cand_obj - curr_obj

                if delta <= 0:
                    accept = True
                else:
                    if temp <= 1e-12:
                        prob = 0.0
                    else:
                        exp_val = -delta / temp
                        prob = math.exp(exp_val) if exp_val > -700.0 else 0.0
                    accept = rng.random() < prob

                if accept:
                    curr_state = cand_state
                    curr_obj = cand_obj

                    if curr_obj < best_obj:
                        best_state = curr_state.copy()
                        best_obj = curr_obj

            best_so_far_trace.append(best_obj)

        actual_runtime_ms = (time.perf_counter() - t0) * 1000.0
        final_assignments = best_state.to_gate_assignments()
        result = evaluate_gate_assignment(
            assignments=final_assignments,
            flights=flights,
            gates=gate_list,
            config=self.config,
            runtime_ms=actual_runtime_ms,
            solver_status="FEASIBLE",
            solver_name="SimulatedAnnealing",
        )
        return result, best_so_far_trace, iterations


@dataclass
class SolverExecutionRecord:
    """Record of a solver benchmark run on a scenario and forecast arm."""

    model_id: str
    scenario_id: str
    solver_name: str
    seed: int
    budget_seconds: float
    runtime_ms: float
    status: str
    feasible: bool
    objective_value: float
    reassignment_count: int
    contact_count: int
    remote_count: int
    unassigned_count: int
    planned_conflicts: int
    realized_conflicts: int
    iterations: int | None = None
    gap: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def execute_four_solvers(
    model_id: str,
    scenario: DownstreamScenario,
    planned_delays: Sequence[float],
    config: GateOptimizationConfig,
    turn_model: AircraftTurnModel,
) -> list[SolverExecutionRecord]:
    """Execute all 4 authorized solvers on planned flights under identical conditions."""
    df = scenario.flights_df
    contact_gates, overflow_gate = build_scenario_gates(scenario.n_contact_gates)
    all_gates = contact_gates + [overflow_gate]

    planned_turns = [
        turn_model.synthesize_turn(
            flight_id=str(row["flight_key"]),
            carrier=str(row["OP_CARRIER"]),
            flight_number=str(row["OP_CARRIER_FL_NUM"]),
            scheduled_arrival_min=int(row["_sched_arr_min"]),
            sampled_delay_min=float(planned_delays[i]),
            nominal_gate_id=str(row["nominal_gate_id"]),
        )
        for i, (_, row) in enumerate(df.iterrows())
    ]
    planned_flights = [t.to_flight(i) for i, t in enumerate(planned_turns)]
    records: list[SolverExecutionRecord] = []

    # 1. DeterministicGreedy
    t_g0 = time.perf_counter()
    solver_greedy = DeterministicGreedyGateSolver(config=config)
    res_greedy = solver_greedy.solve(planned_flights, all_gates, allow_overflow=True)
    rt_greedy_ms = (time.perf_counter() - t_g0) * 1000.0
    diag_g = res_greedy.constraint_diagnostics

    records.append(
        SolverExecutionRecord(
            model_id=model_id,
            scenario_id=scenario.scenario_id,
            solver_name="DeterministicGreedy",
            seed=config.random_seed,
            budget_seconds=config.time_limit_seconds,
            runtime_ms=round(rt_greedy_ms, 2),
            status=res_greedy.status,
            feasible=res_greedy.feasible,
            objective_value=round(res_greedy.objective_value, 4),
            reassignment_count=sum(
                1 for f in planned_flights
                if f.nominal_gate_id is not None
                and res_greedy.assignments.get(f.flight_id) is not None
                and res_greedy.assignments[f.flight_id].gate_id != f.nominal_gate_id
            ),
            contact_count=diag_g.contact_count,
            remote_count=diag_g.remote_count,
            unassigned_count=diag_g.unassigned_count,
            planned_conflicts=diag_g.conflict_count,
            realized_conflicts=diag_g.realized_post_hoc_conflicts_count,
            iterations=None,
            gap=None,
        )
    )

    # 2. CPSat (Standalone, Budget = 2.0s)
    t_cp0 = time.perf_counter()
    solver_cpsat = CPSatGateSolver(config=config)
    res_cpsat = solver_cpsat.solve(planned_flights, all_gates, allow_overflow=True)
    rt_cpsat_ms = (time.perf_counter() - t_cp0) * 1000.0
    diag_cp = res_cpsat.constraint_diagnostics

    records.append(
        SolverExecutionRecord(
            model_id=model_id,
            scenario_id=scenario.scenario_id,
            solver_name="CPSat",
            seed=config.random_seed,
            budget_seconds=config.time_limit_seconds,
            runtime_ms=round(rt_cpsat_ms, 2),
            status=res_cpsat.status,
            feasible=res_cpsat.feasible,
            objective_value=round(res_cpsat.objective_value, 4),
            reassignment_count=sum(
                1 for f in planned_flights
                if f.nominal_gate_id is not None
                and res_cpsat.assignments.get(f.flight_id) is not None
                and res_cpsat.assignments[f.flight_id].gate_id != f.nominal_gate_id
            ),
            contact_count=diag_cp.contact_count,
            remote_count=diag_cp.remote_count,
            unassigned_count=diag_cp.unassigned_count,
            planned_conflicts=diag_cp.conflict_count,
            realized_conflicts=diag_cp.realized_post_hoc_conflicts_count,
            iterations=None,
            gap=res_cpsat.optimality_gap,
        )
    )

    # 3. SimulatedAnnealing (Standalone, Budget = 2.0s, Initial = Greedy)
    t_sa0 = time.perf_counter()
    solver_sa = TimeBudgetedSimulatedAnnealingSolver(
        config=config,
        time_budget_seconds=config.time_limit_seconds,
        seed=config.random_seed,
    )
    res_sa, trace_sa, iters_sa = solver_sa.solve(
        planned_flights,
        all_gates,
        initial_assignments=res_greedy.assignments,
        allow_overflow=True,
    )
    rt_sa_ms = (time.perf_counter() - t_sa0) * 1000.0
    diag_sa = res_sa.constraint_diagnostics

    records.append(
        SolverExecutionRecord(
            model_id=model_id,
            scenario_id=scenario.scenario_id,
            solver_name="SimulatedAnnealing",
            seed=config.random_seed,
            budget_seconds=config.time_limit_seconds,
            runtime_ms=round(rt_sa_ms, 2),
            status=res_sa.status,
            feasible=res_sa.feasible,
            objective_value=round(res_sa.objective_value, 4),
            reassignment_count=sum(
                1 for f in planned_flights
                if f.nominal_gate_id is not None
                and res_sa.assignments.get(f.flight_id) is not None
                and res_sa.assignments[f.flight_id].gate_id != f.nominal_gate_id
            ),
            contact_count=diag_sa.contact_count,
            remote_count=diag_sa.remote_count,
            unassigned_count=diag_sa.unassigned_count,
            planned_conflicts=diag_sa.conflict_count,
            realized_conflicts=diag_sa.realized_post_hoc_conflicts_count,
            iterations=iters_sa,
            gap=None,
        )
    )

    # 4. HybridCPSatSA (Total = 2.0s: CP-SAT 1.0s + SA 1.0s)
    t_hyb0 = time.perf_counter()
    cfg_half_cp = GateOptimizationConfig(
        reassignment_weight=config.reassignment_weight,
        overflow_weight=config.overflow_weight,
        delay_weight=config.delay_weight,
        conflict_weight=config.conflict_weight,
        risk_weight=config.risk_weight,
        time_limit_seconds=config.time_limit_seconds / 2.0,
        num_search_workers=1,
        random_seed=config.random_seed,
    )
    solver_cp_half = CPSatGateSolver(config=cfg_half_cp)
    res_cp_half = solver_cp_half.solve(planned_flights, all_gates, allow_overflow=True)
    incumbent = res_cp_half.assignments if res_cp_half.feasible else res_greedy.assignments

    solver_sa_half = TimeBudgetedSimulatedAnnealingSolver(
        config=config,
        time_budget_seconds=config.time_limit_seconds / 2.0,
        seed=config.random_seed,
    )
    res_hyb, trace_hyb, iters_hyb = solver_sa_half.solve(
        planned_flights,
        all_gates,
        initial_assignments=incumbent,
        allow_overflow=True,
    )
    rt_hyb_ms = (time.perf_counter() - t_hyb0) * 1000.0
    diag_hyb = res_hyb.constraint_diagnostics

    records.append(
        SolverExecutionRecord(
            model_id=model_id,
            scenario_id=scenario.scenario_id,
            solver_name="HybridCPSatSA",
            seed=config.random_seed,
            budget_seconds=config.time_limit_seconds,
            runtime_ms=round(rt_hyb_ms, 2),
            status=res_hyb.status,
            feasible=res_hyb.feasible,
            objective_value=round(res_hyb.objective_value, 4),
            reassignment_count=sum(
                1 for f in planned_flights
                if f.nominal_gate_id is not None
                and res_hyb.assignments.get(f.flight_id) is not None
                and res_hyb.assignments[f.flight_id].gate_id != f.nominal_gate_id
            ),
            contact_count=diag_hyb.contact_count,
            remote_count=diag_hyb.remote_count,
            unassigned_count=diag_hyb.unassigned_count,
            planned_conflicts=diag_hyb.conflict_count,
            realized_conflicts=diag_hyb.realized_post_hoc_conflicts_count,
            iterations=iters_hyb,
            gap=res_cp_half.optimality_gap,
        )
    )

    return records


@dataclass(frozen=True)
class MonteCarloConvergenceResult:
    """Statistical summary across Monte Carlo sample count N."""

    model_id: str
    n_requested: int
    n_actual: int
    n_success: int
    n_failed: int
    mean_objective: float
    median_objective: float
    std_objective: float
    variance_objective: float
    mc_se_objective: float
    ci_95_lower: float
    ci_95_upper: float
    delta_from_previous_n: float | None = None
    rel_change_from_previous_n: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_monte_carlo_grid(
    model_id: str,
    scenario: DownstreamScenario,
    delay_matrix: np.ndarray,
    counts: Sequence[int] = PREREGISTERED_MC_GRID,
    config: GateOptimizationConfig | None = None,
    turn_model: AircraftTurnModel | None = None,
) -> tuple[list[MonteCarloConvergenceResult], list[ScenarioRealizationMeta]]:
    """Run Monte Carlo simulation across preregistered grid of N with full failure accounting."""
    cfg = config or GateOptimizationConfig()
    tm = turn_model or AircraftTurnModel(
        min_turnaround_min=cfg.min_turnaround_minutes,
        default_dwell_min=cfg.default_dwell_minutes,
        separation_buffer_min=cfg.separation_buffer_minutes,
    )

    contact_gates, overflow_gate = build_scenario_gates(scenario.n_contact_gates)
    all_gates = contact_gates + [overflow_gate]
    solver = DeterministicGreedyGateSolver(config=cfg)

    df = scenario.flights_df
    flight_keys = [str(k) for k in df["flight_key"]]
    carriers = [str(c) for c in df["OP_CARRIER"]]
    flight_nums = [str(n) for n in df["OP_CARRIER_FL_NUM"]]
    nominal_gates = [str(g) for g in df["nominal_gate_id"]]
    sched_arrs = [int(a) for a in df["_sched_arr_min"]]
    n_flights = len(df)

    max_n = max(counts)
    if delay_matrix.shape[0] < max_n:
        raise ValueError(f"Delay matrix has {delay_matrix.shape[0]} rows, requires at least {max_n}")

    # Solve all up to max_n realizations
    realizations: list[ScenarioRealizationMeta] = []
    objectives: list[float] = []

    for s_idx in range(max_n):
        s_delays = delay_matrix[s_idx]
        realization_hash = hashlib.sha256(s_delays.tobytes()).hexdigest()
        realization_id = f"{scenario.scenario_id}_{model_id}_S{s_idx:04d}"

        if np.isnan(s_delays).any() or np.isinf(s_delays).any():
            realizations.append(
                ScenarioRealizationMeta(
                    realization_id=realization_id,
                    scenario_index=s_idx,
                    requested_n=max_n,
                    actual_n=max_n,
                    latent_seed=cfg.random_seed,
                    scenario_seed=cfg.random_seed + s_idx,
                    realization_hash=realization_hash,
                    failure_type=MCFailureType.NUMERICAL_ERROR,
                    objective_value=None,
                    feasible=False,
                    runtime_ms=0.0,
                )
            )
            continue

        try:
            turns = [
                tm.synthesize_turn(
                    flight_id=flight_keys[i],
                    carrier=carriers[i],
                    flight_number=flight_nums[i],
                    scheduled_arrival_min=sched_arrs[i],
                    sampled_delay_min=float(s_delays[i]),
                    nominal_gate_id=nominal_gates[i],
                )
                for i in range(n_flights)
            ]
            flights_domain = [t.to_flight(i) for i, t in enumerate(turns)]
            opt_res = solver.solve(flights_domain, all_gates, allow_overflow=True)
            eval_res = evaluate_gate_assignment(
                assignments=opt_res.assignments,
                flights=flights_domain,
                gates=all_gates,
                config=cfg,
                runtime_ms=opt_res.runtime_ms,
                solver_status=opt_res.status,
                solver_name="DeterministicGreedy",
            )
            diag = eval_res.constraint_diagnostics
            is_feasible = bool(eval_res.feasible and diag.is_valid and diag.unassigned_count == 0)
            failure_type = MCFailureType.SUCCESS if is_feasible else MCFailureType.INFEASIBLE
            obj_val = round(eval_res.objective_value, 4)

            realizations.append(
                ScenarioRealizationMeta(
                    realization_id=realization_id,
                    scenario_index=s_idx,
                    requested_n=max_n,
                    actual_n=max_n,
                    latent_seed=cfg.random_seed,
                    scenario_seed=cfg.random_seed + s_idx,
                    realization_hash=realization_hash,
                    failure_type=failure_type,
                    objective_value=obj_val,
                    feasible=is_feasible,
                    runtime_ms=round(opt_res.runtime_ms, 2),
                )
            )
            objectives.append(obj_val)
        except Exception as exc:
            realizations.append(
                ScenarioRealizationMeta(
                    realization_id=realization_id,
                    scenario_index=s_idx,
                    requested_n=max_n,
                    actual_n=max_n,
                    latent_seed=cfg.random_seed,
                    scenario_seed=cfg.random_seed + s_idx,
                    realization_hash=realization_hash,
                    failure_type=MCFailureType.INFEASIBLE,
                    objective_value=None,
                    feasible=False,
                    runtime_ms=0.0,
                )
            )

    # Compute convergence results for each requested N
    convergence_results: list[MonteCarloConvergenceResult] = []
    prev_mean: float | None = None

    for n in counts:
        sub_objs = [r.objective_value for r in realizations[:n] if r.objective_value is not None]
        n_actual = len(sub_objs)
        n_succ = sum(1 for r in realizations[:n] if r.failure_type == MCFailureType.SUCCESS)
        n_fail = n - n_succ

        mean_val = float(np.mean(sub_objs)) if n_actual > 0 else float("inf")
        median_val = float(np.median(sub_objs)) if n_actual > 0 else float("inf")
        std_val = float(np.std(sub_objs, ddof=1)) if n_actual > 1 else 0.0
        var_val = float(np.var(sub_objs, ddof=1)) if n_actual > 1 else 0.0
        mc_se = std_val / math.sqrt(n_actual) if n_actual > 1 else 0.0
        ci_lower = mean_val - 1.96 * mc_se
        ci_upper = mean_val + 1.96 * mc_se

        delta_prev = round(mean_val - prev_mean, 4) if prev_mean is not None else None
        rel_change = round(abs(mean_val - prev_mean) / abs(prev_mean), 6) if prev_mean is not None and prev_mean != 0 else None
        prev_mean = mean_val

        convergence_results.append(
            MonteCarloConvergenceResult(
                model_id=model_id,
                n_requested=n,
                n_actual=n_actual,
                n_success=n_succ,
                n_failed=n_fail,
                mean_objective=round(mean_val, 4),
                median_objective=round(median_val, 4),
                std_objective=round(std_val, 4),
                variance_objective=round(var_val, 4),
                mc_se_objective=round(mc_se, 4),
                ci_95_lower=round(ci_lower, 4),
                ci_95_upper=round(ci_upper, 4),
                delta_from_previous_n=delta_prev,
                rel_change_from_previous_n=rel_change,
            )
        )

    return convergence_results, realizations
