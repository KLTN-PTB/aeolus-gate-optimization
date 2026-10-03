"""Downstream Gate Assignment Model Comparison Engine (Phase 8).

Evaluates whether forecast model differences propagate downstream to Gate Assignment.
Protocol Governance:
1. Exactly same 2023 development scenario set, synthetic turns, gates, and seeds.
2. Exactly same objective function and weights across all models.
3. Exactly same solver configuration and runtime budgets (Greedy, CP-SAT, SA).
4. Strictly NO Weather, NO departure delay, NO 2024 data.
5. Forecast models plan assignments; plans are evaluated against realized operations.
6. Scenario identity strictly preserved across paired deltas.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Final, Mapping, Sequence

import numpy as np
import pandas as pd

from src.data.access_guard import assert_data_access_allowed
from src.data.leakage_rules import ARRIVAL_LEAKAGE_COLUMNS, WEATHER_COLUMNS
from src.features.tabular_features import APPROVED_PREDICTOR_COLUMNS
from src.models.probabilistic.contracts import PREDETERMINED_DEPLOYMENT_SEED
from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import (
    ConstraintDiagnostic,
    Flight,
    Gate,
    GateAssignment,
    ObjectiveBreakdown,
    OptimizationResult,
    verify_hard_constraints_independently,
)
from src.optimization.evaluation import evaluate_gate_assignment
from src.optimization.sa import SAConfig, SimulatedAnnealingGateSolver
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver
from src.simulation.aircraft_turn import AircraftTurn, AircraftTurnModel
from src.simulation.conflict_detector import ConflictDetectionResult, detect_conflicts

LOGGER = logging.getLogger("downstream_comparison")
DEFAULT_DOWNSTREAM_DIR: Final = Path("artifacts/downstream_model_comparison")

FORBIDDEN_DEPARTURE_TERMS: Final[tuple[str, ...]] = (
    "p_dep_delay",
    "y_dep_cls",
    "dep_delay",
    "departure_delay",
    "predicted_departure_delay",
)


@dataclass(frozen=True)
class DownstreamCandidate:
    """Specification of a candidate model evaluated in downstream comparison."""

    candidate_id: str
    display_name: str
    family: str  # "baseline", "point", "probabilistic", "reference"
    is_oracle: bool = False
    role: str = "prediction_model"
    note: str | None = None

    def __post_init__(self) -> None:
        if self.is_oracle:
            if self.role != "non_deployable_reference":
                raise ValueError(
                    f"Oracle model {self.candidate_id} must have role='non_deployable_reference', got '{self.role}'"
                )


DEFAULT_DOWNSTREAM_CANDIDATES: Final[tuple[DownstreamCandidate, ...]] = (
    DownstreamCandidate(
        candidate_id="schedule_only",
        display_name="Schedule-Only (0 min delay)",
        family="baseline",
        is_oracle=False,
        role="baseline",
        note="Assumes zero arrival delay; plans strictly to published schedule",
    ),
    DownstreamCandidate(
        candidate_id="arrival_linear_baseline_v1",
        display_name="Ridge / Linear Regression",
        family="point",
        is_oracle=False,
        role="point_model",
        note="Pre-registered linear point model (Phase 7 selected/tied)",
    ),
    DownstreamCandidate(
        candidate_id="arrival_xgboost_baseline_v1",
        display_name="XGBoost Regression",
        family="point",
        is_oracle=False,
        role="point_model",
        note="Pre-registered gradient boosted tree point model",
    ),
    DownstreamCandidate(
        candidate_id="arrival_weighted_ensemble_v1",
        display_name="Weighted Ensemble",
        family="point",
        is_oracle=False,
        role="point_ensemble",
        note="Pre-registered ensemble combining linear, tree, and boosting point predictions",
    ),
    DownstreamCandidate(
        candidate_id="P5_quantile_regression",
        display_name="P5 Quantile Regression (Median)",
        family="probabilistic",
        is_oracle=False,
        role="probabilistic_model",
        note="Quantile regression median forecast (Phase 7 selected probabilistic)",
    ),
    DownstreamCandidate(
        candidate_id="P4_ngboost_student_t",
        display_name="P4 NGBoost Student-T",
        family="probabilistic",
        is_oracle=False,
        role="probabilistic_comparator",
        note="Historical B5 NGBoost heavy-tailed comparator",
    ),
    DownstreamCandidate(
        candidate_id="oracle_actual",
        display_name="Oracle Ground-Truth Realized Delay",
        family="reference",
        is_oracle=True,
        role="non_deployable_reference",
        note="Development upper/reference bound; not a prediction model",
    ),
)


@dataclass(frozen=True)
class DownstreamScenarioSpec:
    """Specification of an operational bank scenario."""

    scenario_id: str
    day_id: str
    date_str: str
    n_flights: int
    n_contact_gates: int
    bank_start_hour: int = 12
    seed: int = PREDETERMINED_DEPLOYMENT_SEED


DEFAULT_SCENARIO_SPECS: Final[tuple[DownstreamScenarioSpec, ...]] = (
    DownstreamScenarioSpec(
        scenario_id="SCEN_2023_LOW",
        day_id="2023-11-23",
        date_str="2023-11-23",
        n_flights=30,
        n_contact_gates=10,
        bank_start_hour=12,
        seed=202601,
    ),
    DownstreamScenarioSpec(
        scenario_id="SCEN_2023_MEDIUM",
        day_id="2023-07-03",
        date_str="2023-07-03",
        n_flights=50,
        n_contact_gates=15,
        bank_start_hour=12,
        seed=202602,
    ),
    DownstreamScenarioSpec(
        scenario_id="SCEN_2023_HIGH",
        day_id="2023-07-13",
        date_str="2023-07-13",
        n_flights=70,
        n_contact_gates=20,
        bank_start_hour=12,
        seed=202603,
    ),
    DownstreamScenarioSpec(
        scenario_id="SCEN_2023_DISRUPTED",
        day_id="2023-08-07",
        date_str="2023-08-07",
        n_flights=50,
        n_contact_gates=15,
        bank_start_hour=12,
        seed=202604,
    ),
)


@dataclass(frozen=True)
class DownstreamScenario:
    """Operational flight scenario representing an operational bank in 2023."""

    scenario_id: str
    day_id: str
    date_str: str
    n_flights: int
    n_contact_gates: int
    scenario_seed: int
    flights_df: pd.DataFrame
    scenario_hash: str


@dataclass
class DownstreamEvaluationRecord:
    """Evaluation record for one (model, scenario, solver) combination."""

    model_id: str
    scenario_id: str
    solver_name: str
    seed: int
    prediction_version: str
    scenario_version: str
    solver_version: str
    objective_version: str
    status: str  # "COMPLETED" or "FAILED"
    failure_reason: str | None
    hard_feasible: bool
    objective_value: float
    decision_cost: float
    reporting_cost: float
    reassignment_count: int
    contact_count: int
    remote_count: int
    unassigned_count: int
    conflict_count: int
    conflict_duration_min: float
    runtime_ms: float
    solver_status: str
    gap: float | None
    created_at_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PairedDownstreamDelta:
    """Paired difference between model A and model B under identical scenario and solver."""

    model_a: str
    model_b: str
    scenario_id: str
    solver_name: str
    delta_objective: float  # Obj(A) - Obj(B)
    delta_reassignments: int  # Reassign(A) - Reassign(B)
    delta_remote: int  # Remote(A) - Remote(B)
    delta_unassigned: int  # Unassigned(A) - Unassigned(B)
    delta_conflicts: int  # Conflicts(A) - Conflicts(B)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_downstream_input_boundary(df_or_columns: Sequence[str] | pd.DataFrame) -> None:
    """Validate that downstream inputs strictly conform to approved Core Arrival predictors.

    Raises:
        ValueError: If any departure delay, weather column, or arrival leakage is detected.
    """
    if isinstance(df_or_columns, pd.DataFrame):
        cols = set(df_or_columns.columns)
    else:
        cols = set(df_or_columns)

    # 1. Departure delay / auxiliary check
    for col in cols:
        col_lower = str(col).lower()
        for term in FORBIDDEN_DEPARTURE_TERMS:
            if term in col_lower:
                raise ValueError(
                    f"Departure delay / auxiliary field forbidden in downstream gate comparison: '{col}'"
                )

    # 2. Weather features check
    weather_keywords = ("weather", "precip", "temp", "wspd", "wind", "snow")
    for col in cols:
        col_str = str(col)
        if col_str in WEATHER_COLUMNS or any(kw in col_str.lower() for kw in weather_keywords):
            raise ValueError(f"Weather features forbidden in downstream gate comparison: '{col_str}'")

    # 3. Arrival leakage check
    leakage_inter = cols.intersection(set(ARRIVAL_LEAKAGE_COLUMNS))
    if leakage_inter:
        raise ValueError(f"Arrival leakage features forbidden in downstream gate comparison: {sorted(leakage_inter)}")


def assert_auxiliary_departure_isolated(model_role: str, task_name: str) -> None:
    """Ensure auxiliary departure delay models are strictly isolated from gate assignment."""
    if "dep" in task_name.lower() or "departure" in task_name.lower():
        raise ValueError(
            f"Auxiliary departure task '{task_name}' is strictly prohibited from downstream arrival gate assignment."
        )
    if "auxiliary" in model_role.lower():
        raise ValueError(
            f"Auxiliary model role '{model_role}' cannot be routed to downstream arrival gate assignment."
        )


def build_scenario_gates(n_contact_gates: int) -> tuple[list[Gate], Gate]:
    """Construct gates list containing n_contact_gates and exactly 1 remote overflow apron."""
    contact_gates = [
        Gate(gate_id=f"G_{i+1:02d}", gate_index=i, is_overflow=False)
        for i in range(n_contact_gates)
    ]
    overflow_gate = Gate(
        gate_id="REMOTE_APRON_01",
        gate_index=n_contact_gates,
        is_overflow=True,
    )
    return contact_gates, overflow_gate


def extract_scenario_from_raw(
    spec: DownstreamScenarioSpec,
    raw_df: pd.DataFrame,
) -> DownstreamScenario:
    """Extract deterministically an operational bank scenario from raw arrival data."""
    sub = raw_df[raw_df["FL_DATE"].astype(str).str.startswith(spec.date_str)].copy()
    if len(sub) == 0:
        raise ValueError(f"No flights found for date {spec.date_str}")

    # Parse scheduled arrival clock into minutes from midnight
    if "CRS_ARR_TIME" in sub.columns:
        parsed_arr = pd.to_datetime(sub["CRS_ARR_TIME"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
        valid_mask = parsed_arr.notna()
        sched_min = pd.Series(index=sub.index, dtype=int)
        if valid_mask.any():
            sched_min.loc[valid_mask] = parsed_arr.loc[valid_mask].dt.hour * 60 + parsed_arr.loc[valid_mask].dt.minute
        if (~valid_mask).any():
            numeric_vals = pd.to_numeric(sub.loc[~valid_mask, "CRS_ARR_TIME"], errors="coerce").fillna(720).astype(int)
            sched_min.loc[~valid_mask] = (numeric_vals // 100) * 60 + (numeric_vals % 100)
    else:
        # Fallback to dep + elapsed
        sched_min = (pd.to_numeric(sub["CRS_DEP_TIME"], errors="coerce").fillna(720).astype(int) // 100) * 60 + 120

    sub["_sched_arr_min"] = sched_min

    # Bank window filter: bank_start_hour onwards
    min_bank_start = spec.bank_start_hour * 60
    bank_sub = sub[sub["_sched_arr_min"] >= min_bank_start]
    if len(bank_sub) < spec.n_flights:
        bank_sub = sub

    # Deterministic ordering
    sorted_sub = bank_sub.sort_values(
        by=["_sched_arr_min", "OP_CARRIER", "OP_CARRIER_FL_NUM", "flight_key"],
        ascending=[True, True, True, True],
    ).head(spec.n_flights).copy().reset_index(drop=True)

    # Assign deterministic published nominal gate
    sorted_sub["nominal_gate_id"] = [
        f"G_{(i % spec.n_contact_gates) + 1:02d}"
        for i in range(len(sorted_sub))
    ]

    # Compute scenario hash
    keys_str = ",".join(sorted_sub["flight_key"].astype(str))
    scenario_hash = hashlib.sha256(f"{spec.scenario_id}:{keys_str}".encode()).hexdigest()

    return DownstreamScenario(
        scenario_id=spec.scenario_id,
        day_id=spec.day_id,
        date_str=spec.date_str,
        n_flights=len(sorted_sub),
        n_contact_gates=spec.n_contact_gates,
        scenario_seed=spec.seed,
        flights_df=sorted_sub,
        scenario_hash=scenario_hash,
    )


def evaluate_candidate_on_scenario(
    candidate: DownstreamCandidate,
    scenario: DownstreamScenario,
    predicted_delays: Sequence[float],
    solver_name: str,
    *,
    config: GateOptimizationConfig | None = None,
    sa_config: SAConfig | None = None,
    turn_model: AircraftTurnModel | None = None,
) -> DownstreamEvaluationRecord:
    """Plan assignments using predicted delays and evaluate against ground truth realized delays."""
    cfg = config or GateOptimizationConfig()
    sa_cfg = sa_config or SAConfig(seed=cfg.random_seed)
    tm = turn_model or AircraftTurnModel(
        min_turnaround_min=cfg.min_turnaround_minutes,
        default_dwell_min=cfg.default_dwell_minutes,
        separation_buffer_min=cfg.separation_buffer_minutes,
    )

    contact_gates, overflow_gate = build_scenario_gates(scenario.n_contact_gates)
    all_gates = contact_gates + [overflow_gate]
    df = scenario.flights_df

    # 1. Synthesize PLANNED flight turns according to candidate forecast
    planned_turns: list[AircraftTurn] = []
    realized_turns: list[AircraftTurn] = []

    for i, (_, row) in enumerate(df.iterrows()):
        f_id = str(row["flight_key"])
        carrier = str(row["OP_CARRIER"])
        fl_num = str(row["OP_CARRIER_FL_NUM"])
        s_arr = int(row["_sched_arr_min"])
        pred_delay = float(predicted_delays[i])
        actual_delay = float(row["ARR_DELAY"])
        nominal_g = str(row["nominal_gate_id"])

        p_turn = tm.synthesize_turn(
            flight_id=f_id,
            carrier=carrier,
            flight_number=fl_num,
            scheduled_arrival_min=s_arr,
            sampled_delay_min=pred_delay,
            nominal_gate_id=nominal_g,
        )
        r_turn = tm.synthesize_turn(
            flight_id=f_id,
            carrier=carrier,
            flight_number=fl_num,
            scheduled_arrival_min=s_arr,
            sampled_delay_min=actual_delay,
            nominal_gate_id=nominal_g,
        )
        planned_turns.append(p_turn)
        realized_turns.append(r_turn)

    planned_flights = [t.to_flight(i) for i, t in enumerate(planned_turns)]
    realized_flights = [t.to_flight(i) for i, t in enumerate(realized_turns)]

    # 2. Execute Solver on Planned Flights
    solver_status = "UNKNOWN"
    gap: float | None = None
    runtime_ms = 0.0
    assignments: dict[str, GateAssignment] = {}
    failure_reason: str | None = None

    try:
        if solver_name == "DeterministicGreedy":
            solver = DeterministicGreedyGateSolver(config=cfg)
            plan_res = solver.solve(planned_flights, all_gates, allow_overflow=True)
            assignments = plan_res.assignments
            solver_status = plan_res.status
            runtime_ms = plan_res.runtime_ms
        elif solver_name == "CPSat":
            solver_cp = CPSatGateSolver(config=cfg)
            plan_res = solver_cp.solve(planned_flights, all_gates, allow_overflow=True)
            assignments = plan_res.assignments
            solver_status = plan_res.status
            gap = plan_res.optimality_gap
            runtime_ms = plan_res.runtime_ms
        elif solver_name == "SimulatedAnnealing":
            solver_sa = SimulatedAnnealingGateSolver(config=cfg, sa_config=sa_cfg)
            plan_res = solver_sa.solve(planned_flights, all_gates, allow_overflow=True)
            assignments = plan_res.assignments
            solver_status = plan_res.status
            runtime_ms = plan_res.runtime_ms
        else:
            raise ValueError(f"Unsupported solver_name: {solver_name}")
    except Exception as exc:
        LOGGER.exception(f"Solver {solver_name} failed on scenario {scenario.scenario_id}: {exc}")
        return DownstreamEvaluationRecord(
            model_id=candidate.candidate_id,
            scenario_id=scenario.scenario_id,
            solver_name=solver_name,
            seed=cfg.random_seed,
            prediction_version="v1",
            scenario_version=scenario.scenario_hash[:8],
            solver_version="v1",
            objective_version="v1",
            status="FAILED",
            failure_reason=str(exc),
            hard_feasible=False,
            objective_value=float("inf"),
            decision_cost=float("inf"),
            reporting_cost=float("inf"),
            reassignment_count=0,
            contact_count=0,
            remote_count=0,
            unassigned_count=len(scenario.flights_df),
            conflict_count=999,
            conflict_duration_min=999.0,
            runtime_ms=runtime_ms,
            solver_status="ERROR",
            gap=None,
        )

    # 3. Evaluate Planned Assignments Against REALIZED Operations
    realized_eval = evaluate_gate_assignment(
        assignments=assignments,
        flights=realized_flights,
        gates=all_gates,
        config=cfg,
        runtime_ms=runtime_ms,
        solver_status=solver_status,
        solver_name=solver_name,
    )

    conflict_res = detect_conflicts(
        assignments=assignments,
        turns=realized_turns,
        gates=all_gates,
    )

    # Invariants and counts
    n_contact = 0
    n_remote = 0
    n_reassigned = 0
    for f in realized_flights:
        assign = assignments.get(f.flight_id)
        if assign is not None:
            if assign.gate_id == overflow_gate.gate_id or assign.is_overflow:
                n_remote += 1
            else:
                n_contact += 1
            if f.nominal_gate_id is not None and assign.gate_id != f.nominal_gate_id:
                n_reassigned += 1

    n_unassigned = len(realized_flights) - len(assignments)
    is_hard_feasible = bool(
        realized_eval.feasible
        and (conflict_res.conflict_count == 0)
        and (n_unassigned == 0)
    )

    decision_cost = (
        realized_eval.objective_breakdown.reassignment_cost
        + realized_eval.objective_breakdown.overflow_cost
    )
    reporting_cost = (
        realized_eval.objective_breakdown.delay_cost
        + realized_eval.objective_breakdown.risk_cost
    )

    return DownstreamEvaluationRecord(
        model_id=candidate.candidate_id,
        scenario_id=scenario.scenario_id,
        solver_name=solver_name,
        seed=cfg.random_seed,
        prediction_version="v1",
        scenario_version=scenario.scenario_hash[:8],
        solver_version="v1",
        objective_version="v1",
        status="COMPLETED",
        failure_reason=None,
        hard_feasible=is_hard_feasible,
        objective_value=round(realized_eval.objective_value, 4),
        decision_cost=round(decision_cost, 4),
        reporting_cost=round(reporting_cost, 4),
        reassignment_count=n_reassigned,
        contact_count=n_contact,
        remote_count=n_remote,
        unassigned_count=n_unassigned,
        conflict_count=conflict_res.conflict_count,
        conflict_duration_min=round(conflict_res.total_conflict_duration_min, 2),
        runtime_ms=round(runtime_ms, 2),
        solver_status=solver_status,
        gap=gap,
    )


def compute_paired_downstream_deltas(
    records: Sequence[DownstreamEvaluationRecord],
) -> list[PairedDownstreamDelta]:
    """Compute exact scenario-level paired differences between all model pairs."""
    records_by_key: dict[tuple[str, str, str], DownstreamEvaluationRecord] = {}
    for r in records:
        if r.status == "COMPLETED":
            records_by_key[(r.model_id, r.scenario_id, r.solver_name)] = r

    models = sorted({r.model_id for r in records if r.status == "COMPLETED"})
    scenarios = sorted({r.scenario_id for r in records if r.status == "COMPLETED"})
    solvers = sorted({r.solver_name for r in records if r.status == "COMPLETED"})

    deltas: list[PairedDownstreamDelta] = []

    for scen in scenarios:
        for solv in solvers:
            for i in range(len(models)):
                for j in range(i + 1, len(models)):
                    m_a = models[i]
                    m_b = models[j]
                    rec_a = records_by_key.get((m_a, scen, solv))
                    rec_b = records_by_key.get((m_b, scen, solv))
                    if rec_a is not None and rec_b is not None:
                        deltas.append(
                            PairedDownstreamDelta(
                                model_a=m_a,
                                model_b=m_b,
                                scenario_id=scen,
                                solver_name=solv,
                                delta_objective=round(rec_a.objective_value - rec_b.objective_value, 4),
                                delta_reassignments=rec_a.reassignment_count - rec_b.reassignment_count,
                                delta_remote=rec_a.remote_count - rec_b.remote_count,
                                delta_unassigned=rec_a.unassigned_count - rec_b.unassigned_count,
                                delta_conflicts=rec_a.conflict_count - rec_b.conflict_count,
                            )
                        )
    return deltas


def export_downstream_artifacts(
    records: Sequence[DownstreamEvaluationRecord],
    deltas: Sequence[PairedDownstreamDelta],
    output_dir: Path = DEFAULT_DOWNSTREAM_DIR,
) -> dict[str, str]:
    """Export authoritative downstream comparison artifacts and sha256 checksums."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. evaluations.json & evaluations.csv
    rec_dicts = [r.to_dict() for r in records]
    evals_json_path = output_dir / "evaluations.json"
    with open(evals_json_path, "w", encoding="utf-8") as f:
        json.dump(rec_dicts, f, indent=2)

    df_evals = pd.DataFrame(rec_dicts)
    evals_csv_path = output_dir / "evaluations.csv"
    df_evals.to_csv(evals_csv_path, index=False)

    # 2. paired_deltas.json & paired_deltas.csv
    delta_dicts = [d.to_dict() for d in deltas]
    deltas_json_path = output_dir / "paired_deltas.json"
    with open(deltas_json_path, "w", encoding="utf-8") as f:
        json.dump(delta_dicts, f, indent=2)

    df_deltas = pd.DataFrame(delta_dicts)
    deltas_csv_path = output_dir / "paired_deltas.csv"
    df_deltas.to_csv(deltas_csv_path, index=False)

    # 3. downstream_summary.json
    summary = {
        "benchmark": "Phase 8 Downstream Model Gate Assignment Evaluation",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "total_evaluations": len(records),
        "total_completed": sum(1 for r in records if r.status == "COMPLETED"),
        "total_paired_comparisons": len(deltas),
        "models_evaluated": sorted(list({r.model_id for r in records})),
        "scenarios_evaluated": sorted(list({r.scenario_id for r in records})),
        "solvers_evaluated": sorted(list({r.solver_name for r in records})),
        "model_summary": {},
    }

    for m in sorted(list({r.model_id for r in records if r.status == "COMPLETED"})):
        m_recs = [r for r in records if r.model_id == m and r.status == "COMPLETED"]
        summary["model_summary"][m] = {
            "completed_runs": len(m_recs),
            "feasible_runs": sum(1 for r in m_recs if r.hard_feasible),
            "mean_objective": float(np.mean([r.objective_value for r in m_recs])),
            "total_conflicts": int(sum(r.conflict_count for r in m_recs)),
            "mean_reassignments": float(np.mean([r.reassignment_count for r in m_recs])),
            "mean_remote_count": float(np.mean([r.remote_count for r in m_recs])),
            "mean_runtime_ms": float(np.mean([r.runtime_ms for r in m_recs])),
        }

    summary_json_path = output_dir / "downstream_summary.json"
    with open(summary_json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # 4. manifest.sha256
    files_to_hash = [
        evals_json_path,
        evals_csv_path,
        deltas_json_path,
        deltas_csv_path,
        summary_json_path,
    ]
    manifest_hashes: dict[str, str] = {}
    manifest_lines: list[str] = []

    for p in files_to_hash:
        with open(p, "rb") as f:
            digest = hashlib.sha256(f.read()).hexdigest()
        manifest_hashes[p.name] = digest
        manifest_lines.append(f"{digest}  {p.name}")

    manifest_path = output_dir / "manifest.sha256"
    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write("\n".join(manifest_lines) + "\n")

    return manifest_hashes
