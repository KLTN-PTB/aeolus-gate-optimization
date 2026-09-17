"""Materialize immutable tuned Week-5 development OOF; never performs HPO."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_week4_linear_production import (  # noqa: E402
    REQUIRED_YEARS, _assert_oof_alignment, _load_fold, _process_memory,
)
from src.data.load_aeolus import load_base_config, resolve_project_root  # noqa: E402
from src.models.artifacts import ParquetOOFSink, write_json_artifact  # noqa: E402
from src.models.contracts import (  # noqa: E402
    FEATURE_MANIFEST_VERSION, OOF_SCHEMA_VERSION, load_week4_rolling_folds,
)
from src.models.metrics import classification_metrics, regression_metrics  # noqa: E402
from src.models.rolling import run_fold_experiment  # noqa: E402
from src.models.week5_hpo_protocol_v1_1 import load_week5_hpo_protocol_v1_1  # noqa: E402
from src.models.week5_contracts import Week5ExperimentSpec  # noqa: E402
from src.models.week5_tuned_oof import (  # noqa: E402
    TunedMethodInputs, build_tuned_estimator_bundle_factory, load_tuned_method_inputs,
)


METHODS = ("random_forest", "hist_gradient_boosting", "xgboost")
RUN_VERSIONS = {method: f"arrival_{method}_tuned_rolling_run_v1_1" for method in METHODS}
OOF_DIR = Path("artifacts/predictions")
MANIFEST_DIR = Path("artifacts/manifests")
LINEAR_MANIFEST = Path("artifacts/manifests/arrival_linear_rolling_run_v1.json")
XGB_RECOVERY_PREFLIGHT = Path(
    "artifacts/manifests/arrival_xgboost_tuned_rolling_run_v1_1_preflight_v2.json"
)
XGB_RECOVERY_INCIDENT = Path(
    "artifacts/manifests/week5_step07_xgb_contract_recovery_v1.json"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _paths(method: str) -> dict[str, Path]:
    version = RUN_VERSIONS[method]
    return {
        "preflight": MANIFEST_DIR / f"{version}_preflight.json",
        "final": MANIFEST_DIR / f"{version}.json",
        **{fold: OOF_DIR / f"{version}_{fold}.parquet" for fold in ("fold_1", "fold_2", "fold_3", "fold_4")},
    }


def planned_paths(root: Path) -> dict[str, list[Path]]:
    root = Path(root)
    return {method: [root / path for path in _paths(method).values()] for method in METHODS}


def _linear_anchor(root: Path) -> tuple[dict[str, Any], dict[str, Path]]:
    try:
        manifest = json.loads((root / LINEAR_MANIFEST).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError("completed Linear Week-4 anchor is unreadable") from error
    if manifest.get("status") != "PASS" or manifest.get("oof_schema_version") != OOF_SCHEMA_VERSION:
        raise RuntimeError("completed Linear Week-4 anchor is invalid")
    paths: dict[str, Path] = {}
    for report in manifest.get("folds", []):
        paths[str(report["fold_id"])] = root / str(report["oof_artifact"])
    if set(paths) != {"fold_1", "fold_2", "fold_3", "fold_4"} or not all(path.exists() for path in paths.values()):
        raise RuntimeError("completed Linear Week-4 anchor lacks all OOF folds")
    return manifest, paths


def _assert_exact_anchor_parity(anchor: Mapping[str, Any], candidate: Mapping[str, Any], fold_id: str) -> None:
    for column in ("flight_key", "y_arr_cls", "y_arr_reg"):
        left = np.asarray(anchor[column])
        right = np.asarray(candidate[column])
        if left.shape != right.shape or not np.array_equal(left, right):
            raise RuntimeError(f"exact Linear-anchor row/target parity failed for {fold_id}/{column}")


def _source_reference(inputs: TunedMethodInputs) -> dict[str, str]:
    return {
        "summary": inputs.summary_path, "summary_sha256": inputs.summary_sha256,
        "classification_result": inputs.classification_result_path,
        "classification_result_sha256": inputs.classification_result_sha256,
        "regression_result": inputs.regression_result_path,
        "regression_result_sha256": inputs.regression_result_sha256,
    }


def build_preflight(root: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    protocol = load_week5_hpo_protocol_v1_1(project_root=root)
    inputs = load_tuned_method_inputs(root, protocol)
    project = load_base_config(project_root=root)
    folds = load_week4_rolling_folds(project_root=root)
    expected = (((2016, 2017, 2018), 2019), ((2016, 2017, 2018, 2019), 2020), ((2016, 2017, 2018, 2019, 2020), 2021), ((2016, 2017, 2018, 2019, 2020, 2021), 2022))
    if tuple((fold.train_years, fold.validation_year) for fold in folds) != expected:
        raise RuntimeError("tuned OOF folds differ from the frozen four folds")
    linear, anchor_paths = _linear_anchor(root)
    all_paths = planned_paths(root)
    for paths in all_paths.values():
        for path in paths:
            if path.exists() or path.with_suffix(path.suffix + ".tmp").exists():
                raise FileExistsError(f"refusing to overwrite tuned OOF artifact: {path}")
    baseline_paths = [root / LINEAR_MANIFEST, *anchor_paths.values()]
    for method in METHODS:
        baseline = root / MANIFEST_DIR / f"arrival_{method.replace('hist_gradient_boosting', 'hist_gradient_boosting')}_rolling_run_v1.json"
        if not baseline.exists():
            raise RuntimeError(f"baseline manifest missing: {baseline}")
        baseline_paths.append(baseline)
    return {
        "status": "PREPARED", "created_at_utc": _utc_now(), "protocol_version": protocol.protocol_version,
        "protocol_hash": protocol.protocol_hash, "seed": int(project["reproducibility"]["project_seed"]),
        "folds": [asdict(fold) for fold in folds], "linear_anchor_manifest": str(LINEAR_MANIFEST),
        "linear_anchor_sha256": _sha256(root / LINEAR_MANIFEST),
        "linear_anchor_oof_sha256": {fold: _sha256(path) for fold, path in anchor_paths.items()},
        "baseline_immutable_sha256": {str(path.relative_to(root)): _sha256(path) for path in baseline_paths},
        "methods": {method: {"run_version": RUN_VERSIONS[method], "source_hpo": _source_reference(inputs[method]), "classification_params": inputs[method].classification_params, "regression_params": inputs[method].regression_params, "planned_oof_artifacts": [str((root / path).relative_to(root)) for path in _paths(method).values() if path.suffix == ".parquet"]} for method in METHODS},
        "row_level_2023_accessed": False, "row_level_2024_accessed": False,
        "hpo_rerun": False, "champion_selected": False,
    }


def _rf_hgb_tuned_artifact_hashes(root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for method in ("random_forest", "hist_gradient_boosting"):
        for label in ("final", "fold_1", "fold_2", "fold_3", "fold_4"):
            path = root / _paths(method)[label]
            if not path.is_file():
                raise RuntimeError(f"completed {method} tuned artifact is missing: {path}")
            hashes[str(path.relative_to(root))] = _sha256(path)
    return hashes


def build_xgboost_recovery_preflight(root: Path) -> dict[str, Any]:
    """Validate immutable completed evidence and a fresh XGB-only continuation."""

    root = Path(root).resolve()
    prior_relative = _paths("xgboost")["preflight"]
    prior_path = root / prior_relative
    try:
        prior = json.loads(prior_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError("historical failed XGBoost tuned preflight is unreadable") from error
    if prior.get("status") != "PREPARED" or prior.get("current_method") != "xgboost":
        raise RuntimeError("historical XGBoost tuned preflight is invalid")
    if prior.get("protocol_hash") != load_week5_hpo_protocol_v1_1(project_root=root).protocol_hash:
        raise RuntimeError("historical XGBoost tuned preflight protocol mismatch")
    for method in ("random_forest", "hist_gradient_boosting"):
        manifest = json.loads((root / _paths(method)["final"]).read_text(encoding="utf-8"))
        if (
            manifest.get("status") != "PASS"
            or manifest.get("row_parity") != "PASS"
            or len(manifest.get("folds", [])) != 4
            or manifest.get("aggregate_development_metrics", {}).get("rows") != 1_254_518
        ):
            raise RuntimeError(f"completed {method} tuned evidence is invalid")
    for relative, expected in prior.get("baseline_immutable_sha256", {}).items():
        if _sha256(root / relative) != expected:
            raise RuntimeError("baseline evidence changed before XGBoost recovery")
    xgb_paths = _paths("xgboost")
    for label in ("final", "fold_1", "fold_2", "fold_3", "fold_4"):
        path = root / xgb_paths[label]
        if path.exists() or path.with_suffix(path.suffix + ".tmp").exists():
            raise FileExistsError(f"refusing XGBoost recovery artifact collision: {path}")
    for path in (root / XGB_RECOVERY_PREFLIGHT, root / XGB_RECOVERY_INCIDENT):
        if path.exists():
            raise FileExistsError(f"refusing recovery evidence collision: {path}")
    protocol = load_week5_hpo_protocol_v1_1(project_root=root)
    inputs = load_tuned_method_inputs(root, protocol)["xgboost"]
    return {
        "status": "PREPARED_XGBOOST_ONLY_RECOVERY",
        "created_at_utc": _utc_now(),
        "incident_type": "WEEK4_METHOD_CONTRACT_REUSED_FOR_WEEK5_XGBOOST",
        "fix_type": "VERSIONED_WEEK5_EXPERIMENT_SPEC",
        "protocol_version": protocol.protocol_version,
        "protocol_hash": protocol.protocol_hash,
        "prior_failed_preflight": str(prior_relative),
        "prior_failed_preflight_sha256": _sha256(prior_path),
        "source_hpo": _source_reference(inputs),
        "classification_params": inputs.classification_params,
        "regression_params": inputs.regression_params,
        "rf_hgb_immutable_sha256": _rf_hgb_tuned_artifact_hashes(root),
        "baseline_immutable_sha256": dict(prior["baseline_immutable_sha256"]),
        "planned_oof_artifacts": [
            str(xgb_paths[fold]) for fold in ("fold_1", "fold_2", "fold_3", "fold_4")
        ],
        "rf_rerun": False,
        "hgb_rerun": False,
        "hpo_rerun": False,
        "row_level_2023_accessed": False,
        "row_level_2024_accessed": False,
        "champion_selected": False,
        "ensemble_fitted": False,
    }


def run_xgboost_recovery_sequence(
    run_method: Any,
) -> dict[str, Any]:
    """Make the recovery call graph incapable of invoking RF or HGB."""

    return run_method("xgboost")


def _verify_recovery_immutability(root: Path, recovery: dict[str, Any]) -> None:
    for relative, expected in recovery["rf_hgb_immutable_sha256"].items():
        if _sha256(root / relative) != expected:
            raise RuntimeError("RF/HGB tuned evidence changed during XGBoost recovery")


def _write_recovery_incident(root: Path, recovery: dict[str, Any]) -> None:
    write_json_artifact(
        root / XGB_RECOVERY_INCIDENT,
        {
            "incident_id": "week5_step07_xgb_contract_recovery_v1",
            "status": "RECOVERED",
            "created_at_utc": _utc_now(),
            "root_cause": recovery["incident_type"],
            "historical_failure": (
                "Step 07 initially failed before XGBoost tuned OOF materialization "
                "because the Week-4 ExperimentSpec rejected method_id='xgboost'."
            ),
            "fix_type": recovery["fix_type"],
            "week4_contract_preserved": True,
            "rf_hgb_tuned_artifacts_preserved": True,
            "rf_rerun": False,
            "hgb_rerun": False,
            "hpo_rerun": False,
            "xgboost_materialized_from_prompt06_frozen_params": True,
            "protocol_version": recovery["protocol_version"],
            "protocol_hash": recovery["protocol_hash"],
            "prior_failed_preflight": recovery["prior_failed_preflight"],
            "recovery_preflight": str(XGB_RECOVERY_PREFLIGHT),
            "rf_hgb_immutable_sha256": recovery["rf_hgb_immutable_sha256"],
            "row_level_2023_accessed": False,
            "row_level_2024_accessed": False,
        },
    )


def run_tuned_method(root: Path, preflight: dict[str, Any], inputs: TunedMethodInputs) -> dict[str, Any]:
    root = Path(root).resolve()
    protocol = load_week5_hpo_protocol_v1_1(project_root=root)
    project = load_base_config(project_root=root)
    folds = load_week4_rolling_folds(project_root=root)
    _, anchors = _linear_anchor(root)
    spec = Week5ExperimentSpec(method_id=inputs.method_id, model_version=RUN_VERSIONS[inputs.method_id], config_version=str(project["project"]["version"]), seed=202601, feature_manifest_version=FEATURE_MANIFEST_VERSION)
    factory = build_tuned_estimator_bundle_factory(inputs, protocol)
    seen: set[str] = set(); reports: list[dict[str, Any]] = []
    ys_cls: list[np.ndarray] = []; ps_cls: list[np.ndarray] = []; ys_reg: list[np.ndarray] = []; ps_reg: list[np.ndarray] = []
    started = time.perf_counter()
    for fold in folds:
        fold_started = time.perf_counter(); data = _load_fold(root, fold)
        result, oof = run_fold_experiment(spec, fold=fold, data=data, estimator_factory=factory)
        _assert_oof_alignment(oof, fold, seen)
        anchor = pq.read_table(anchors[fold.fold_id], columns=["flight_key", "y_arr_cls", "y_arr_reg"]).to_pandas()
        _assert_exact_anchor_parity(anchor, oof, fold.fold_id)
        path = root / _paths(inputs.method_id)[fold.fold_id]
        with ParquetOOFSink(path) as sink:
            sink.append(oof)
        rows = int(pq.ParquetFile(path).metadata.num_rows)
        if rows != len(oof) or rows != len(anchor):
            raise RuntimeError(f"published tuned OOF row count mismatch for {fold.fold_id}")
        ys_cls.append(oof["y_arr_cls"].to_numpy(dtype=np.int8, copy=True)); ps_cls.append(oof["p_arr_delay_15"].to_numpy(dtype=float, copy=True))
        ys_reg.append(oof["y_arr_reg"].to_numpy(dtype=float, copy=True)); ps_reg.append(oof["predicted_arr_delay_min"].to_numpy(dtype=float, copy=True))
        reports.append({"fold_id": fold.fold_id, "train_years": list(fold.train_years), "validation_year": fold.validation_year, "train_rows": len(data.train.X), "validation_rows": len(data.validation.X), "oof_rows": rows, "oof_artifact": str(path.relative_to(root)), "metrics": {"classification": result.classification.to_dict(), "regression": result.regression.to_dict()}, "row_fingerprints": {"train": result.train_row_fingerprint, "validation": result.validation_row_fingerprint}, "linear_anchor_parity": "PASS", "class_weights_from_training_only": result.class_weights, "preprocessor_state_unchanged_after_validation": result.preprocessor_state_unchanged_after_validation, "runtime": {"fit": result.fit_resources.to_dict(), "prediction": result.prediction_resources.to_dict(), "total_seconds": result.total_runtime_seconds, "fold_wall_seconds": time.perf_counter()-fold_started, "post_fold_memory": _process_memory()}})
        del data, result, oof, anchor; gc.collect()
    cls = classification_metrics(np.concatenate(ys_cls), np.concatenate(ps_cls), threshold=0.5)
    reg = regression_metrics(np.concatenate(ys_reg), np.concatenate(ps_reg))
    return {"run_version": RUN_VERSIONS[inputs.method_id], "status": "PASS", "completed_at_utc": _utc_now(), "method": {"method_id": inputs.method_id, "model_version": RUN_VERSIONS[inputs.method_id], "seed": 202601, "feature_manifest_version": FEATURE_MANIFEST_VERSION, "preprocessing_version": spec.preprocessing_version}, "protocol_version": protocol.protocol_version, "protocol_hash": protocol.protocol_hash, "hpo_result_source": _source_reference(inputs), "frozen_best_params": {"classification": inputs.classification_params, "regression": inputs.regression_params}, "folds": reports, "oof_artifacts": [report["oof_artifact"] for report in reports], "oof_schema_version": OOF_SCHEMA_VERSION, "aggregate_development_metrics": {"classification": cls.to_dict(), "regression": reg.to_dict(), "rows": sum(report["oof_rows"] for report in reports), "note": "2016-2022 development OOF diagnostics only; no champion or calibration selection"}, "row_parity": "PASS", "row_level_2023_accessed": False, "row_level_2024_accessed": False, "weather_used": False, "departure_prediction_used": False, "dep_delay_predictor_used": False, "chain_used": False, "arr_b_enabled": False, "hpo_rerun": False, "champion_selected": False, "resource_measurement": {"total_wall_seconds": time.perf_counter()-started, "final_memory": _process_memory()}}


def verify_tuned_oof_outputs(root: Path, preflight: dict[str, Any]) -> None:
    root = Path(root).resolve(); _, anchors = _linear_anchor(root)
    for method in METHODS:
        manifest = json.loads((root / _paths(method)["final"]).read_text(encoding="utf-8"))
        if manifest.get("status") != "PASS" or manifest.get("row_parity") != "PASS" or manifest.get("hpo_rerun") is not False:
            raise RuntimeError("tuned OOF manifest verification failed")
        for fold in ("fold_1", "fold_2", "fold_3", "fold_4"):
            anchor = pq.read_table(anchors[fold], columns=["flight_key", "y_arr_cls", "y_arr_reg"]).to_pandas()
            output = pq.read_table(root / _paths(method)[fold]).to_pandas()
            _assert_exact_anchor_parity(anchor, output, fold)
        for path, expected in preflight["baseline_immutable_sha256"].items():
            if _sha256(root / path) != expected:
                raise RuntimeError("baseline evidence changed during tuned OOF materialization")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--production", action="store_true")
    mode.add_argument("--recover-xgboost", action="store_true")
    args = parser.parse_args()
    root = resolve_project_root()
    if args.recover_xgboost:
        recovery = build_xgboost_recovery_preflight(root)
        write_json_artifact(root / XGB_RECOVERY_PREFLIGHT, recovery)
        protocol = load_week5_hpo_protocol_v1_1(project_root=root)
        inputs = load_tuned_method_inputs(root, protocol)
        result = run_xgboost_recovery_sequence(
            lambda method: run_tuned_method(root, recovery, inputs[method])
        )
        write_json_artifact(root / _paths("xgboost")["final"], result)
        verify_tuned_oof_outputs(root, recovery)
        _verify_recovery_immutability(root, recovery)
        _write_recovery_incident(root, recovery)
        print(json.dumps({"status": "PASS", "method": "xgboost"}, indent=2))
        return 0
    preflight = build_preflight(root)
    if args.preflight:
        print(json.dumps(preflight, indent=2, sort_keys=True)); return 0
    for method in METHODS:
        write_json_artifact(root / _paths(method)["preflight"], {**preflight, "current_method": method})
    protocol = load_week5_hpo_protocol_v1_1(project_root=root); inputs = load_tuned_method_inputs(root, protocol)
    for method in METHODS:
        result = run_tuned_method(root, preflight, inputs[method])
        write_json_artifact(root / _paths(method)["final"], result)
    verify_tuned_oof_outputs(root, preflight)
    print(json.dumps({"status": "PASS", "methods": list(METHODS)}, indent=2)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
