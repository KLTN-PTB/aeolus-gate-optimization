"""Day 3 XGBoost B2 carrier ablation.

This run removes only ``OP_CARRIER`` from the model matrix. The carrier-hour
baseline remains unchanged and is still fit from the original fold-local
features, so the ablation measures the model feature's contribution rather
than changing the reference baseline.
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

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.preprocessing import (  # noqa: E402
    _categorical_pipeline,
    _high_cardinality_pipeline,
    _numeric_pipeline,
)
from src.data.stratified_loader import load_stratified_fold_data  # noqa: E402
from src.features.tabular_features import (  # noqa: E402
    CATEGORICAL_FEATURE_COLUMNS,
    HIGH_CARDINALITY_FEATURE_COLUMNS,
    NUMERIC_FEATURE_COLUMNS_V1_1,
)
from src.models.baselines import NaiveDelayBaselines, compute_skill_score  # noqa: E402
from src.models.metrics import evaluate_all  # noqa: E402
from scripts.run_phase_a_benchmark_mae import (  # noqa: E402
    build_tuned_xgb_regressor,
)

SEEDS = [42, 43, 44, 45, 46]
SAMPLE_TRAIN_PER_YEAR = 25_000
SAMPLE_VAL = 25_000
ABLATION_FEATURES = ("OP_CARRIER",)
SIGNAL_THRESHOLD_PP = 0.1
LOCKED_FOLDS: dict[str, tuple[list[int], int]] = {
    "fold_1": ([2016, 2017, 2018], 2019),
    "fold_2": ([2016, 2017, 2018, 2019], 2020),
    "fold_3": ([2016, 2017, 2018, 2019, 2020], 2021),
    "fold_4": ([2016, 2017, 2018, 2019, 2020, 2021], 2022),
}

FEATURE_MANIFEST = ROOT / "artifacts" / "manifests" / "feature_manifest_arrival_v1_1.json"
HPO_RESULT = ROOT / "artifacts" / "manifests" / (
    "week5_hpo_protocol_v1_1__xgboost_regression_result_v1.json"
)
HPO_PROTOCOL = ROOT / "configs" / "week5_hpo_v1_1.yaml"
DAY2_PER_FOLD = ROOT / "artifacts" / "manifests" / "phase_a_benchmark_mae_per_fold.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT.resolve()))


def drop_model_features(X: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    """Return a copy with only the requested model features removed."""

    columns_to_drop = tuple(columns)
    missing = sorted(set(columns_to_drop).difference(X.columns))
    if missing:
        raise KeyError(f"Cannot ablate missing model feature columns: {missing}")
    return X.drop(columns=list(columns_to_drop)).copy()


def build_carrier_ablation_preprocessor() -> ColumnTransformer:
    """Build V1.1 preprocessing with OP_CARRIER excluded from the matrix."""

    categorical_columns = [
        column for column in CATEGORICAL_FEATURE_COLUMNS if column not in ABLATION_FEATURES
    ]
    return ColumnTransformer(
        [
            ("numeric", _numeric_pipeline(scale=False), list(NUMERIC_FEATURE_COLUMNS_V1_1)),
            ("categorical", _categorical_pipeline(one_hot=False), categorical_columns),
            ("high_cardinality", _high_cardinality_pipeline(), list(HIGH_CARDINALITY_FEATURE_COLUMNS)),
        ],
        remainder="drop",
        sparse_threshold=0.0,
        verbose_feature_names_out=True,
    )


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


def _run_fold_seed(fold_id: str, seed: int) -> dict[str, Any]:
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
        feature_set="v1.1",
    )

    baseline = NaiveDelayBaselines().fit(X_train, y_train_reg)
    baseline_eval = evaluate_all(y_val_reg, baseline.predict_carrier_hour_median(X_val))
    baseline_mae = float(baseline_eval["point_regression"]["mae"])

    X_train_ablation = drop_model_features(X_train, ABLATION_FEATURES)
    X_val_ablation = drop_model_features(X_val, ABLATION_FEATURES)
    preprocessor = build_carrier_ablation_preprocessor()
    X_train_encoded = preprocessor.fit_transform(X_train_ablation)
    X_val_encoded = preprocessor.transform(X_val_ablation)
    xgb = build_tuned_xgb_regressor("reg:absoluteerror", seed=seed)
    xgb.fit(X_train_encoded, y_train_reg.to_numpy(dtype=np.float64))
    ablation_eval = evaluate_all(y_val_reg, xgb.predict(X_val_encoded))
    metrics = _model_metrics(ablation_eval, baseline_mae)
    print(
        f"[*] {fold_id} seed={seed} baseline_mae={baseline_mae:.4f} "
        f"ablation_mae={metrics['mae']:.4f} skill={metrics['skill_score_vs_carrier_hour']:+.4f}%"
    )

    result = {
        "fold_id": fold_id,
        "validation_year": val_year,
        "seed": seed,
        "train_years": train_years,
        "sample_train_per_year": SAMPLE_TRAIN_PER_YEAR,
        "sample_val": SAMPLE_VAL,
        "baseline_mae": baseline_mae,
        "ablation": metrics,
    }
    del X_train, X_val, X_train_ablation, X_val_ablation, X_train_encoded, X_val_encoded
    gc.collect()
    return result


def _mean_std(values: Iterable[float | int | None]) -> dict[str, float | None]:
    clean = [float(value) for value in values if value is not None]
    if not clean:
        return {"mean": None, "std": None}
    return {"mean": float(np.mean(clean)), "std": float(np.std(clean))}


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    metric_names = (
        "baseline_mae",
        "mae",
        "rmse",
        "r2",
        "severe_mae",
        "shrinkage_ratio",
        "pr_auc_severe",
        "skill_score_vs_carrier_hour",
    )
    metrics: dict[str, dict[str, float | None]] = {
        "baseline_mae": _mean_std(row["baseline_mae"] for row in rows)
    }
    metrics.update(
        {
            name: _mean_std(row["ablation"][name] for row in rows)
            for name in metric_names
            if name != "baseline_mae"
        }
    )
    return {
        "validation_year": rows[0]["validation_year"],
        "seeds": [row["seed"] for row in rows],
        "metrics": metrics,
        "per_seed": rows,
    }


def _load_b2_reference() -> dict[str, Any]:
    with DAY2_PER_FOLD.open("r", encoding="utf-8") as handle:
        artifact = json.load(handle)
    return artifact["fold_summary"]["b2"]


def classify_carrier_effect(fold4_delta_pp: float, macro_delta_pp: float) -> dict[str, Any]:
    """Classify carrier effect using fold-4 and macro skill deltas."""

    if fold4_delta_pp >= SIGNAL_THRESHOLD_PP:
        conclusion = "carrier_harmful_under_drift"
    elif fold4_delta_pp <= -SIGNAL_THRESHOLD_PP:
        conclusion = "carrier_signal_is_useful"
    else:
        conclusion = "carrier_low_impact"
    return {
        "conclusion": conclusion,
        "fold4_skill_delta_pp": float(fold4_delta_pp),
        "macro_skill_delta_pp": float(macro_delta_pp),
        "signal_threshold_pp": SIGNAL_THRESHOLD_PP,
    }


def run_ablation() -> Path:
    started = time.perf_counter()
    rows_by_fold = {
        fold_id: [_run_fold_seed(fold_id, seed) for seed in SEEDS]
        for fold_id in LOCKED_FOLDS
    }
    fold_summary = {fold_id: _aggregate(rows) for fold_id, rows in rows_by_fold.items()}
    b2_reference = _load_b2_reference()

    comparison: dict[str, Any] = {}
    for fold_id in LOCKED_FOLDS:
        ablation_skill = float(fold_summary[fold_id]["metrics"]["skill_score_vs_carrier_hour"]["mean"])
        b2_skill = float(b2_reference[fold_id]["skill_mean"])
        ablation_mae = float(fold_summary[fold_id]["metrics"]["mae"]["mean"])
        b2_mae = float(b2_reference[fold_id]["mae_mean"])
        comparison[fold_id] = {
            "validation_year": b2_reference[fold_id]["validation_year"],
            "b2_reference": {
                "skill_mean": b2_skill,
                "mae_mean": b2_mae,
            },
            "carrier_ablation": {
                "skill_mean": ablation_skill,
                "mae_mean": ablation_mae,
            },
            "delta": {
                "skill_pp_ablation_minus_b2": ablation_skill - b2_skill,
                "mae_ablation_minus_b2": ablation_mae - b2_mae,
            },
        }

    macro_ablation = float(
        np.mean([comparison[fold_id]["carrier_ablation"]["skill_mean"] for fold_id in LOCKED_FOLDS])
    )
    macro_b2 = float(
        np.mean([comparison[fold_id]["b2_reference"]["skill_mean"] for fold_id in LOCKED_FOLDS])
    )
    fold4_delta = float(comparison["fold_4"]["delta"]["skill_pp_ablation_minus_b2"])
    effect = classify_carrier_effect(fold4_delta, macro_ablation - macro_b2)

    report = {
        "benchmark_version": "day3_carrier_ablation_v1",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "purpose": "Determine whether OP_CARRIER helps or harms B2 under temporal drift before LightGBM",
        "config": {
            "base_config": "b2",
            "feature_set": "v1.1",
            "ablated_model_features": list(ABLATION_FEATURES),
            "objective": "reg:absoluteerror",
            "eval_metric": "mae",
            "baseline_unchanged": True,
            "baseline": "carrier_hour_median fit on original fold-local X_train",
            "xgboost_parameters_source": relative(HPO_RESULT),
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
            "hpo_result": {relative(HPO_RESULT): sha256_file(HPO_RESULT)},
            "hpo_protocol": {relative(HPO_PROTOCOL): sha256_file(HPO_PROTOCOL)},
            "day2_per_fold": {relative(DAY2_PER_FOLD): sha256_file(DAY2_PER_FOLD)},
        },
        "fold_summary": fold_summary,
        "comparison_to_b2": comparison,
        "macro_skill": {
            "b2_reference": macro_b2,
            "carrier_ablation": macro_ablation,
            "delta_pp_ablation_minus_b2": macro_ablation - macro_b2,
        },
        "carrier_effect": effect,
        "execution_time_seconds": round(time.perf_counter() - started, 2),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
    }
    output = ROOT / "artifacts" / "manifests" / "day3_carrier_ablation_v1.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, allow_nan=False)
    print(f"[+] Saved {output}")
    print(
        f"[+] Carrier effect={effect['conclusion']} fold4_delta={fold4_delta:+.4f}pp "
        f"macro_delta={macro_ablation - macro_b2:+.4f}pp"
    )
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Day 3 OP_CARRIER ablation")
    parser.parse_args()
    run_ablation()


if __name__ == "__main__":
    main()

