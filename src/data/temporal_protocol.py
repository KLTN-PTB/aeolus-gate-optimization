"""Locked temporal roles and manifest generation for Aeolus development."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

from src.data.load_aeolus import load_base_config, resolve_project_root


TEMPORAL_PROTOCOL_VERSION: Final = "v1"
ROLLING_DEVELOPMENT_YEARS: Final = tuple(range(2016, 2023))
MODEL_SELECTION_YEAR: Final = 2023
FINAL_HOLDOUT_YEAR: Final = 2024
ROLE_BY_YEAR: Final = {
    **{year: "ROLLING_DEVELOPMENT" for year in ROLLING_DEVELOPMENT_YEARS},
    MODEL_SELECTION_YEAR: "DEVELOPMENT_MODEL_SELECTION",
    FINAL_HOLDOUT_YEAR: "FINAL_HOLDOUT",
}


def role_for_year(year: int) -> str:
    """Return the locked temporal role and reject years outside Aeolus scope."""
    try:
        return ROLE_BY_YEAR[year]
    except KeyError as error:
        raise ValueError(f"Unsupported temporal year: {year}") from error


def _rolling_folds(config: dict[str, Any]) -> list[dict[str, Any]]:
    temporal = config.get("temporal", {})
    rolling = temporal.get("rolling_folds", {}) if isinstance(temporal, dict) else {}
    folds = rolling.get("folds") if isinstance(rolling, dict) else None
    if not isinstance(folds, list) or not folds:
        raise ValueError("configs/base.yaml must define temporal.rolling_folds.folds")

    normalized: list[dict[str, Any]] = []
    for raw_fold in folds:
        if not isinstance(raw_fold, dict):
            raise ValueError("Each rolling fold must be a mapping")
        fold_id = raw_fold.get("id")
        train_years = raw_fold.get("train_years")
        validation_year = raw_fold.get("validation_year")
        if not isinstance(fold_id, str) or not isinstance(train_years, list) or not isinstance(validation_year, int):
            raise ValueError("Each rolling fold requires id, train_years, validation_year")
        if not train_years or not all(isinstance(year, int) for year in train_years):
            raise ValueError(f"Fold {fold_id} must contain integer train_years")
        if len(set(train_years)) != len(train_years) or validation_year in train_years:
            raise ValueError(f"Fold {fold_id} has overlapping train/validation years")
        if validation_year <= max(train_years):
            raise ValueError(f"Fold {fold_id} validation must be later than every train year")
        if set(train_years + [validation_year]).difference(ROLLING_DEVELOPMENT_YEARS):
            raise ValueError(f"Fold {fold_id} must remain within 2016-2022")
        normalized.append(
            {
                "id": fold_id,
                "train_years": train_years,
                "validation_year": validation_year,
                "allowed_operations": [
                    "preprocessing_fit_in_fold",
                    "ml_train",
                    "hpo",
                    "calibration_development",
                    "oof_generation",
                ],
                "forbidden_operations": ["random_split", "use_2023", "use_2024"],
            }
        )
    return normalized


def _operations_for_role(role: str) -> tuple[list[str], list[str]]:
    if role == "ROLLING_DEVELOPMENT":
        return (
            ["schema", "preprocessing_fit_in_fold", "ml_train", "hpo", "calibration_development", "oof"],
            ["random_split", "cross_fold_preprocessing_fit", "use_2023_for_hpo", "use_2024"],
        )
    if role == "DEVELOPMENT_MODEL_SELECTION":
        return (
            ["transform_later", "evaluate_later", "model_selection_later", "simulation_optimization_development_later"],
            ["hpo", "calibration_fit", "ensemble_weight_optimization", "random_split", "use_2024"],
        )
    if role == "FINAL_HOLDOUT":
        return (
            ["schema_audit", "canonicalize_holdout"],
            ["model_fit", "hpo", "feature_selection_by_performance", "model_selection", "simulation_parameter_tuning", "optimization_tuning", "final_evaluation_before_system_freeze"],
        )
    raise ValueError(f"Unknown temporal role: {role}")


def _partition_view(entry: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "flow": partition["flow"],
            "path": partition["path"],
            "row_count": partition["row_count"],
        }
        for partition in entry["partitions"]
    ]


def build_temporal_manifests(*, project_root: Path | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build canonical temporal manifests from existing processed-data metadata only."""
    root = resolve_project_root(project_root)
    config = load_base_config(project_root=root)
    processed_path = root / "artifacts" / "manifests" / "processed_data_manifest_v1.json"
    processed = json.loads(processed_path.read_text(encoding="utf-8"))
    rolling_folds = _rolling_folds(config)
    generated_at = datetime.now(timezone.utc).isoformat()
    expected_years = set(ROLE_BY_YEAR)
    entries = processed.get("years", [])
    if {entry.get("year") for entry in entries} != expected_years:
        raise ValueError("Processed-data manifest does not contain exactly 2016-2024")

    memberships: dict[int, list[dict[str, str]]] = {year: [] for year in ROLE_BY_YEAR}
    for fold in rolling_folds:
        for year in fold["train_years"]:
            memberships[year].append({"fold_id": fold["id"], "set": "train"})
        memberships[fold["validation_year"]].append({"fold_id": fold["id"], "set": "validation"})

    years: list[dict[str, Any]] = []
    for entry in sorted(entries, key=lambda item: item["year"]):
        year = int(entry["year"])
        role = role_for_year(year)
        allowed, forbidden = _operations_for_role(role)
        partitions = _partition_view(entry)
        if any(not (root / partition["path"]).is_dir() for partition in partitions):
            raise FileNotFoundError(f"A processed partition is missing for {year}")
        years.append(
            {
                "year": year,
                "role": role,
                "fold_membership": memberships[year],
                "processed_partitions": partitions,
                "schema_version": entry["schema_version"],
                "row_count": entry["source_rows"],
                "allowed_operations": allowed,
                "forbidden_operations": forbidden,
            }
        )

    schema_version = str(processed["schema_version"])
    config_version = str(config["project"]["version"])
    folds_manifest = {
        "manifest_version": TEMPORAL_PROTOCOL_VERSION,
        "generated_at_utc": generated_at,
        "implementation_decision": "I003 / expanding_window_v1",
        "schema_version": schema_version,
        "config_version": config_version,
        "random_split_allowed": False,
        "rolling_folds": rolling_folds,
        "years": years,
    }
    split_manifest = {
        "manifest_version": TEMPORAL_PROTOCOL_VERSION,
        "generated_at_utc": generated_at,
        "canonical_temporal_manifest": "artifacts/manifests/temporal_folds_manifest.json",
        "schema_version": schema_version,
        "config_version": config_version,
        "random_split_allowed": False,
        "temporal_roles": years,
        "hpo_policy": {
            "allowed_years": list(ROLLING_DEVELOPMENT_YEARS),
            "blocked_years": [MODEL_SELECTION_YEAR, FINAL_HOLDOUT_YEAR],
        },
        "final_evaluation_policy": {
            "year": FINAL_HOLDOUT_YEAR,
            "requires": "artifacts/manifests/system_freeze_manifest.json with freeze_status=FROZEN",
            "currently_allowed": False,
        },
    }
    output_root = root / "artifacts" / "manifests"
    (output_root / "temporal_folds_manifest.json").write_text(
        json.dumps(folds_manifest, indent=2) + "\n", encoding="utf-8"
    )
    (output_root / "split_manifest.json").write_text(
        json.dumps(split_manifest, indent=2) + "\n", encoding="utf-8"
    )
    return folds_manifest, split_manifest


def build_week2_2024_access_log(*, project_root: Path | None = None) -> dict[str, Any]:
    """Create an evidence-backed, metadata-only log of known Week-2 2024 access."""
    root = resolve_project_root(project_root)
    manifest_root = root / "artifacts" / "manifests"
    schema_report_path = manifest_root / "schema_audit" / "schema_2024.json"
    index_audit = json.loads((manifest_root / "airport_index_mapping_audit.json").read_text(encoding="utf-8"))
    processed = json.loads((manifest_root / "processed_data_manifest_v1.json").read_text(encoding="utf-8"))
    holdout = next(entry for entry in processed["years"] if entry["year"] == FINAL_HOLDOUT_YEAR)
    chain_audit_path = manifest_root / "flight_chain_structure_audit_v1.json"
    entries = [
        {
            "operation": "schema_audit_2024",
            "purpose": "schema_audit",
            "timestamp_utc": datetime.fromtimestamp(
                schema_report_path.stat().st_mtime, tz=timezone.utc
            ).isoformat(),
            "allowed": True,
            "reason": "Structural/data-quality audit only; no model-development decision.",
            "evidence": "filesystem metadata for artifacts/manifests/schema_audit/schema_2024.json",
        },
        {
            "operation": "airport_index_mapping_audit_2024",
            "purpose": "schema_audit",
            "timestamp_utc": index_audit["generated_at_utc"],
            "allowed": True,
            "reason": "Streaming schema-only airport-code/index mapping audit.",
            "evidence": "artifacts/manifests/airport_index_mapping_audit.json",
        },
        {
            "operation": "materialize_canonical_holdout_2024",
            "purpose": "canonicalize_holdout",
            "timestamp_utc": holdout["created_at_utc"],
            "allowed": True,
            "reason": "Sealed canonical/ATL partition materialization; no model fit, HPO, or performance access.",
            "evidence": "artifacts/manifests/processed_data_manifest_v1.json",
        },
    ]
    if chain_audit_path.is_file():
        chain_audit = json.loads(chain_audit_path.read_text(encoding="utf-8"))
        chain_2024_reports = [
            report for report in chain_audit.get("reports", []) if report.get("year") == FINAL_HOLDOUT_YEAR
        ]
        if len(chain_2024_reports) != 3 or any(
            report.get("storage_payload_bytes_read") != 0 for report in chain_2024_reports
        ):
            raise ValueError("2024 Flight Chain audit evidence is incomplete or read tensor payload")
        entries.append(
            {
                "operation": "flight_chain_container_audit_2024",
                "purpose": "schema_audit",
                "timestamp_utc": chain_audit["generated_at_utc"],
                "allowed": True,
                "reason": "Archive/container structure only; tensor payload and model performance were not read.",
                "evidence": "artifacts/manifests/flight_chain_structure_audit_v1.json",
            }
        )
    payload = {
        "log_version": "v1",
        "scope": "Known Week-2 2024 raw/processed data accesses reconstructed from generated manifests.",
        "policy_note": "New access-guard decisions are timestamped by project logging; this file preserves the manifest-backed historical record before persistent access-log output existed.",
        "year": FINAL_HOLDOUT_YEAR,
        "entries": entries,
    }
    (manifest_root / "week2_2024_access_log.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    return payload
