from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.data.access_guard import DataAccessDenied, assert_data_access_allowed
from src.data.load_aeolus import load_base_config
from src.data.temporal_protocol import FINAL_HOLDOUT_YEAR, MODEL_SELECTION_YEAR, ROLLING_DEVELOPMENT_YEARS


ROOT = Path(__file__).parents[1]


def _load(name: str) -> dict:
    return json.loads((ROOT / "artifacts" / "manifests" / name).read_text(encoding="utf-8"))


def test_rolling_folds_are_expanding_and_isolated() -> None:
    manifest = _load("temporal_folds_manifest.json")
    assert manifest["random_split_allowed"] is False
    for fold in manifest["rolling_folds"]:
        train_years = fold["train_years"]
        validation_year = fold["validation_year"]
        assert validation_year not in train_years
        assert validation_year > max(train_years)
        assert set(train_years + [validation_year]).issubset(ROLLING_DEVELOPMENT_YEARS)


def test_manifest_fold_schedule_matches_versioned_base_config() -> None:
    manifest = _load("temporal_folds_manifest.json")
    configured = load_base_config(project_root=ROOT)["temporal"]["rolling_folds"]["folds"]
    observed = [
        {
            "id": fold["id"],
            "train_years": fold["train_years"],
            "validation_year": fold["validation_year"],
        }
        for fold in manifest["rolling_folds"]
    ]
    assert observed == configured


def test_2023_and_2024_are_outside_rolling_folds() -> None:
    manifest = _load("temporal_folds_manifest.json")
    fold_years = {
        year
        for fold in manifest["rolling_folds"]
        for year in [*fold["train_years"], fold["validation_year"]]
    }
    assert MODEL_SELECTION_YEAR not in fold_years
    assert FINAL_HOLDOUT_YEAR not in fold_years


def test_manifest_roles_match_locked_protocol() -> None:
    manifest = _load("temporal_folds_manifest.json")
    roles = {entry["year"]: entry["role"] for entry in manifest["years"]}
    assert {year for year, role in roles.items() if role == "ROLLING_DEVELOPMENT"} == set(ROLLING_DEVELOPMENT_YEARS)
    assert roles[MODEL_SELECTION_YEAR] == "DEVELOPMENT_MODEL_SELECTION"
    assert roles[FINAL_HOLDOUT_YEAR] == "FINAL_HOLDOUT"


def test_manifests_match_processed_partitions() -> None:
    temporal = _load("temporal_folds_manifest.json")
    processed = _load("processed_data_manifest_v1.json")
    processed_by_year = {entry["year"]: entry for entry in processed["years"]}
    for entry in temporal["years"]:
        expected = processed_by_year[entry["year"]]
        assert entry["row_count"] == expected["source_rows"]
        assert entry["schema_version"] == expected["schema_version"]
        assert entry["processed_partitions"] == [
            {"flow": partition["flow"], "path": partition["path"], "row_count": partition["row_count"]}
            for partition in expected["partitions"]
        ]
        assert all((ROOT / partition["path"]).is_dir() for partition in entry["processed_partitions"])


def test_hpo_and_final_holdout_access_are_fail_closed() -> None:
    with pytest.raises(DataAccessDenied, match="HPO is blocked"):
        assert_data_access_allowed(2023, "hpo")
    with pytest.raises(DataAccessDenied, match="HPO is blocked"):
        assert_data_access_allowed(2024, "hpo")
    with pytest.raises(DataAccessDenied, match="sealed from development"):
        assert_data_access_allowed(2024, "development")
    with pytest.raises(DataAccessDenied, match="freeze manifest"):
        assert_data_access_allowed(2024, "final_evaluation")


def test_2024_access_log_is_manifest_backed_and_metadata_only() -> None:
    payload = _load("week2_2024_access_log.json")
    assert payload["year"] == 2024
    assert {entry["purpose"] for entry in payload["entries"]} == {
        "schema_audit", "canonicalize_holdout"
    }
    assert all(entry["allowed"] is True and entry["timestamp_utc"] for entry in payload["entries"])
    chain_entry = next(
        entry for entry in payload["entries"]
        if entry["operation"] == "flight_chain_container_audit_2024"
    )
    assert chain_entry["purpose"] == "schema_audit"
    assert chain_entry["evidence"].endswith("flight_chain_structure_audit_v1.json")
