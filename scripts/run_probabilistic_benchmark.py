"""CLI executable for Phase 3 Multi-Candidate Probabilistic Benchmark."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.pipeline.probabilistic_benchmark_runner import (
    ProbabilisticBenchmarkConfig,
    ProbabilisticBenchmarkRunner,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Phase 3 Probabilistic Benchmark for Core Arrival."
    )
    parser.add_argument(
        "--experiment-id",
        type=str,
        default="probabilistic_benchmark_v1",
        help="Unique experiment identifier.",
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
        "--seed",
        type=int,
        default=202601,
        help="Random seed for data sampling and models.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/probabilistic_benchmark"),
        help="Base output directory for artifacts.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = ProbabilisticBenchmarkConfig(
        experiment_id=args.experiment_id,
        sample_train_per_year=args.sample_train_per_year,
        sample_val=args.sample_val,
        seed=args.seed,
        output_dir=args.output_dir,
    )
    runner = ProbabilisticBenchmarkRunner(config)
    results = runner.run_benchmark()

    print("\n" + "=" * 95)
    print("PHASE 3 PROBABILISTIC BENCHMARK EXECUTION SUMMARY")
    print("=" * 95)
    print(f"{'Candidate':<26} {'Fold':<8} {'Status':<10} {'CRPS':<8} {'NLL':<10} {'Brier':<8} {'Pinball':<8} {'Cov_80':<8} {'Cov_90':<8}")
    print("-" * 105)

    def _fmt(val: Any) -> str:
        if isinstance(val, (int, float)):
            return f"{val:.4f}"
        return str(val) if val is not None else "N/A"

    for r in results:
        crps = _fmt(r.metrics.get('crps'))
        nll = _fmt(r.metrics.get('nll'))
        brier = _fmt(r.metrics.get('brier_score_delay_ge_15'))
        pinball = _fmt(r.metrics.get('mean_pinball_loss'))
        cov80 = _fmt(r.metrics.get('empirical_coverage', {}).get('interval_80') if isinstance(r.metrics.get('empirical_coverage'), dict) else 'NOT_AVAILABLE')
        cov90 = _fmt(r.metrics.get('empirical_coverage', {}).get('interval_90') if isinstance(r.metrics.get('empirical_coverage'), dict) else 'NOT_AVAILABLE')
        print(f"{r.candidate_id:<26} {r.fold_id:<8} {r.status:<10} {crps:<8} {nll:<10} {brier:<8} {pinball:<8} {cov80:<8} {cov90:<8}")

    print("=" * 105)
    print(f"Probabilistic artifacts successfully written to: {runner.run_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
