"""Command-line runner for Academic Core Arrival Point Benchmark (Phase 2)."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sys

# Ensure project root in sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.pipeline.academic_point_benchmark import (
    AcademicBenchmarkConfig,
    AcademicPointBenchmarkRunner,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Academic Benchmark for Core Arrival Point Models."
    )
    parser.add_argument(
        "--experiment-id",
        type=str,
        default="academic_benchmark_v1",
        help="Unique experiment identifier.",
    )
    parser.add_argument(
        "--sample-train-per-year",
        type=int,
        default=3500,
        help="Number of monthly-stratified training samples per year.",
    )
    parser.add_argument(
        "--sample-val",
        type=int,
        default=4000,
        help="Number of monthly-stratified validation samples per fold.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=202601,
        help="Random seed for sampling and model initialization.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/model_benchmark/core_point"),
        help="Base output directory for benchmark artifacts.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = AcademicBenchmarkConfig(
        experiment_id=args.experiment_id,
        sample_train_per_year=args.sample_train_per_year,
        sample_val=args.sample_val,
        random_seed=args.seed,
        output_dir=args.output_dir,
    )
    runner = AcademicPointBenchmarkRunner(config)
    results = runner.run_benchmark()

    print("\n" + "=" * 80)
    print("ACADEMIC BENCHMARK EXECUTION SUMMARY")
    print("=" * 80)
    print(f"{'Model':<40} {'Fold':<8} {'Status':<10} {'ROC-AUC':<9} {'PR-AUC':<9} {'Brier':<9} {'MAE':<8} {'RMSE':<8}")
    print("-" * 105)

    for r in results:
        roc = f"{r.classification.get('roc_auc', 0.0):.4f}" if r.classification.get("roc_auc") is not None else "N/A"
        pr = f"{r.classification.get('pr_auc', 0.0):.4f}" if r.classification.get("pr_auc") is not None else "N/A"
        brier = f"{r.classification.get('brier_score', 0.0):.4f}" if r.classification.get("brier_score") is not None else "N/A"
        mae = f"{r.regression.get('mae', 0.0):.2f}" if r.regression.get("mae") is not None else "N/A"
        rmse = f"{r.regression.get('rmse', 0.0):.2f}" if r.regression.get("rmse") is not None else "N/A"
        print(f"{r.model_id:<40} {r.fold_id:<8} {r.status:<10} {roc:<9} {pr:<9} {brier:<9} {mae:<8} {rmse:<8}")

    print("=" * 105)
    print(f"Artifacts preserved in: {runner.run_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
