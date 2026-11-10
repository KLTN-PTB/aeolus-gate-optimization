"""Day 2 Phase A sample-size scan.

The scan keeps the selected V1.1 feature set, the exact scheduled-arrival
baseline, the frozen Week 5 parameters, and the objective selected by the Day
2 A/B test.  Only the per-year training sample size changes; validation stays
at 25,000 rows from 2022 for every level.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_phase_a_benchmark_mae import (
    BENCHMARK_SEEDS,
    HPO_PROTOCOL,
    HPO_XGB_RESULT,
    ROOT as RUNNER_ROOT,
    SAMPLE_VAL,
    aggregate_results,
    run_single_benchmark,
    sha256_file,
)

FEATURE_SET = "v1.1"
DEFAULT_OBJECTIVE = "reg:absoluteerror"
SAMPLE_LEVELS = [25_000, 75_000, 150_000, 250_000]
STABILITY_SEEDS = list(range(42, 52))
FEATURE_MANIFEST = ROOT / "artifacts" / "manifests" / "feature_manifest_arrival_v1_1.json"


def _relative(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT.resolve()))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, allow_nan=False)


def _base_metadata(sample_train_per_year: int, objective: str) -> dict[str, Any]:
    return {
        "benchmark_version": "phase_a_day2_sample_scan_v1",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "feature_set": FEATURE_SET,
        "feature_manifest": _relative(FEATURE_MANIFEST),
        "feature_manifest_sha256": sha256_file(FEATURE_MANIFEST),
        "protocol": {
            "fold": "Fold 4 (Train 2016-2021, Val 2022)",
            "train_years": [2016, 2017, 2018, 2019, 2020, 2021],
            "validation_year": 2022,
            "sample_train_per_year": sample_train_per_year,
            "sample_val": SAMPLE_VAL,
            "seeds": BENCHMARK_SEEDS,
            "sampling_method": "stratified by calendar month",
            "validation_population_fixed_across_levels": True,
            "allowed_row_level_years": [2016, 2017, 2018, 2019, 2020, 2021, 2022],
            "blocked_row_level_years": [2023, 2024],
            "row_level_2023_accessed": False,
            "row_level_2024_accessed": False,
        },
        "xgboost": {
            "objective": objective,
            "eval_metric": "mae",
            "best_params_source": _relative(HPO_XGB_RESULT),
            "best_params_sha256": sha256_file(HPO_XGB_RESULT),
        },
        "inputs": {
            _relative(FEATURE_MANIFEST): sha256_file(FEATURE_MANIFEST),
            _relative(HPO_XGB_RESULT): sha256_file(HPO_XGB_RESULT),
            _relative(HPO_PROTOCOL): sha256_file(HPO_PROTOCOL),
        },
        "actual_operation_features_used": False,
        "weather_features_used": False,
        "flight_chain_features_used": False,
    }


def run_level(sample_train_per_year: int, *, objective: str) -> Path:
    """Run five seeds and save one versioned report for one sample level."""
    started = time.perf_counter()
    report = _base_metadata(sample_train_per_year, objective)
    report["status"] = "RUNNING"
    output = ROOT / "artifacts" / "manifests" / (
        f"phase_a_benchmark_sample_{sample_train_per_year // 1000}k.json"
    )
    try:
        seed_results = [
            run_single_benchmark(
                seed,
                feature_set=FEATURE_SET,
                xgb_objective=objective,
                sample_train_per_year=sample_train_per_year,
                sample_val=SAMPLE_VAL,
            )
            for seed in BENCHMARK_SEEDS
        ]
    except Exception as exc:
        report.update(
            {
                "status": "FAILED",
                "failure": {"type": type(exc).__name__, "message": str(exc)},
                "execution_time_seconds": round(time.perf_counter() - started, 2),
            }
        )
        _write_json(output, report)
        print(f"[!] Sample level {sample_train_per_year} failed: {type(exc).__name__}: {exc}")
        return output

    report.update(
        {
            "status": "COMPLETED",
            "execution_time_seconds": round(time.perf_counter() - started, 2),
            "summary": aggregate_results(seed_results),
            "per_seed_results": seed_results,
        }
    )
    _write_json(output, report)
    summary = report["summary"]["xgboost"]
    print(
        f"[+] {sample_train_per_year:,}/year: skill={summary['skill_score_vs_carrier_hour']['mean']:+.4f}% "
        f"+/- {summary['skill_score_vs_carrier_hour']['std']:.4f}% "
        f"MAE={summary['mae']['mean']:.4f} time={report['execution_time_seconds']:.1f}s"
    )
    return output


def run_stability(sample_train_per_year: int, *, objective: str) -> Path:
    """Rerun the selected level with ten seeds and save a separate report."""
    started = time.perf_counter()
    seed_results = [
        run_single_benchmark(
            seed,
            feature_set=FEATURE_SET,
            xgb_objective=objective,
            sample_train_per_year=sample_train_per_year,
            sample_val=SAMPLE_VAL,
        )
        for seed in STABILITY_SEEDS
    ]
    report = _base_metadata(sample_train_per_year, objective)
    report.update(
        {
            "benchmark_version": "phase_a_day2_sample_stability_10_seed_v1",
            "status": "COMPLETED",
            "stability_seed_count": len(STABILITY_SEEDS),
            "stability_seeds": STABILITY_SEEDS,
            "execution_time_seconds": round(time.perf_counter() - started, 2),
            "summary": aggregate_results(seed_results),
            "per_seed_results": seed_results,
            "stability_gate": {
                "skill_std_percentage_points": aggregate_results(seed_results)["xgboost"][
                    "skill_score_vs_carrier_hour"
                ]["std"],
                "unstable_if_greater_than": 1.0,
                "unstable": aggregate_results(seed_results)["xgboost"][
                    "skill_score_vs_carrier_hour"
                ]["std"] > 1.0,
            },
        }
    )
    report["protocol"]["seeds"] = STABILITY_SEEDS
    output = ROOT / "artifacts" / "manifests" / (
        f"phase_a_benchmark_sample_{sample_train_per_year // 1000}k_10seed.json"
    )
    _write_json(output, report)
    print(f"[+] Saved 10-seed stability report {output}")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Day 2 sample-size scan")
    parser.add_argument("--objective", choices=("reg:squarederror", "reg:absoluteerror"), default=DEFAULT_OBJECTIVE)
    parser.add_argument("--levels", nargs="+", type=int, default=SAMPLE_LEVELS)
    parser.add_argument("--skip-stability", action="store_true")
    args = parser.parse_args()

    level_outputs = [run_level(level, objective=args.objective) for level in args.levels]
    completed: list[dict[str, Any]] = []
    for path in level_outputs:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if payload.get("status") == "COMPLETED":
            skill = payload["summary"]["xgboost"]["skill_score_vs_carrier_hour"]["mean"]
            completed.append({"sample_train_per_year": payload["protocol"]["sample_train_per_year"], "skill_mean": skill})

    best = max(completed, key=lambda row: row["skill_mean"]) if completed else None
    stability_path = None
    if best is not None and not args.skip_stability:
        stability_path = run_stability(int(best["sample_train_per_year"]), objective=args.objective)

    selection_report = {
        "benchmark_version": "phase_a_day2_sample_scan_selection_v1",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "objective": args.objective,
        "feature_set": FEATURE_SET,
        "sample_levels_requested": args.levels,
        "completed_levels": completed,
        "best_level_by_mean_skill": best,
        "stability_report": None if stability_path is None else _relative(stability_path),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "inputs": {
            _relative(FEATURE_MANIFEST): sha256_file(FEATURE_MANIFEST),
            _relative(HPO_XGB_RESULT): sha256_file(HPO_XGB_RESULT),
            _relative(HPO_PROTOCOL): sha256_file(HPO_PROTOCOL),
        },
    }
    selection_output = ROOT / "artifacts" / "manifests" / "phase_a_benchmark_sample_scan_selection.json"
    _write_json(selection_output, selection_report)
    print("\nSample-size skill table:")
    for row in completed:
        print(f"  {row['sample_train_per_year']:,}/year -> {row['skill_mean']:+.4f}%")
    print(f"[+] Saved selection report {selection_output}")


if __name__ == "__main__":
    main()
