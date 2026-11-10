"""Day 3 LightGBM native-categorical benchmark.

This runner is independent from the Day 2 XGBoost runner. It keeps the
locked V1.1 data protocol, trains LightGBM with ``regression_l1`` and native
categoricals, and writes new versioned artifacts for Fold 4 and all four
rolling folds.
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

import lightgbm as lgb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.stratified_loader import load_stratified_fold_data  # noqa: E402
from src.models.baselines import NaiveDelayBaselines, compute_skill_score  # noqa: E402
from src.models.metrics import evaluate_all  # noqa: E402

SEEDS = [42, 43, 44, 45, 46]
SAMPLE_TRAIN_PER_YEAR = 25_000
SAMPLE_VAL = 25_000
FEATURE_SET = "v1.1"
LIGHTGBM_CATEGORICAL_FEATURES = (
    "OP_CARRIER",
    "ORIGIN",
    "OP_CARRIER_FL_NUM",
)
LOCKED_FOLDS: dict[str, tuple[list[int], int]] = {
    "fold_1": ([2016, 2017, 2018], 2019),
    "fold_2": ([2016, 2017, 2018, 2019], 2020),
    "fold_3": ([2016, 2017, 2018, 2019, 2020], 2021),
    "fold_4": ([2016, 2017, 2018, 2019, 2020, 2021], 2022),
}

FEATURE_MANIFEST = ROOT / "artifacts" / "manifests" / "feature_manifest_arrival_v1_1.json"
B2_ARTIFACT = ROOT / "artifacts" / "manifests" / "phase_a_benchmark_mae_b2.json"
B2_PER_FOLD_ARTIFACT = ROOT / "artifacts" / "manifests" / "phase_a_benchmark_mae_per_fold.json"
HPO_RESULT = ROOT / "artifacts" / "manifests" / (
    "week5_hpo_protocol_v1_1__xgboost_regression_result_v1.json"
)
HPO_PROTOCOL = ROOT / "configs" / "week5_hpo_v1_1.yaml"

LIGHTGBM_PARAM_TEMPLATE: dict[str, Any] = {
    "objective": "regression_l1",
    "metric": "mae",
    "num_leaves": 31,
    "learning_rate": 0.05,
    "n_estimators": 500,
    "min_data_in_leaf": 20,
    "n_jobs": 1,
    "verbosity": -1,
    "force_col_wise": True,
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT.resolve()))


def build_lightgbm_regressor(seed: int) -> lgb.LGBMRegressor:
    """Build the locked, untuned LightGBM L1 model for one seed."""

    return lgb.LGBMRegressor(
        **LIGHTGBM_PARAM_TEMPLATE,
        random_state=seed,
    )


def _category_dtype(series: pd.Series) -> pd.api.types.CategoricalDtype:
    if isinstance(series.dtype, pd.CategoricalDtype):
        categories = series.cat.categories
    else:
        categories = pd.Index(pd.unique(series.dropna()))
    return pd.api.types.CategoricalDtype(categories=categories, ordered=False)


def prepare_native_categorical_frames(
    X_train: pd.DataFrame,
    X_val: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Cast native categorical columns with identical train-derived dtypes.

    Validation-only category levels become missing categories rather than
    receiving a different integer code. No target or validation labels are
    used to construct the category vocabulary.
    """

    missing_train = [column for column in LIGHTGBM_CATEGORICAL_FEATURES if column not in X_train]
    missing_val = [column for column in LIGHTGBM_CATEGORICAL_FEATURES if column not in X_val]
    if missing_train or missing_val:
        raise KeyError(
            f"Missing LightGBM categorical columns: train={missing_train}, val={missing_val}"
        )

    train_out = X_train.copy()
    val_out = X_val.copy()
    for column in LIGHTGBM_CATEGORICAL_FEATURES:
        dtype = _category_dtype(train_out[column])
        train_out[column] = train_out[column].astype(dtype)
        val_out[column] = val_out[column].astype(dtype)
    return train_out, val_out


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


def run_single_benchmark(fold_id: str, seed: int) -> dict[str, Any]:
    train_years, val_year = LOCKED_FOLDS[fold_id]
    (
        X_train,
        _y_train_cls,
        y_train_reg,
        _train_years,
        X_val,
        _y_val_cls,
        y_val_reg,
        _val_keys,
    ) = load_stratified_fold_data(
        train_years=train_years,
        val_year=val_year,
        sample_train_per_year=SAMPLE_TRAIN_PER_YEAR,
        sample_val=SAMPLE_VAL,
        project_root=ROOT,
        random_state=seed,
        feature_set=FEATURE_SET,
    )

    baseline = NaiveDelayBaselines().fit(X_train, y_train_reg)
    baseline_eval = evaluate_all(y_val_reg, baseline.predict_carrier_hour_median(X_val))
    baseline_mae = float(baseline_eval["point_regression"]["mae"])

    X_train_lgbm, X_val_lgbm = prepare_native_categorical_frames(X_train, X_val)
    model = build_lightgbm_regressor(seed)
    model.fit(
        X_train_lgbm,
        y_train_reg.to_numpy(dtype=np.float64),
        categorical_feature=list(LIGHTGBM_CATEGORICAL_FEATURES),
    )
    lgbm_eval = evaluate_all(y_val_reg, model.predict(X_val_lgbm))
    metrics = _model_metrics(lgbm_eval, baseline_mae)
    print(
        f"[*] {fold_id} seed={seed} baseline_mae={baseline_mae:.4f} "
        f"lightgbm_mae={metrics['mae']:.4f} skill={metrics['skill_score_vs_carrier_hour']:+.4f}%"
    )

    result = {
        "fold_id": fold_id,
        "validation_year": val_year,
        "seed": seed,
        "train_years": train_years,
        "sample_train_per_year": SAMPLE_TRAIN_PER_YEAR,
        "sample_val": SAMPLE_VAL,
        "train_rows": int(len(X_train_lgbm)),
        "validation_rows": int(len(X_val_lgbm)),
        "baseline": {
            "mae": baseline_mae,
            "rmse": baseline_eval["point_regression"]["rmse"],
            "r2": baseline_eval["point_regression"]["r2"],
            "severe_mae": baseline_eval["severe_conditioned"]["severe_mae"],
            "shrinkage_ratio": baseline_eval["severe_conditioned"]["shrinkage_ratio"],
            "skill_score_vs_carrier_hour": 0.0,
        },
        "lightgbm": metrics,
    }
    del X_train, X_val, X_train_lgbm, X_val_lgbm
    gc.collect()
    return result


def _mean_std(values: Iterable[float | int | None]) -> dict[str, float | None]:
    clean = [float(value) for value in values if value is not None]
    if not clean:
        return {"mean": None, "std": None}
    return {"mean": float(np.mean(clean)), "std": float(np.std(clean))}


def _aggregate_fold(rows: list[dict[str, Any]]) -> dict[str, Any]:
    metric_names = (
        "mae",
        "rmse",
        "r2",
        "severe_mae",
        "shrinkage_ratio",
        "skill_score_vs_carrier_hour",
    )
    return {
        "validation_year": rows[0]["validation_year"],
        "seeds": [row["seed"] for row in rows],
        "baseline": {
            name: _mean_std(row["baseline"][name] for row in rows)
            for name in ("mae", "rmse", "r2", "severe_mae", "shrinkage_ratio")
        },
        "lightgbm": {
            name: _mean_std(row["lightgbm"][name] for row in rows)
            for name in metric_names
        },
        "per_seed": rows,
    }


def _load_b2_reference() -> dict[str, Any]:
    with B2_PER_FOLD_ARTIFACT.open("r", encoding="utf-8") as handle:
        artifact = json.load(handle)
    return artifact["fold_summary"]["b2"]


def _comparison(
    fold_summary: dict[str, dict[str, Any]],
    b2_reference: dict[str, Any],
) -> dict[str, Any]:
    comparison: dict[str, Any] = {}
    for fold_id in LOCKED_FOLDS:
        lgbm_skill = float(fold_summary[fold_id]["lightgbm"]["skill_score_vs_carrier_hour"]["mean"])
        b2_skill = float(b2_reference[fold_id]["skill_mean"])
        lgbm_mae = float(fold_summary[fold_id]["lightgbm"]["mae"]["mean"])
        b2_mae = float(b2_reference[fold_id]["mae_mean"])
        comparison[fold_id] = {
            "validation_year": b2_reference[fold_id]["validation_year"],
            "b2_xgboost": {"skill_mean": b2_skill, "mae_mean": b2_mae},
            "lightgbm": {"skill_mean": lgbm_skill, "mae_mean": lgbm_mae},
            "delta_lightgbm_minus_b2": {
                "skill_pp": lgbm_skill - b2_skill,
                "mae": lgbm_mae - b2_mae,
            },
        }
    return comparison


def _base_report(
    *,
    scope: str,
    fold_summary: dict[str, dict[str, Any]],
    comparison: dict[str, Any],
    execution_time_seconds: float,
) -> dict[str, Any]:
    fold_ids = list(LOCKED_FOLDS)
    macro_skill = float(
        np.mean([comparison[fold_id]["lightgbm"]["skill_mean"] for fold_id in fold_ids])
    )
    b2_macro_skill = float(
        np.mean([comparison[fold_id]["b2_xgboost"]["skill_mean"] for fold_id in fold_ids])
    )
    trend = [
        {
            "fold_id": fold_id,
            "validation_year": fold_summary[fold_id]["validation_year"],
            "lightgbm_skill_mean": comparison[fold_id]["lightgbm"]["skill_mean"],
            "b2_skill_mean": comparison[fold_id]["b2_xgboost"]["skill_mean"],
            "lightgbm_mae_mean": comparison[fold_id]["lightgbm"]["mae_mean"],
            "b2_mae_mean": comparison[fold_id]["b2_xgboost"]["mae_mean"],
        }
        for fold_id in fold_ids
    ]
    report = {
        "benchmark_version": "phase_a_day3_lightgbm_native_categorical_v1",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "scope": scope,
        "purpose": "Compare untuned LightGBM native categorical L1 against XGBoost B2",
        "config": {
            "model": "LightGBM LGBMRegressor",
            "feature_set": FEATURE_SET,
            "feature_manifest": relative(FEATURE_MANIFEST),
            "objective": "regression_l1",
            "metric": "mae",
            "categorical_features": list(LIGHTGBM_CATEGORICAL_FEATURES),
            "native_categorical": True,
            "params": {
                **LIGHTGBM_PARAM_TEMPLATE,
                "random_state": "per_seed",
            },
            "fit_params": {
                "categorical_feature": list(LIGHTGBM_CATEGORICAL_FEATURES),
            },
            "forbidden_feature_families_used": {
                "actual_operation": False,
                "weather": False,
                "flight_chain": False,
                "dest": False,
            },
        },
        "protocol": {
            "sample_train_per_year": SAMPLE_TRAIN_PER_YEAR,
            "sample_val": SAMPLE_VAL,
            "seeds": SEEDS,
            "folds": {
                fold_id: {"train_years": train_years, "validation_year": val_year}
                for fold_id, (train_years, val_year) in LOCKED_FOLDS.items()
            },
            "allowed_row_level_years": [2016, 2017, 2018, 2019, 2020, 2021, 2022],
            "blocked_row_level_years": [2023, 2024],
            "row_level_2023_accessed": False,
            "row_level_2024_accessed": False,
        },
        "input_hashes": {
            "feature_manifest": {relative(FEATURE_MANIFEST): sha256_file(FEATURE_MANIFEST)},
            "b2_fold4_artifact": {relative(B2_ARTIFACT): sha256_file(B2_ARTIFACT)},
            "b2_per_fold_artifact": {
                relative(B2_PER_FOLD_ARTIFACT): sha256_file(B2_PER_FOLD_ARTIFACT)
            },
            "hpo_result_reference": {relative(HPO_RESULT): sha256_file(HPO_RESULT)},
            "hpo_protocol_reference": {relative(HPO_PROTOCOL): sha256_file(HPO_PROTOCOL)},
        },
        "fold_summary": fold_summary,
        "comparison_to_b2": comparison,
        "trend_2019_to_2022": trend,
        "macro_4_fold": {
            "lightgbm_skill_mean": macro_skill,
            "b2_skill_mean": b2_macro_skill,
            "delta_lightgbm_minus_b2_pp": macro_skill - b2_macro_skill,
        },
        "execution_time_seconds": round(execution_time_seconds, 2),
    }
    return report


def _write_report(report: dict[str, Any], filename: str) -> Path:
    output = ROOT / "artifacts" / "manifests" / filename
    report["runner_sha256"] = sha256_file(Path(__file__).resolve())
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, allow_nan=False)
    print(f"[+] Saved {output}")
    return output


def run_benchmark(scope: str = "all") -> tuple[Path, ...]:
    if scope not in {"fold4", "all"}:
        raise ValueError("scope must be 'fold4' or 'all'")
    started = time.perf_counter()
    fold_ids = ["fold_4"] if scope == "fold4" else list(LOCKED_FOLDS)
    rows_by_fold = {
        fold_id: [run_single_benchmark(fold_id, seed) for seed in SEEDS]
        for fold_id in fold_ids
    }
    fold_summary = {fold_id: _aggregate_fold(rows) for fold_id, rows in rows_by_fold.items()}
    b2_reference = _load_b2_reference()
    comparison = _comparison(fold_summary, b2_reference)
    report = _base_report(
        scope=scope,
        fold_summary=fold_summary,
        comparison=comparison,
        execution_time_seconds=time.perf_counter() - started,
    )
    if scope == "fold4":
        report["macro_4_fold"] = None
        return (_write_report(report, "phase_a_benchmark_lightgbm_v1_1_fold4.json"),)
    fold4_report = dict(report)
    fold4_report["scope"] = "fold4"
    fold4_report["fold_summary"] = {"fold_4": fold_summary["fold_4"]}
    fold4_report["comparison_to_b2"] = {"fold_4": comparison["fold_4"]}
    fold4_report["trend_2019_to_2022"] = [row for row in report["trend_2019_to_2022"] if row["fold_id"] == "fold_4"]
    fold4_report["macro_4_fold"] = None
    return (
        _write_report(fold4_report, "phase_a_benchmark_lightgbm_v1_1_fold4.json"),
        _write_report(report, "phase_a_benchmark_lightgbm_v1_1_per_fold.json"),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Day 3 LightGBM benchmark")
    parser.add_argument("--scope", choices=("fold4", "all"), default="all")
    args = parser.parse_args()
    run_benchmark(args.scope)


if __name__ == "__main__":
    main()
