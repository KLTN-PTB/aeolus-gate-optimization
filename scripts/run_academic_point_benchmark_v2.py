"""CLI runner for V2 Academic Point Benchmark (Core Arrival).

Protocol: Phase 2 Academic Benchmark / V4 Synchronized Protocol
Enforces:
- Exactly 5 Core Point Models
- Same rows, folds, and information set
- Pure evaluation without champion selection
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sys

# Ensure project root in sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.evaluation.model_benchmark_runner import (
    CommonBenchmarkConfig,
    CommonPointBenchmarkRunner,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run V2 Academic Point Benchmark for Core Arrival Models."
    )
    parser.add_argument(
        "--experiment-id",
        type=str,
        default="core_point_benchmark_v2",
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
        help="Random seed for data sampling and model initialization.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/model_benchmark_v2/core_point"),
        help="Base output directory for benchmark artifacts.",
    )
    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=Path("artifacts/manifests/core_point_benchmark_v2.json"),
        help="Output path for top-level benchmark manifest.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = CommonBenchmarkConfig(
        experiment_id=args.experiment_id,
        sample_train_per_year=args.sample_train_per_year,
        sample_val=args.sample_val,
        random_seed=args.seed,
        output_dir=args.output_dir,
        manifest_path=args.manifest_path,
    )

    runner = CommonPointBenchmarkRunner(config)
    results = runner.run_benchmark()

    print("\n" + "=" * 115)
    print("V2 CORE POINT BENCHMARK EXECUTION SUMMARY")
    print("=" * 115)
    print(
        f"{'Model':<40} {'Fold':<8} {'Status':<9} {'MAE':<7} {'RMSE':<7} {'R²':<7} "
        f"{'SevMAE':<8} {'ROC-AUC':<9} {'PR-AUC':<9} {'Brier':<8}"
    )
    print("-" * 115)

    for r in results:
        m = r.metrics
        status = r.status
        mae = f"{m.get('mae', 0.0):.2f}" if m.get("mae") is not None else "N/A"
        rmse = f"{m.get('rmse', 0.0):.2f}" if m.get("rmse") is not None else "N/A"
        r2 = f"{m.get('r2', 0.0):.3f}" if m.get("r2") is not None else "N/A"
        sev = f"{m.get('severe_delay_mae_ge_60', 0.0):.2f}" if m.get("severe_delay_mae_ge_60") is not None else "N/A"
        roc = f"{m.get('roc_auc', 0.0):.4f}" if m.get("roc_auc") is not None else "N/A"
        pr = f"{m.get('pr_auc', 0.0):.4f}" if m.get("pr_auc") is not None else "N/A"
        brier = f"{m.get('brier_score', 0.0):.4f}" if m.get("brier_score") is not None else "N/A"

        print(
            f"{r.model_id:<40} {r.fold_id:<8} {status:<9} {mae:<7} {rmse:<7} {r2:<7} "
            f"{sev:<8} {roc:<9} {pr:<9} {brier:<8}"
        )

    print("=" * 115)
    print("CHAMPION SELECTION: NONE (Champion selection forbidden in Task R3)")
    print(f"Artifacts preserved in: {runner.run_dir}")
    print(f"Top-level manifest:     {args.manifest_path}")
    print("=" * 115 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
