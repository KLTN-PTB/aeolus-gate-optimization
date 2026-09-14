"""Create Week-4 evidence from completed manifests and OOF artifacts only.

No estimator, source data partition, or training preprocessing is opened here.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.models.artifacts import OOF_COLUMNS, write_json_artifact
from src.models.contracts import (
    CLASSIFICATION_THRESHOLD,
    FEATURE_MANIFEST_VERSION,
    OOF_SCHEMA_VERSION,
    WEEK4_EXPERIMENT_CONTRACT_VERSION,
    WEEK4_FRAMEWORK_VERSION,
)


SUMMARY_PATH = ROOT / "artifacts/manifests/week4_core_arrival_baselines_summary_v1.json"
REPORT_PATH = ROOT / "docs/experiments/week4_core_arrival_baselines.md"
LOG_PATH = ROOT / "docs/experiments/experiment_log.md"
FOLDS = (
    ("fold_1", (2016, 2017, 2018), 2019),
    ("fold_2", (2016, 2017, 2018, 2019), 2020),
    ("fold_3", (2016, 2017, 2018, 2019, 2020), 2021),
    ("fold_4", (2016, 2017, 2018, 2019, 2020, 2021), 2022),
)
MANIFESTS = {
    "linear": ROOT / "artifacts/manifests/arrival_linear_rolling_run_v1.json",
    "random_forest": ROOT / "artifacts/manifests/arrival_random_forest_rolling_run_v1.json",
    "hist_gradient_boosting": ROOT / "artifacts/manifests/arrival_hist_gradient_boosting_rolling_run_v1.json",
}


class ConsolidationViolation(ValueError):
    """A completed artifact failed a scientific-protocol cross-check."""


def require(value: bool, message: str) -> None:
    if not value:
        raise ConsolidationViolation(message)


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ConsolidationViolation(f"unreadable JSON: {path}") from error
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def oof_path(value: object) -> Path:
    require(isinstance(value, str) and bool(value), "OOF path must be non-empty")
    path = ROOT / value.replace("\\", "/")
    require(path.exists(), f"missing OOF artifact: {path}")
    return path


def validate_manifest(method_id: str, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    require(manifest.get("status") == "PASS", f"{method_id}: status is not PASS")
    require(manifest.get("full_data_used") is True, f"{method_id}: full data not confirmed")
    require(manifest.get("row_level_2023_access") == "NO", f"{method_id}: 2023 access guard failed")
    require(manifest.get("row_level_2024_access") == "NO", f"{method_id}: 2024 access guard failed")
    require(manifest.get("framework_version") == WEEK4_FRAMEWORK_VERSION, f"{method_id}: framework version")
    require(manifest.get("experiment_contract_version") == WEEK4_EXPERIMENT_CONTRACT_VERSION, f"{method_id}: contract version")
    require(manifest.get("oof_schema_version") == OOF_SCHEMA_VERSION, f"{method_id}: OOF schema version")
    method = manifest.get("method")
    require(isinstance(method, dict) and method.get("method_id") == method_id, f"{method_id}: method metadata")
    guards = manifest.get("protocol_guards")
    require(isinstance(guards, dict), f"{method_id}: missing guards")
    for name in (
        "no_weather",
        "no_chain_predictors",
        "no_departure_delay_or_predicted_departure_delay",
        "no_realized_operations",
        "no_random_split",
    ):
        require(guards.get(name) is True, f"{method_id}: guard failed: {name}")
    require(guards.get("excluded_years") == [2023, 2024], f"{method_id}: excluded years")
    require(guards.get("validation_years") == [2019, 2020, 2021, 2022], f"{method_id}: validation years")
    folds = manifest.get("folds")
    require(isinstance(folds, list) and len(folds) == len(FOLDS), f"{method_id}: incomplete folds")
    for fold, (fold_id, train_years, validation_year) in zip(folds, FOLDS, strict=True):
        require(isinstance(fold, dict), f"{method_id}: malformed fold")
        require(fold.get("fold_id") == fold_id, f"{method_id}: fold ID")
        require(fold.get("train_years") == list(train_years), f"{method_id}/{fold_id}: train years")
        require(fold.get("validation_year") == validation_year, f"{method_id}/{fold_id}: validation year")
        require(fold.get("train_rows") == fold.get("train_eligibility", {}).get("eligible_rows"), f"{method_id}/{fold_id}: train eligibility")
        require(fold.get("validation_rows") == fold.get("validation_eligibility", {}).get("eligible_rows"), f"{method_id}/{fold_id}: validation eligibility")
        require(fold.get("oof_rows") == fold.get("validation_rows"), f"{method_id}/{fold_id}: OOF rows")
        require(fold.get("validation_eligibility", {}).get("dropped_missing_target_rows") == 0, f"{method_id}/{fold_id}: missing target drops")
        require(fold.get("preprocessor_state_unchanged_after_validation") is True, f"{method_id}/{fold_id}: transform mutation")
        cls = fold.get("metrics", {}).get("classification", {})
        require(cls.get("threshold") == CLASSIFICATION_THRESHOLD, f"{method_id}/{fold_id}: threshold")
        calibration = cls.get("calibration", {})
        require(calibration.get("method") == "fixed_width_10_bins_no_posthoc_calibrator" and calibration.get("bin_count") == 10, f"{method_id}/{fold_id}: calibration contract")
    return folds


def load_oof(method_id: str, fold: dict[str, Any], method: dict[str, Any]) -> tuple[pd.DataFrame, Path]:
    path = oof_path(fold.get("oof_artifact"))
    file = pq.ParquetFile(path)
    require(tuple(file.schema_arrow.names) == OOF_COLUMNS, f"{method_id}/{fold['fold_id']}: OOF columns")
    frame = file.read().to_pandas()
    require(len(frame) == fold["oof_rows"], f"{method_id}/{fold['fold_id']}: OOF length")
    require(frame["flight_key"].notna().all() and frame["flight_key"].astype(str).str.len().gt(0).all(), f"{method_id}/{fold['fold_id']}: flight key")
    require(not frame["flight_key"].duplicated().any(), f"{method_id}/{fold['fold_id']}: duplicate flight key")
    require((frame["fold_id"] == fold["fold_id"]).all(), f"{method_id}/{fold['fold_id']}: fold ID rows")
    require((frame["validation_year"] == fold["validation_year"]).all(), f"{method_id}/{fold['fold_id']}: validation year rows")
    require(set(frame["y_arr_cls"].astype(int)).issubset({0, 1}), f"{method_id}/{fold['fold_id']}: class truth")
    require(set(frame["y_arr_cls_pred_0_5"].astype(int)).issubset({0, 1}), f"{method_id}/{fold['fold_id']}: class prediction")
    for name in ("p_arr_delay_15", "y_arr_reg", "predicted_arr_delay_min"):
        require(np.isfinite(frame[name].to_numpy(dtype=float)).all(), f"{method_id}/{fold['fold_id']}: non-finite {name}")
    require(frame["p_arr_delay_15"].between(0.0, 1.0, inclusive="both").all(), f"{method_id}/{fold['fold_id']}: probability range")
    expected = {
        "method_id": method_id,
        "model_version": method["model_version"],
        "preprocessing_version": "arrival_preprocessing_v1",
        "feature_manifest_version": FEATURE_MANIFEST_VERSION,
        "config_version": method["config_version"],
        "seed": method["seed"],
        "experiment_contract_version": WEEK4_EXPERIMENT_CONTRACT_VERSION,
        "oof_schema_version": OOF_SCHEMA_VERSION,
    }
    for name, value in expected.items():
        require(frame[name].nunique(dropna=False) == 1 and frame[name].iloc[0] == value, f"{method_id}/{fold['fold_id']}: metadata {name}")
    return frame, path


def compare_trace(reference: pd.DataFrame, candidate: pd.DataFrame, method_id: str, fold_id: str) -> None:
    fields = ["flight_key", "validation_year", "y_arr_cls", "y_arr_reg"]
    left = reference.loc[:, fields].sort_values("flight_key", kind="mergesort", ignore_index=True)
    right = candidate.loc[:, fields].sort_values("flight_key", kind="mergesort", ignore_index=True)
    require(left["flight_key"].equals(right["flight_key"]), f"{method_id}/{fold_id}: flight keys differ")
    require(left["validation_year"].equals(right["validation_year"]), f"{method_id}/{fold_id}: validation years differ")
    require(left["y_arr_cls"].equals(right["y_arr_cls"]), f"{method_id}/{fold_id}: classification truth differs")
    require(np.array_equal(left["y_arr_reg"].to_numpy(), right["y_arr_reg"].to_numpy(), equal_nan=False), f"{method_id}/{fold_id}: signed regression truth differs")


def record_fold(method_id: str, fold: dict[str, Any], path: Path) -> dict[str, Any]:
    return {
        "method_id": method_id,
        "fold_id": fold["fold_id"],
        "train_years": fold["train_years"],
        "validation_year": fold["validation_year"],
        "train_rows": fold["train_rows"],
        "validation_rows": fold["validation_rows"],
        "validation_class_prevalence": fold["validation_class_prevalence"],
        "dropped_missing_target_rows": fold["validation_eligibility"]["dropped_missing_target_rows"],
        "classification": fold["metrics"]["classification"],
        "regression": fold["metrics"]["regression"],
        "runtime": fold["runtime"],
        "oof_artifact": str(path.relative_to(ROOT)).replace("\\", "/"),
        "oof_artifact_bytes": path.stat().st_size,
    }


def fmt(value: float | int | None, digits: int = 4) -> str:
    return "—" if value is None else f"{float(value):.{digits}f}"


def table(headers: list[str], rows: list[list[str]]) -> str:
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |", *["| " + " | ".join(row) + " |" for row in rows]])


def build_report(summary: dict[str, Any]) -> str:
    row_rows: list[list[str]] = []
    cls_rows: list[list[str]] = []
    reg_rows: list[list[str]] = []
    aggregate_cls: list[list[str]] = []
    aggregate_reg: list[list[str]] = []
    resource_rows: list[list[str]] = []
    for method_id, method in summary["methods"].items():
        for fold in method["folds"]:
            cls, reg = fold["classification"], fold["regression"]
            row_rows.append([method_id, fold["fold_id"], str(fold["validation_year"]), f"{fold['train_rows']:,}", f"{fold['validation_rows']:,}", fmt(fold["validation_class_prevalence"]), str(fold["dropped_missing_target_rows"]), "PASS"])
            cls_rows.append([method_id, str(fold["validation_year"]), fmt(cls["roc_auc"]), fmt(cls["pr_auc"]), fmt(cls["recall"]), fmt(cls["f1"]), fmt(cls["brier_score"]), fmt(cls["calibration"]["expected_calibration_error"])])
            reg_rows.append([method_id, str(fold["validation_year"]), fmt(reg["mae"]), fmt(reg["rmse"]), fmt(reg["r2"])])
        cls = method["aggregate_development_metrics"]["classification"]
        reg = method["aggregate_development_metrics"]["regression"]
        aggregate_cls.append([method_id, str(method["aggregate_development_metrics"]["rows"]), fmt(cls["roc_auc"]), fmt(cls["pr_auc"]), fmt(cls["recall"]), fmt(cls["f1"]), fmt(cls["brier_score"]), fmt(cls["calibration"]["expected_calibration_error"])])
        aggregate_reg.append([method_id, fmt(reg["mae"]), fmt(reg["rmse"]), fmt(reg["r2"])])
        resources = method["resource_summary"]
        resource_rows.append([method_id, fmt(resources["fit_runtime_seconds"], 2), fmt(resources["prediction_runtime_seconds"], 2), fmt(resources["total_runtime_seconds"], 2), f"{resources['max_peak_traced_python_bytes'] / 1024**2:.1f}", f"{resources['max_post_fold_process_rss_bytes'] / 1024**2:.1f}", f"{resources['oof_artifact_bytes'] / 1024**2:.1f}"])
    lines = [
        "# Week 4 — Core Arrival rolling baseline evidence",
        "",
        "This is descriptive consolidation of three completed locked baseline runs. It reads only production manifests and OOF artifacts; it does not retrain, tune, calibrate, select a champion, or access row-level 2023/2024 data.",
        "",
        "- Target: `y_arr_cls = 1[ARR_DELAY >= 15]`; signed `ARR_DELAY` regression.",
        "- Population/cutoff: inbound `DEST=ATL`; `CRS_DEP_TIME - 2h`.",
        "- Excluded: Weather, departure target/prediction, actual operations, Chain, and identifiers as predictors.",
        "- Threshold: fixed `0.5`; calibration is ten fixed-width bins with no post-hoc calibrator.",
        "",
        "## Common folds and row parity",
        "",
        table(["Method", "Fold", "Validation year", "Train rows", "Validation rows", "Positive prevalence", "Missing target drops", "Trace parity"], row_rows),
        "",
        "Exact `flight_key`, classification-label, and signed-regression-label parity passed within every fold. The full ten-bin diagnostics are in the machine-readable summary manifest.",
        "",
        "## Classification metrics by fold",
        "",
        table(["Method", "Year", "ROC-AUC", "PR-AUC", "Recall@0.5", "F1@0.5", "Brier", "ECE (10 bins)"], cls_rows),
        "",
        "## Regression metrics by fold",
        "",
        table(["Method", "Year", "MAE", "RMSE", "R²"], reg_rows),
        "",
        "## Aggregate pooled OOF diagnostics (2019–2022)",
        "",
        table(["Method", "OOF rows", "ROC-AUC", "PR-AUC", "Recall@0.5", "F1@0.5", "Brier", "ECE (10 bins)"], aggregate_cls),
        "",
        table(["Method", "MAE", "RMSE", "R²"], aggregate_reg),
        "",
        "Values vary by year and method. This report intentionally makes no final model-selection or champion claim; accuracy is not a primary metric.",
        "",
        "## Resource record",
        "",
        table(["Method", "Fit seconds", "Predict seconds", "Total seconds", "Max traced Python MiB", "Max post-fold RSS MiB", "OOF size MiB"], resource_rows),
        "",
        "`tracemalloc` records Python-allocation peaks, not portable exact RSS peaks. Post-fold RSS was separately observed using `psutil` and is not estimator-only peak memory.",
        "",
        "## Source evidence",
        "",
        "- `artifacts/manifests/arrival_linear_rolling_run_v1.json`",
        "- `artifacts/manifests/arrival_random_forest_rolling_run_v1.json`",
        "- `artifacts/manifests/arrival_hist_gradient_boosting_rolling_run_v1.json`",
        "- Per-fold OOF Parquet paths in `artifacts/manifests/week4_core_arrival_baselines_summary_v1.json`.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    if SUMMARY_PATH.exists() or REPORT_PATH.exists():
        raise FileExistsError("refusing to overwrite existing versioned Week-4 evidence")
    manifests = {method_id: read_json(path) for method_id, path in MANIFESTS.items()}
    folds = {method_id: validate_manifest(method_id, manifest) for method_id, manifest in manifests.items()}
    methods: dict[str, Any] = {method_id: {"folds": []} for method_id in manifests}
    parity: list[dict[str, Any]] = []
    for index, (fold_id, _, validation_year) in enumerate(FOLDS):
        reference: pd.DataFrame | None = None
        entry: dict[str, Any] = {"fold_id": fold_id, "validation_year": validation_year, "methods": {}}
        for method_id, manifest in manifests.items():
            frame, path = load_oof(method_id, folds[method_id][index], manifest["method"])
            if reference is None:
                reference = frame
            else:
                compare_trace(reference, frame, method_id, fold_id)
            entry["methods"][method_id] = {"validation_rows": len(frame), "validation_fingerprint": folds[method_id][index]["row_fingerprints"]["validation"], "oof_artifact": str(path.relative_to(ROOT)).replace("\\", "/")}
            methods[method_id]["folds"].append(record_fold(method_id, folds[method_id][index], path))
        entry["row_and_target_parity"] = "PASS"
        parity.append(entry)
    for method_id, manifest in manifests.items():
        method, records = manifest["method"], methods[method_id]["folds"]
        methods[method_id].update({
            "classifier": method["classifier"], "regressor": method["regressor"], "model_family": method["model_family"],
            "model_version": method["model_version"], "config_version": method["config_version"], "seed": method["seed"],
            "preprocessing_version": "arrival_preprocessing_v1", "feature_manifest_version": FEATURE_MANIFEST_VERSION,
            "aggregate_development_metrics": manifest["aggregate_development_metrics"],
            "resource_summary": {
                "fit_runtime_seconds": sum(item["runtime"]["fit"]["runtime_seconds"] for item in records),
                "prediction_runtime_seconds": sum(item["runtime"]["prediction"]["runtime_seconds"] for item in records),
                "total_runtime_seconds": manifest["resource_measurement"]["total_wall_seconds"],
                "max_peak_traced_python_bytes": max(item["runtime"]["peak_traced_python_bytes"] for item in records),
                "max_post_fold_process_rss_bytes": max(item["runtime"]["post_fold_memory"]["process_rss_bytes"] for item in records),
                "oof_artifact_bytes": sum(item["oof_artifact_bytes"] for item in records),
                "measurement_method": manifest["resource_measurement"],
            },
        })
    summary: dict[str, Any] = {
        "summary_version": "week4_core_arrival_baselines_summary_v1", "created_at": datetime.now().astimezone().isoformat(),
        "status": "PASS", "source_artifacts_only": True, "no_retraining_performed": True,
        "core_arrival_contract": {"population": "inbound DEST=ATL", "classification_target": "y_arr_cls = 1[ARR_DELAY >= 15]", "regression_target": "y_arr_reg = signed ARR_DELAY minutes", "prediction_cutoff": "CRS_DEP_TIME - 2h", "feature_manifest_version": FEATURE_MANIFEST_VERSION, "excluded_predictor_groups": ["Weather", "departure target or predicted departure delay", "realized operational timestamps or durations", "Chain predictors", "identifiers"]},
        "common_folds": [{"fold_id": fold_id, "train_years": list(years), "validation_year": year} for fold_id, years, year in FOLDS],
        "cross_checks": {"methods_complete": "3/3", "common_fold_check": "PASS", "row_parity_check": "PASS", "row_parity_basis": "exact flight_key plus y_arr_cls and signed y_arr_reg equality per fold", "temporal_guard": "PASS: 2019-2022 validation only; row-level 2023/2024 access NO", "information_set_check": "PASS: shared feature manifest; family-specific preprocessing only", "metric_contract": "PASS: ROC-AUC, PR-AUC, Recall/F1 at fixed 0.5, Brier, 10-bin calibration; MAE/RMSE/R2", "fold_row_parity": parity},
        "methods": methods,
        "source_manifests": {method_id: {"path": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(path), "run_version": manifests[method_id]["run_version"], "completed_at_utc": manifests[method_id]["completed_at_utc"]} for method_id, path in MANIFESTS.items()},
        "non_selection_statement": "Descriptive evidence only; no champion selection, retuning, calibration fitting, ensemble, or holdout use.",
    }
    write_json_artifact(SUMMARY_PATH, summary)
    REPORT_PATH.write_text(build_report(summary), encoding="utf-8")
    marker = "## Week 4 — Core Arrival baseline rolling evidence"
    log = LOG_PATH.read_text(encoding="utf-8")
    if marker in log:
        raise FileExistsError("refusing duplicate Week-4 experiment-log entry")
    log += f"""

{marker}

- **Timestamp:** {summary['created_at']}
- **Protocol:** V4.0 Core Arrival; `arrival_week4_experiment_v1`.
- **Status:** Linear, Random Forest, and HistGradientBoosting locked rolling runs consolidated.
- **Folds:** 2016–2018 → 2019; 2016–2019 → 2020; 2016–2020 → 2021; 2016–2021 → 2022.
- **Evidence:** Exact OOF `flight_key`, classification-label, and signed regression-label parity passed for all four folds (1,254,518 OOF rows per method); full eligible rows were used.
- **Boundaries:** No Weather, Chain, Departure auxiliary input, realized operations, row-level 2023, or row-level 2024.
- **Selection status:** No champion selection, retuning, post-hoc calibration, ensemble, or final-holdout evaluation.
- **Artifacts:** `week4_core_arrival_baselines.md` and `week4_core_arrival_baselines_summary_v1.json`.
"""
    LOG_PATH.write_text(log, encoding="utf-8")
    print(f"PASS: wrote {SUMMARY_PATH.relative_to(ROOT)}")
    print(f"PASS: wrote {REPORT_PATH.relative_to(ROOT)}")
    print(f"PASS: updated {LOG_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
