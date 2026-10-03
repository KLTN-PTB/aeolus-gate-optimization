"""Day 3 LightGBM diagnostics after the native-categorical benchmark.

This runner intentionally creates new artifacts and does not modify the
default LightGBM runner or any Day 1/2/3 artifact.  Both diagnostics use the
locked 25K/year rolling protocol and seeds [42, 43, 44, 45, 46].

Diagnostic 1 compares LightGBM L1 using the exact V1.1 ordinal preprocessor
used by XGBoost B2 with the existing native-categorical LightGBM L1 result.
Diagnostic 2 compares a reduced-capacity LightGBM L2 model with XGBoost B2.
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

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_phase_a_benchmark_lightgbm import (  # noqa: E402
    LIGHTGBM_CATEGORICAL_FEATURES,
    prepare_native_categorical_frames,
)
from src.data.preprocessing import build_v1_1_tree_preprocessor  # noqa: E402
from src.data.stratified_loader import load_stratified_fold_data  # noqa: E402
from src.models.baselines import NaiveDelayBaselines, compute_skill_score  # noqa: E402
from src.models.metrics import evaluate_all  # noqa: E402


SEEDS = [42, 43, 44, 45, 46]
SAMPLE_TRAIN_PER_YEAR = 25_000
SAMPLE_VAL = 25_000
FEATURE_SET = "v1.1"
LOCKED_FOLDS: dict[str, tuple[list[int], int]] = {
    "fold_1": ([2016, 2017, 2018], 2019),
    "fold_2": ([2016, 2017, 2018, 2019], 2020),
    "fold_3": ([2016, 2017, 2018, 2019, 2020], 2021),
    "fold_4": ([2016, 2017, 2018, 2019, 2020, 2021], 2022),
}

FEATURE_MANIFEST = ROOT / "artifacts" / "manifests" / "feature_manifest_arrival_v1_1.json"
B2_PER_FOLD_ARTIFACT = ROOT / "artifacts" / "manifests" / "phase_a_benchmark_mae_per_fold.json"
DEFAULT_LGBM_ARTIFACT = (
    ROOT / "artifacts" / "manifests" / "phase_a_benchmark_lightgbm_v1_1_per_fold.json"
)
DEFAULT_LGBM_RUNNER = ROOT / "scripts" / "run_phase_a_benchmark_lightgbm.py"
HPO_RESULT = ROOT / "artifacts" / "manifests" / (
    "week5_hpo_protocol_v1_1__xgboost_regression_result_v1.json"
)
HPO_PROTOCOL = ROOT / "configs" / "week5_hpo_v1_1.yaml"

DEFAULT_L1_PARAMS: dict[str, Any] = {
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
REDUCED_L2_PARAMS: dict[str, Any] = {
    "objective": "regression",
    "metric": "mae",
    "num_leaves": 15,
    "learning_rate": 0.05,
    "n_estimators": 200,
    "min_data_in_leaf": 50,
    "lambda_l2": 1.0,
    "n_jobs": 1,
    "verbosity": -1,
    "force_col_wise": True,
}

DIAGNOSTIC_CONFIGS: dict[str, dict[str, Any]] = {
    "l1_ordinal": {
        "label": "LightGBM L1 ordinal V1.1",
        "mode": "ordinal",
        "params": DEFAULT_L1_PARAMS,
        "artifact": "day3_lightgbm_l1_ordinal_v1.json",
    },
    "l2_reduced_native": {
        "label": "LightGBM L2 reduced-capacity native categorical V1.1",
        "mode": "native",
        "params": REDUCED_L2_PARAMS,
        "artifact": "day3_lightgbm_l2_reduced_v1.json",
    },
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT.resolve()))


def diagnostic_mode(config_name: str) -> str:
    """Return the feature-matrix mode used by a diagnostic config."""
    try:
        return str(DIAGNOSTIC_CONFIGS[config_name]["mode"])
    except KeyError as error:
        raise ValueError(f"Unknown diagnostic config: {config_name}") from error


def build_diagnostic_regressor(config_name: str, *, seed: int) -> lgb.LGBMRegressor:
    """Build one diagnostic model with fully explicit, reproducible params."""
    try:
        config = DIAGNOSTIC_CONFIGS[config_name]
    except KeyError as error:
        raise ValueError(f"Unknown diagnostic config: {config_name}") from error
    return lgb.LGBMRegressor(
        **dict(config["params"]),
        random_state=seed,
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


def _prepare_model_frames(config_name: str, X_train: Any, X_val: Any) -> tuple[Any, Any, dict[str, Any]]:
    mode = diagnostic_mode(config_name)
    if mode == "ordinal":
        preprocessor = build_v1_1_tree_preprocessor()
        return (
            preprocessor.fit_transform(X_train),
            preprocessor.transform(X_val),
            {
                "mode": "ordinal",
                "preprocessor": "build_v1_1_tree_preprocessor",
                "categorical_features": [],
                "native_categorical": False,
            },
        )
    if mode == "native":
        train_frame, val_frame = prepare_native_categorical_frames(X_train, X_val)
        return (
            train_frame,
            val_frame,
            {
                "mode": "native",
                "preprocessor": "prepare_native_categorical_frames",
                "categorical_features": list(LIGHTGBM_CATEGORICAL_FEATURES),
                "native_categorical": True,
            },
        )
    raise ValueError(f"Unsupported diagnostic mode: {mode}")


def run_single_diagnostic(fold_id: str, seed: int, config_name: str) -> dict[str, Any]:
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

    X_train_model, X_val_model, matrix_info = _prepare_model_frames(config_name, X_train, X_val)
    model = build_diagnostic_regressor(config_name, seed=seed)
    fit_kwargs: dict[str, Any] = {}
    if matrix_info["native_categorical"]:
        fit_kwargs["categorical_feature"] = matrix_info["categorical_features"]
    model.fit(
        X_train_model,
        y_train_reg.to_numpy(dtype=np.float64),
        **fit_kwargs,
    )
    evaluation = evaluate_all(y_val_reg, model.predict(X_val_model))
    metrics = _model_metrics(evaluation, baseline_mae)
    print(
        f"[*] {config_name} {fold_id} seed={seed} baseline_mae={baseline_mae:.4f} "
        f"model_mae={metrics['mae']:.4f} skill={metrics['skill_score_vs_carrier_hour']:+.4f}%"
    )

    result = {
        "config_name": config_name,
        "fold_id": fold_id,
        "validation_year": val_year,
        "seed": seed,
        "train_years": train_years,
        "sample_train_per_year": SAMPLE_TRAIN_PER_YEAR,
        "sample_val": SAMPLE_VAL,
        "train_rows": int(len(X_train_model)),
        "validation_rows": int(len(X_val_model)),
        "matrix": matrix_info,
        "baseline": {
            "mae": baseline_mae,
            "rmse": baseline_eval["point_regression"]["rmse"],
            "r2": baseline_eval["point_regression"]["r2"],
            "severe_mae": baseline_eval["severe_conditioned"]["severe_mae"],
            "shrinkage_ratio": baseline_eval["severe_conditioned"]["shrinkage_ratio"],
            "skill_score_vs_carrier_hour": 0.0,
        },
        "model": metrics,
    }
    del X_train, X_val, X_train_model, X_val_model
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
        "model": {
            name: _mean_std(row["model"][name] for row in rows)
            for name in metric_names
        },
        "per_seed": rows,
    }


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _reference_row(reference: dict[str, Any], fold_id: str, *, model_key: str) -> dict[str, float]:
    if model_key == "b2":
        row = reference["fold_summary"][model_key][fold_id]
        return {
            "skill_mean": float(row["skill_mean"]),
            "mae_mean": float(row["mae_mean"]),
        }
    row = reference["fold_summary"][fold_id]
    return {
        "skill_mean": float(row["lightgbm"]["skill_score_vs_carrier_hour"]["mean"]),
        "mae_mean": float(row["lightgbm"]["mae"]["mean"]),
    }


def _comparison(
    fold_summary: dict[str, dict[str, Any]],
    reference: dict[str, Any],
    *,
    reference_model_key: str,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for fold_id in LOCKED_FOLDS:
        model_skill = float(fold_summary[fold_id]["model"]["skill_score_vs_carrier_hour"]["mean"])
        model_mae = float(fold_summary[fold_id]["model"]["mae"]["mean"])
        ref = _reference_row(reference, fold_id, model_key=reference_model_key)
        result[fold_id] = {
            "validation_year": fold_summary[fold_id]["validation_year"],
            "reference": ref,
            "diagnostic_model": {"skill_mean": model_skill, "mae_mean": model_mae},
            "delta_diagnostic_minus_reference": {
                "skill_pp": model_skill - ref["skill_mean"],
                "mae": model_mae - ref["mae_mean"],
            },
        }
    return result


def _macro(comparison: dict[str, Any]) -> dict[str, float]:
    model_skill = float(np.mean([row["diagnostic_model"]["skill_mean"] for row in comparison.values()]))
    reference_skill = float(np.mean([row["reference"]["skill_mean"] for row in comparison.values()]))
    model_mae = float(np.mean([row["diagnostic_model"]["mae_mean"] for row in comparison.values()]))
    reference_mae = float(np.mean([row["reference"]["mae_mean"] for row in comparison.values()]))
    return {
        "diagnostic_skill_mean": model_skill,
        "reference_skill_mean": reference_skill,
        "delta_skill_pp": model_skill - reference_skill,
        "diagnostic_mae_mean": model_mae,
        "reference_mae_mean": reference_mae,
        "delta_mae": model_mae - reference_mae,
    }


def _comparison_interpretation(
    comparison_to_b2: dict[str, Any],
    comparison_to_native: dict[str, Any],
    *,
    config_name: str,
) -> dict[str, Any]:
    """Make the diagnostic labels auditable with explicit pp thresholds."""
    near_pp = 0.10
    clear_pp = 0.30

    def deltas(comparison: dict[str, Any]) -> tuple[float, float]:
        return (
            float(comparison["fold_4"]["delta_diagnostic_minus_reference"]["skill_pp"]),
            float(_macro(comparison)["delta_skill_pp"]),
        )

    fold4_native, macro_native = deltas(comparison_to_native)
    fold4_b2, macro_b2 = deltas(comparison_to_b2)
    native_abs_near = abs(fold4_native) <= near_pp and abs(macro_native) <= near_pp
    native_clear_better = fold4_native >= clear_pp and macro_native >= clear_pp
    native_clear_worse = fold4_native <= -clear_pp and macro_native <= -clear_pp
    if config_name == "l1_ordinal":
        if native_abs_near:
            native_conclusion = "l1_ordinal_approximately_equals_native_l1"
        elif native_clear_better:
            native_conclusion = "native_categorical_harmful"
        elif native_clear_worse:
            native_conclusion = "ordinal_encoding_harmful"
        else:
            native_conclusion = "mixed_or_small_difference"
    else:
        if native_abs_near:
            native_conclusion = "reduced_l2_approximately_equals_default_native_l1"
        elif native_clear_better:
            native_conclusion = "reduced_l2_better_than_default_native_l1"
        elif native_clear_worse:
            native_conclusion = "reduced_l2_worse_than_default_native_l1"
        else:
            native_conclusion = "mixed_or_small_difference"

    if abs(fold4_b2) <= near_pp and abs(macro_b2) <= near_pp:
        b2_conclusion = "lightgbm_approximately_equals_b2_params_are_primary_lever"
    elif fold4_b2 <= -clear_pp and macro_b2 <= -clear_pp:
        b2_conclusion = "lightgbm_still_worse_than_b2"
    else:
        b2_conclusion = "lightgbm_difference_from_b2_is_mixed_or_small"

    capacity_conclusion = None
    if config_name == "l2_reduced_native":
        if abs(fold4_b2) <= near_pp and abs(macro_b2) <= near_pp:
            capacity_conclusion = "capacity_overfitting_supported"
        elif fold4_b2 <= -near_pp and macro_b2 <= -near_pp:
            capacity_conclusion = "lightgbm_still_worse_after_capacity_reduction"
        else:
            capacity_conclusion = "capacity_effect_mixed_or_small"
    return {
        "thresholds": {
            "near_equal_abs_skill_pp": near_pp,
            "clear_difference_abs_skill_pp": clear_pp,
            "comparison_basis": "both Fold 4 and macro must meet a threshold for a strong label",
        },
        "vs_default_native_l1": {
            "fold4_delta_skill_pp": fold4_native,
            "macro_delta_skill_pp": macro_native,
            "conclusion": native_conclusion,
        },
        "vs_b2": {
            "fold4_delta_skill_pp": fold4_b2,
            "macro_delta_skill_pp": macro_b2,
            "conclusion": b2_conclusion,
        },
        "capacity_diagnostic": capacity_conclusion,
    }


def _base_report(
    config_name: str,
    fold_summary: dict[str, dict[str, Any]],
    comparison_to_b2: dict[str, Any],
    comparison_to_native: dict[str, Any],
    execution_time_seconds: float,
) -> dict[str, Any]:
    config = DIAGNOSTIC_CONFIGS[config_name]
    b2_macro = _macro(comparison_to_b2)
    native_macro = _macro(comparison_to_native)
    trend = [
        {
            "fold_id": fold_id,
            "validation_year": fold_summary[fold_id]["validation_year"],
            "diagnostic_skill_mean": comparison_to_b2[fold_id]["diagnostic_model"]["skill_mean"],
            "b2_skill_mean": comparison_to_b2[fold_id]["reference"]["skill_mean"],
            "default_native_l1_skill_mean": comparison_to_native[fold_id]["reference"]["skill_mean"],
            "diagnostic_mae_mean": comparison_to_b2[fold_id]["diagnostic_model"]["mae_mean"],
        }
        for fold_id in LOCKED_FOLDS
    ]
    return {
        "benchmark_version": "phase_a_day3_lightgbm_diagnostics_v1",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "diagnostic": config_name,
        "purpose": config["label"],
        "config": {
            "model": "LightGBM LGBMRegressor",
            "feature_set": FEATURE_SET,
            "feature_manifest": relative(FEATURE_MANIFEST),
            "mode": config["mode"],
            "objective": config["params"]["objective"],
            "metric": config["params"]["metric"],
            "categorical_features": list(LIGHTGBM_CATEGORICAL_FEATURES)
            if config["mode"] == "native"
            else [],
            "native_categorical": config["mode"] == "native",
            "preprocessor": (
                "prepare_native_categorical_frames"
                if config["mode"] == "native"
                else "build_v1_1_tree_preprocessor"
            ),
            "params": {**config["params"], "random_state": "per_seed"},
            "fit_params": (
                {"categorical_feature": list(LIGHTGBM_CATEGORICAL_FEATURES)}
                if config["mode"] == "native"
                else {}
            ),
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
            "b2_per_fold_artifact": {
                relative(B2_PER_FOLD_ARTIFACT): sha256_file(B2_PER_FOLD_ARTIFACT)
            },
            "default_native_l1_artifact": {
                relative(DEFAULT_LGBM_ARTIFACT): sha256_file(DEFAULT_LGBM_ARTIFACT)
            },
            "default_lightgbm_runner": {
                relative(DEFAULT_LGBM_RUNNER): sha256_file(DEFAULT_LGBM_RUNNER)
            },
            "hpo_result_reference": {relative(HPO_RESULT): sha256_file(HPO_RESULT)},
            "hpo_protocol_reference": {relative(HPO_PROTOCOL): sha256_file(HPO_PROTOCOL)},
        },
        "fold_summary": fold_summary,
        "comparison_to_b2": comparison_to_b2,
        "comparison_to_default_native_l1": comparison_to_native,
        "macro_4_fold_vs_b2": b2_macro,
        "macro_4_fold_vs_default_native_l1": native_macro,
        "trend_2019_to_2022": trend,
        "interpretation": _comparison_interpretation(
            comparison_to_b2,
            comparison_to_native,
            config_name=config_name,
        ),
        "execution_time_seconds": round(execution_time_seconds, 2),
    }


def run_diagnostic(config_name: str) -> Path:
    if config_name not in DIAGNOSTIC_CONFIGS:
        raise ValueError(f"Unknown diagnostic config: {config_name}")
    started = time.perf_counter()
    rows_by_fold = {
        fold_id: [run_single_diagnostic(fold_id, seed, config_name) for seed in SEEDS]
        for fold_id in LOCKED_FOLDS
    }
    fold_summary = {fold_id: _aggregate_fold(rows) for fold_id, rows in rows_by_fold.items()}
    b2_reference = _load_json(B2_PER_FOLD_ARTIFACT)
    native_reference = _load_json(DEFAULT_LGBM_ARTIFACT)
    comparison_to_b2 = _comparison(
        fold_summary,
        b2_reference,
        reference_model_key="b2",
    )
    comparison_to_native = _comparison(
        fold_summary,
        native_reference,
        reference_model_key="lightgbm",
    )
    report = _base_report(
        config_name,
        fold_summary,
        comparison_to_b2,
        comparison_to_native,
        time.perf_counter() - started,
    )
    report["runner_sha256"] = sha256_file(Path(__file__).resolve())
    output = ROOT / "artifacts" / "manifests" / DIAGNOSTIC_CONFIGS[config_name]["artifact"]
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, allow_nan=False)
    print(f"[+] Saved {output}")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Day 3 LightGBM diagnostics")
    parser.add_argument(
        "--config",
        choices=("all", *DIAGNOSTIC_CONFIGS.keys()),
        default="all",
    )
    args = parser.parse_args()
    configs = list(DIAGNOSTIC_CONFIGS) if args.config == "all" else [args.config]
    for config_name in configs:
        run_diagnostic(config_name)


if __name__ == "__main__":
    main()
