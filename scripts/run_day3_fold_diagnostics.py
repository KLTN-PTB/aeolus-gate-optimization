"""Day 3 fold, drift, baseline, and tail diagnostics.

The diagnostic deliberately re-runs the locked B2 protocol so the report has
fold-local baseline, model, severe-MAE, and shrinkage measurements rather than
inferring tail behavior from the Day 2 summary artifact.
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

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.preprocessing import build_v1_1_tree_preprocessor  # noqa: E402
from src.data.stratified_loader import load_stratified_fold_data  # noqa: E402
from src.models.baselines import NaiveDelayBaselines, compute_skill_score  # noqa: E402
from src.models.metrics import evaluate_all  # noqa: E402
from scripts.run_phase_a_benchmark_mae import (  # noqa: E402
    build_tuned_xgb_regressor,
)

SEEDS = [42, 43, 44, 45, 46]
SAMPLE_TRAIN_PER_YEAR = 25_000
SAMPLE_VAL = 25_000
LOCKED_FOLDS: dict[str, tuple[list[int], int]] = {
    "fold_1": ([2016, 2017, 2018], 2019),
    "fold_2": ([2016, 2017, 2018, 2019], 2020),
    "fold_3": ([2016, 2017, 2018, 2019, 2020], 2021),
    "fold_4": ([2016, 2017, 2018, 2019, 2020, 2021], 2022),
}
PSI_FEATURES = (
    "OP_CARRIER",
    "ORIGIN",
    "scheduled_departure_hour",
    "scheduled_arrival_hour",
    "calendar_month",
    "calendar_day_of_week",
)
TREND_WARNING_DROP_PP = 0.4

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


def _as_category(series: pd.Series) -> pd.Series:
    return series.astype("string").fillna("<NA>")


def population_stability_index(
    reference: pd.Series,
    current: pd.Series,
    *,
    epsilon: float = 1e-6,
) -> float:
    """Compute categorical PSI with a shared category universe."""

    reference_categories = _as_category(reference)
    current_categories = _as_category(current)
    categories = sorted(
        set(reference_categories.astype(str).unique())
        | set(current_categories.astype(str).unique())
    )
    if not categories or reference_categories.empty or current_categories.empty:
        raise ValueError("PSI requires non-empty reference and current series")

    ref_counts = reference_categories.astype(str).value_counts().reindex(categories, fill_value=0)
    cur_counts = current_categories.astype(str).value_counts().reindex(categories, fill_value=0)
    ref_pct = np.maximum(ref_counts.to_numpy(dtype=float) / len(reference_categories), epsilon)
    cur_pct = np.maximum(cur_counts.to_numpy(dtype=float) / len(current_categories), epsilon)
    return float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))


def _mae(errors: pd.Series) -> float | None:
    return float(errors.mean()) if not errors.empty else None


def summarize_carrier_hour_stability(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    *,
    sparse_threshold: int = 100,
) -> dict[str, Any]:
    """Measure train cell sparsity and validation MAE by cell-density class."""

    baseline = NaiveDelayBaselines().fit(X_train, y_train)
    train_carrier, train_hour = baseline._extract_carrier_and_hour(X_train)
    val_carrier, val_hour = baseline._extract_carrier_and_hour(X_val)
    train_keys = pd.Series(
        list(zip(train_carrier.astype(str), train_hour.astype(int))), index=X_train.index
    )
    val_keys = pd.Series(
        list(zip(val_carrier.astype(str), val_hour.astype(int))), index=X_val.index
    )
    counts = train_keys.value_counts()
    sparse_cells = set(counts[counts < sparse_threshold].index)
    known_cells = set(counts.index)

    predictions = baseline.predict_carrier_hour_median(X_val)
    errors = pd.Series(np.abs(y_val.to_numpy(dtype=float) - predictions), index=X_val.index)
    sparse_mask = val_keys.isin(sparse_cells)
    unseen_mask = ~val_keys.isin(known_cells)
    dense_mask = val_keys.isin(known_cells - sparse_cells)

    return {
        "sparse_threshold_rows": sparse_threshold,
        "train_cell_count": int(len(counts)),
        "sparse_train_cell_count": int(len(sparse_cells)),
        "dense_train_cell_count": int(len(known_cells - sparse_cells)),
        "train_sparse_cell_fraction": float(len(sparse_cells) / len(counts)) if len(counts) else 0.0,
        "validation_row_count": int(len(X_val)),
        "validation_sparse_row_count": int(sparse_mask.sum()),
        "validation_dense_row_count": int(dense_mask.sum()),
        "validation_unseen_row_count": int(unseen_mask.sum()),
        "validation_sparse_mae": _mae(errors[sparse_mask]),
        "validation_dense_mae": _mae(errors[dense_mask]),
        "validation_unseen_mae": _mae(errors[unseen_mask]),
        "validation_known_mae": _mae(errors[~unseen_mask]),
        "validation_overall_mae": _mae(errors),
    }


def _mean_std(values: Iterable[float | int | None]) -> dict[str, float | None]:
    clean = [float(value) for value in values if value is not None]
    if not clean:
        return {"mean": None, "std": None}
    return {"mean": float(np.mean(clean)), "std": float(np.std(clean))}


def classify_temporal_case(
    *,
    macro_skill: float,
    fold4_skill: float,
    skill_2021: float,
    skill_2022: float,
    max_psi: float,
) -> dict[str, Any]:
    """Classify the diagnostic result for the Day 3 execution gate.

    Case A: point gate passes and no material temporal/drift warning.
    Case B: point gate passes but temporal or feature-drift warning remains.
    Case C: point gate fails, so a new model-class run is not justified yet.
    """

    macro_positive = macro_skill > 0.0
    fold4_above_minus_1pp = fold4_skill >= -1.0
    trend_drop = float(skill_2022 - skill_2021)
    trend_warning = trend_drop <= -TREND_WARNING_DROP_PP
    drift_warning = max_psi > 0.25
    point_gate_passes = macro_positive and fold4_above_minus_1pp
    case = "C" if not point_gate_passes else ("B" if trend_warning or drift_warning else "A")
    return {
        "case": case,
        "macro_positive": macro_positive,
        "fold4_above_minus_1pp": fold4_above_minus_1pp,
        "skill_2021_to_2022_change_pp": trend_drop,
        "trend_warning": trend_warning,
        "trend_warning_threshold_pp": -TREND_WARNING_DROP_PP,
        "max_psi": float(max_psi),
        "drift_warning": drift_warning,
        "point_gate_passes": point_gate_passes,
        "registry_gate_passes": bool(point_gate_passes and not trend_warning),
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

    psi = {
        feature: population_stability_index(X_train[feature], X_val[feature])
        for feature in PSI_FEATURES
    }
    baseline = NaiveDelayBaselines().fit(X_train, y_train_reg)
    baseline_eval = evaluate_all(y_val_reg, baseline.predict_carrier_hour_median(X_val))
    baseline_mae = float(baseline_eval["point_regression"]["mae"])
    stability = summarize_carrier_hour_stability(X_train, y_train_reg, X_val, y_val_reg)

    tree_prep = build_v1_1_tree_preprocessor()
    X_train_encoded = tree_prep.fit_transform(X_train)
    X_val_encoded = tree_prep.transform(X_val)
    xgb = build_tuned_xgb_regressor("reg:absoluteerror", seed=seed)
    xgb.fit(X_train_encoded, y_train_reg.to_numpy(dtype=np.float64))
    xgb_eval = evaluate_all(y_val_reg, xgb.predict(X_val_encoded))
    xgb_mae = float(xgb_eval["point_regression"]["mae"])

    result = {
        "fold_id": fold_id,
        "validation_year": val_year,
        "seed": seed,
        "baseline_mae": baseline_mae,
        "xgboost_mae": xgb_mae,
        "xgboost_skill_score_vs_carrier_hour": compute_skill_score(xgb_mae, baseline_mae),
        "xgboost_severe_mae": xgb_eval["severe_conditioned"]["severe_mae"],
        "xgboost_shrinkage_ratio": xgb_eval["severe_conditioned"]["shrinkage_ratio"],
        "baseline_severe_mae": baseline_eval["severe_conditioned"]["severe_mae"],
        "baseline_shrinkage_ratio": baseline_eval["severe_conditioned"]["shrinkage_ratio"],
        "psi": psi,
        "baseline_stability": stability,
    }
    del X_train, X_val, X_train_encoded, X_val_encoded
    gc.collect()
    return result


def _aggregate_fold(rows: list[dict[str, Any]]) -> dict[str, Any]:
    psi_summary = {
        feature: {
            **_mean_std(row["psi"][feature] for row in rows),
            "per_seed": [float(row["psi"][feature]) for row in rows],
            "drift_class": (
                "large" if float(np.mean([row["psi"][feature] for row in rows])) > 0.25
                else "moderate" if float(np.mean([row["psi"][feature] for row in rows])) > 0.10
                else "small"
            ),
        }
        for feature in PSI_FEATURES
    }
    metric_names = (
        "baseline_mae",
        "xgboost_mae",
        "xgboost_skill_score_vs_carrier_hour",
        "xgboost_severe_mae",
        "xgboost_shrinkage_ratio",
        "baseline_severe_mae",
        "baseline_shrinkage_ratio",
    )
    metrics = {name: _mean_std(row[name] for row in rows) for name in metric_names}
    stability_names = (
        "train_cell_count",
        "sparse_train_cell_count",
        "dense_train_cell_count",
        "train_sparse_cell_fraction",
        "validation_sparse_row_count",
        "validation_dense_row_count",
        "validation_unseen_row_count",
        "validation_sparse_mae",
        "validation_dense_mae",
        "validation_unseen_mae",
        "validation_known_mae",
        "validation_overall_mae",
    )
    stability = {name: _mean_std(row["baseline_stability"][name] for row in rows) for name in stability_names}
    return {
        "validation_year": rows[0]["validation_year"],
        "seeds": [row["seed"] for row in rows],
        "metrics": metrics,
        "psi": psi_summary,
        "baseline_stability": stability,
        "per_seed": rows,
    }


def run_diagnostics() -> Path:
    started = time.perf_counter()
    fold_rows = {
        fold_id: [
            _run_fold_seed(fold_id, seed)
            for seed in SEEDS
        ]
        for fold_id in LOCKED_FOLDS
    }
    fold_summary = {fold_id: _aggregate_fold(rows) for fold_id, rows in fold_rows.items()}

    trend = []
    for fold_id in LOCKED_FOLDS:
        fold = fold_summary[fold_id]
        trend.append(
            {
                "fold_id": fold_id,
                "validation_year": fold["validation_year"],
                "skill_mean": fold["metrics"]["xgboost_skill_score_vs_carrier_hour"]["mean"],
                "baseline_mae_mean": fold["metrics"]["baseline_mae"]["mean"],
                "xgboost_mae_mean": fold["metrics"]["xgboost_mae"]["mean"],
                "max_psi": max(float(feature["mean"]) for feature in fold["psi"].values()),
            }
        )
    macro_skill = float(np.mean([row["skill_mean"] for row in trend]))
    fold4 = fold_summary["fold_4"]
    fold4_skill = float(fold4["metrics"]["xgboost_skill_score_vs_carrier_hour"]["mean"])
    max_fold4_psi = max(float(feature["mean"]) for feature in fold4["psi"].values())
    case = classify_temporal_case(
        macro_skill=macro_skill,
        fold4_skill=fold4_skill,
        skill_2021=float(trend[2]["skill_mean"]),
        skill_2022=float(trend[3]["skill_mean"]),
        max_psi=max_fold4_psi,
    )

    report = {
        "benchmark_version": "day3_fold_diagnostics_v1",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "purpose": "Diagnose 2019-2022 temporal degradation before changing model class",
        "protocol": {
            "feature_set": "v1.1",
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
        "inputs": {
            "feature_manifest": relative(FEATURE_MANIFEST),
            "feature_manifest_sha256": sha256_file(FEATURE_MANIFEST),
            "hpo_result_manifest": relative(HPO_RESULT),
            "hpo_result_manifest_sha256": sha256_file(HPO_RESULT),
            "hpo_protocol": relative(HPO_PROTOCOL),
            "hpo_protocol_sha256": sha256_file(HPO_PROTOCOL),
            "day2_per_fold_artifact": relative(DAY2_PER_FOLD),
            "day2_per_fold_artifact_sha256": sha256_file(DAY2_PER_FOLD),
        },
        "psi_features": list(PSI_FEATURES),
        "psi_thresholds": {"small_below": 0.10, "large_above": 0.25},
        "baseline_stability_definition": {
            "baseline": "carrier_hour_median fit on each fold's train side",
            "sparse_cell_threshold_rows": 100,
            "unseen_validation_cell_fallback": "carrier median then global median",
        },
        "fold_summary": fold_summary,
        "trend_2019_to_2022": trend,
        "macro_skill_4_fold": macro_skill,
        "fold4_skill": fold4_skill,
        "case_classification": case,
        "execution_time_seconds": round(time.perf_counter() - started, 2),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
    }
    output = ROOT / "artifacts" / "manifests" / "day3_fold_diagnostics_v1.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, allow_nan=False)
    print(f"[+] Saved {output}")
    print(f"[+] Case {case['case']}: macro={macro_skill:+.4f}% fold4={fold4_skill:+.4f}% max_psi={max_fold4_psi:.4f}")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Day 3 fold diagnostics")
    parser.parse_args()
    run_diagnostics()


if __name__ == "__main__":
    main()
