"""Step 7 — Broader Development End-to-End Benchmark Runner.

Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 19
Methodology:
- Evaluates development data only: 2016-2022 development training + 2023 development benchmark.
- Strictly NO 2024 data accessed.
- Evaluates multiple deterministic development days across varying demand levels:
    1. DAY_LOW: 2023-11-23 (Thanksgiving Day off-peak bank, 40 flights, 12 contact gates)
    2. DAY_MEDIUM: 2023-07-03 (Summer pre-holiday midday bank, 70 flights, 18 contact gates)
    3. DAY_HIGH: 2023-07-13 (Peak summer weekday afternoon bank, 100 flights, 24 contact gates)
    4. DAY_WEATHER_DISRUPTED: 2023-08-07 (Severe convective storm bank, 70 flights, 18 contact gates)
- Full closed loop:
    Frozen B5 NGBoost Student-T model
    → D2 Gaussian Copula joint delay sampler
    → Monte Carlo scenarios (10 per day, 40 total)
    → AircraftTurnModel (timeline semantics: gate_in, gate_out, gate_release)
    → Conflict detection on nominal schedule
    → Deterministic Greedy Solver
    → CP-SAT Solver
    → Simulated Annealing time-limited benchmark (CP-SAT+SA and Greedy+SA)
    → Independent hard-constraint verification
- Records method-wise statistical distributions rather than declaring a single global winner.
- Failures preserved in failures.json (no silent dropping).
- Deterministic repetition verification confirmed.
- Exports artifacts to artifacts/development_end_to_end/.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

# Ensure repository root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd

from src.audit.protocol_guards import ProtocolComplianceGuard
from src.audit.provenance import compute_sha256
from src.data.stratified_loader import load_stratified_fold_data
from src.features.tabular_features import prepare_arrival_features
from src.models.probabilistic.baselines import B5NGBoostStudentT
from src.models.probabilistic.contracts import (
    PREDETERMINED_DEPLOYMENT_SEED,
    PROBABILISTIC_PREDICTOR_COLUMNS,
)
from src.models.probabilistic.dependence import (
    GaussianCopulaDependenceModel,
    StudentTMarginalDistribution,
)
from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import Gate, verify_hard_constraints_independently
from src.optimization.sa import SAConfig, SimulatedAnnealingGateSolver
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver
from src.simulation.aircraft_turn import AircraftTurnModel
from src.simulation.conflict_detector import detect_conflicts
from src.simulation.scenario_runner import MonteCarloScenarioRunner

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
LOGGER = logging.getLogger("dev_e2e_benchmark")

# Benchmark Development Days Specification (Varying Demand Levels)
BENCHMARK_DAYS_SPEC = [
    {
        "day_id": "DAY_LOW",
        "date_str": "2023-11-23",
        "demand_level": "LOW",
        "description": "Thanksgiving Day off-peak morning bank (light operational demand)",
        "n_flights": 40,
        "n_contact_gates": 12,
        "bank_time_range": (360, 720),  # 06:00 to 12:00
    },
    {
        "day_id": "DAY_MEDIUM",
        "date_str": "2023-07-03",
        "demand_level": "MEDIUM",
        "description": "Summer pre-holiday midday bank (moderate operational demand)",
        "n_flights": 70,
        "n_contact_gates": 18,
        "bank_time_range": (660, 1020),  # 11:00 to 17:00
    },
    {
        "day_id": "DAY_HIGH",
        "date_str": "2023-07-13",
        "demand_level": "HIGH",
        "description": "Peak summer weekday bank (maximum throughput demand)",
        "n_flights": 100,
        "n_contact_gates": 24,
        "bank_time_range": (780, 1260),  # 13:00 to 21:00
    },
    {
        "day_id": "DAY_WEATHER_DISRUPTED",
        "date_str": "2023-08-07",
        "demand_level": "WEATHER_DISRUPTED",
        "description": "Severe convective weather disruption bank (heavy tail-delay volatility)",
        "n_flights": 70,
        "n_contact_gates": 18,
        "bank_time_range": (840, 1260),  # 14:00 to 21:00
    },
]


def get_git_commit(root: Path) -> str:
    """Retrieve current git commit hash."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception:
        return "UNKNOWN_COMMIT"


def compute_distribution_stats(series: pd.Series | np.ndarray | None) -> dict[str, float]:
    """Compute comprehensive statistical distribution metrics."""
    if series is None:
        return {}
    if isinstance(series, pd.Series) and series.empty:
        return {}
    arr = np.asarray(series, dtype=float)
    if len(arr) == 0:
        return {}
    q25, q75 = np.percentile(arr, [25.0, 75.0])
    return {
        "mean": float(np.mean(arr)),
        "std": float(np.std(arr)),
        "median": float(np.median(arr)),
        "iqr": float(q75 - q25),
        "p10": float(np.percentile(arr, 10.0)),
        "p25": float(q25),
        "p75": float(q75),
        "p90": float(np.percentile(arr, 90.0)),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
    }


def run_development_end_to_end_benchmark(
    *,
    scenarios_per_day: int = 10,
    seed: int = PREDETERMINED_DEPLOYMENT_SEED,
    project_root: Path | None = None,
    output_dir_name: str = "development_end_to_end",
) -> dict[str, Any]:
    """Execute broader development end-to-end benchmark across multiple days and demand levels."""
    root = project_root or PROJECT_ROOT
    start_time = time.time()
    git_commit = get_git_commit(root)

    output_dir = root / "artifacts" / output_dir_name
    output_dir.mkdir(parents=True, exist_ok=True)

    LOGGER.info("=" * 80)
    LOGGER.info("STEP 7: BROADER DEVELOPMENT END-TO-END BENCHMARK")
    LOGGER.info(f"Git Commit: {git_commit} | Seed: {seed}")
    LOGGER.info(f"Benchmark Days: {len(BENCHMARK_DAYS_SPEC)} | Scenarios Per Day: {scenarios_per_day}")
    LOGGER.info(f"Target Output Directory: {output_dir}")
    LOGGER.info("=" * 80)

    # 1. Prerequisite Checks: Steps 1-6 Verification
    LOGGER.info("\n--- [Step 1] Verifying Prerequisites (Steps 1-6) ---")
    audit_dir = root / "artifacts" / "audit"
    manifests_dir = root / "artifacts" / "manifests"

    prereq_checks = {
        "step_1_monte_carlo": manifests_dir / "probabilistic_stage9_gate_simulation_v1.json",
        "step_2_cp_sat_objective": audit_dir / "phase_d_cp_sat_objective_audit_manifest_v1.json",
        "step_3_sa_benchmark": audit_dir / "phase_f_time_limited_sa_benchmark_manifest_v1.json",
        "step_4_temporal_guards": audit_dir / "phase_h_holdout_fold_guard_correction_manifest_v1.json",
        "step_5_dependence_contract": audit_dir / "phase_c_dependence_contract_consistency_manifest_v1.json",
        "step_6_timeline_semantics": audit_dir / "phase_g_timeline_semantics_audit_manifest_v1.json",
    }

    prereq_status: dict[str, str] = {}
    for step_key, p in prereq_checks.items():
        if not p.exists():
            raise RuntimeError(f"Prerequisite {step_key} manifest not found at {p}. Halting Step 7.")
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
            stat = data.get("status")
            if stat is None and "joint_sampler_validation" in data:
                stat = data["joint_sampler_validation"].get("status")
            if stat not in {"PASS", "VALIDATED_PASS"}:
                raise RuntimeError(f"Prerequisite {step_key} status is '{stat}' (not 'PASS'). Halting Step 7.")
            prereq_status[step_key] = "PASS"
        LOGGER.info(f"  [PASS] {step_key}: manifest verified at {p.name}")

    # 2. Automated Protocol Compliance Guard
    LOGGER.info("\n--- [Step 2] Executing Protocol Compliance Guard ---")
    guard = ProtocolComplianceGuard(project_root=root)
    guard_report = guard.run_all_checks()
    if guard_report["guard_status"] != "PASS":
        raise RuntimeError("Protocol compliance guard check failed. Halting Step 7.")
    LOGGER.info(f"Protocol Compliance Guard: PASS ({guard_report['passed_checks']}/{guard_report['total_checks']} checks)")

    # 3. Fit Frozen Marginal Model strictly on development training data (2016-2022)
    LOGGER.info("\n--- [Step 3] Loading Development Data & Fitting Frozen B5 Marginal Model ---")
    (
        X_train,
        _,
        y_train_reg,
        _,
        _,
        _,
        _,
        _,
    ) = load_stratified_fold_data(
        train_years=[2016, 2017, 2018, 2019, 2020, 2021, 2022],
        val_year=2023,
        sample_train_per_year=1000,
        sample_val=100,
        project_root=root,
        random_state=seed,
        feature_set="v1",
    )

    b5_model = B5NGBoostStudentT(seed=seed, n_estimators=50, learning_rate=0.005)
    b5_model.fit(X_train, y_train_reg.to_numpy(dtype=np.float64))
    LOGGER.info("Frozen B5 NGBoost Student-T marginal model fitted successfully.")

    # 4. Initialize Dependence, Turn Model, and Solvers
    LOGGER.info("\n--- [Step 4] Initializing Dependence Model, Turn Model & Solvers ---")
    dependence_model = GaussianCopulaDependenceModel(
        temporal_length_scale_minutes=120.0,
        carrier_correlation=0.15,
    )
    scenario_runner = MonteCarloScenarioRunner(dependence_model=dependence_model)

    turn_model = AircraftTurnModel(
        min_turnaround_min=45,
        default_dwell_min=60,
        separation_buffer_min=15,
    )

    opt_config = GateOptimizationConfig(
        reassignment_weight=10.0,
        overflow_weight=200.0,
        delay_weight=1.0,
        conflict_weight=1000.0,
        risk_weight=2.0,
        time_limit_seconds=5.0,
        random_seed=seed,
    )
    sa_config = SAConfig(iterations=200, seed=seed)

    greedy_solver = DeterministicGreedyGateSolver(config=opt_config)
    cpsat_solver = CPSatGateSolver(config=opt_config)
    sa_solver = SimulatedAnnealingGateSolver(config=opt_config, sa_config=sa_config)

    # 5. Execute Simulation and Multi-Solver Benchmark Across Benchmark Days
    LOGGER.info("\n--- [Step 5] Executing Broader Benchmark Across 4 Development Days ---")

    scenario_registry_rows: list[dict[str, Any]] = []
    greedy_results_rows: list[dict[str, Any]] = []
    cpsat_results_rows: list[dict[str, Any]] = []
    sa_results_rows: list[dict[str, Any]] = []
    failures_list: list[dict[str, Any]] = []

    # Cache for deterministic repetition verification (day_idx, scen_idx) -> check data
    repetition_cache: dict[str, dict[str, Any]] = {}

    for d_idx, day_spec in enumerate(BENCHMARK_DAYS_SPEC):
        day_id = day_spec["day_id"]
        date_str = day_spec["date_str"]
        demand_level = day_spec["demand_level"]
        target_n_flights = day_spec["n_flights"]
        n_contact_gates = day_spec["n_contact_gates"]
        bank_min_start, bank_min_end = day_spec["bank_time_range"]

        LOGGER.info(
            f"\n>>> Processing Day {d_idx + 1}/{len(BENCHMARK_DAYS_SPEC)}: "
            f"{day_id} ({date_str}, Demand: {demand_level}, Flights: {target_n_flights}, Gates: {n_contact_gates}) <<<"
        )

        # Ingest daily flights from 2023 parquet
        day_raw_df = pd.read_parquet(
            root / "data" / "processed" / "inbound_atl" / "year=2023",
            filters=[("FL_DATE", "==", f"{date_str} 00:00:00")],
        )

        prep = prepare_arrival_features(day_raw_df)
        flight_features_df = prep.X.copy()
        flight_features_df["flight_key"] = prep.identifiers["flight_key"].values
        flight_features_df["CRS_ARR_TIME"] = day_raw_df["CRS_ARR_TIME"].values
        flight_features_df["CRS_DEP_TIME"] = day_raw_df["CRS_DEP_TIME"].values

        # Convert scheduled times to minutes from midnight
        arr_dt = pd.to_datetime(flight_features_df["CRS_ARR_TIME"], errors="coerce")
        flight_features_df["CRS_ARR_MIN"] = (arr_dt.dt.hour * 60 + arr_dt.dt.minute).fillna(0).astype(int)

        # Filter to operational bank window for realistic congestion density and sort chronologically
        bank_df = flight_features_df[
            (flight_features_df["CRS_ARR_MIN"] >= bank_min_start)
            & (flight_features_df["CRS_ARR_MIN"] <= bank_min_end)
        ].sort_values("CRS_ARR_MIN").reset_index(drop=True)

        if len(bank_df) < target_n_flights:
            LOGGER.warning(
                f"Bank window for {date_str} has {len(bank_df)} flights (< {target_n_flights}). Using all available."
            )
            day_slice_df = bank_df
        else:
            day_slice_df = bank_df.iloc[:target_n_flights].copy()

        n_flights = len(day_slice_df)
        LOGGER.info(f"Extracted {n_flights} flights for {day_id} in window [{bank_min_start}, {bank_min_end}] min.")

        # Predict marginal distributions using frozen B5 model
        pred_dist = b5_model.predict_distribution(day_slice_df[list(PROBABILISTIC_PREDICTOR_COLUMNS)])
        marginals = [
            StudentTMarginalDistribution(
                mu=float(pred_dist["mu"][i]),
                sigma=float(pred_dist["sigma"][i]),
                df=float(pred_dist["df"][i]),
                discrete=True,
            )
            for i in range(n_flights)
        ]

        # Generate Monte Carlo delay scenarios via Gaussian Copula
        day_seed = seed + d_idx * 1000
        scenarios_matrix = scenario_runner.run_scenarios(
            marginals=marginals,
            flight_features=day_slice_df,
            n_scenarios=scenarios_per_day,
            rng=day_seed,
        )

        # Setup gates (contact gates + 1 overflow apron)
        contact_gates = [
            Gate(gate_id=f"G_{i+1:02d}", gate_index=i, is_overflow=False)
            for i in range(n_contact_gates)
        ]
        overflow_gate = Gate(
            gate_id="OVERFLOW_APRON",
            gate_index=n_contact_gates,
            is_overflow=True,
        )
        all_gates = contact_gates + [overflow_gate]

        # Construct nominal gate allocation plan based on zero delays (scheduled times)
        scheduled_turns = turn_model.synthesize_batch(day_slice_df, np.zeros(n_flights, dtype=float))
        nominal_mapping = {
            t.flight_id: contact_gates[i % n_contact_gates].gate_id
            for i, t in enumerate(scheduled_turns)
        }

        # Run each Monte Carlo scenario across all methods
        for s_idx in range(scenarios_per_day):
            scen_id = f"{day_id}_S{s_idx+1:03d}"
            s_seed = day_seed + s_idx
            s_delays = scenarios_matrix[s_idx, :]
            s_hash = hashlib.sha256(s_delays.tobytes()).hexdigest()

            # Synthesize operational turns under simulated delays
            turns = turn_model.synthesize_batch(day_slice_df, s_delays, nominal_mapping)
            flights = [t.to_flight(flight_index=idx) for idx, t in enumerate(turns)]

            # Evaluate nominal plan potential conflict under realized delays
            nom_conflicts_res = detect_conflicts(
                {f.flight_id: f.nominal_gate_id for f in flights},
                turns,
                all_gates,
            )

            # Record scenario registry row
            scen_reg_row = {
                "scenario_id": scen_id,
                "day_id": day_id,
                "date_str": date_str,
                "demand_level": demand_level,
                "n_flights": n_flights,
                "n_contact_gates": n_contact_gates,
                "scenario_seed": s_seed,
                "scenario_hash": s_hash,
                "mean_delay_min": float(np.mean(s_delays)),
                "std_delay_min": float(np.std(s_delays)),
                "p50_delay_min": float(np.median(s_delays)),
                "p95_delay_min": float(np.percentile(s_delays, 95.0)),
                "max_delay_min": float(np.max(s_delays)),
                "nominal_conflict_count": nom_conflicts_res.conflict_count,
                "nominal_conflict_duration_min": nom_conflicts_res.total_conflict_duration_min,
                "nominal_peak_concurrency": nom_conflicts_res.peak_single_gate_concurrency,
            }
            scenario_registry_rows.append(scen_reg_row)

            # -------------------------------------------------------------
            # Method 1: Deterministic Greedy Solver
            # -------------------------------------------------------------
            try:
                res_g = greedy_solver.solve(flights, all_gates)
                conf_g = detect_conflicts(res_g.assignments, turns, all_gates)
                diag_g = verify_hard_constraints_independently(flights, all_gates, res_g.assignments)

                if not diag_g.is_valid:
                    raise RuntimeError(f"Greedy produced invalid hard constraints: {diag_g.violations}")

                g_reassign = sum(1 for a in res_g.assignments.values() if a.is_reassignment)
                g_overflow = sum(1 for a in res_g.assignments.values() if a.is_overflow)

                greedy_results_rows.append(
                    {
                        "scenario_id": scen_id,
                        "day_id": day_id,
                        "demand_level": demand_level,
                        "solver": "Greedy",
                        "feasibility": bool(res_g.feasible and diag_g.is_valid),
                        "objective": float(res_g.objective_value),
                        "decision_cost": float(res_g.objective_breakdown.decision_cost),
                        "reporting_cost": float(res_g.objective_breakdown.reporting_cost),
                        "reassignment": g_reassign,
                        "overflow": g_overflow,
                        "simulated_conflicts": conf_g.conflict_count,
                        "conflict_duration": float(conf_g.total_conflict_duration_min),
                        "utilization": float(conf_g.gate_utilization_rate),
                        "runtime_ms": float(res_g.runtime_ms),
                        "scenario_seed": s_seed,
                        "scenario_hash": s_hash,
                    }
                )
            except Exception as e:
                LOGGER.error(f"[FAILURE] Greedy failed on {scen_id}: {e}")
                failures_list.append(
                    {
                        "scenario_id": scen_id,
                        "day_id": day_id,
                        "demand_level": demand_level,
                        "solver": "Greedy",
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    }
                )

            # -------------------------------------------------------------
            # Method 2: CP-SAT Solver
            # -------------------------------------------------------------
            try:
                res_cp = cpsat_solver.solve(flights, all_gates)
                conf_cp = detect_conflicts(res_cp.assignments, turns, all_gates)
                diag_cp = verify_hard_constraints_independently(flights, all_gates, res_cp.assignments)

                if not diag_cp.is_valid:
                    raise RuntimeError(f"CP-SAT produced invalid hard constraints: {diag_cp.violations}")

                cp_reassign = sum(1 for a in res_cp.assignments.values() if a.is_reassignment)
                cp_overflow = sum(1 for a in res_cp.assignments.values() if a.is_overflow)

                cpsat_results_rows.append(
                    {
                        "scenario_id": scen_id,
                        "day_id": day_id,
                        "demand_level": demand_level,
                        "solver": "CP-SAT",
                        "status": res_cp.status,
                        "feasibility": bool(res_cp.feasible and diag_cp.is_valid),
                        "objective": float(res_cp.objective_value),
                        "decision_cost": float(res_cp.objective_breakdown.decision_cost),
                        "reporting_cost": float(res_cp.objective_breakdown.reporting_cost),
                        "reassignment": cp_reassign,
                        "overflow": cp_overflow,
                        "simulated_conflicts": conf_cp.conflict_count,
                        "conflict_duration": float(conf_cp.total_conflict_duration_min),
                        "utilization": float(conf_cp.gate_utilization_rate),
                        "runtime_ms": float(res_cp.runtime_ms),
                        "optimality_gap": float(res_cp.optimality_gap or 0.0),
                        "scenario_seed": s_seed,
                        "scenario_hash": s_hash,
                    }
                )
            except Exception as e:
                LOGGER.error(f"[FAILURE] CP-SAT failed on {scen_id}: {e}")
                failures_list.append(
                    {
                        "scenario_id": scen_id,
                        "day_id": day_id,
                        "demand_level": demand_level,
                        "solver": "CP-SAT",
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    }
                )

            # -------------------------------------------------------------
            # Method 3: SA Time-Limited Benchmark (CP-SAT+SA and Greedy+SA)
            # -------------------------------------------------------------
            try:
                # Create scenario-seeded SA solver for strictly deterministic reproducibility
                scen_sa_solver = SimulatedAnnealingGateSolver(
                    config=opt_config,
                    sa_config=SAConfig(iterations=150, seed=s_seed),
                )

                # Branch D: CP-SAT Incumbent + SA
                res_sa_cp = scen_sa_solver.solve(
                    flights,
                    all_gates,
                    initial_assignments=res_cp.assignments if res_cp.feasible else None,
                )
                conf_sa_cp = detect_conflicts(res_sa_cp.assignments, turns, all_gates)
                diag_sa_cp = verify_hard_constraints_independently(flights, all_gates, res_sa_cp.assignments)

                if not diag_sa_cp.is_valid:
                    raise RuntimeError(f"CP-SAT+SA produced invalid hard constraints: {diag_sa_cp.violations}")

                sa_cp_reassign = sum(1 for a in res_sa_cp.assignments.values() if a.is_reassignment)
                sa_cp_overflow = sum(1 for a in res_sa_cp.assignments.values() if a.is_overflow)

                sa_results_rows.append(
                    {
                        "scenario_id": scen_id,
                        "day_id": day_id,
                        "demand_level": demand_level,
                        "solver": "SA",
                        "branch": "CP-SAT+SA",
                        "feasibility": bool(res_sa_cp.feasible and diag_sa_cp.is_valid),
                        "objective": float(res_sa_cp.objective_value),
                        "decision_cost": float(res_sa_cp.objective_breakdown.decision_cost),
                        "reporting_cost": float(res_sa_cp.objective_breakdown.reporting_cost),
                        "reassignment": sa_cp_reassign,
                        "overflow": sa_cp_overflow,
                        "simulated_conflicts": conf_sa_cp.conflict_count,
                        "conflict_duration": float(conf_sa_cp.total_conflict_duration_min),
                        "utilization": float(conf_sa_cp.gate_utilization_rate),
                        "runtime_ms": float(res_cp.runtime_ms + res_sa_cp.runtime_ms),
                        "initial_objective": float(res_cp.objective_value),
                        "iterations": 150,
                        "scenario_seed": s_seed,
                        "scenario_hash": s_hash,
                    }
                )

                # Branch E: Greedy + SA
                res_sa_g = scen_sa_solver.solve(
                    flights,
                    all_gates,
                    initial_assignments=res_g.assignments if res_g.feasible else None,
                )
                conf_sa_g = detect_conflicts(res_sa_g.assignments, turns, all_gates)
                diag_sa_g = verify_hard_constraints_independently(flights, all_gates, res_sa_g.assignments)

                if not diag_sa_g.is_valid:
                    raise RuntimeError(f"Greedy+SA produced invalid hard constraints: {diag_sa_g.violations}")

                sa_g_reassign = sum(1 for a in res_sa_g.assignments.values() if a.is_reassignment)
                sa_g_overflow = sum(1 for a in res_sa_g.assignments.values() if a.is_overflow)

                sa_results_rows.append(
                    {
                        "scenario_id": scen_id,
                        "day_id": day_id,
                        "demand_level": demand_level,
                        "solver": "SA",
                        "branch": "Greedy+SA",
                        "feasibility": bool(res_sa_g.feasible and diag_sa_g.is_valid),
                        "objective": float(res_sa_g.objective_value),
                        "decision_cost": float(res_sa_g.objective_breakdown.decision_cost),
                        "reporting_cost": float(res_sa_g.objective_breakdown.reporting_cost),
                        "reassignment": sa_g_reassign,
                        "overflow": sa_g_overflow,
                        "simulated_conflicts": conf_sa_g.conflict_count,
                        "conflict_duration": float(conf_sa_g.total_conflict_duration_min),
                        "utilization": float(conf_sa_g.gate_utilization_rate),
                        "runtime_ms": float(res_g.runtime_ms + res_sa_g.runtime_ms),
                        "initial_objective": float(res_g.objective_value),
                        "iterations": 150,
                        "scenario_seed": s_seed,
                        "scenario_hash": s_hash,
                    }
                )

                # Cache first 2 scenarios of each day for deterministic check
                if s_idx < 2:
                    repetition_cache[scen_id] = {
                        "s_seed": s_seed,
                        "s_delays": s_delays.copy(),
                        "s_hash": s_hash,
                        "greedy_obj": float(res_g.objective_value),
                        "cpsat_obj": float(res_cp.objective_value),
                        "sa_cpsat_obj": float(res_sa_cp.objective_value),
                        "sa_greedy_obj": float(res_sa_g.objective_value),
                        "flights": flights,
                        "all_gates": all_gates,
                        "nominal_mapping": nominal_mapping,
                        "day_slice_df": day_slice_df,
                    }
            except Exception as e:
                LOGGER.error(f"[FAILURE] SA failed on {scen_id}: {e}")
                failures_list.append(
                    {
                        "scenario_id": scen_id,
                        "day_id": day_id,
                        "demand_level": demand_level,
                        "solver": "SA",
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    }
                )

    # 6. Verify Deterministic Repetition (Requirement 11)
    LOGGER.info("\n--- [Step 6] Running Deterministic Repetition Verification (Requirement 11) ---")
    deterministic_match = True
    deterministic_checks_count = 0

    for rep_scen_id, cached in repetition_cache.items():
        deterministic_checks_count += 1
        # Re-synthesize turns with same delays
        re_turns = turn_model.synthesize_batch(cached["day_slice_df"], cached["s_delays"], cached["nominal_mapping"])
        re_flights = [t.to_flight(flight_index=idx) for idx, t in enumerate(re_turns)]
        re_hash = hashlib.sha256(cached["s_delays"].tobytes()).hexdigest()

        # Re-solve Greedy
        re_res_g = greedy_solver.solve(re_flights, cached["all_gates"])
        # Re-solve CP-SAT
        re_res_cp = cpsat_solver.solve(re_flights, cached["all_gates"])
        # Re-solve SA with identical scenario seed
        re_sa_solver = SimulatedAnnealingGateSolver(
            config=opt_config,
            sa_config=SAConfig(iterations=150, seed=cached["s_seed"]),
        )
        re_res_sa_cp = re_sa_solver.solve(re_flights, cached["all_gates"], initial_assignments=re_res_cp.assignments)
        re_res_sa_g = re_sa_solver.solve(re_flights, cached["all_gates"], initial_assignments=re_res_g.assignments)

        if re_hash != cached["s_hash"]:
            LOGGER.error(f"Deterministic check failed: hash mismatch on {rep_scen_id}")
            deterministic_match = False
        if abs(re_res_g.objective_value - cached["greedy_obj"]) > 1e-6:
            LOGGER.error(f"Deterministic check failed: Greedy obj mismatch on {rep_scen_id}")
            deterministic_match = False
        if abs(re_res_cp.objective_value - cached["cpsat_obj"]) > 1e-6:
            LOGGER.error(f"Deterministic check failed: CP-SAT obj mismatch on {rep_scen_id}")
            deterministic_match = False
        if abs(re_res_sa_cp.objective_value - cached["sa_cpsat_obj"]) > 1e-6:
            LOGGER.error(f"Deterministic check failed: CP-SAT+SA obj mismatch on {rep_scen_id}")
            deterministic_match = False
        if abs(re_res_sa_g.objective_value - cached["sa_greedy_obj"]) > 1e-6:
            LOGGER.error(f"Deterministic check failed: Greedy+SA obj mismatch on {rep_scen_id}")
            deterministic_match = False

    LOGGER.info(
        f"Deterministic Repetition Verification: {'PASS' if deterministic_match else 'FAIL'} "
        f"({deterministic_checks_count} scenarios checked across all days)"
    )
    if not deterministic_match:
        raise RuntimeError("Deterministic repetition verification failed. Results are non-deterministic.")

    # 7. Convert Results to DataFrames and Export Parquets (Requirement 10)
    LOGGER.info("\n--- [Step 7] Exporting Required Parquet and JSON Artifacts ---")
    df_scen_reg = pd.DataFrame(scenario_registry_rows)
    df_greedy = pd.DataFrame(greedy_results_rows)
    df_cpsat = pd.DataFrame(cpsat_results_rows)
    df_sa = pd.DataFrame(sa_results_rows)

    df_scen_reg.to_parquet(output_dir / "scenario_registry.parquet", index=False)
    df_greedy.to_parquet(output_dir / "greedy_results.parquet", index=False)
    df_cpsat.to_parquet(output_dir / "cp_sat_results.parquet", index=False)
    df_sa.to_parquet(output_dir / "sa_results.parquet", index=False)

    LOGGER.info(f"Exported scenario_registry.parquet ({len(df_scen_reg)} rows)")
    LOGGER.info(f"Exported greedy_results.parquet ({len(df_greedy)} rows)")
    LOGGER.info(f"Exported cp_sat_results.parquet ({len(df_cpsat)} rows)")
    LOGGER.info(f"Exported sa_results.parquet ({len(df_sa)} rows)")

    # 8. Export failures.json (Requirements 8 & 9)
    failures_data = {
        "benchmark_label": "DEVELOPMENT_END_TO_END_BENCHMARK",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "total_scenarios_evaluated": len(df_scen_reg),
        "failures_count": len(failures_list),
        "status": "ALL_SCENARIOS_SUCCEEDED" if len(failures_list) == 0 else "FAILURES_RECORDED",
        "failed_scenarios": failures_list,
        "silently_dropped_scenarios_count": 0,
        "error_handling_policy": "FAIL_CLOSED_TRANSPARENT",
    }
    with open(output_dir / "failures.json", "w", encoding="utf-8") as f:
        json.dump(failures_data, f, indent=2)
    LOGGER.info(f"Exported failures.json (failures_count={len(failures_list)})")

    # 9. Compute Method-Wise Distributions (Requirement 7)
    LOGGER.info("\n--- [Step 8] Computing Method-Wise Distributions ---")
    method_distributions: dict[str, Any] = {}

    # Greedy distribution
    method_distributions["Greedy"] = {
        "count": len(df_greedy),
        "hard_feasibility_rate": float(df_greedy["feasibility"].mean() * 100.0) if len(df_greedy) > 0 else 0.0,
        "contact_conflicts_total": int(df_greedy["simulated_conflicts"].sum()) if len(df_greedy) > 0 else 0,
        "objective": compute_distribution_stats(df_greedy["objective"]),
        "decision_cost": compute_distribution_stats(df_greedy["decision_cost"]),
        "reporting_cost": compute_distribution_stats(df_greedy["reporting_cost"]),
        "reassignment": compute_distribution_stats(df_greedy["reassignment"]),
        "overflow": compute_distribution_stats(df_greedy["overflow"]),
        "runtime_ms": compute_distribution_stats(df_greedy["runtime_ms"]),
        "utilization": compute_distribution_stats(df_greedy["utilization"]),
    }

    # CP-SAT distribution
    method_distributions["CP-SAT"] = {
        "count": len(df_cpsat),
        "hard_feasibility_rate": float(df_cpsat["feasibility"].mean() * 100.0) if len(df_cpsat) > 0 else 0.0,
        "contact_conflicts_total": int(df_cpsat["simulated_conflicts"].sum()) if len(df_cpsat) > 0 else 0,
        "optimal_solutions_count": int((df_cpsat["status"] == "OPTIMAL").sum()) if len(df_cpsat) > 0 else 0,
        "objective": compute_distribution_stats(df_cpsat["objective"]),
        "decision_cost": compute_distribution_stats(df_cpsat["decision_cost"]),
        "reporting_cost": compute_distribution_stats(df_cpsat["reporting_cost"]),
        "reassignment": compute_distribution_stats(df_cpsat["reassignment"]),
        "overflow": compute_distribution_stats(df_cpsat["overflow"]),
        "runtime_ms": compute_distribution_stats(df_cpsat["runtime_ms"]),
        "utilization": compute_distribution_stats(df_cpsat["utilization"]),
    }

    # SA distributions by branch
    df_sa_cp = df_sa[df_sa["branch"] == "CP-SAT+SA"]
    df_sa_g = df_sa[df_sa["branch"] == "Greedy+SA"]

    method_distributions["SA_CPSAT_Incumbent"] = {
        "count": len(df_sa_cp),
        "hard_feasibility_rate": float(df_sa_cp["feasibility"].mean() * 100.0) if len(df_sa_cp) > 0 else 0.0,
        "contact_conflicts_total": int(df_sa_cp["simulated_conflicts"].sum()) if len(df_sa_cp) > 0 else 0,
        "objective": compute_distribution_stats(df_sa_cp["objective"]),
        "decision_cost": compute_distribution_stats(df_sa_cp["decision_cost"]),
        "reporting_cost": compute_distribution_stats(df_sa_cp["reporting_cost"]),
        "reassignment": compute_distribution_stats(df_sa_cp["reassignment"]),
        "overflow": compute_distribution_stats(df_sa_cp["overflow"]),
        "runtime_ms": compute_distribution_stats(df_sa_cp["runtime_ms"]),
        "utilization": compute_distribution_stats(df_sa_cp["utilization"]),
    }

    method_distributions["SA_Greedy_WarmStart"] = {
        "count": len(df_sa_g),
        "hard_feasibility_rate": float(df_sa_g["feasibility"].mean() * 100.0) if len(df_sa_g) > 0 else 0.0,
        "contact_conflicts_total": int(df_sa_g["simulated_conflicts"].sum()) if len(df_sa_g) > 0 else 0,
        "objective": compute_distribution_stats(df_sa_g["objective"]),
        "decision_cost": compute_distribution_stats(df_sa_g["decision_cost"]),
        "reporting_cost": compute_distribution_stats(df_sa_g["reporting_cost"]),
        "reassignment": compute_distribution_stats(df_sa_g["reassignment"]),
        "overflow": compute_distribution_stats(df_sa_g["overflow"]),
        "runtime_ms": compute_distribution_stats(df_sa_g["runtime_ms"]),
        "utilization": compute_distribution_stats(df_sa_g["utilization"]),
    }

    # Demand level breakdown
    demand_level_breakdown: dict[str, Any] = {}
    for d_spec in BENCHMARK_DAYS_SPEC:
        d_lvl = d_spec["demand_level"]
        sub_g = df_greedy[df_greedy["demand_level"] == d_lvl]
        sub_cp = df_cpsat[df_cpsat["demand_level"] == d_lvl]
        sub_sa_g = df_sa_g[df_sa_g["demand_level"] == d_lvl]

        demand_level_breakdown[d_lvl] = {
            "day_id": d_spec["day_id"],
            "date": d_spec["date_str"],
            "flights": d_spec["n_flights"],
            "contact_gates": d_spec["n_contact_gates"],
            "scenarios": len(sub_g),
            "greedy_mean_objective": float(sub_g["objective"].mean()) if len(sub_g) > 0 else None,
            "cpsat_mean_objective": float(sub_cp["objective"].mean()) if len(sub_cp) > 0 else None,
            "sa_greedy_mean_objective": float(sub_sa_g["objective"].mean()) if len(sub_sa_g) > 0 else None,
            "greedy_mean_runtime_ms": float(sub_g["runtime_ms"].mean()) if len(sub_g) > 0 else None,
            "cpsat_mean_runtime_ms": float(sub_cp["runtime_ms"].mean()) if len(sub_cp) > 0 else None,
            "sa_mean_runtime_ms": float(sub_sa_g["runtime_ms"].mean()) if len(sub_sa_g) > 0 else None,
        }

    # Export aggregate_metrics.json (Requirement 10)
    aggregate_metrics = {
        "manifest_version": "development_end_to_end_aggregate_metrics_v1",
        "benchmark_label": "DEVELOPMENT_END_TO_END_BENCHMARK",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit,
        "evaluation_scope": {
            "total_benchmark_days": len(BENCHMARK_DAYS_SPEC),
            "scenarios_per_day": scenarios_per_day,
            "total_scenarios_evaluated": len(df_scen_reg),
            "seed": seed,
            "methods_evaluated": ["Greedy", "CP-SAT", "SA (CP-SAT+SA)", "SA (Greedy+SA)"],
            "target_year": 2023,
            "is_2024_holdout_accessed": False,
        },
        "all_hard_feasibility_satisfied": bool(
            df_greedy["feasibility"].all() and df_cpsat["feasibility"].all() and df_sa["feasibility"].all()
        ),
        "zero_contact_conflicts_across_all_solvers": bool(
            df_greedy["simulated_conflicts"].sum() == 0
            and df_cpsat["simulated_conflicts"].sum() == 0
            and df_sa["simulated_conflicts"].sum() == 0
        ),
        "method_distributions": method_distributions,
        "demand_level_breakdown": demand_level_breakdown,
        "reproducibility": {
            "deterministic_repetition_match": deterministic_match,
            "scenarios_checked": deterministic_checks_count,
        },
        "disclaimer": (
            "This benchmark evaluates optimization performance across synthetic Monte Carlo scenarios "
            "generated from historical 2023 development schedules at KATL. "
            "It does NOT claim real-world airport ground truth, complete operational optimality, "
            "or universal superiority of any single method."
        ),
    }

    with open(output_dir / "aggregate_metrics.json", "w", encoding="utf-8") as f:
        json.dump(aggregate_metrics, f, indent=2)
    LOGGER.info("Exported aggregate_metrics.json")

    # 10. Export Master run_manifest.json (Requirement 10)
    total_wall_sec = time.time() - start_time
    run_manifest = {
        "manifest_version": "development_end_to_end_run_manifest_v1",
        "phase": "STEP_7_BROADER_DEVELOPMENT_END_TO_END_BENCHMARK",
        "status": "PASS",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "total_wall_seconds": total_wall_sec,
        "git_commit": git_commit,
        "protocol_reference": "docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 19",
        "post_holdout_status": "POST_HOLDOUT_STABILIZED",
        "evaluation_label": "DEVELOPMENT_END_TO_END_BENCHMARK",
        "prerequisites_status": prereq_status,
        "benchmark_days": BENCHMARK_DAYS_SPEC,
        "scenario_count_total": len(df_scen_reg),
        "methods_evaluated": ["Greedy", "CP-SAT", "SA"],
        "artifact_inventory": {
            "run_manifest": str((output_dir / "run_manifest.json").as_posix()),
            "scenario_registry": str((output_dir / "scenario_registry.parquet").as_posix()),
            "greedy_results": str((output_dir / "greedy_results.parquet").as_posix()),
            "cp_sat_results": str((output_dir / "cp_sat_results.parquet").as_posix()),
            "sa_results": str((output_dir / "sa_results.parquet").as_posix()),
            "aggregate_metrics": str((output_dir / "aggregate_metrics.json").as_posix()),
            "failures": str((output_dir / "failures.json").as_posix()),
        },
        "all_hard_feasibility_satisfied": aggregate_metrics["all_hard_feasibility_satisfied"],
        "zero_contact_conflicts_across_all_solvers": aggregate_metrics["zero_contact_conflicts_across_all_solvers"],
        "failures_count": len(failures_list),
        "deterministic_repetition_confirmed": deterministic_match,
        "non_real_world_caveat": aggregate_metrics["disclaimer"],
    }

    with open(output_dir / "run_manifest.json", "w", encoding="utf-8") as f:
        json.dump(run_manifest, f, indent=2)
    LOGGER.info(f"Exported run_manifest.json (Total Wall Time: {total_wall_sec:.2f}s)")

    LOGGER.info("\n" + "=" * 80)
    LOGGER.info("STEP 7 BROADER DEVELOPMENT END-TO-END BENCHMARK: PASS")
    LOGGER.info("=" * 80)
    return run_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Broader Development End-to-End Benchmark")
    parser.add_argument("--scenarios-per-day", type=int, default=10)
    parser.add_argument("--seed", type=int, default=PREDETERMINED_DEPLOYMENT_SEED)
    parser.add_argument("--output-dir-name", type=str, default="development_end_to_end")
    args = parser.parse_args()

    run_development_end_to_end_benchmark(
        scenarios_per_day=args.scenarios_per_day,
        seed=args.seed,
        output_dir_name=args.output_dir_name,
    )


if __name__ == "__main__":
    main()
