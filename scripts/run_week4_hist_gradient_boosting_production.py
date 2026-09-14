"""Full rolling HistGradientBoosting production run for Core Arrival."""

from __future__ import annotations

import gc
import hashlib
import json
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.access_guard import assert_data_access_allowed  # noqa: E402
from src.data.load_aeolus import load_base_config, resolve_project_root  # noqa: E402
from src.models.artifacts import ParquetOOFSink, write_json_artifact  # noqa: E402
from src.models.contracts import (  # noqa: E402
    FEATURE_MANIFEST_VERSION,
    OOF_SCHEMA_VERSION,
    WEEK4_FRAMEWORK_VERSION,
    ExperimentSpec,
    RollingFold,
    load_week4_rolling_folds,
)
from src.models.hist_gradient_boosting_models import (  # noqa: E402
    HGB_BASELINE_CONFIG_PATH,
    HGB_BASELINE_VERSION,
    build_hgb_estimators,
    load_hgb_baseline_config,
)
from src.models.metrics import classification_metrics, regression_metrics  # noqa: E402
from src.models.rolling import run_fold_experiment  # noqa: E402
from scripts.run_week4_linear_production import (  # noqa: E402
    FORBIDDEN_ROW_YEARS,
    IO_BATCH_SIZE,
    REQUIRED_YEARS,
    _assert_oof_alignment,
    _assert_runtime_capacity,
    _load_fold,
    _manifest_hashes,
    _process_memory,
    _processed_row_counts,
)


RUN_VERSION = "arrival_hist_gradient_boosting_rolling_run_v1"
OOF_DIR = Path("artifacts/predictions")
MANIFEST_DIR = Path("artifacts/manifests")
PREFLIGHT_MANIFEST = MANIFEST_DIR / f"{RUN_VERSION}_preflight.json"
FINAL_MANIFEST = MANIFEST_DIR / f"{RUN_VERSION}.json"
FAILURE_MANIFEST = MANIFEST_DIR / f"{RUN_VERSION}_failure.json"


class ResourceBlocked(RuntimeError):
    def __init__(self, reason: str, *, completed_folds: list[str] | None = None) -> None:
        super().__init__(reason)
        self.completed_folds = list(completed_folds or [])


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _manifest_hashes_hgb(root: Path) -> dict[str, str]:
    hashes = _manifest_hashes(root)
    hashes.pop("linear_baseline_config", None)
    hashes["hist_gradient_boosting_baseline_config"] = _sha256(root / HGB_BASELINE_CONFIG_PATH)
    linear_manifest = root / "artifacts" / "manifests" / "arrival_linear_rolling_run_v1.json"
    if not linear_manifest.is_file():
        raise RuntimeError("completed Linear production manifest is required for row-identity checking")
    hashes["linear_run_manifest"] = _sha256(linear_manifest)
    return hashes


def _linear_validation_fingerprints(root: Path, folds: tuple[RollingFold, ...]) -> dict[str, str]:
    payload = json.loads(
        (root / "artifacts" / "manifests" / "arrival_linear_rolling_run_v1.json").read_text(
            encoding="utf-8"
        )
    )
    if payload.get("status") != "PASS" or not isinstance(payload.get("folds"), list):
        raise RuntimeError("Linear production manifest is not a valid PASS anchor")
    fingerprints: dict[str, str] = {}
    for report in payload["folds"]:
        if not isinstance(report, dict) or not isinstance(report.get("row_fingerprints"), dict):
            raise RuntimeError("Linear production manifest has malformed row fingerprints")
        fingerprints[str(report["fold_id"])] = str(report["row_fingerprints"]["validation"])
    if set(fingerprints) != {fold.fold_id for fold in folds}:
        raise RuntimeError("Linear validation fingerprints do not cover exactly the locked folds")
    return fingerprints


def _planned_paths(root: Path, folds: tuple[RollingFold, ...]) -> list[str]:
    return [
        str((root / OOF_DIR / f"{RUN_VERSION}_{fold.fold_id}.parquet").relative_to(root))
        for fold in folds
    ]


def build_preflight(root: Path) -> dict[str, Any]:
    config = load_hgb_baseline_config(project_root=root)
    project = load_base_config(project_root=root)
    folds = load_week4_rolling_folds(project_root=root)
    expected = (
        ((2016, 2017, 2018), 2019),
        ((2016, 2017, 2018, 2019), 2020),
        ((2016, 2017, 2018, 2019, 2020), 2021),
        ((2016, 2017, 2018, 2019, 2020, 2021), 2022),
    )
    if tuple((fold.train_years, fold.validation_year) for fold in folds) != expected:
        raise RuntimeError("locked folds differ from required Week-4 shape")
    try:
        assert_data_access_allowed(2024, "development")
    except PermissionError:
        pass
    else:
        raise RuntimeError("2024 development access guard unexpectedly allowed")
    counts = _processed_row_counts(root, REQUIRED_YEARS)
    fingerprints = _linear_validation_fingerprints(root, folds)
    capacity = _assert_runtime_capacity(root)
    hashes = _manifest_hashes_hgb(root)
    planned = _planned_paths(root, folds)
    for relative in planned:
        artifact = root / relative
        if artifact.exists() or artifact.with_suffix(".parquet.tmp").exists():
            raise FileExistsError(f"refusing to overwrite existing OOF artifact: {relative}")
    for relative in (PREFLIGHT_MANIFEST, FINAL_MANIFEST, FAILURE_MANIFEST):
        if (root / relative).exists():
            raise FileExistsError(f"refusing to overwrite existing run manifest: {root / relative}")
    return {
        "run_version": RUN_VERSION,
        "status": "PREPARED",
        "created_at_utc": _utc_now(),
        "python": sys.version,
        "project_root": str(root),
        "method": "hist_gradient_boosting",
        "classifier": "HistGradientBoostingClassifier",
        "regressor": "HistGradientBoostingRegressor",
        "baseline_version": config.baseline_version,
        "project_config_version": str(project["project"]["version"]),
        "seed": int(project["reproducibility"]["project_seed"]),
        "full_data_required": True,
        "io_batch_size": IO_BATCH_SIZE,
        "no_sampling_or_truncation": True,
        "folds": [asdict(fold) for fold in folds],
        "source_manifest_row_counts_2016_2022": counts,
        "reference_linear_validation_fingerprints": fingerprints,
        "excluded_row_years": list(FORBIDDEN_ROW_YEARS),
        "row_level_2024_access": "DENIED_BY_GUARD",
        "config_and_manifest_sha256": hashes,
        "planned_oof_artifacts": planned,
        "capacity_preflight": capacity,
        "resource_policy": {
            "learning_rate": config.learning_rate,
            "max_iter": config.max_iter,
            "max_leaf_nodes": config.max_leaf_nodes,
            "max_depth": config.max_depth,
            "min_samples_leaf": config.min_samples_leaf,
            "l2_regularization": config.l2_regularization,
            "early_stopping": False,
            "production_sampling_allowed": False,
        },
        "protocol": {
            "target": "DEST=ATL; y_arr_cls=1[ARR_DELAY>=15]; y_arr_reg=ARR_DELAY signed",
            "prediction_cutoff": "CRS_DEP_TIME - 2h",
            "no_weather": True,
            "no_departure_delay_or_actual_operations": True,
            "chain_predictors": "blocked",
            "random_split": False,
        },
    }


def _run(root: Path, preflight: dict[str, Any]) -> dict[str, Any]:
    config = load_hgb_baseline_config(project_root=root)
    project = load_base_config(project_root=root)
    folds = load_week4_rolling_folds(project_root=root)
    fingerprints = _linear_validation_fingerprints(root, folds)
    spec = ExperimentSpec(
        method_id="hist_gradient_boosting",
        model_version=HGB_BASELINE_VERSION,
        config_version=str(project["project"]["version"]),
        seed=int(project["reproducibility"]["project_seed"]),
        feature_manifest_version=FEATURE_MANIFEST_VERSION,
        expected_validation_row_fingerprints=fingerprints,
    )
    seen_keys: set[str] = set()
    completed_folds: list[str] = []
    fold_reports: list[dict[str, Any]] = []
    cls_y: list[np.ndarray] = []
    cls_p: list[np.ndarray] = []
    reg_y: list[np.ndarray] = []
    reg_p: list[np.ndarray] = []
    total_rows = 0
    started_all = time.perf_counter()
    for fold in folds:
        capacity = _assert_runtime_capacity(root)
        fold_started = time.perf_counter()
        try:
            data = _load_fold(root, fold)
            fold_result, oof = run_fold_experiment(
                spec,
                fold=fold,
                data=data,
                estimator_factory=lambda context: build_hgb_estimators(context, config=config),
            )
        except MemoryError as error:
            raise ResourceBlocked(
                f"MemoryError during {fold.fold_id} full-data fit/predict",
                completed_folds=completed_folds,
            ) from error
        _assert_oof_alignment(oof, fold, seen_keys)
        oof_path = root / OOF_DIR / f"{RUN_VERSION}_{fold.fold_id}.parquet"
        with ParquetOOFSink(oof_path) as sink:
            sink.append(oof)
        parquet_rows = int(pq.ParquetFile(oof_path).metadata.num_rows)
        if parquet_rows != len(oof) or parquet_rows != len(data.validation.X):
            raise RuntimeError(f"published OOF row count mismatch for {fold.fold_id}")
        cls_y.append(oof["y_arr_cls"].to_numpy(dtype=np.int8, copy=True))
        cls_p.append(oof["p_arr_delay_15"].to_numpy(dtype=float, copy=True))
        reg_y.append(oof["y_arr_reg"].to_numpy(dtype=float, copy=True))
        reg_p.append(oof["predicted_arr_delay_min"].to_numpy(dtype=float, copy=True))
        fold_reports.append(
            {
                "fold_id": fold.fold_id,
                "train_years": list(fold.train_years),
                "validation_year": fold.validation_year,
                "train_rows": int(len(data.train.X)),
                "validation_rows": int(len(data.validation.X)),
                "train_class_prevalence": float(data.train.y_arr_cls.mean()),
                "validation_class_prevalence": float(data.validation.y_arr_cls.mean()),
                "train_eligibility": asdict(data.train.eligibility),
                "validation_eligibility": asdict(data.validation.eligibility),
                "oof_artifact": str(oof_path.relative_to(root)),
                "oof_rows": parquet_rows,
                "metrics": {
                    "classification": fold_result.classification.to_dict(),
                    "regression": fold_result.regression.to_dict(),
                },
                "row_fingerprints": {
                    "validation": fold_result.validation_row_fingerprint,
                    "linear_validation_match": fold_result.validation_row_fingerprint
                    == fingerprints[fold.fold_id],
                },
                "class_weights_from_training_only": fold_result.class_weights,
                "runtime": {
                    "fit": fold_result.fit_resources.to_dict(),
                    "prediction": fold_result.prediction_resources.to_dict(),
                    "total_seconds": fold_result.total_runtime_seconds,
                    "fold_wall_seconds": time.perf_counter() - fold_started,
                    "peak_traced_python_bytes": fold_result.peak_memory_bytes,
                    "preflight_capacity": capacity,
                    "post_fold_memory": _process_memory(),
                },
                "preprocessor_state_unchanged_after_validation": fold_result.preprocessor_state_unchanged_after_validation,
            }
        )
        total_rows += parquet_rows
        completed_folds.append(fold.fold_id)
        del data, oof, fold_result
        gc.collect()
        after = _process_memory()
        if after["system_available_bytes"] < capacity["memory_safety_floor_bytes"]:
            raise ResourceBlocked(
                f"available memory fell below safety floor after {fold.fold_id}: {after}",
                completed_folds=completed_folds,
            )
    aggregate_cls = classification_metrics(np.concatenate(cls_y), np.concatenate(cls_p), threshold=0.5)
    aggregate_reg = regression_metrics(np.concatenate(reg_y), np.concatenate(reg_p))
    return {
        "run_version": RUN_VERSION,
        "status": "PASS",
        "completed_at_utc": _utc_now(),
        "framework_version": WEEK4_FRAMEWORK_VERSION,
        "experiment_contract_version": spec.experiment_contract_version,
        "oof_schema_version": OOF_SCHEMA_VERSION,
        "method": {
            "method_id": spec.method_id,
            "model_family": spec.model_family,
            "classifier": "HistGradientBoostingClassifier",
            "regressor": "HistGradientBoostingRegressor",
            "model_version": spec.model_version,
            "config_version": spec.config_version,
            "seed": spec.seed,
            "preprocessing_version": spec.preprocessing_version,
            "feature_manifest_version": spec.feature_manifest_version,
        },
        "config_and_manifest_sha256": preflight["config_and_manifest_sha256"],
        "resource_policy": preflight["resource_policy"],
        "folds": fold_reports,
        "aggregate_development_metrics": {
            "classification": aggregate_cls.to_dict(),
            "regression": aggregate_reg.to_dict(),
            "rows": total_rows,
            "note": "pooled OOF diagnostics only; HGB config remained locked",
        },
        "oof_artifacts": [report["oof_artifact"] for report in fold_reports],
        "full_data_used": True,
        "row_level_2023_access": "NO",
        "row_level_2024_access": "NO",
        "resource_measurement": {
            "phase_method": "tracemalloc_python_allocations",
            "process_memory_method": "psutil_process_rss_and_system_available",
            "total_wall_seconds": time.perf_counter() - started_all,
            "final_memory": _process_memory(),
        },
        "protocol_guards": {
            "no_weather": True,
            "no_departure_delay_or_predicted_departure_delay": True,
            "no_realized_operations": True,
            "no_chain_predictors": True,
            "no_random_split": True,
            "validation_years": [2019, 2020, 2021, 2022],
            "excluded_years": [2023, 2024],
        },
    }


def _write_failure(root: Path, reason: str, preflight_path: Path, completed: list[str]) -> None:
    path = root / FAILURE_MANIFEST
    if path.exists():
        return
    write_json_artifact(
        path,
        {
            "run_version": RUN_VERSION,
            "status": "BLOCKED_RESOURCE",
            "failed_at_utc": _utc_now(),
            "reason": reason,
            "preflight_manifest": str(preflight_path),
            "completed_folds": completed,
            "full_data_used": False,
            "row_level_2023_access": "NO",
            "row_level_2024_access": "NO",
        },
    )


def main() -> int:
    root = resolve_project_root()
    preflight_path = root / PREFLIGHT_MANIFEST
    try:
        preflight = build_preflight(root)
        write_json_artifact(preflight_path, preflight)
        print(json.dumps({"status": "PREPARED", "manifest": str(preflight_path)}, indent=2))
        result = _run(root, preflight)
        final_path = root / FINAL_MANIFEST
        write_json_artifact(final_path, result)
        print(json.dumps({"status": "PASS", "manifest": str(final_path), "oof": result["oof_artifacts"]}, indent=2))
        return 0
    except ResourceBlocked as error:
        _write_failure(root, str(error), preflight_path, error.completed_folds)
        print(json.dumps({"status": "BLOCKED_RESOURCE", "reason": str(error)}, indent=2), file=sys.stderr)
        return 2
    except MemoryError as error:
        _write_failure(root, f"MemoryError during unsampled full-data HGB run: {error}", preflight_path, [])
        print(json.dumps({"status": "BLOCKED_RESOURCE", "reason": str(error)}, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
