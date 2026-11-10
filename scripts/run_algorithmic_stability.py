"""Executable runner for Phase 6 Algorithmic Stability Benchmark across Pre-registered Seeds."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import sys
from typing import Any

# Ensure project root in sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from src.evaluation.algorithmic_stability import (
    DEFAULT_SEED_REGISTRY_PATH,
    DEFAULT_STABILITY_DIR,
    RunRecord,
    SeedRegistry,
    aggregate_stability_records,
    audit_equal_seed_count,
    compute_metric_stability,
    extract_scalar_metrics,
)
from src.pipeline.academic_point_benchmark import (
    AcademicBenchmarkConfig,
    AcademicPointBenchmarkRunner,
    CORE_METHOD_IDS,
)
from src.pipeline.probabilistic_benchmark_runner import (
    ProbabilisticBenchmarkConfig,
    ProbabilisticBenchmarkRunner,
    PROBABILISTIC_CANDIDATE_IDS,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
LOGGER = logging.getLogger("run_algorithmic_stability")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Phase 6 Algorithmic Stability across fixed pre-registered seeds."
    )
    parser.add_argument(
        "--seed-registry",
        type=Path,
        default=DEFAULT_SEED_REGISTRY_PATH,
        help="Path to seed_registry.yaml",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_STABILITY_DIR,
        help="Directory to save stability artifacts.",
    )
    parser.add_argument(
        "--sample-train-per-year",
        type=int,
        default=3500,
        help="Monthly-stratified training samples per year.",
    )
    parser.add_argument(
        "--sample-val",
        type=int,
        default=4000,
        help="Monthly-stratified validation samples per fold.",
    )
    parser.add_argument(
        "--force-rerun-seed1",
        action="store_true",
        help="Force rerunning seed 202601 even if existing Phase 2/3 artifacts exist.",
    )
    return parser.parse_args()


def load_or_run_point_benchmark(
    seed: int,
    data_seed: int,
    sample_train: int,
    sample_val: int,
    force_rerun: bool = False,
) -> list[RunRecord]:
    """Load existing point benchmark results for seed, or execute benchmark."""
    # Check for existing Phase 2 run for seed 202601
    existing_dir = Path("artifacts/model_benchmark/core_point/core_point_academic_benchmark_v1_20260930_124849")
    if seed == 202601 and existing_dir.exists() and not force_rerun:
        summary_path = existing_dir / "benchmark_summary.json"
        if summary_path.exists():
            LOGGER.info(f"Loading existing Point Benchmark artifacts for seed {seed} from {summary_path}")
            with open(summary_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            runs: list[RunRecord] = []
            for r in data.get("results", []):
                runs.append(
                    RunRecord(
                        model_id=r["model_id"],
                        family="point",
                        fold_id=r["fold_id"],
                        validation_year=r["validation_year"],
                        seed=seed,
                        data_seed=data_seed,
                        status=r.get("status", "COMPLETED"),
                        runtime_seconds=float(r.get("runtime_seconds", 0.0)),
                        memory_mb=float(r.get("memory_mb", 0.0)),
                        failure_reason=r.get("failure_reason"),
                        error_category=None if r.get("status") == "COMPLETED" else "TRAINING_ERROR",
                        model_version="core_point_v1",
                        data_version="aeolus_canonical_v1",
                        feature_version="v1",
                        metrics={
                            "classification": r.get("classification", {}),
                            "regression": r.get("regression", {}),
                        },
                    )
                )
            if len(runs) == 20:
                return runs

    # Otherwise execute benchmark with seed and locked data_seed
    exp_id = f"core_point_stability_seed_{seed}"
    LOGGER.info(f"Executing Academic Point Benchmark for seed {seed} (data_seed={data_seed})...")
    config = AcademicBenchmarkConfig(
        experiment_id=exp_id,
        random_seed=seed,
        data_seed=data_seed,
        sample_train_per_year=sample_train,
        sample_val=sample_val,
        output_dir=Path("artifacts/model_benchmark/core_point"),
    )
    runner = AcademicPointBenchmarkRunner(config)
    results = runner.run_benchmark()

    runs = []
    for r in results:
        runs.append(
            RunRecord(
                model_id=r.model_id,
                family="point",
                fold_id=r.fold_id,
                validation_year=r.validation_year,
                seed=seed,
                data_seed=data_seed,
                status=r.status,
                runtime_seconds=r.runtime_seconds,
                memory_mb=r.memory_mb,
                failure_reason=r.failure_reason,
                error_category=None if r.status == "COMPLETED" else "POINT_MODEL_TRAINING_ERROR",
                model_version="core_point_v1",
                data_version="aeolus_canonical_v1",
                feature_version="v1",
                metrics={
                    "classification": r.classification,
                    "regression": r.regression,
                },
            )
        )
    return runs


def load_or_run_probabilistic_benchmark(
    seed: int,
    data_seed: int,
    sample_train: int,
    sample_val: int,
    force_rerun: bool = False,
) -> list[RunRecord]:
    """Load existing probabilistic benchmark results for seed, or execute benchmark."""
    existing_dir = Path("artifacts/probabilistic_benchmark/core_probabilistic_benchmark_v1")
    if seed == 202601 and existing_dir.exists() and not force_rerun:
        summary_path = existing_dir / "benchmark_summary.json"
        if summary_path.exists():
            LOGGER.info(f"Loading existing Probabilistic Benchmark artifacts for seed {seed} from {summary_path}")
            with open(summary_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            runs: list[RunRecord] = []
            for r in data.get("results", []):
                runs.append(
                    RunRecord(
                        model_id=r["candidate_id"],
                        family="probabilistic",
                        fold_id=r["fold_id"],
                        validation_year=r["validation_year"],
                        seed=seed,
                        data_seed=data_seed,
                        status=r.get("status", "COMPLETED"),
                        runtime_seconds=float(r.get("runtime_seconds", 0.0)),
                        memory_mb=float(r.get("memory_mb", 0.0)),
                        failure_reason=r.get("failure_reason"),
                        error_category=None if r.get("status") == "COMPLETED" else "PROBABILISTIC_ERROR",
                        model_version="core_probabilistic_v1",
                        data_version="aeolus_canonical_v1",
                        feature_version="v1",
                        metrics=r.get("metrics", {}),
                    )
                )
            if len(runs) == 20:
                return runs

    exp_id = f"core_probabilistic_stability_seed_{seed}"
    LOGGER.info(f"Executing Probabilistic Benchmark for seed {seed} (data_seed={data_seed})...")
    config = ProbabilisticBenchmarkConfig(
        experiment_id=exp_id,
        seed=seed,
        data_seed=data_seed,
        sample_train_per_year=sample_train,
        sample_val=sample_val,
        output_dir=Path("artifacts/probabilistic_benchmark"),
    )
    runner = ProbabilisticBenchmarkRunner(config)
    results = runner.run_benchmark()

    runs = []
    for r in results:
        runs.append(
            RunRecord(
                model_id=r.candidate_id,
                family="probabilistic",
                fold_id=r.fold_id,
                validation_year=r.validation_year,
                seed=seed,
                data_seed=data_seed,
                status=r.status,
                runtime_seconds=r.runtime_seconds,
                memory_mb=r.memory_mb,
                failure_reason=r.failure_reason,
                error_category=None if r.status == "COMPLETED" else "PROBABILISTIC_TRAINING_ERROR",
                model_version="core_probabilistic_v1",
                data_version="aeolus_canonical_v1",
                feature_version="v1",
                metrics=r.metrics,
            )
        )
    return runs


def generate_sha256_manifest(directory: Path) -> dict[str, str]:
    """Generate SHA-256 checksums for all files in directory."""
    hashes: dict[str, str] = {}
    for p in sorted(directory.rglob("*")):
        if p.is_file() and p.name != "manifest.sha256":
            rel = str(p.relative_to(directory)).replace("\\", "/")
            sha = hashlib.sha256(p.read_bytes()).hexdigest()
            hashes[rel] = sha
    manifest_path = directory / "manifest.sha256"
    with open(manifest_path, "w", encoding="utf-8") as f:
        for rel, sha in sorted(hashes.items()):
            f.write(f"{sha}  {rel}\n")
    return hashes


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    runs_dir = output_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load seed registry
    LOGGER.info(f"Loading seed registry from: {args.seed_registry}")
    registry = SeedRegistry.load(args.seed_registry)
    LOGGER.info(f"Registered seeds: {registry.registered_seeds}")
    LOGGER.info(f"Deployment seed: {registry.predetermined_deployment_seed}")
    LOGGER.info(f"Data sampling seed: {registry.data_sampling_seed}")

    # Save seed manifest
    seed_manifest = {
        "manifest_version": "seed_manifest_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "registry_version": registry.registry_version,
        "registered_seeds": list(registry.registered_seeds),
        "predetermined_deployment_seed": registry.predetermined_deployment_seed,
        "data_sampling_seed": registry.data_sampling_seed,
        "policy": registry.policy,
        "status": registry.status,
        "provenance_hash": registry.provenance_hash,
    }
    with open(output_dir / "seed_manifest.json", "w", encoding="utf-8") as f:
        json.dump(seed_manifest, f, indent=2)

    all_runs: list[RunRecord] = []
    failure_records: list[dict[str, Any]] = []

    # 2. Execute runs across all registered seeds
    for s in registry.registered_seeds:
        LOGGER.info(f"\n========================================================")
        LOGGER.info(f"=== PROCESSING SEED {s} (Row parity locked to {registry.data_sampling_seed}) ===")
        LOGGER.info(f"========================================================")

        # Point models
        point_runs = load_or_run_point_benchmark(
            seed=s,
            data_seed=registry.data_sampling_seed,
            sample_train=args.sample_train_per_year,
            sample_val=args.sample_val,
            force_rerun=args.force_rerun_seed1,
        )
        all_runs.extend(point_runs)

        # Probabilistic models
        prob_runs = load_or_run_probabilistic_benchmark(
            seed=s,
            data_seed=registry.data_sampling_seed,
            sample_train=args.sample_train_per_year,
            sample_val=args.sample_val,
            force_rerun=args.force_rerun_seed1,
        )
        all_runs.extend(prob_runs)

    # 3. Save individual run records and track failures
    for r in all_runs:
        run_file = runs_dir / f"{r.family}_{r.model_id}_{r.fold_id}_seed_{r.seed}.json"
        with open(run_file, "w", encoding="utf-8") as f:
            json.dump(r.to_dict(), f, indent=2)

        if r.status != "COMPLETED":
            failure_records.append({
                "model_id": r.model_id,
                "family": r.family,
                "fold_id": r.fold_id,
                "seed": r.seed,
                "error_category": r.error_category or "UNKNOWN_ERROR",
                "failure_reason": r.failure_reason,
                "timestamp_utc": r.created_at_utc,
                "was_rerun": False,
                "rerun_notes": None,
            })

    # Save failure records artifact
    total_evals = len(all_runs)
    total_failures = len(failure_records)
    overall_failure_rate = float(total_failures / total_evals) if total_evals > 0 else 0.0

    failure_artifact = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "total_runs_evaluated": total_evals,
        "failed_runs_count": total_failures,
        "overall_failure_rate": round(overall_failure_rate, 6),
        "failures": failure_records,
        "rerun_policy": "Rerun only if proven infrastructure/transient issue, recorded explicitly.",
    }
    with open(output_dir / "failure_records.json", "w", encoding="utf-8") as f:
        json.dump(failure_artifact, f, indent=2)

    # 4. Audit equal seed count
    equal_seeds_ok, seed_audit_msg = audit_equal_seed_count(
        all_runs, expected_seeds=registry.registered_seeds
    )
    LOGGER.info(f"Seed count fairness audit: {seed_audit_msg}")
    if not equal_seeds_ok:
        LOGGER.error("FAIRNESS VIOLATION: Seed counts are unequal across models!")
        return 1

    # 5. Compute Stability Metrics per model x fold
    runs_by_model_fold: dict[tuple[str, str], list[RunRecord]] = {}
    for r in all_runs:
        runs_by_model_fold.setdefault((r.model_id, r.fold_id), []).append(r)

    stability_by_model_fold: dict[str, Any] = {}
    csv_rows: list[dict[str, Any]] = []

    for (m_id, f_id), r_list in sorted(runs_by_model_fold.items()):
        family = r_list[0].family
        val_year = r_list[0].validation_year
        agg = aggregate_stability_records(r_list)
        key = f"{m_id}__{f_id}"
        stability_by_model_fold[key] = {
            "model_id": m_id,
            "family": family,
            "fold_id": f_id,
            "validation_year": val_year,
            "seeds_evaluated": [r.seed for r in r_list],
            "aggregation": agg,
        }

        # Format CSV row
        metrics_dict = agg.get("metrics", {})
        row = {
            "model_id": m_id,
            "family": family,
            "fold_id": f_id,
            "val_year": val_year,
            "total_seeds": agg["total_runs"],
            "failure_rate": agg["failure_rate"],
            "mean_runtime_s": agg["runtime_seconds"]["mean"],
        }
        if family == "point":
            row["mae_mean"] = metrics_dict.get("regression.mae", {}).get("mean")
            row["mae_std"] = metrics_dict.get("regression.mae", {}).get("std")
            row["mae_cv"] = metrics_dict.get("regression.mae", {}).get("cv")
            row["rmse_mean"] = metrics_dict.get("regression.rmse", {}).get("mean")
            row["rmse_std"] = metrics_dict.get("regression.rmse", {}).get("std")
            row["pr_auc_mean"] = metrics_dict.get("classification.pr_auc", {}).get("mean")
            row["pr_auc_std"] = metrics_dict.get("classification.pr_auc", {}).get("std")
            row["brier_mean"] = metrics_dict.get("classification.brier_score", {}).get("mean")
            row["brier_std"] = metrics_dict.get("classification.brier_score", {}).get("std")
        else:
            row["crps_mean"] = metrics_dict.get("crps", {}).get("mean")
            row["crps_std"] = metrics_dict.get("crps", {}).get("std")
            row["crps_cv"] = metrics_dict.get("crps", {}).get("cv")
            row["nll_mean"] = metrics_dict.get("nll", {}).get("mean")
            row["nll_std"] = metrics_dict.get("nll", {}).get("std")
            row["brier_mean"] = metrics_dict.get("brier_score_delay_ge_15", {}).get("mean")
            row["brier_std"] = metrics_dict.get("brier_score_delay_ge_15", {}).get("std")
            row["cov80_mean"] = metrics_dict.get("empirical_coverage.interval_80", {}).get("mean")
            row["cov90_mean"] = metrics_dict.get("empirical_coverage.interval_90", {}).get("mean")

        csv_rows.append(row)

    # 6. Save stability_metrics_by_model.json
    with open(output_dir / "stability_metrics_by_model.json", "w", encoding="utf-8") as f:
        json.dump(stability_by_model_fold, f, indent=2)

    # 7. Save stability_summary.json
    summary_doc = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "total_evaluations": total_evals,
        "completed_evaluations": total_evals - total_failures,
        "failed_evaluations": total_failures,
        "overall_failure_rate": round(overall_failure_rate, 6),
        "seed_count": len(registry.registered_seeds),
        "registered_seeds": list(registry.registered_seeds),
        "data_sampling_seed": registry.data_sampling_seed,
        "models_count": len({r.model_id for r in all_runs}),
        "folds_count": len({r.fold_id for r in all_runs}),
        "equal_seed_count_verified": equal_seeds_ok,
        "results": stability_by_model_fold,
    }
    with open(output_dir / "stability_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary_doc, f, indent=2)

    # 8. Save stability_summary.csv
    df_summary = pd.DataFrame(csv_rows)
    df_summary.to_csv(output_dir / "stability_summary.csv", index=False)

    # 9. Generate manifest.sha256
    generate_sha256_manifest(output_dir)

    print("\n" + "=" * 115)
    print("PHASE 6 ALGORITHMIC STABILITY BENCHMARK COMPLETE")
    print("=" * 115)
    print(f"Total Evaluations: {total_evals} (10 models x 4 folds x 3 seeds)")
    print(f"Completed: {total_evals - total_failures} | Failed: {total_failures} (Rate: {overall_failure_rate:.2%})")
    print(f"Fairness Audit: {seed_audit_msg}")
    print(f"Artifacts preserved in: {output_dir}")
    print("=" * 115)

    return 0


if __name__ == "__main__":
    sys.exit(main())
