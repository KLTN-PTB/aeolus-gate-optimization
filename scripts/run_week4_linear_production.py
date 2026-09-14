"""Production rolling Logistic/Ridge run for the locked Core Arrival protocol.

This runner is intentionally year-wise at the IO boundary.  It never calls the
bounded ``load_arrival_development_batch`` helper, never samples, and never
opens 2023/2024 row payloads.  Each fold gets a fresh prepared data object,
preprocessor, and estimator bundle; completed folds are committed to their
own OOF Parquet artifact so a later resource failure remains auditable.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import psutil
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.access_guard import assert_data_access_allowed
from src.data.load_aeolus import load_base_config, resolve_project_root
from src.data.preprocessing import ARRIVAL_PROJECTED_SOURCE_COLUMNS, iter_arrival_development_batches
from src.features.tabular_features import ArrivalEligibilityReport, PreparedArrivalFeatures, prepare_arrival_features
from src.models.artifacts import ParquetOOFSink, write_json_artifact
from src.models.contracts import (
    FEATURE_MANIFEST_VERSION,
    OOF_SCHEMA_VERSION,
    WEEK4_FRAMEWORK_VERSION,
    ExperimentSpec,
    FoldData,
    RollingFold,
    load_week4_rolling_folds,
    validate_fold_data,
)
from src.models.linear_models import (
    LINEAR_BASELINE_CONFIG_PATH,
    LINEAR_BASELINE_VERSION,
    build_linear_estimators,
    load_linear_baseline_config,
)
from src.models.metrics import classification_metrics, regression_metrics
from src.models.rolling import run_fold_experiment


RUN_VERSION = "arrival_linear_rolling_run_v1"
OOF_DIR = Path("artifacts/predictions")
MANIFEST_DIR = Path("artifacts/manifests")
PREFLIGHT_MANIFEST = MANIFEST_DIR / f"{RUN_VERSION}_preflight.json"
FINAL_MANIFEST = MANIFEST_DIR / f"{RUN_VERSION}.json"
FAILURE_MANIFEST = MANIFEST_DIR / f"{RUN_VERSION}_failure.json"
REQUIRED_YEARS = tuple(range(2016, 2023))
FORBIDDEN_ROW_YEARS = (2023, 2024)
IO_BATCH_SIZE = 65_536
MIN_FREE_DISK_BYTES = 10 * 1024**3
MIN_AVAILABLE_MEMORY_BYTES = 512 * 1024**2


class ResourceBlocked(RuntimeError):
    """Raised when a full, unsampled run cannot safely continue."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _process_memory() -> dict[str, int | float]:
    virtual = psutil.virtual_memory()
    process = psutil.Process(os.getpid()).memory_info()
    return {
        "process_rss_bytes": int(process.rss),
        "system_total_bytes": int(virtual.total),
        "system_available_bytes": int(virtual.available),
        "system_used_percent": float(virtual.percent),
    }


def _assert_runtime_capacity(root: Path) -> dict[str, Any]:
    usage = psutil.disk_usage(str(root.drive or root))
    memory = _process_memory()
    if usage.free < MIN_FREE_DISK_BYTES:
        raise ResourceBlocked(
            f"free disk {usage.free} bytes is below {MIN_FREE_DISK_BYTES} byte safety floor"
        )
    if memory["system_available_bytes"] < MIN_AVAILABLE_MEMORY_BYTES:
        raise ResourceBlocked(
            "available system memory is below the 512 MiB safety floor; full run would risk OOM"
        )
    return {
        "disk_free_bytes": int(usage.free),
        "disk_total_bytes": int(usage.total),
        "memory": memory,
        "disk_safety_floor_bytes": MIN_FREE_DISK_BYTES,
        "memory_safety_floor_bytes": MIN_AVAILABLE_MEMORY_BYTES,
    }


def _manifest_hashes(root: Path) -> dict[str, str]:
    paths = {
        "base_config": root / "configs" / "base.yaml",
        "linear_baseline_config": root / LINEAR_BASELINE_CONFIG_PATH,
        "feature_manifest": root / "artifacts" / "manifests" / "feature_manifest_arrival_v1.json",
        "feature_pipeline_registry": root / "artifacts" / "manifests" / "feature_pipeline_registry_arrival_v1.json",
        "temporal_folds_manifest": root / "artifacts" / "manifests" / "temporal_folds_manifest.json",
        "reconstructed_chain_audit": root / "artifacts" / "manifests" / "reconstructed_chain_feature_availability_audit_v1.json",
        "processed_data_manifest": root / "artifacts" / "manifests" / "processed_data_manifest_v1.json",
    }
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        raise RuntimeError(f"required manifest/config files are missing: {missing}")
    return {name: _sha256(path) for name, path in paths.items()}


def _processed_row_counts(root: Path, years: Iterable[int]) -> dict[str, int]:
    """Read Parquet metadata only and cross-check the processed manifest."""

    manifest_path = root / "artifacts" / "manifests" / "processed_data_manifest_v1.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = {int(item["year"]): item for item in payload.get("years", [])}
    result: dict[str, int] = {}
    for year in years:
        entry = entries.get(year)
        if not isinstance(entry, dict):
            raise RuntimeError(f"processed manifest lacks year {year}")
        partitions = [item for item in entry.get("partitions", []) if item.get("flow") == "inbound_atl"]
        if not partitions:
            raise RuntimeError(f"processed manifest lacks inbound_atl partition for {year}")
        partition_entry = partitions[0]
        directory = root / "data" / "processed" / "inbound_atl" / f"year={year}"
        if not directory.is_dir():
            raise RuntimeError(f"missing inbound_atl partition directory: {directory}")
        parquet_files = sorted(directory.glob("*.parquet"))
        if not parquet_files:
            raise RuntimeError(f"inbound_atl partition has no parquet files: {directory}")
        metadata_rows = sum(int(pq.ParquetFile(path).metadata.num_rows) for path in parquet_files)
        manifest_rows = int(partition_entry.get("row_count", partition_entry.get("output_rows", -1)))
        if metadata_rows != manifest_rows:
            raise RuntimeError(
                f"year {year} metadata row count {metadata_rows} != manifest row count {manifest_rows}"
            )
        schema_names = set(pq.ParquetFile(parquet_files[0]).schema_arrow.names)
        missing = set(ARRIVAL_PROJECTED_SOURCE_COLUMNS).difference(schema_names)
        if missing:
            raise RuntimeError(f"year {year} inbound schema lacks projected columns: {sorted(missing)}")
        result[str(year)] = metadata_rows
    return result


def _concat_prepared(parts: list[PreparedArrivalFeatures]) -> PreparedArrivalFeatures:
    if not parts:
        raise ValueError("cannot concatenate an empty prepared partition")
    X = pd.concat([part.X for part in parts], ignore_index=True)
    y_cls = pd.concat([part.y_arr_cls for part in parts], ignore_index=True).astype("int8")
    y_reg = pd.concat([part.y_arr_reg for part in parts], ignore_index=True).astype("float64")
    identifiers = pd.concat([part.identifiers for part in parts], ignore_index=True)
    cutoff = pd.concat([part.prediction_cutoff for part in parts], ignore_index=True)
    eligibility = ArrivalEligibilityReport(
        input_rows=sum(part.eligibility.input_rows for part in parts),
        inbound_rows=sum(part.eligibility.inbound_rows for part in parts),
        eligible_rows=sum(part.eligibility.eligible_rows for part in parts),
        dropped_non_inbound_rows=sum(part.eligibility.dropped_non_inbound_rows for part in parts),
        dropped_missing_target_rows=sum(part.eligibility.dropped_missing_target_rows for part in parts),
        target_imputation_used=any(part.eligibility.target_imputation_used for part in parts),
    )
    return PreparedArrivalFeatures(
        X=X,
        y_arr_cls=y_cls,
        y_arr_reg=y_reg,
        identifiers=identifiers,
        prediction_cutoff=cutoff,
        eligibility=eligibility,
    )


def _load_full_year(root: Path, year: int) -> PreparedArrivalFeatures:
    """Prepare every eligible row in one year, retaining only prepared columns."""

    parts: list[PreparedArrivalFeatures] = []
    for raw_batch in iter_arrival_development_batches(
        year, project_root=root, batch_size=IO_BATCH_SIZE
    ):
        parts.append(prepare_arrival_features(raw_batch))
    if not parts:
        raise RuntimeError(f"year {year} produced no inbound rows")
    return _concat_prepared(parts)


def _load_fold(root: Path, fold: RollingFold) -> FoldData:
    train_parts = [_load_full_year(root, year) for year in fold.train_years]
    validation = _load_full_year(root, fold.validation_year)
    train = _concat_prepared(train_parts)
    return FoldData(train=train, validation=validation)


def _eligibility(prepared: PreparedArrivalFeatures) -> dict[str, int | bool]:
    return asdict(prepared.eligibility)


def _assert_oof_alignment(frame: pd.DataFrame, fold: RollingFold, seen: set[str]) -> None:
    if not frame["flight_key"].is_unique:
        raise RuntimeError(f"{fold.fold_id} OOF flight keys are not unique")
    if set(frame["fold_id"].astype(str)) != {fold.fold_id}:
        raise RuntimeError(f"{fold.fold_id} OOF fold_id mismatch")
    if set(frame["validation_year"].astype(int)) != {fold.validation_year}:
        raise RuntimeError(f"{fold.fold_id} OOF validation year mismatch")
    keys = set(frame["flight_key"].astype(str))
    if seen.intersection(keys):
        raise RuntimeError(f"OOF flight_key overlap detected at {fold.fold_id}")
    seen.update(keys)


def _planned_paths(root: Path, folds: Iterable[RollingFold]) -> list[str]:
    return [
        str((root / OOF_DIR / f"{RUN_VERSION}_{fold.fold_id}.parquet").relative_to(root))
        for fold in folds
    ]


def build_preflight(root: Path) -> dict[str, Any]:
    config = load_linear_baseline_config(project_root=root)
    folds = load_week4_rolling_folds(project_root=root)
    expected_shape = (
        ((2016, 2017, 2018), 2019),
        ((2016, 2017, 2018, 2019), 2020),
        ((2016, 2017, 2018, 2019, 2020), 2021),
        ((2016, 2017, 2018, 2019, 2020, 2021), 2022),
    )
    observed_shape = tuple((fold.train_years, fold.validation_year) for fold in folds)
    if observed_shape != expected_shape:
        raise RuntimeError(f"locked folds differ from required Week-4 shape: {observed_shape}")
    # Explicitly exercise the 2024 guard without opening any 2024 partition.
    guard_2024 = "DENIED"
    try:
        assert_data_access_allowed(2024, "development")
    except PermissionError:
        pass
    else:
        raise RuntimeError("2024 development access guard unexpectedly allowed")
    counts = _processed_row_counts(root, REQUIRED_YEARS)
    capacity = _assert_runtime_capacity(root)
    hashes = _manifest_hashes(root)
    planned = _planned_paths(root, folds)
    for relative in planned:
        if (root / relative).exists() or (root / relative).with_suffix(".parquet.tmp").exists():
            raise FileExistsError(f"refusing to overwrite existing OOF artifact: {relative}")
    for path in (PREFLIGHT_MANIFEST, FINAL_MANIFEST, FAILURE_MANIFEST):
        if path.is_absolute():
            candidate = path
        else:
            candidate = root / path
        if candidate.exists():
            raise FileExistsError(f"refusing to overwrite existing run manifest: {candidate}")
    return {
        "run_version": RUN_VERSION,
        "status": "PREPARED",
        "created_at_utc": _utc_now(),
        "python": sys.version,
        "project_root": str(root),
        "method": "linear",
        "classifier": "LogisticRegression",
        "regressor": "Ridge",
        "baseline_version": config.baseline_version,
        "full_data_required": True,
        "io_batch_size": IO_BATCH_SIZE,
        "no_sampling_or_truncation": True,
        "folds": [asdict(fold) for fold in folds],
        "source_manifest_row_counts_2016_2022": counts,
        "excluded_row_years": list(FORBIDDEN_ROW_YEARS),
        "row_level_2024_access": "DENIED_BY_GUARD",
        "config_and_manifest_sha256": hashes,
        "planned_oof_artifacts": planned,
        "capacity_preflight": capacity,
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
    config = load_linear_baseline_config(project_root=root)
    project_config = load_base_config(project_root=root)
    folds = load_week4_rolling_folds(project_root=root)
    spec = ExperimentSpec(
        method_id="linear",
        model_version=LINEAR_BASELINE_VERSION,
        config_version=str(project_config["project"]["version"]),
        seed=int(project_config["reproducibility"]["project_seed"]),
        feature_manifest_version=FEATURE_MANIFEST_VERSION,
    )
    seen_keys: set[str] = set()
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
        data = _load_fold(root, fold)
        validate_fold_data(fold, data)
        fold_result, oof = run_fold_experiment(
            spec,
            fold=fold,
            data=data,
            estimator_factory=lambda context: build_linear_estimators(context, config=config),
        )
        _assert_oof_alignment(oof, fold, seen_keys)
        oof_path = root / OOF_DIR / f"{RUN_VERSION}_{fold.fold_id}.parquet"
        with ParquetOOFSink(oof_path) as sink:
            sink.append(oof)
        parquet_rows = int(pq.ParquetFile(oof_path).metadata.num_rows)
        if parquet_rows != len(oof):
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
                "train_eligibility": _eligibility(data.train),
                "validation_eligibility": _eligibility(data.validation),
                "oof_artifact": str(oof_path.relative_to(root)),
                "oof_rows": parquet_rows,
                "metrics": {
                    "classification": fold_result.classification.to_dict(),
                    "regression": fold_result.regression.to_dict(),
                },
                "row_fingerprints": {
                    "train": fold_result.train_row_fingerprint,
                    "validation": fold_result.validation_row_fingerprint,
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
        del data, oof, fold_result
        gc.collect()
        after = _process_memory()
        if after["system_available_bytes"] < MIN_AVAILABLE_MEMORY_BYTES:
            raise ResourceBlocked(
                f"available memory fell below safety floor after {fold.fold_id}: {after}"
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
            "classifier": "LogisticRegression",
            "regressor": "Ridge",
            "model_version": spec.model_version,
            "config_version": spec.config_version,
            "seed": spec.seed,
        },
        "config_and_manifest_sha256": preflight["config_and_manifest_sha256"],
        "folds": fold_reports,
        "aggregate_development_metrics": {
            "classification": aggregate_cls.to_dict(),
            "regression": aggregate_reg.to_dict(),
            "rows": total_rows,
            "note": "pooled OOF diagnostics only; no retuning or model selection",
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=None)
    args = parser.parse_args()
    root = resolve_project_root(args.project_root)
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
        payload = {
            "run_version": RUN_VERSION,
            "status": "BLOCKED_RESOURCE",
            "failed_at_utc": _utc_now(),
            "reason": str(error),
            "preflight_manifest": str(preflight_path),
            "full_data_used": False,
            "row_level_2023_access": "NO",
            "row_level_2024_access": "NO",
        }
        failure_path = root / FAILURE_MANIFEST
        if not failure_path.exists():
            write_json_artifact(failure_path, payload)
        print(json.dumps(payload, indent=2), file=sys.stderr)
        return 2
    except MemoryError as error:
        payload = {
            "run_version": RUN_VERSION,
            "status": "BLOCKED_RESOURCE",
            "failed_at_utc": _utc_now(),
            "reason": f"MemoryError during unsampled full-data run: {error}",
            "preflight_manifest": str(preflight_path),
            "full_data_used": False,
            "row_level_2023_access": "NO",
            "row_level_2024_access": "NO",
        }
        failure_path = root / FAILURE_MANIFEST
        if not failure_path.exists():
            write_json_artifact(failure_path, payload)
        print(json.dumps(payload, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
