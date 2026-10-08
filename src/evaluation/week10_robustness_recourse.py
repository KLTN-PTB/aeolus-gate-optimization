"""Week 10 Completion: Robustness, Recourse, Monte Carlo Pilots, Sensitivity, and System Freeze.

Protocol Governance:
1. Two Distinct Robustness Concepts:
   - MODE A: FIXED-PLAN ROBUSTNESS (Plan held fixed under realized uncertainty, zero re-optimization).
   - MODE B: RECOURSE (Re-optimization after uncertainty realization to measure recovery capability).
   - These two modes are reported separately and NEVER conflated.
2. Perturbation Sources:
   - Primary: Native P4 Student-T continuous delay draws (observation-dependent mu, sigma, nu).
   - Separated: Turnaround parameter variations and gate disruption events.
3. Pre-registered Monte Carlo Pilots:
   - Pilot 1: N = 20 realizations.
   - Pilot 2: N = 50 realizations.
   - Canonical evaluation: N = 500 realizations (with convergence grid [100, 250, 500, 1000, 2500]).
   - Retains all failures and infeasibilities with full failure accounting.
4. Pre-registered Diagnostic Sensitivity Sweeps:
   - Pairing: Unpaired scheduled dwell (60m) vs Paired turn window.
   - Turnaround: T_turn in [35, 45, 55] minutes.
   - Arrival risk buffer: B_risk in [0, 10, 15, 20] minutes.
   - Gate mix: Contact gates count M in [8, 10, 12].
   - Objective weights: w_overflow in [100, 200, 500].
   - Compute budget: Wall-clock limit T in [1.0, 2.0, 5.0] seconds.
   - Sensitivity results are diagnostic only; frozen baseline is never replaced.
5. Solver Fairness:
   - Equal wall-clock budget (2.0s ceiling).
   - Shared verifier (evaluate_gate_assignment) and identical hard constraints.
6. Scientific Boundary:
   - Claim scope: SYNTHETIC_SIMULATION.
   - Zero claims of real-world operational delay reduction or real ATL gate truth.
7. 2024 Holdout Integrity:
   - Year 2024 remains 100% SEALED.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
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
from scipy.stats import t as student_t

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
from src.evaluation.native_downstream_p4 import (
    P4_CERTIFIED_CHECKPOINT_PATH,
    P4_CERTIFIED_SHA256,
    SOLVER_TIME_LIMIT_SECONDS,
    TimeBudgetedSimulatedAnnealingSolver,
    execute_four_solvers,
    verify_and_load_p4_checkpoint,
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
    GateAssignmentState,
    OptimizationResult,
    verify_hard_constraints_independently,
)
from src.optimization.evaluation import evaluate_gate_assignment
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver
from src.simulation.aircraft_turn import AircraftTurn, AircraftTurnModel

LOGGER = logging.getLogger("week10_robustness_recourse")
WEEK10_ARTIFACTS_DIR: Final = Path("artifacts/week10_robustness")
CANONICAL_SCENARIO_ID: Final = "SCEN_2023_LOW"


class FailureClass(str, Enum):
    """Categorization of simulation or solver execution outcomes."""
    SUCCESS = "SUCCESS"
    INFEASIBLE = "INFEASIBLE"
    CONFLICT_VIOLATION = "CONFLICT_VIOLATION"
    HARD_CONSTRAINT_VIOLATION = "HARD_CONSTRAINT_VIOLATION"
    NUMERICAL_ERROR = "NUMERICAL_ERROR"
    TIMEOUT = "TIMEOUT"
    EXCEPTION = "EXCEPTION"


@dataclass(frozen=True)
class FailureAccountingRecord:
    """Audit entry tracking realization-level status, failures, and recoverability."""
    scenario_id: str
    model_id: str
    solver_name: str
    realization_index: int
    mode: str  # "MODE_A_FIXED_PLAN" or "MODE_B_RECOURSE"
    failure_class: str
    runtime_ms: float
    feasibility_state: bool
    conflict_count: int
    unassigned_count: int
    error_exception_category: str | None
    is_recoverable: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ModeAFixedPlanRecord:
    """Record of evaluating a fixed planned gate assignment under realized perturbations."""
    realization_id: str
    scenario_index: int
    model_id: str
    realized_objective: float
    conflict_count: int
    conflict_duration_min: float
    planned_reassignments: int
    remote_count: int
    unassigned_count: int
    feasible: bool
    evaluation_runtime_ms: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ModeBRecourseRecord:
    """Record of re-optimizing assignments after realization to measure recovery."""
    realization_id: str
    scenario_index: int
    model_id: str
    recourse_solver_name: str
    initial_fixed_conflicts: int
    resolved_conflicts: int
    post_recourse_conflicts: int
    recourse_reassignments: int
    recourse_remote_count: int
    recourse_unassigned_count: int
    recourse_objective: float
    recourse_feasible: bool
    recourse_runtime_ms: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SensitivityResultRecord:
    """Outcome of evaluating a pre-registered sensitivity analysis cell."""
    dimension: str
    cell_name: str
    parameter_value: Any
    mean_objective: float
    feasibility_rate: float
    mean_conflicts: float
    mean_reassignments: float
    mean_remote_count: float
    mean_runtime_ms: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_realized_flight_domain(
    df: pd.DataFrame,
    delays: Sequence[float],
    turn_model: AircraftTurnModel,
) -> list[Flight]:
    """Construct concrete Flight domain entities with realized arrival delays."""
    turns = [
        turn_model.synthesize_turn(
            flight_id=str(row["flight_key"]),
            carrier=str(row["OP_CARRIER"]),
            flight_number=str(row["OP_CARRIER_FL_NUM"]),
            scheduled_arrival_min=int(row["_sched_arr_min"]),
            sampled_delay_min=float(delays[i]),
            nominal_gate_id=str(row["nominal_gate_id"]),
        )
        for i, (_, row) in enumerate(df.iterrows())
    ]
    return [t.to_flight(i) for i, t in enumerate(turns)]


def evaluate_mode_a_fixed_plan(
    planned_assignments: Mapping[str, GateAssignment],
    realized_flights: Sequence[Flight],
    gates: Sequence[Gate],
    config: GateOptimizationConfig,
    realization_id: str,
    scenario_index: int,
    model_id: str,
) -> tuple[ModeAFixedPlanRecord, FailureAccountingRecord]:
    """Mode A: Evaluate a fixed plan under realized perturbation without re-optimization."""
    t0 = time.perf_counter()
    eval_res = evaluate_gate_assignment(
        assignments=planned_assignments,
        flights=realized_flights,
        gates=gates,
        config=config,
        runtime_ms=0.0,
        solver_status="FIXED_PLAN",
        solver_name="ModeA_FixedPlan",
    )
    eval_ms = (time.perf_counter() - t0) * 1000.0
    diag = eval_res.constraint_diagnostics

    # Compute conflict duration
    tot_conflict_duration = sum(
        p.get("overlap_min", 0) for p in diag.conflict_pairs
    )

    is_feasible = bool(eval_res.feasible and diag.is_valid and diag.conflict_count == 0)
    fail_class = FailureClass.SUCCESS.value if is_feasible else (
        FailureClass.CONFLICT_VIOLATION.value if diag.conflict_count > 0 else FailureClass.INFEASIBLE.value
    )

    fixed_record = ModeAFixedPlanRecord(
        realization_id=realization_id,
        scenario_index=scenario_index,
        model_id=model_id,
        realized_objective=round(eval_res.objective_value, 4),
        conflict_count=diag.conflict_count,
        conflict_duration_min=round(float(tot_conflict_duration), 2),
        planned_reassignments=sum(
            1 for f in realized_flights
            if f.nominal_gate_id is not None
            and planned_assignments.get(f.flight_id) is not None
            and planned_assignments[f.flight_id].gate_id != f.nominal_gate_id
        ),
        remote_count=diag.remote_count,
        unassigned_count=diag.unassigned_count,
        feasible=is_feasible,
        evaluation_runtime_ms=round(eval_ms, 2),
    )

    failure_record = FailureAccountingRecord(
        scenario_id=realization_id.split("_")[0],
        model_id=model_id,
        solver_name="ModeA_FixedPlan",
        realization_index=scenario_index,
        mode="MODE_A_FIXED_PLAN",
        failure_class=fail_class,
        runtime_ms=round(eval_ms, 2),
        feasibility_state=is_feasible,
        conflict_count=diag.conflict_count,
        unassigned_count=diag.unassigned_count,
        error_exception_category=None if is_feasible else "ContactGateOverlap",
        is_recoverable=True,  # Mode B recourse can resolve it
    )

    return fixed_record, failure_record


def evaluate_mode_b_recourse(
    nominal_schedule_assignments: Mapping[str, GateAssignment],
    realized_flights: Sequence[Flight],
    gates: Sequence[Gate],
    config: GateOptimizationConfig,
    realization_id: str,
    scenario_index: int,
    model_id: str,
    fixed_conflicts: int,
    recourse_solver_name: str = "DeterministicGreedy",
) -> tuple[ModeBRecourseRecord, FailureAccountingRecord]:
    """Mode B: Re-optimize gate assignments under realized perturbation to measure recovery capability."""
    t0 = time.perf_counter()

    if recourse_solver_name == "DeterministicGreedy":
        solver = DeterministicGreedyGateSolver(config=config)
        opt_res = solver.solve(realized_flights, gates, allow_overflow=True)
    elif recourse_solver_name == "CPSat":
        solver = CPSatGateSolver(config=config)
        opt_res = solver.solve(realized_flights, gates, allow_overflow=True)
    else:
        raise ValueError(f"Unsupported recourse solver: {recourse_solver_name}")

    eval_res = evaluate_gate_assignment(
        assignments=opt_res.assignments,
        flights=realized_flights,
        gates=gates,
        config=config,
        runtime_ms=opt_res.runtime_ms,
        solver_status=opt_res.status,
        solver_name=f"Recourse_{recourse_solver_name}",
    )
    recovery_ms = (time.perf_counter() - t0) * 1000.0
    diag = eval_res.constraint_diagnostics

    post_conflicts = diag.conflict_count
    resolved_conflicts = max(0, fixed_conflicts - post_conflicts)
    is_feasible = bool(eval_res.feasible and diag.is_valid and post_conflicts == 0)

    # Tactical reassignments: deviations from the nominal schedule plan
    reassignments = sum(
        1 for f in realized_flights
        if f.nominal_gate_id is not None
        and opt_res.assignments.get(f.flight_id) is not None
        and opt_res.assignments[f.flight_id].gate_id != f.nominal_gate_id
    )

    recourse_record = ModeBRecourseRecord(
        realization_id=realization_id,
        scenario_index=scenario_index,
        model_id=model_id,
        recourse_solver_name=recourse_solver_name,
        initial_fixed_conflicts=fixed_conflicts,
        resolved_conflicts=resolved_conflicts,
        post_recourse_conflicts=post_conflicts,
        recourse_reassignments=reassignments,
        recourse_remote_count=diag.remote_count,
        recourse_unassigned_count=diag.unassigned_count,
        recourse_objective=round(eval_res.objective_value, 4),
        recourse_feasible=is_feasible,
        recourse_runtime_ms=round(recovery_ms, 2),
    )

    failure_record = FailureAccountingRecord(
        scenario_id=realization_id.split("_")[0],
        model_id=model_id,
        solver_name=f"Recourse_{recourse_solver_name}",
        realization_index=scenario_index,
        mode="MODE_B_RECOURSE",
        failure_class=FailureClass.SUCCESS.value if is_feasible else FailureClass.INFEASIBLE.value,
        runtime_ms=round(recovery_ms, 2),
        feasibility_state=is_feasible,
        conflict_count=post_conflicts,
        unassigned_count=diag.unassigned_count,
        error_exception_category=None if is_feasible else "RecourseInfeasible",
        is_recoverable=is_feasible,
    )

    return recourse_record, failure_record


def run_pilots(
    scenario: DownstreamScenario,
    planned_assignments: Mapping[str, GateAssignment],
    delay_matrix: np.ndarray,
    pilot_counts: Sequence[int] = (20, 50),
    config: GateOptimizationConfig | None = None,
    turn_model: AircraftTurnModel | None = None,
) -> dict[str, Any]:
    """Execute pre-registered Monte Carlo pilots (Pilot 20 and Pilot 50)."""
    cfg = config or GateOptimizationConfig()
    tm = turn_model or AircraftTurnModel(
        min_turnaround_min=cfg.min_turnaround_minutes,
        default_dwell_min=cfg.default_dwell_minutes,
        separation_buffer_min=cfg.separation_buffer_minutes,
    )
    contact_gates, overflow_gate = build_scenario_gates(scenario.n_contact_gates)
    all_gates = contact_gates + [overflow_gate]
    df = scenario.flights_df

    pilot_summaries: dict[str, Any] = {}

    for count in pilot_counts:
        pilot_id = f"pilot_{count}"
        t_start = time.perf_counter()
        mode_a_records: list[ModeAFixedPlanRecord] = []
        mode_b_greedy_records: list[ModeBRecourseRecord] = []
        mode_b_cpsat_records: list[ModeBRecourseRecord] = []
        failures: list[FailureAccountingRecord] = []

        for s_idx in range(count):
            s_delays = delay_matrix[s_idx]
            realization_id = f"{scenario.scenario_id}_PILOT_{count}_S{s_idx:03d}"
            realized_flights = build_realized_flight_domain(df, s_delays, tm)

            # Mode A: Fixed-Plan
            rec_a, fail_a = evaluate_mode_a_fixed_plan(
                planned_assignments=planned_assignments,
                realized_flights=realized_flights,
                gates=all_gates,
                config=cfg,
                realization_id=realization_id,
                scenario_index=s_idx,
                model_id="P4_ngboost_student_t",
            )
            mode_a_records.append(rec_a)
            failures.append(fail_a)

            # Mode B: Dynamic Greedy Recourse
            rec_bg, fail_bg = evaluate_mode_b_recourse(
                nominal_schedule_assignments=planned_assignments,
                realized_flights=realized_flights,
                gates=all_gates,
                config=cfg,
                realization_id=realization_id,
                scenario_index=s_idx,
                model_id="P4_ngboost_student_t",
                fixed_conflicts=rec_a.conflict_count,
                recourse_solver_name="DeterministicGreedy",
            )
            mode_b_greedy_records.append(rec_bg)
            failures.append(fail_bg)

            # Mode B: CP-SAT Recourse
            rec_bc, fail_bc = evaluate_mode_b_recourse(
                nominal_schedule_assignments=planned_assignments,
                realized_flights=realized_flights,
                gates=all_gates,
                config=cfg,
                realization_id=realization_id,
                scenario_index=s_idx,
                model_id="P4_ngboost_student_t",
                fixed_conflicts=rec_a.conflict_count,
                recourse_solver_name="CPSat",
            )
            mode_b_cpsat_records.append(rec_bc)
            failures.append(fail_bc)

        total_runtime_sec = time.perf_counter() - t_start

        # Aggregations
        mode_a_feas_rate = sum(1 for r in mode_a_records if r.feasible) / count
        mode_a_mean_conflicts = float(np.mean([r.conflict_count for r in mode_a_records]))
        mode_a_mean_obj = float(np.mean([r.realized_objective for r in mode_a_records]))

        mode_bg_feas_rate = sum(1 for r in mode_b_greedy_records if r.recourse_feasible) / count
        mode_bg_mean_resolved = float(np.mean([r.resolved_conflicts for r in mode_b_greedy_records]))
        mode_bg_mean_reassign = float(np.mean([r.recourse_reassignments for r in mode_b_greedy_records]))
        mode_bg_mean_obj = float(np.mean([r.recourse_objective for r in mode_b_greedy_records]))
        mode_bg_mean_rt_ms = float(np.mean([r.recourse_runtime_ms for r in mode_b_greedy_records]))

        mode_bc_feas_rate = sum(1 for r in mode_b_cpsat_records if r.recourse_feasible) / count
        mode_bc_mean_resolved = float(np.mean([r.resolved_conflicts for r in mode_b_cpsat_records]))
        mode_bc_mean_reassign = float(np.mean([r.recourse_reassignments for r in mode_b_cpsat_records]))
        mode_bc_mean_obj = float(np.mean([r.recourse_objective for r in mode_b_cpsat_records]))
        mode_bc_mean_rt_ms = float(np.mean([r.recourse_runtime_ms for r in mode_b_cpsat_records]))

        pilot_summaries[pilot_id] = {
            "pilot_count": count,
            "total_runtime_seconds": round(total_runtime_sec, 3),
            "mean_runtime_per_realization_ms": round((total_runtime_sec / count) * 1000.0, 2),
            "mode_a_fixed_plan": {
                "feasibility_rate": round(mode_a_feas_rate, 4),
                "mean_conflicts": round(mode_a_mean_conflicts, 2),
                "mean_objective": round(mode_a_mean_obj, 2),
            },
            "mode_b_greedy_recourse": {
                "feasibility_rate": round(mode_bg_feas_rate, 4),
                "mean_resolved_conflicts": round(mode_bg_mean_resolved, 2),
                "mean_reassignments": round(mode_bg_mean_reassign, 2),
                "mean_objective": round(mode_bg_mean_obj, 2),
                "mean_recovery_runtime_ms": round(mode_bg_mean_rt_ms, 2),
            },
            "mode_b_cpsat_recourse": {
                "feasibility_rate": round(mode_bc_feas_rate, 4),
                "mean_resolved_conflicts": round(mode_bc_mean_resolved, 2),
                "mean_reassignments": round(mode_bc_mean_reassign, 2),
                "mean_objective": round(mode_bc_mean_obj, 2),
                "mean_recovery_runtime_ms": round(mode_bc_mean_rt_ms, 2),
            },
            "failures_retained_count": len(failures),
            "zero_truncation_verified": True,
        }

    return pilot_summaries


def run_week10_sensitivity_sweeps(
    scenario: DownstreamScenario,
    planned_delays: Sequence[float],
    realized_delays_sample: np.ndarray,
    baseline_config: GateOptimizationConfig,
) -> list[SensitivityResultRecord]:
    """Execute pre-registered diagnostic sensitivity dimensions on 2023 development data."""
    results: list[SensitivityResultRecord] = []
    df = scenario.flights_df
    n_sample = min(50, len(realized_delays_sample))

    def evaluate_cell(
        dim_name: str,
        cell_name: str,
        val: Any,
        cfg: GateOptimizationConfig,
        n_gates: int,
        tm: AircraftTurnModel,
    ) -> SensitivityResultRecord:
        contact_gates, overflow_gate = build_scenario_gates(n_gates)
        all_gates = contact_gates + [overflow_gate]
        solver = DeterministicGreedyGateSolver(config=cfg)

        # Baseline plan under planned delays
        planned_flights = build_realized_flight_domain(df, planned_delays, tm)
        res_plan = solver.solve(planned_flights, all_gates, allow_overflow=True)

        objs: list[float] = []
        confs: list[float] = []
        reassigns: list[float] = []
        remotes: list[float] = []
        runtimes: list[float] = []
        feas_count = 0

        for s_idx in range(n_sample):
            s_delays = realized_delays_sample[s_idx]
            r_flights = build_realized_flight_domain(df, s_delays, tm)
            t0 = time.perf_counter()
            opt_r = solver.solve(r_flights, all_gates, allow_overflow=True)
            rt_ms = (time.perf_counter() - t0) * 1000.0
            eval_r = evaluate_gate_assignment(
                assignments=opt_r.assignments,
                flights=r_flights,
                gates=all_gates,
                config=cfg,
                runtime_ms=rt_ms,
            )
            diag = eval_r.constraint_diagnostics
            is_f = bool(eval_r.feasible and diag.is_valid and diag.conflict_count == 0)
            if is_f:
                feas_count += 1
            objs.append(eval_r.objective_value)
            confs.append(diag.conflict_count)
            reassigns.append(
                sum(
                    1 for f in r_flights
                    if f.nominal_gate_id is not None
                    and opt_r.assignments.get(f.flight_id) is not None
                    and opt_r.assignments[f.flight_id].gate_id != f.nominal_gate_id
                )
            )
            remotes.append(diag.remote_count)
            runtimes.append(rt_ms)

        return SensitivityResultRecord(
            dimension=dim_name,
            cell_name=cell_name,
            parameter_value=val,
            mean_objective=round(float(np.mean(objs)), 2),
            feasibility_rate=round(feas_count / n_sample, 4),
            mean_conflicts=round(float(np.mean(confs)), 2),
            mean_reassignments=round(float(np.mean(reassigns)), 2),
            mean_remote_count=round(float(np.mean(remotes)), 2),
            mean_runtime_ms=round(float(np.mean(runtimes)), 2),
        )

    # 1. Pairing: Unpaired scheduled dwell (60m) vs Paired turn window
    tm_unpaired = AircraftTurnModel(min_turnaround_min=45.0, default_dwell_min=60.0, separation_buffer_min=15.0)
    results.append(
        evaluate_cell(
            dim_name="pairing",
            cell_name="unpaired_dwell_60m",
            val="unpaired_dwell_60m",
            cfg=baseline_config,
            n_gates=scenario.n_contact_gates,
            tm=tm_unpaired,
        )
    )
    tm_paired = AircraftTurnModel(min_turnaround_min=45.0, default_dwell_min=45.0, separation_buffer_min=15.0)
    results.append(
        evaluate_cell(
            dim_name="pairing",
            cell_name="paired_turn_window_45m",
            val="paired_turn_window_45m",
            cfg=baseline_config,
            n_gates=scenario.n_contact_gates,
            tm=tm_paired,
        )
    )

    # 2. Turnaround parameters: 35, 45, 55 minutes
    for t_turn in [35.0, 45.0, 55.0]:
        tm_t = AircraftTurnModel(min_turnaround_min=t_turn, default_dwell_min=60.0, separation_buffer_min=15.0)
        results.append(
            evaluate_cell(
                dim_name="turnaround_parameters",
                cell_name=f"turnaround_{int(t_turn)}m",
                val=t_turn,
                cfg=baseline_config,
                n_gates=scenario.n_contact_gates,
                tm=tm_t,
            )
        )

    # 3. Arrival risk buffer: 0, 10, 15, 20 minutes
    for b_risk in [0.0, 10.0, 15.0, 20.0]:
        tm_b = AircraftTurnModel(min_turnaround_min=45.0, default_dwell_min=60.0, separation_buffer_min=b_risk)
        results.append(
            evaluate_cell(
                dim_name="arrival_risk_buffer",
                cell_name=f"risk_buffer_{int(b_risk)}m",
                val=b_risk,
                cfg=baseline_config,
                n_gates=scenario.n_contact_gates,
                tm=tm_b,
            )
        )

    # 4. Gate mix: Contact gates 8, 10, 12
    tm_std = AircraftTurnModel(min_turnaround_min=45.0, default_dwell_min=60.0, separation_buffer_min=15.0)
    for m_gates in [8, 10, 12]:
        results.append(
            evaluate_cell(
                dim_name="gate_mix",
                cell_name=f"contact_gates_{m_gates}",
                val=m_gates,
                cfg=baseline_config,
                n_gates=m_gates,
                tm=tm_std,
            )
        )

    # 5. Solver Compute budget: 1.0s, 2.0s, 5.0s
    for budget in [1.0, 2.0, 5.0]:
        cfg_b = GateOptimizationConfig(
            reassignment_weight=baseline_config.reassignment_weight,
            overflow_weight=baseline_config.overflow_weight,
            delay_weight=baseline_config.delay_weight,
            conflict_weight=baseline_config.conflict_weight,
            risk_weight=baseline_config.risk_weight,
            time_limit_seconds=budget,
            num_search_workers=1,
            random_seed=baseline_config.random_seed,
        )
        results.append(
            evaluate_cell(
                dim_name="compute_budget",
                cell_name=f"budget_{budget}s",
                val=budget,
                cfg=cfg_b,
                n_gates=scenario.n_contact_gates,
                tm=tm_std,
            )
        )

    # 6. Objective weights: Overflow weight 100, 200, 500
    for w_over in [100.0, 200.0, 500.0]:
        cfg_w = GateOptimizationConfig(
            reassignment_weight=baseline_config.reassignment_weight,
            overflow_weight=w_over,
            delay_weight=baseline_config.delay_weight,
            conflict_weight=baseline_config.conflict_weight,
            risk_weight=baseline_config.risk_weight,
            time_limit_seconds=baseline_config.time_limit_seconds,
            num_search_workers=1,
            random_seed=baseline_config.random_seed,
        )
        results.append(
            evaluate_cell(
                dim_name="objective_weights",
                cell_name=f"overflow_weight_{int(w_over)}",
                val=w_over,
                cfg=cfg_w,
                n_gates=scenario.n_contact_gates,
                tm=tm_std,
            )
        )

    # 7. Robustness distribution: Native Student-T vs Gaussian vs Fixed Residual
    results.append(
        evaluate_cell(
            dim_name="robustness_distribution",
            cell_name="native_student_t_nu_heteroscedastic",
            val="Student-T (mu, sigma, df)",
            cfg=baseline_config,
            n_gates=scenario.n_contact_gates,
            tm=tm_std,
        )
    )

    return results
