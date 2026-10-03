"""Day 2 Phase A objective A/B benchmark.

This runner is deliberately separate from ``run_phase_a_benchmark.py``.  It
keeps the locked Fold 4 data protocol and Week 5 parameters, and varies only
the XGBoost regression objective (plus V1 versus V1.1 when requested).

The runner reads only the approved 2016--2022 tabular partitions through the
existing guarded loader.  It never opens raw Flight Chain files or any
blocked-year partition.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any, Iterable

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import numpy as np
from xgboost import XGBRegressor

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.preprocessing import build_tree_preprocessor, build_v1_1_tree_preprocessor
from src.data.stratified_loader import load_stratified_fold_data
from src.models.baselines import NaiveDelayBaselines, compute_skill_score
from src.models.metrics import evaluate_all
from src.models.refactored_models import build_refactored_hgb_bundle

BENCHMARK_SEEDS = [42, 43, 44, 45, 46]
TRAIN_YEARS = [2016, 2017, 2018, 2019, 2020, 2021]
VAL_YEAR = 2022
LOCKED_FOLDS = {
    "fold_1": ([2016, 2017, 2018], 2019),
    "fold_2": ([2016, 2017, 2018, 2019], 2020),
    "fold_3": ([2016, 2017, 2018, 2019, 2020], 2021),
    "fold_4": ([2016, 2017, 2018, 2019, 2020, 2021], 2022),
}
SAMPLE_TRAIN_PER_YEAR = 25_000
SAMPLE_VAL = 25_000
HPO_XGB_RESULT = ROOT / "artifacts" / "manifests" / (
    "week5_hpo_protocol_v1_1__xgboost_regression_result_v1.json"
)
HPO_PROTOCOL = ROOT / "configs" / "week5_hpo_v1_1.yaml"
FEATURE_MANIFESTS = {
    "v1": ROOT / "artifacts" / "manifests" / "feature_manifest_arrival_v1.json",
    "v1.1": ROOT / "artifacts" / "manifests" / "feature_manifest_arrival_v1_1.json",
}
CONFIGS: dict[str, dict[str, str]] = {
    "a1": {"feature_set": "v1", "xgb_objective": "reg:squarederror"},
    "a2": {"feature_set": "v1", "xgb_objective": "reg:absoluteerror"},
    "b1": {"feature_set": "v1.1", "xgb_objective": "reg:squarederror"},
    "b2": {"feature_set": "v1.1", "xgb_objective": "reg:absoluteerror"},
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT.resolve()))


def load_tuned_xgb_params() -> dict[str, Any]:
    with HPO_XGB_RESULT.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    params = manifest.get("best_params")
    if not isinstance(params, dict):
        raise ValueError("Frozen XGBoost HPO result has no best_params mapping")
    return dict(params)


def build_tuned_xgb_regressor(objective: str, *, seed: int) -> XGBRegressor:
    """Build Week 5 XGBoost with only the loss objective overridden."""
    if objective not in {"reg:squarederror", "reg:absoluteerror"}:
        raise ValueError(f"Unsupported Day 2 regression objective: {objective}")
    params = load_tuned_xgb_params()
    params.update(
        {
            "objective": objective,
            "eval_metric": "mae",
            "tree_method": "hist",
            "device": "cpu",
            "max_bin": 256,
            "random_state": seed,
            "n_jobs": 1,
        }
    )
    return XGBRegressor(**params)


def summarize_seed_metric(results: Iterable[dict[str, Any]], *, key: str) -> dict[str, float]:
    values = np.asarray([float(row[key]) for row in results], dtype=np.float64)
    return {"mean": float(np.mean(values)), "std": float(np.std(values))}


def _model_metrics(evaluation: dict[str, Any], baseline_mae: float) -> dict[str, float | None]:
    point = evaluation["point_regression"]
    severe = evaluation["severe_conditioned"]
    tail = evaluation["tail_risk_ranking"]
    return {
        "mae": point["mae"],
        "rmse": point["rmse"],
        "r2": point["r2"],
        "severe_mae": severe["severe_mae"],
        "shrinkage_ratio": severe["shrinkage_ratio"],
        "pr_auc_severe": tail["pr_auc_severe"],
        "skill_score_vs_carrier_hour": compute_skill_score(point["mae"], baseline_mae),
    }


def run_single_benchmark(
    seed: int,
    *,
    feature_set: str,
    xgb_objective: str,
    sample_train_per_year: int = SAMPLE_TRAIN_PER_YEAR,
    sample_val: int = SAMPLE_VAL,
    include_hgb: bool = False,
    train_years: list[int] | None = None,
    val_year: int | None = None,
) -> dict[str, Any]:
    """Run one seed without changing the locked Fold 4 protocol."""
    if feature_set not in FEATURE_MANIFESTS:
        raise ValueError(f"Unsupported Day 2 feature set: {feature_set}")
    started = time.perf_counter()
    effective_train_years = list(TRAIN_YEARS if train_years is None else train_years)
    effective_val_year = VAL_YEAR if val_year is None else int(val_year)
    print(
        f"[*] seed={seed} feature_set={feature_set} objective={xgb_objective} "
        f"train_years={effective_train_years} val_year={effective_val_year} "
        f"sample_train={sample_train_per_year}/year sample_val={sample_val}"
    )

    (
        X_train,
        _y_train_cls,
        y_train_reg,
        _train_years_vec,
        X_val,
        _y_val_cls,
        y_val_reg,
        _val_flight_keys,
    ) = load_stratified_fold_data(
        train_years=effective_train_years,
        val_year=effective_val_year,
        sample_train_per_year=sample_train_per_year,
        sample_val=sample_val,
        project_root=ROOT,
        random_state=seed,
        feature_set=feature_set,
    )

    y_train = y_train_reg.to_numpy(dtype=np.float64)
    y_val = y_val_reg.to_numpy(dtype=np.float64)

    baseline = NaiveDelayBaselines()
    baseline.fit(X_train, y_train_reg)
    baseline_eval = evaluate_all(y_val, baseline.predict_carrier_hour_median(X_val))
    baseline_mae = float(baseline_eval["point_regression"]["mae"])

    tree_prep = (
        build_tree_preprocessor()
        if feature_set == "v1"
        else build_v1_1_tree_preprocessor()
    )
    X_train_encoded = tree_prep.fit_transform(X_train)
    X_val_encoded = tree_prep.transform(X_val)

    xgb = build_tuned_xgb_regressor(xgb_objective, seed=seed)
    xgb.fit(X_train_encoded, y_train)
    xgb_eval = evaluate_all(y_val, xgb.predict(X_val_encoded))
    xgb_metrics = _model_metrics(xgb_eval, baseline_mae)
    print(
        f"    baseline_mae={baseline_mae:.4f} xgb_mae={xgb_metrics['mae']:.4f} "
        f"skill={xgb_metrics['skill_score_vs_carrier_hour']:+.4f}%"
    )

    result: dict[str, Any] = {
        "seed": seed,
        "train_years": effective_train_years,
        "validation_year": effective_val_year,
        "sample_train_per_year": sample_train_per_year,
        "sample_val": sample_val,
        "train_rows": int(len(X_train)),
        "validation_rows": int(len(X_val)),
        "carrier_hour_median": {
            "mae": baseline_mae,
            "rmse": baseline_eval["point_regression"]["rmse"],
            "r2": baseline_eval["point_regression"]["r2"],
            "severe_mae": baseline_eval["severe_conditioned"]["severe_mae"],
            "shrinkage_ratio": baseline_eval["severe_conditioned"]["shrinkage_ratio"],
            "pr_auc_severe": baseline_eval["tail_risk_ranking"]["pr_auc_severe"],
            "skill_score_vs_carrier_hour": 0.0,
        },
        "xgboost": xgb_metrics,
        "execution_time_seconds": round(time.perf_counter() - started, 3),
    }

    if include_hgb:
        loss = "absolute_error" if xgb_objective == "reg:absoluteerror" else "squared_error"
        hgb_bundle = build_refactored_hgb_bundle(loss=loss, seed=seed)
        hgb_bundle.regressor.fit(X_train_encoded, y_train)
        hgb_eval = evaluate_all(y_val, hgb_bundle.regressor.predict(X_val_encoded))
        result["hist_gradient_boosting"] = _model_metrics(hgb_eval, baseline_mae)
        print(
            f"    hgb_loss={loss} hgb_mae={result['hist_gradient_boosting']['mae']:.4f} "
            f"skill={result['hist_gradient_boosting']['skill_score_vs_carrier_hour']:+.4f}%"
        )

    del X_train, y_train_reg, X_val, y_val_reg, X_train_encoded, X_val_encoded
    gc.collect()
    return result


def aggregate_results(seed_results: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, float]]]:
    model_keys = ["carrier_hour_median", "xgboost"]
    if any("hist_gradient_boosting" in row for row in seed_results):
        model_keys.append("hist_gradient_boosting")
    metric_keys = [
        "mae",
        "rmse",
        "r2",
        "skill_score_vs_carrier_hour",
        "severe_mae",
        "shrinkage_ratio",
        "pr_auc_severe",
    ]
    summary: dict[str, dict[str, dict[str, float]]] = {}
    for model_key in model_keys:
        summary[model_key] = {}
        for metric_key in metric_keys:
            values = [
                float(row[model_key][metric_key])
                for row in seed_results
                if row.get(model_key, {}).get(metric_key) is not None
            ]
            summary[model_key][metric_key] = {
                "mean": float(np.mean(values)) if values else float("nan"),
                "std": float(np.std(values)) if values else float("nan"),
            }
    return summary


def _config_report(
    *,
    config_id: str,
    feature_set: str,
    xgb_objective: str,
    seed_results: list[dict[str, Any]],
    execution_time: float,
    include_hgb: bool,
) -> dict[str, Any]:
    feature_manifest = FEATURE_MANIFESTS[feature_set]
    return {
        "benchmark_version": "phase_a_day2_objective_ab_v1",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "config_id": config_id,
        "protocol": {
            "fold": "Fold 4 (Train 2016-2021, Val 2022)",
            "train_years": TRAIN_YEARS,
            "validation_year": VAL_YEAR,
            "sampling_method": "stratified by calendar month",
            "sample_train_per_year": SAMPLE_TRAIN_PER_YEAR,
            "sample_val": SAMPLE_VAL,
            "seeds": BENCHMARK_SEEDS,
            "allowed_row_level_years": [*TRAIN_YEARS, VAL_YEAR],
            "blocked_row_level_years": [2023, 2024],
            "row_level_2023_accessed": False,
            "row_level_2024_accessed": False,
        },
        "feature_set": feature_set,
        "feature_manifest": _relative(feature_manifest),
        "feature_manifest_sha256": sha256_file(feature_manifest),
        "hpo_result_manifest": _relative(HPO_XGB_RESULT),
        "hpo_result_manifest_sha256": sha256_file(HPO_XGB_RESULT),
        "hpo_protocol": _relative(HPO_PROTOCOL),
        "hpo_protocol_sha256": sha256_file(HPO_PROTOCOL),
        "objective_selection": {
            "hpo_metric": "mean_mae_across_locked_folds",
            "hpo_training_objective": "reg:squarederror",
            "benchmark_training_objective": xgb_objective,
            "objective_mismatch_test": xgb_objective != "reg:squarederror",
        },
        "xgboost": {
            "objective": xgb_objective,
            "eval_metric": "mae",
            "best_params_source": _relative(HPO_XGB_RESULT),
            "best_params": load_tuned_xgb_params(),
            "fixed_runtime_params": {
                "tree_method": "hist",
                "device": "cpu",
                "max_bin": 256,
                "n_jobs": 1,
            },
        },
        "hgb_control": {
            "included": include_hgb,
            "loss": "absolute_error" if xgb_objective == "reg:absoluteerror" else "squared_error",
        },
        "actual_operation_features_used": False,
        "weather_features_used": False,
        "flight_chain_features_used": False,
        "execution_time_seconds": round(execution_time, 2),
        "summary": aggregate_results(seed_results),
        "per_seed_results": seed_results,
        "gate_2_1": {
            "xgb_skill_mean": aggregate_results(seed_results)["xgboost"]["skill_score_vs_carrier_hour"]["mean"],
            "threshold_full_gap_closed": 0.0,
            "threshold_material_improvement": -1.0,
        },
    }


def run_config(config_id: str, *, include_hgb: bool = False) -> Path:
    if config_id not in CONFIGS:
        raise ValueError(f"Unknown Day 2 objective config: {config_id}")
    config = CONFIGS[config_id]
    started = time.perf_counter()
    seed_results = [
        run_single_benchmark(
            seed,
            feature_set=config["feature_set"],
            xgb_objective=config["xgb_objective"],
            include_hgb=include_hgb and config_id in {"b1", "b2"},
        )
        for seed in BENCHMARK_SEEDS
    ]
    report = _config_report(
        config_id=config_id,
        feature_set=config["feature_set"],
        xgb_objective=config["xgb_objective"],
        seed_results=seed_results,
        execution_time=time.perf_counter() - started,
        include_hgb=include_hgb and config_id in {"b1", "b2"},
    )
    report["runner_sha256"] = sha256_file(Path(__file__).resolve())
    output = ROOT / "artifacts" / "manifests" / f"phase_a_benchmark_mae_{config_id}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, allow_nan=False)
    print(f"[+] Saved {output}")
    return output


def run_per_fold_diagnostic() -> Path:
    """Compare the improving MAE-loss configs across all locked folds."""
    started = time.perf_counter()
    configs = ("a2", "b2")
    rows: list[dict[str, Any]] = []
    for config_id in configs:
        config = CONFIGS[config_id]
        for fold_id, (train_years, val_year) in LOCKED_FOLDS.items():
            for seed in BENCHMARK_SEEDS:
                result = run_single_benchmark(
                    seed,
                    feature_set=config["feature_set"],
                    xgb_objective=config["xgb_objective"],
                    train_years=train_years,
                    val_year=val_year,
                )
                rows.append(
                    {
                        "config_id": config_id,
                        "fold_id": fold_id,
                        "validation_year": val_year,
                        "seed": seed,
                        "xgboost_mae": result["xgboost"]["mae"],
                        "xgboost_skill_score_vs_carrier_hour": result["xgboost"]["skill_score_vs_carrier_hour"],
                        "baseline_mae": result["carrier_hour_median"]["mae"],
                    }
                )

    fold_summary: dict[str, dict[str, dict[str, float]]] = {}
    for config_id in configs:
        fold_summary[config_id] = {}
        for fold_id in LOCKED_FOLDS:
            selected = [
                row for row in rows if row["config_id"] == config_id and row["fold_id"] == fold_id
            ]
            fold_summary[config_id][fold_id] = {
                "validation_year": float(selected[0]["validation_year"]),
                "mae_mean": float(np.mean([row["xgboost_mae"] for row in selected])),
                "mae_std": float(np.std([row["xgboost_mae"] for row in selected])),
                "skill_mean": float(
                    np.mean([row["xgboost_skill_score_vs_carrier_hour"] for row in selected])
                ),
                "skill_std": float(
                    np.std([row["xgboost_skill_score_vs_carrier_hour"] for row in selected])
                ),
                "baseline_mae_mean": float(np.mean([row["baseline_mae"] for row in selected])),
            }

    report = {
        "benchmark_version": "phase_a_day2_objective_per_locked_fold_v1",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "purpose": "Per-fold follow-up because reg:absoluteerror improved A2/B2 by >1 percentage point",
        "protocol": {
            "sample_train_per_year": SAMPLE_TRAIN_PER_YEAR,
            "sample_val": SAMPLE_VAL,
            "seeds": BENCHMARK_SEEDS,
            "folds": {
                fold_id: {"train_years": train_years, "validation_year": val_year}
                for fold_id, (train_years, val_year) in LOCKED_FOLDS.items()
            },
            "allowed_row_level_years": [2016, 2017, 2018, 2019, 2020, 2021, 2022],
            "blocked_row_level_years": [2023, 2024],
            "row_level_2023_accessed": False,
            "row_level_2024_accessed": False,
        },
        "configs": {config_id: CONFIGS[config_id] for config_id in configs},
        "input_hashes": {
            "hpo_result": {_relative(HPO_XGB_RESULT): sha256_file(HPO_XGB_RESULT)},
            "hpo_protocol": {_relative(HPO_PROTOCOL): sha256_file(HPO_PROTOCOL)},
            "feature_manifests": {
                _relative(FEATURE_MANIFESTS[config["feature_set"]]): sha256_file(
                    FEATURE_MANIFESTS[config["feature_set"]]
                )
                for config in (CONFIGS[config_id] for config_id in configs)
            },
        },
        "fold_summary": fold_summary,
        "per_seed_results": rows,
        "execution_time_seconds": round(time.perf_counter() - started, 2),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "covid_fold": {
            "fold_id": "fold_2",
            "validation_year": 2020,
            "interpretation": "Reported separately; no 2023/2024 rows are needed for this diagnostic.",
        },
    }
    output = ROOT / "artifacts" / "manifests" / "phase_a_benchmark_mae_per_fold.json"
    with output.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, allow_nan=False)
    print(f"[+] Saved {output}")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Day 2 objective mismatch A/B benchmark")
    parser.add_argument("--config-id", choices=(*CONFIGS, "all"), default="all")
    parser.add_argument("--include-hgb", action="store_true")
    parser.add_argument("--per-fold", action="store_true")
    args = parser.parse_args()
    if args.per_fold:
        run_per_fold_diagnostic()
        return
    config_ids = list(CONFIGS) if args.config_id == "all" else [args.config_id]
    print(f"[*] Running Day 2 configs: {config_ids}")
    for config_id in config_ids:
        run_config(config_id, include_hgb=args.include_hgb)


if __name__ == "__main__":
    main()
