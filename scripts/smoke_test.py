"""Week 1/2 metadata-only reproducibility smoke test.

This script validates project scaffolding, configuration, filesystem inventory, package
imports, Week-2 manifests, and the sealed 2024 development guard. It never reads CSV
or Parquet rows and never loads PyTorch tensors.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


YEARS = tuple(range(2016, 2025))
REQUIRED_DIRECTORIES = (
    "configs",
    "data/raw/tabular",
    "data/raw/chain",
    "data/processed",
    "data/processed/tabular_by_year",
    "data/processed/inbound_atl",
    "data/processed/outbound_atl",
    "data/simulation",
    "docs/roadmap",
    "docs/decisions",
    "docs/dataset_audit",
    "docs/experiments",
    "docs/thesis_notes",
    "notebooks",
    "scripts",
    "src",
    "dashboard",
    "tests",
    "reports",
    "artifacts",
    "results",
)
REQUIRED_FILES = (
    ".gitignore",
    "README.md",
    "project_structure.md",
    "configs/base.yaml",
    "docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V3_DONG_BO.md",
    "docs/roadmap/02_Bo_cong_nghe_de_xuat_Aeolus_Gate_Optimization_V3_DONG_BO.md",
    "docs/roadmap/03_Chi_tiet_tung_tuan_Roadmap_Aeolus_Gate_Optimization_V3_DONG_BO.md",
    "docs/decisions/decision_registry.md",
    "docs/decisions/decision_include_chain.md",
    "docs/dataset_audit/data_inventory.md",
    "docs/dataset_audit/schema_audit_plan.md",
    "docs/dataset_audit/schema_compatibility_matrix.md",
    "docs/dataset_audit/canonical_schema_v1.md",
    "docs/dataset_audit/data_dictionary_v0.md",
    "docs/dataset_audit/data_dictionary_v1.md",
    "docs/dataset_audit/leakage_audit.md",
    "docs/dataset_audit/weather_timing_audit.md",
    "docs/dataset_audit/flight_chain_feasibility_v0.md",
    "docs/dataset_audit/flight_chain_feasibility_report.md",
    "artifacts/manifests/canonical_schema_v1.json",
    "artifacts/manifests/processed_data_manifest_v1.json",
    "artifacts/manifests/temporal_folds_manifest.json",
    "artifacts/manifests/split_manifest.json",
    "artifacts/manifests/week2_2024_access_log.json",
    "docs/thesis_notes/assumptions.md",
    "docs/thesis_notes/limitations.md",
    "docs/experiments/experiment_log.md",
)
EXPECTED_METHODS = [
    "linear",
    "random_forest",
    "hist_gradient_boosting",
    "xgboost",
    "weighted_ensemble",
]


def require(condition: bool, message: str) -> None:
    """Raise an actionable failure without accessing raw-data content."""
    if not condition:
        raise AssertionError(message)


def load_config() -> dict[str, Any]:
    """Parse the small YAML configuration only."""
    config_path = ROOT / "configs" / "base.yaml"
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    require(isinstance(payload, dict), "configs/base.yaml must parse to a mapping")
    return payload


def load_json(relative_path: str) -> dict[str, Any]:
    """Parse a small machine-readable manifest without touching data rows."""
    payload = json.loads((ROOT / relative_path).read_text(encoding="utf-8"))
    require(isinstance(payload, dict), f"{relative_path} must parse to a mapping")
    return payload


def validate_structure() -> None:
    for relative_path in REQUIRED_DIRECTORIES:
        require((ROOT / relative_path).is_dir(), f"Missing directory: {relative_path}")
    for relative_path in REQUIRED_FILES:
        require((ROOT / relative_path).is_file(), f"Missing file: {relative_path}")


def validate_config(config: dict[str, Any]) -> None:
    require(config["data"]["hub"] == "ATL", "Hub must be ATL")
    require(config["data"]["years"] == "2016-2024", "Data years must be 2016-2024")
    require(
        config["data"]["raw_tabular_path"] == "data/raw/tabular",
        "Raw Tabular path is incorrect",
    )
    require(
        config["data"]["raw_chain_path"] == "data/raw/chain",
        "Raw Chain path is incorrect",
    )
    require(
        config["prediction"]["cutoff_hours_before_crs_dep"] == 2,
        "Prediction cut-off must be 2 hours",
    )
    require(
        config["prediction"]["classification_threshold_minutes"] == 15,
        "Classification threshold must be 15 minutes",
    )
    require(config["prediction"]["regression_target"] == "ARR_DELAY", "Target mismatch")
    require(config["prediction"]["signed_regression"] is True, "Target must be signed")
    require(
        config["temporal"]["development_years"] == "2016-2022",
        "Development years mismatch",
    )
    require(
        config["temporal"]["model_selection_year"] == 2023,
        "Model-selection year must be 2023",
    )
    require(
        config["temporal"]["final_holdout_year"] == 2024,
        "Final holdout must be 2024",
    )
    require(config["models"]["core_methods"] == EXPECTED_METHODS, "Core method list mismatch")
    require(
        config["flight_chain"]
        == {
            "enabled_by_default": False,
            "status": "no_go",
            "include_in_core": False,
            "week6_ablation": False,
        },
        "Flight Chain default state mismatch",
    )


def validate_raw_inventory() -> None:
    tabular_root = ROOT / "data" / "raw" / "tabular"
    chain_root = ROOT / "data" / "raw" / "chain"

    tabular_files = list(tabular_root.rglob("*.csv"))
    require(len(tabular_files) == 9, f"Expected 9 Tabular CSV files, found {len(tabular_files)}")

    chain_files = list(chain_root.rglob("*.pt"))
    require(len(chain_files) == 27, f"Expected 27 Chain PT files, found {len(chain_files)}")

    for year in YEARS:
        tabular_file = tabular_root / str(year) / f"flight_with_weather_{year}.csv"
        require(tabular_file.is_file(), f"Missing Tabular file: {tabular_file.relative_to(ROOT)}")

        year_chain_dir = chain_root / str(year)
        year_chain_files = list(year_chain_dir.glob("*.pt"))
        require(year_chain_dir.is_dir(), f"Missing Chain year directory: {year_chain_dir.relative_to(ROOT)}")
        require(len(year_chain_files) == 3, f"Expected 3 Chain files for {year}")
        split_names = {"train", "val", "test"}
        observed_splits = {
            split
            for split in split_names
            if any(split in file_path.name.lower() for file_path in year_chain_files)
        }
        require(observed_splits == split_names, f"Missing filename-inferred Chain split for {year}")
        require(
            all(str(year) in file_path.name for file_path in year_chain_files),
            f"Chain filename year mismatch for {year}",
        )


def validate_week2_manifests() -> None:
    canonical = load_json("artifacts/manifests/canonical_schema_v1.json")
    processed = load_json("artifacts/manifests/processed_data_manifest_v1.json")
    temporal = load_json("artifacts/manifests/temporal_folds_manifest.json")
    split = load_json("artifacts/manifests/split_manifest.json")
    access_log = load_json("artifacts/manifests/week2_2024_access_log.json")

    expected_years = list(YEARS)
    require(canonical["canonical_schema_version"] == "v1", "Canonical schema must be v1")
    require(canonical["audit_basis"]["years"] == expected_years, "Canonical audit must cover 2016-2024")
    require(len(canonical["column_order"]) == 34, "Canonical schema must contain 34 ordered fields")
    require(len(canonical["fields"]) == 34, "Canonical field metadata is incomplete")

    processed_by_year = {item["year"]: item for item in processed["years"]}
    require(sorted(processed_by_year) == expected_years, "Processed manifest years mismatch")
    require(processed["schema_version"] == "v1", "Processed manifest schema mismatch")
    for year in YEARS:
        item = processed_by_year[year]
        expected_role = "FINAL_HOLDOUT" if year == 2024 else "DEVELOPMENT"
        require(item["role"] == expected_role, f"Processed role mismatch for {year}")
        by_flow = {partition["flow"]: partition for partition in item["partitions"]}
        for flow in ("tabular_by_year", "inbound_atl", "outbound_atl"):
            require(flow in by_flow, f"Missing {flow} manifest partition for {year}")
            partition_path = ROOT / by_flow[flow]["path"]
            require(partition_path.is_dir(), f"Missing processed partition: {by_flow[flow]['path']}")
            require(any(partition_path.glob("*.parquet")), f"No Parquet part in {by_flow[flow]['path']}")
        require(by_flow["tabular_by_year"]["row_count"] == item["source_rows"], f"Canonical rows mismatch for {year}")
        require(by_flow["inbound_atl"]["row_count"] <= item["source_rows"], f"Inbound rows exceed source for {year}")
        require(by_flow["outbound_atl"]["row_count"] <= item["source_rows"], f"Outbound rows exceed source for {year}")

    temporal_by_year = {item["year"]: item for item in temporal["years"]}
    require(temporal["manifest_version"] == "v1", "Temporal manifest must be v1")
    require(temporal["random_split_allowed"] is False, "Random split must be disabled")
    require(sorted(temporal_by_year) == expected_years, "Temporal manifest years mismatch")
    require(all(temporal_by_year[year]["role"] == "ROLLING_DEVELOPMENT" for year in range(2016, 2023)), "2016-2022 temporal roles mismatch")
    require(temporal_by_year[2023]["role"] == "DEVELOPMENT_MODEL_SELECTION", "2023 role mismatch")
    require(temporal_by_year[2024]["role"] == "FINAL_HOLDOUT", "2024 role mismatch")
    require(not temporal_by_year[2023]["fold_membership"], "2023 must remain outside rolling folds")
    require(not temporal_by_year[2024]["fold_membership"], "2024 must remain outside development folds")

    require(split["random_split_allowed"] is False, "Split manifest permits random split")
    require(split["hpo_policy"]["blocked_years"] == [2023, 2024], "HPO block years mismatch")
    require(split["final_evaluation_policy"]["currently_allowed"] is False, "2024 final evaluation must remain blocked pre-freeze")
    require(access_log["year"] == 2024, "Access log must describe 2024 structural access")
    require(bool(access_log["entries"]), "2024 access log is empty")
    require(all(entry["allowed"] is True for entry in access_log["entries"]), "Access log contains a failed or malformed entry")
    require(all(entry["purpose"] in {"schema_audit", "canonicalize_holdout"} for entry in access_log["entries"]), "Access log contains a development/performance purpose")

    for year in YEARS:
        require(
            (ROOT / "artifacts" / "manifests" / "schema_audit" / f"schema_{year}.json").is_file(),
            f"Missing schema audit report for {year}",
        )


def validate_imports_and_holdout_guard() -> None:
    for package_name in (
        "src.data",
        "src.features",
        "src.models",
        "src.simulation",
        "src.optimization",
        "src.evaluation",
    ):
        importlib.import_module(package_name)

    from src.data.access_guard import DataAccessDenied, assert_data_access_allowed

    try:
        assert_data_access_allowed(2024, "development")
    except DataAccessDenied:
        return
    raise AssertionError("2024 development access was not blocked")


def main() -> int:
    validate_structure()
    config = load_config()
    validate_config(config)
    validate_raw_inventory()
    validate_week2_manifests()
    validate_imports_and_holdout_guard()
    print("SMOKE_TEST: PASS")
    print("Checked Week-1/2 structure, config, metadata-only inventories/manifests, imports, and 2024 guard.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
