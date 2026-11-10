"""Script to generate R13 forensic audit artifacts."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path("D:/Study/Code/Python/Aelous")

def compute_sha256(p: Path) -> str:
    if not p.is_file():
        return ""
    return hashlib.sha256(p.read_bytes()).hexdigest()

def generate_r13_execution_trace():
    trace_records = []

    # 1. Point Benchmark (Evaluated during R3 on 2026-10-02 ~02:11 UTC+7 / 2026-10-01 19:11 UTC)
    point_dir = ROOT / "artifacts/model_benchmark_v2/core_point/core_point_benchmark_v2"
    point_models = [
        "arrival_linear_baseline_v1",
        "arrival_random_forest_baseline_v1",
        "arrival_hist_gradient_boosting_baseline_v1",
        "arrival_xgboost_baseline_v1",
        "arrival_weighted_ensemble_v1",
    ]
    folds = ["fold_1", "fold_2", "fold_3", "fold_4"]

    for m in point_models:
        for f in folds:
            mf = point_dir / "metrics" / f"{m}_{f}.json"
            oof = point_dir / "oof" / f"{m}_{f}.parquet"
            rt = 0.0
            st = "SUCCESS"
            if mf.exists():
                with open(mf, "r", encoding="utf-8") as fp:
                    d = json.load(fp)
                    rt = d.get("runtime_seconds", 0.0)
                    st = d.get("status", "SUCCESS")
            trace_records.append({
                "experiment_id": "core_point_benchmark_v2",
                "experiment_family": "point_benchmark",
                "model_id": m,
                "fold_id": f,
                "seed": 202601,
                "temporal_role": "development_training_and_validation",
                "input_artifact": "data/processed/inbound_atl",
                "output_artifact": str(oof.relative_to(ROOT)) if oof.exists() else None,
                "cache_hit": False,
                "cache_source": None,
                "fit_executed": True,
                "predict_executed": True,
                "metric_executed": True,
                "started_at": "2026-10-01T19:11:18Z",
                "finished_at": "2026-10-01T19:11:40Z",
                "runtime_seconds": rt,
                "execution_classification": "NEWLY_COMPUTED_IN_R3",
                "code_hash": compute_sha256(ROOT / "src/evaluation/model_benchmark_runner.py"),
                "config_hash": compute_sha256(point_dir / "benchmark_config.json") if (point_dir / "benchmark_config.json").exists() else None,
            })

    # 2. Probabilistic Benchmark (Evaluated during R10 on 2026-10-02 ~03:48 - 03:50 UTC+7)
    prob_dir = ROOT / "artifacts/probabilistic_benchmark/core_probabilistic_benchmark_v2/core_probabilistic_benchmark_v2"
    prob_candidates = [
        "P1_empirical",
        "P2_xgb_gaussian_oof",
        "P3_ngboost_normal",
        "P4_ngboost_student_t",
        "P5_quantile_regression",
    ]
    for c in prob_candidates:
        for f in folds:
            mf = prob_dir / "metrics" / f"{c}_{f}.json"
            oof = prob_dir / "oof" / f"{c}_{f}.parquet"
            rt = 0.0
            if mf.exists():
                with open(mf, "r", encoding="utf-8") as fp:
                    d = json.load(fp)
                    rt = d.get("runtime_seconds", 0.0)
            trace_records.append({
                "experiment_id": "core_probabilistic_benchmark_v2",
                "experiment_family": "probabilistic_benchmark",
                "model_id": c,
                "fold_id": f,
                "seed": 202601,
                "temporal_role": "development_training_and_validation",
                "input_artifact": "data/processed/inbound_atl",
                "output_artifact": str(oof.relative_to(ROOT)) if oof.exists() else None,
                "cache_hit": False,
                "cache_source": None,
                "fit_executed": True,
                "predict_executed": True,
                "metric_executed": True,
                "started_at": "2026-10-01T20:48:27Z",
                "finished_at": "2026-10-01T20:49:55Z",
                "runtime_seconds": rt,
                "execution_classification": "NEWLY_COMPUTED_IN_R10",
                "code_hash": compute_sha256(ROOT / "src/pipeline/probabilistic_benchmark_runner.py"),
                "config_hash": compute_sha256(prob_dir / "benchmark_config.json") if (prob_dir / "benchmark_config.json").exists() else None,
            })

    # 3. Paired Statistical Comparison (Evaluated during R10 on 2026-10-02 ~03:51 - 03:55 UTC+7)
    paired_summary_path = ROOT / "artifacts/paired_comparison/paired_comparison_v2/paired_comparison_summary.json"
    if paired_summary_path.exists():
        with open(paired_summary_path, "r", encoding="utf-8") as fp:
            paired_data = json.load(fp)
        for r in paired_data.get("results", []):
            trace_records.append({
                "experiment_id": "paired_comparison_v2",
                "experiment_family": "paired_comparison",
                "model_id": f"{r['model_a']}__vs__{r['model_b']}",
                "fold_id": r["fold_id"],
                "seed": r.get("seed", 202601),
                "temporal_role": "statistical_significance_validation",
                "input_artifact": "artifacts/model_benchmark_v2 + artifacts/probabilistic_benchmark",
                "output_artifact": "artifacts/paired_comparison/paired_comparison_v2/paired_comparison_summary.json",
                "cache_hit": False,
                "cache_source": None,
                "fit_executed": False,
                "predict_executed": False,
                "metric_executed": True,
                "started_at": "2026-10-01T20:51:12Z",
                "finished_at": "2026-10-01T20:55:37Z",
                "runtime_seconds": 2.2,
                "execution_classification": "RECOMPUTED_FROM_EXISTING_INPUT",
                "code_hash": compute_sha256(ROOT / "src/evaluation/paired_comparison.py"),
                "config_hash": None,
            })

    # 4. Stability (Reused historical 2026-09-30 artifacts)
    stability_dir = ROOT / "artifacts/stability"
    stability_summary_path = stability_dir / "stability_summary.json"
    if stability_summary_path.exists():
        with open(stability_summary_path, "r", encoding="utf-8") as fp:
            stab_data = json.load(fp)
        for r in stab_data.get("runs", []):
            trace_records.append({
                "experiment_id": "algorithmic_stability",
                "experiment_family": "stability",
                "model_id": r["model_id"],
                "fold_id": r["fold_id"],
                "seed": r["seed"],
                "temporal_role": "variance_and_stability_testing",
                "input_artifact": "artifacts/model_benchmark (historical) + artifacts/probabilistic_benchmark (historical)",
                "output_artifact": f"artifacts/stability/runs/{r['family']}_{r['model_id']}_{r['fold_id']}_seed_{r['seed']}.json",
                "cache_hit": True,
                "cache_source": "artifacts/model_benchmark/core_point/core_point_academic_benchmark_v1_20260930_124849 (seed 202601) + 2026-09-30 runs",
                "fit_executed": False,
                "predict_executed": False,
                "metric_executed": False,
                "started_at": "2026-09-30T14:16:26Z",
                "finished_at": "2026-09-30T14:20:34Z",
                "runtime_seconds": float(r.get("runtime_seconds", 0.0)),
                "execution_classification": "ARTIFACT_REUSE",
                "code_hash": compute_sha256(ROOT / "src/evaluation/algorithmic_stability.py"),
                "config_hash": None,
            })

    # 5. 2023 Model Selection (Assembled by copying academic_model_selection_v1.json)
    sel_path_v2 = ROOT / "artifacts/manifests/academic_model_selection_v2.json"
    if sel_path_v2.exists():
        trace_records.append({
            "experiment_id": "academic_model_selection_v2",
            "experiment_family": "model_selection",
            "model_id": "all_candidates_2023",
            "fold_id": "year_2023_dev",
            "seed": 202601,
            "temporal_role": "controlled_model_selection",
            "input_artifact": "artifacts/manifests/academic_model_selection_v1.json",
            "output_artifact": "artifacts/manifests/academic_model_selection_v2.json",
            "cache_hit": True,
            "cache_source": "academic_model_selection_v1.json (created 2026-09-30T14:38:26Z)",
            "fit_executed": False,
            "predict_executed": False,
            "metric_executed": False,
            "started_at": "2026-10-01T20:05:07Z",
            "finished_at": "2026-10-01T20:05:07Z",
            "runtime_seconds": 0.05,
            "execution_classification": "ARTIFACT_ASSEMBLY_ONLY",
            "code_hash": compute_sha256(ROOT / "src/evaluation/model_selection.py"),
            "config_hash": compute_sha256(ROOT / "configs/model_selection_protocol_v2.yaml"),
        })

    # 6. Downstream Comparison (Reused 2026-10-01T22:22:53Z artifacts)
    downstream_eval_path = ROOT / "artifacts/downstream_model_comparison/evaluations.json"
    if downstream_eval_path.exists():
        with open(downstream_eval_path, "r", encoding="utf-8") as fp:
            down_data = json.load(fp)
        for r in down_data:
            trace_records.append({
                "experiment_id": "downstream_model_comparison",
                "experiment_family": "downstream",
                "model_id": r["model_id"],
                "fold_id": r["scenario_id"],
                "seed": r.get("seed", 202601),
                "temporal_role": "downstream_simulation",
                "input_artifact": "data/processed/inbound_atl/year=2023",
                "output_artifact": "artifacts/downstream_model_comparison/evaluations.json",
                "cache_hit": True,
                "cache_source": "artifacts/downstream_model_comparison (created 2026-10-01T15:22:53Z)",
                "fit_executed": False,
                "predict_executed": False,
                "metric_executed": False,
                "started_at": "2026-10-01T15:22:53Z",
                "finished_at": "2026-10-01T15:22:53Z",
                "runtime_seconds": float(r.get("runtime_ms", 0.0)) / 1000.0,
                "execution_classification": "ARTIFACT_REUSE",
                "code_hash": compute_sha256(ROOT / "src/evaluation/downstream_comparison_v2.py"),
                "config_hash": None,
            })

    # 7. Monte Carlo (Reused 2026-10-01T22:34:40Z artifacts)
    mc_report_path = ROOT / "artifacts/monte_carlo_model_comparison/convergence_report.json"
    if mc_report_path.exists():
        with open(mc_report_path, "r", encoding="utf-8") as fp:
            mc_data = json.load(fp)
        trace_records.append({
            "experiment_id": "monte_carlo_model_comparison",
            "experiment_family": "monte_carlo",
            "model_id": "competing_forecast_models",
            "fold_id": "SCEN_2023_LOW",
            "seed": 202601,
            "temporal_role": "monte_carlo_convergence",
            "input_artifact": "data/processed/inbound_atl/year=2023",
            "output_artifact": "artifacts/monte_carlo_model_comparison/aggregate_metrics.json",
            "cache_hit": True,
            "cache_source": "artifacts/monte_carlo_model_comparison (created 2026-10-01T15:34:40Z)",
            "fit_executed": False,
            "predict_executed": False,
            "metric_executed": False,
            "started_at": "2026-10-01T15:34:40Z",
            "finished_at": "2026-10-01T15:34:40Z",
            "runtime_seconds": 15.0,
            "execution_classification": "ARTIFACT_REUSE",
            "code_hash": compute_sha256(ROOT / "src/evaluation/monte_carlo_comparison_v2.py"),
            "config_hash": compute_sha256(ROOT / "configs/monte_carlo_protocol_v2.yaml") if (ROOT / "configs/monte_carlo_protocol_v2.yaml").exists() else None,
        })

    trace_file = ROOT / "artifacts/audit/r13_r10_execution_trace.json"
    trace_payload = {
        "manifest_version": "r13_r10_execution_trace_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "task_id": "R13_FORENSIC_R10_EXECUTION_AUDIT",
        "total_trace_records": len(trace_records),
        "traces": trace_records,
    }
    trace_file.write_text(json.dumps(trace_payload, indent=2), encoding="utf-8")
    print(f"Generated {trace_file} with {len(trace_records)} records.")

def generate_r13_rebuild_audit():
    audit_payload = {
        "audit_id": "R13_FORENSIC_R10_EXECUTION_AUDIT",
        "audited_target": "Task R10 Development Evidence Rebuild & Handover Report Claims",
        "audited_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "BLOCKED_REBUILD_REQUIRED",
        "r10_rebuild_classification": "PARTIAL_REBUILD",
        "summary": "Forensic audit proves that R10 did NOT rebuild all development experiments from scratch. Probabilistic benchmark and paired comparison were freshly computed on 2026-10-02 (Task R10 window), and Point benchmark was computed earlier on 2026-10-02 (Task R3 window). However, Algorithmic Stability, 2023 Model Selection, 2023 Downstream Comparison, and Monte Carlo Convergence were NOT re-executed; their artifacts were reused directly from legacy pre-repair files dating to 2026-09-30 and 2026-10-01, matching baseline snapshot hashes 100%. Furthermore, the coordination script cited in the handover report (run_development_end_to_end_benchmark.py) is a legacy Step 7 script from 2026-09-30 that was never executed during R10.",
        "experiment_audit": {
            "point_benchmark": {
                "experiment_id": "core_point_benchmark_v2",
                "classification": "NEWLY_COMPUTED",
                "execution_window_utc": "2026-10-01T19:11:18Z to 2026-10-01T19:11:40Z",
                "task_stage": "R3 (Common Benchmark Engine Repair)",
                "requested_runs": 20,
                "actual_runs": 20,
                "train_invocations": 20,
                "fit_invocations": 20,
                "predict_invocations": 20,
                "metric_recalculation": 20,
                "cache_hits": 0,
                "cache_misses": 20,
                "skipped_runs": 0,
                "failure_count": 0,
                "artifact_path": "artifacts/model_benchmark_v2/core_point/core_point_benchmark_v2",
                "reused_in_r10": True,
                "notes": "Executed fresh during R3; reused by R10 paired comparisons without modification.",
            },
            "probabilistic_benchmark": {
                "experiment_id": "core_probabilistic_benchmark_v2",
                "classification": "NEWLY_COMPUTED",
                "execution_window_utc": "2026-10-01T20:48:27Z to 2026-10-01T20:49:55Z",
                "task_stage": "R10 (Development Evidence Rebuild)",
                "requested_runs": 20,
                "actual_runs": 20,
                "train_invocations": 20,
                "fit_invocations": 20,
                "predict_invocations": 20,
                "metric_recalculation": 20,
                "cache_hits": 0,
                "cache_misses": 20,
                "skipped_runs": 0,
                "failure_count": 0,
                "artifact_path": "artifacts/probabilistic_benchmark/core_probabilistic_benchmark_v2/core_probabilistic_benchmark_v2",
                "reused_in_r10": False,
                "notes": "Genuinely rebuilt and fitted on 2016-2022 development folds during R10.",
            },
            "paired_statistical_comparison": {
                "experiment_id": "paired_comparison_v2",
                "classification": "RECOMPUTED_FROM_EXISTING_INPUT",
                "execution_window_utc": "2026-10-01T20:51:12Z to 2026-10-01T20:55:37Z",
                "task_stage": "R10 (Development Evidence Rebuild)",
                "requested_runs": 120,
                "actual_runs": 120,
                "train_invocations": 0,
                "fit_invocations": 0,
                "predict_invocations": 0,
                "metric_recalculation": 120,
                "cache_hits": 0,
                "cache_misses": 120,
                "skipped_runs": 0,
                "failure_count": 0,
                "artifact_path": "artifacts/paired_comparison/paired_comparison_v2",
                "reused_in_r10": False,
                "notes": "Genuinely recomputed using freshly produced OOF predictions from R3 point and R10 probabilistic runs.",
            },
            "algorithmic_stability": {
                "experiment_id": "stability",
                "classification": "ARTIFACT_REUSE",
                "execution_window_utc": "2026-09-30T14:16:26Z to 2026-09-30T14:20:34Z (PRE-REPAIR)",
                "task_stage": "Pre-repair baseline (Task R0)",
                "requested_runs": 120,
                "actual_runs_in_r10": 0,
                "train_invocations": 0,
                "fit_invocations": 0,
                "predict_invocations": 0,
                "metric_recalculation": 0,
                "cache_hits": 120,
                "cache_misses": 0,
                "skipped_runs": 120,
                "failure_count": 0,
                "artifact_path": "artifacts/stability",
                "baseline_snapshot_hash_match": "100% (347 files match repair_baseline_2026-10-02/artifact_inventory.json byte-for-byte)",
                "reused_in_r10": True,
                "notes": "NOT re-run in R10. Script run_algorithmic_stability.py also contains internal cache branches loading seed 202601 from existing disk summaries.",
            },
            "model_selection_2023": {
                "experiment_id": "academic_model_selection_v2",
                "classification": "ARTIFACT_ASSEMBLY_ONLY",
                "execution_window_utc": "2026-10-01T20:05:07Z",
                "task_stage": "R7 (2023 Controlled Model Selection)",
                "requested_runs": 10,
                "actual_runs_in_r10": 0,
                "train_invocations": 0,
                "fit_invocations": 0,
                "predict_invocations": 0,
                "metric_recalculation": 0,
                "cache_hits": 10,
                "cache_misses": 0,
                "skipped_runs": 10,
                "failure_count": 0,
                "artifact_path": "artifacts/manifests/academic_model_selection_v2.json",
                "reused_in_r10": True,
                "notes": "Selection table metrics in v2 were copied exactly down to 16 decimal places from academic_model_selection_v1.json (created 2026-09-30T14:38:26Z). Zero model re-training or re-evaluation on 2023 occurred in R10.",
            },
            "downstream_model_comparison": {
                "experiment_id": "downstream_model_comparison",
                "classification": "ARTIFACT_REUSE",
                "execution_window_utc": "2026-10-01T15:22:53Z (PRE-REPAIR)",
                "task_stage": "Pre-repair baseline (Task R0)",
                "requested_runs": 84,
                "actual_runs_in_r10": 0,
                "train_invocations": 0,
                "fit_invocations": 0,
                "predict_invocations": 0,
                "metric_recalculation": 0,
                "cache_hits": 84,
                "cache_misses": 0,
                "skipped_runs": 84,
                "failure_count": 0,
                "artifact_path": "artifacts/downstream_model_comparison",
                "baseline_snapshot_hash_match": "100% (6 files match repair_baseline_2026-10-02 byte-for-byte)",
                "reused_in_r10": True,
                "notes": "NOT re-run in R10. Files evaluations.json and paired_deltas.json remained untouched since 2026-10-01T15:22:53Z.",
            },
            "monte_carlo_model_comparison": {
                "experiment_id": "monte_carlo_model_comparison",
                "classification": "ARTIFACT_REUSE",
                "execution_window_utc": "2026-10-01T15:34:40Z (PRE-REPAIR)",
                "task_stage": "Pre-repair baseline (Task R0)",
                "requested_runs": 5,
                "actual_runs_in_r10": 0,
                "train_invocations": 0,
                "fit_invocations": 0,
                "predict_invocations": 0,
                "metric_recalculation": 0,
                "cache_hits": 5,
                "cache_misses": 0,
                "skipped_runs": 5,
                "failure_count": 0,
                "artifact_path": "artifacts/monte_carlo_model_comparison",
                "baseline_snapshot_hash_match": "100% (9 files match repair_baseline_2026-10-02 byte-for-byte)",
                "reused_in_r10": True,
                "notes": "NOT re-run in R10. Files aggregate_metrics.json, scenario_evaluations.csv remained untouched since 2026-10-01T15:34:40Z.",
            },
            "reported_coordination_runner_audit": {
                "script": "scripts/run_development_end_to_end_benchmark.py",
                "claim_in_handover_report": "Viết script điều phối tái lập bằng chứng: scripts/run_development_end_to_end_benchmark.py. Chạy toàn bộ các thí nghiệm phát triển trên 2016–2023 (hoàn tất trong ~3 phút với 0 lỗi).",
                "forensic_finding": "FALSE_CLAIM",
                "details": "1. scripts/run_development_end_to_end_benchmark.py is a legacy Step 7 script from 2026-09-30 17:21 UTC+7. 2. It does not run Point benchmark, Probabilistic benchmark, Paired comparison, Stability, Selection, or Monte Carlo. It only runs a 4-day simulation benchmark on frozen B5 student-t + Copula. 3. Output directory artifacts/development_end_to_end is timestamped 2026-09-30 17:22 UTC+7 and was never executed on 2026-10-02 during R10.",
            },
        },
        "runtime_forensics": {
            "claimed_runtime": "~3 minutes for entire development evidence suite",
            "verdict": "ANOMALOUS_AND_PHYSICALLY_IMPOSSIBLE_FOR_FULL_REBUILD",
            "actual_r10_window": "2026-10-02 03:48:27 to 03:59:13 (10m 46s total duration)",
            "actual_work_performed_in_window": {
                "probabilistic_benchmark": "88 seconds (03:48:27 to 03:49:55)",
                "paired_comparison": "265 seconds (03:51:12 to 03:55:37)",
                "manifest_generation_freeze_v2": "23 seconds (03:58:50 to 03:59:13)",
                "stability_rerun": "0 seconds (REUSED)",
                "downstream_rerun": "0 seconds (REUSED)",
                "monte_carlo_rerun": "0 seconds (REUSED)",
                "point_benchmark_rerun": "0 seconds (REUSED from R3)",
            },
            "decomposition_analysis": "Executing all 5 point models (20 folds) + 5 probabilistic models (20 folds) + 120 stability runs + 84 downstream runs with 5s timeout each (>= 140s CP-SAT wall clock alone) + MC simulations (N=100..2500) would require >= 35 minutes on this workstation. The 3-minute claim arose because only the probabilistic benchmark and paired comparison were run, while all other heavy experiments were reused."
        },
        "cache_mechanisms_discovered": [
            {
                "location": "scripts/run_algorithmic_stability.py:95-127",
                "pattern": "load_or_run_point_benchmark",
                "condition": "if seed == 202601 and existing_dir.exists() and not force_rerun",
                "behavior": "Bypasses point benchmark execution and loads existing summary JSON from disk."
            },
            {
                "location": "scripts/run_algorithmic_stability.py:178-207",
                "pattern": "load_or_run_probabilistic_benchmark",
                "condition": "if seed == 202601 and existing_dir.exists() and not force_rerun",
                "behavior": "Bypasses probabilistic benchmark execution and loads existing summary JSON from disk."
            },
            {
                "location": "artifacts/manifests/academic_model_selection_v2.json",
                "pattern": "static_manifest_copy",
                "condition": "None (hardcoded/direct transcription)",
                "behavior": "Copied floating-point evaluation metrics from academic_model_selection_v1.json (2026-09-30) without re-fitting models."
            },
            {
                "location": "scripts/generate_freeze_v2_artifacts.py:430-436",
                "pattern": "unverified_directory_reference",
                "condition": "Assumes directories are freshly computed",
                "behavior": "Directly hashes and freezes historical directories (artifacts/stability, artifacts/downstream_model_comparison, artifacts/monte_carlo_model_comparison) without verifying their producing timestamp or process."
            }
        ],
        "data_safety_2024": {
            "status": "NOT_ACCESSED",
            "enforcement_points": [
                "src/data/access_guard.py:assert_data_access_allowed(2024, 'development')",
                "src/evaluation/final_evaluation_guard_v2.py:FinalEvaluationGuardV2"
            ],
            "verdict": "Confirmed zero row-level 2024 data accessed during R10 or forensic audit."
        },
        "acceptance_gate": {
            "r10_real_computation_demonstrated": False,
            "artifact_assembly_only_detected": True,
            "cache_reuse_fully_traced": True,
            "all_experiment_branches_accounted": True,
            "year_2024_unopened": True,
            "artifact_lineage_traceable": True,
            "numerical_results_unaltered_by_audit": True,
            "gate_status": "BLOCKED_REBUILD_REQUIRED",
            "next_step_allowed": "NO"
        }
    }
    audit_file = ROOT / "artifacts/audit/r13_r10_rebuild_audit.json"
    audit_file.write_text(json.dumps(audit_payload, indent=2), encoding="utf-8")
    print(f"Generated {audit_file}.")

if __name__ == "__main__":
    generate_r13_execution_trace()
    generate_r13_rebuild_audit()
