"""Week 1/2, V4, Week 3A, and closed Week 3B metadata-only smoke test.

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
    "requirements.txt",
    "configs/base.yaml",
    "configs/reconstructed_chain_feature_policy.yaml",
    "configs/outlier_and_simulation_guard.yaml",
    "src/data/preprocessing.py",
    "src/data/weather_contract.py",
    "src/features/tabular_features.py",
    "src/data/flight_chain_reconstruction.py",
    "src/features/chain_feature_policy.py",
    "src/data/canonical_schedule_datetime_audit.py",
    "scripts/reconstruct_flight_chain.py",
    "scripts/audit_canonical_schedule_datetime.py",
    "scripts/smoke_week3a_preprocessing.py",
    "docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V3_DONG_BO.md",
    "docs/roadmap/02_Bo_cong_nghe_de_xuat_Aeolus_Gate_Optimization_V3_DONG_BO.md",
    "docs/roadmap/03_Chi_tiet_tung_tuan_Roadmap_Aeolus_Gate_Optimization_V3_DONG_BO.md",
    "docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md",
    "docs/roadmap/02_Bo_cong_nghe_de_xuat_Aeolus_Gate_Optimization_V4_DONG_BO.md",
    "docs/roadmap/03_Chi_tiet_tung_tuan_Roadmap_Aeolus_Gate_Optimization_V4_DONG_BO.md",
    "docs/decisions/decision_registry.md",
    "docs/decisions/decision_include_chain.md",
    "docs/decisions/decision_dual_prediction_architecture_v4.md",
    "docs/dataset_audit/data_inventory.md",
    "docs/dataset_audit/schema_audit_plan.md",
    "docs/dataset_audit/schema_compatibility_matrix.md",
    "docs/dataset_audit/canonical_schema_v1.md",
    "docs/dataset_audit/data_dictionary_v0.md",
    "docs/dataset_audit/data_dictionary_v1.md",
    "docs/dataset_audit/leakage_audit.md",
    "docs/dataset_audit/weather_timing_audit.md",
    "docs/dataset_audit/point_in_time_weather_plan_v1.md",
    "docs/dataset_audit/weather_point_in_time_contract_v1.md",
    "docs/dataset_audit/reconstructed_chain_feature_availability_plan_v1.md",
    "docs/dataset_audit/reconstructed_chain_feature_availability_audit_v1.md",
    "docs/dataset_audit/flight_chain_feasibility_v0.md",
    "docs/dataset_audit/flight_chain_feasibility_report.md",
    "docs/dataset_audit/flight_chain_reconstruction_report.md",
    "docs/dataset_audit/canonical_schedule_datetime_representation_audit.md",
    "artifacts/manifests/flight_chain_reconstructed_smoke_manifest_v1.json",
    "artifacts/manifests/canonical_schedule_datetime_representation_audit_v1.json",
    "artifacts/manifests/canonical_schema_v1.json",
    "artifacts/manifests/processed_data_manifest_v1.json",
    "artifacts/manifests/temporal_folds_manifest.json",
    "artifacts/manifests/split_manifest.json",
    "artifacts/manifests/week2_2024_access_log.json",
    "artifacts/manifests/feature_manifest_arrival_v1.json",
    "artifacts/manifests/feature_pipeline_registry_arrival_v1.json",
    "artifacts/manifests/reconstructed_chain_feature_availability_audit_v1.json",
    "artifacts/manifests/weather_point_in_time_contract_v1.json",
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
    arrival = config["prediction"]["arrival_core"]
    require(
        arrival["role"] == "core"
        and arrival["flow"] == "inbound"
        and arrival["filter"] == "DEST=ATL",
        "Core Arrival flow contract mismatch",
    )
    require(
        arrival["classification"]
        == {
            "target": "ARR_DELAY",
            "label_name": "y_arr_cls",
            "threshold_minutes": 15,
        },
        "Core Arrival classification contract mismatch",
    )
    require(
        arrival["regression"]
        == {
            "enabled": True,
            "target": "ARR_DELAY",
            "label_name": "y_arr_reg",
            "signed": True,
        },
        "Core Arrival regression contract mismatch",
    )
    require(
        arrival["weather"]
        == {"allowed": False, "aeolus_raw_policy": "drop"},
        "Core Arrival Weather must remain disabled with raw Aeolus DROP",
    )
    require(
        arrival["reconstructed_chain"]["artifact_version"]
        == "schedule_chain_v1"
        and arrival["reconstructed_chain"]["allowed_for_ablation"] is True
        and arrival["reconstructed_chain"]["enabled_by_default"] is False,
        "Core Arrival reconstructed Chain ablation contract mismatch",
    )
    departure = config["prediction"]["departure_auxiliary"]
    require(
        departure["role"] == "auxiliary"
        and departure["flow"] == "outbound"
        and departure["filter"] == "ORIGIN=ATL",
        "Auxiliary Departure flow contract mismatch",
    )
    require(
        departure["classification"]
        == {
            "target": "DEP_DELAY",
            "label_name": "y_dep_cls",
            "threshold_minutes": 15,
        }
        and departure["regression"] == {"enabled": False},
        "Auxiliary Departure target contract mismatch",
    )
    require(
        departure["weather"]["aeolus_raw_policy"] == "drop"
        and departure["weather"]["point_in_time_source"]
        == {
            "artifact_version": "weather_point_in_time_v1",
            "contract_version": "weather_point_in_time_contract_v1",
            "contract_path": "artifacts/manifests/weather_point_in_time_contract_v1.json",
            "provider": "TBD",
            "status": "audit_required",
            "enabled": False,
            "row_parity_required": True,
        },
        "Auxiliary point-in-time Weather must remain audit-required and disabled",
    )
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
        config["flows"]["inbound"]["role"] == "core_arrival_ml"
        and config["flows"]["outbound"]["role"]
        == ["auxiliary_departure_ml", "synthetic_turn_simulation"],
        "Inbound/outbound V4 roles mismatch",
    )
    require(
        config["simulation"]["prediction_source_task"] == "arrival_core"
        and config["simulation"]["auxiliary_departure_prediction_allowed"]
        is False,
        "Only Core Arrival prediction may feed downstream simulation",
    )
    raw_chain = config["flight_chain"]["raw"]
    require(
        raw_chain
        == {
            "status": "final_no_go",
            "enabled_by_default": False,
            "include_in_core": False,
            "ablation": False,
        },
        "Original raw Flight Chain state mismatch",
    )
    reconstructed = config["flight_chain"]["reconstructed"]
    require(
        reconstructed["version"] == "schedule_chain_v1"
        and reconstructed["status"] == "go_for_ablation"
        and reconstructed["enabled_by_default"] is False
        and reconstructed["include_in_core"] is False
        and reconstructed["ablation"] is True
        and reconstructed["ablation_week"] == 6
        and reconstructed["source"] == "canonical_tabular"
        and reconstructed["physical_aircraft_identity"] is False,
        "Reconstructed schedule Flight Chain contract mismatch",
    )
    feature_engineering = reconstructed["feature_engineering"]
    require(
        feature_engineering
        == {
            "policy_version": "reconstructed_chain_feature_availability_v1",
            "policy_path": "configs/reconstructed_chain_feature_policy.yaml",
            "audit_status": "completed",
            "audit_result_version": "reconstructed_chain_feature_availability_audit_v1",
            "audit_result_path": "artifacts/manifests/reconstructed_chain_feature_availability_audit_v1.json",
            "ml_enabled": False,
            "arr_b_enabled": False,
            "keep_safe_feature_count": 0,
            "diagnostic_materialization_allowed": True,
            "diagnostic_materialization_executed": False,
            "ml_materialization_allowed": False,
            "ml_branch_status": "blocked_pending_new_evidence",
            "closure_status": "completed_with_blocked_ml_branch",
            "availability_gate_required": True,
        },
        "Reconstructed Chain feature availability gate mismatch",
    )
    policy = yaml.safe_load(
        (ROOT / feature_engineering["policy_path"]).read_text(encoding="utf-8")
    )
    require(
        policy["policy_version"] == feature_engineering["policy_version"]
        and policy["source_artifact"] == "schedule_chain_v1"
        and policy["current_status"] == "AUDIT_COMPLETE"
        and policy["audit_result"] == "NO_KEEP_SAFE_FEATURES"
        and policy["ml_enabled"] is False
        and policy["arr_b_enabled"] is False
        and policy["keep_safe_feature_count"] == 0
        and policy["diagnostic_materialization_allowed"] is True
        and policy["diagnostic_materialization_executed"] is False
        and policy["ml_materialization_allowed"] is False
        and policy["ml_branch_status"] == "BLOCKED_PENDING_NEW_EVIDENCE"
        and policy["closure_status"] == "COMPLETED_WITH_BLOCKED_ML_BRANCH"
        and policy["availability_gate_required"] is True
        and policy["prediction_cutoff_hours_before_target_crs_dep"] == 2
        and policy["groups"]["target_or_position_local"]["status"]
        == "REVIEW_REQUIRED"
        and policy["groups"]["past_context"]["status"] == "REVIEW_REQUIRED"
        and policy["groups"]["future_or_full_chain"]["status"]
        == "BLOCKED_UNTIL_PROVEN"
        and "is_single_leg_chain"
        in policy["groups"]["future_or_full_chain"]["features"]
        and "is_single_leg_chain"
        not in policy["groups"]["target_or_position_local"]["features"]
        and policy["groups"]["identifiers"]["status"] == "IDENTIFIER_ONLY",
        "Reconstructed Chain feature policy must remain conservative and disabled",
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


def validate_week3a_contracts() -> None:
    feature = load_json("artifacts/manifests/feature_manifest_arrival_v1.json")
    pipelines = load_json(
        "artifacts/manifests/feature_pipeline_registry_arrival_v1.json"
    )
    guard = yaml.safe_load(
        (ROOT / "configs" / "outlier_and_simulation_guard.yaml").read_text(
            encoding="utf-8"
        )
    )
    require(feature["task"] == "arrival_core", "Week 3A task mismatch")
    require(feature["target_filter"] == "DEST=ATL", "Week 3A flow mismatch")
    require(
        feature["prediction_cutoff"] == "CRS_DEP_TIME - 2 hours",
        "Week 3A cutoff mismatch",
    )
    require(
        feature["weather_policy"]
        == {"arrival_allowed": False, "aeolus_raw": "DROP", "external": "NOT_ALLOWED"},
        "Week 3A Weather boundary mismatch",
    )
    require(
        feature["chain_policy"]["included_in_base_matrix"] is False
        and feature["chain_policy"]["arr_b_enabled"] is False,
        "Week 3A must not enable reconstructed Chain features",
    )
    require(
        feature["fit_boundary"] == "EACH_FOLD_TRAIN_ROWS_ONLY",
        "Week 3A preprocessing fit scope mismatch",
    )
    require(
        set(pipelines["pipelines"])
        == {"linear", "tree", "boosting_future_tree"}
        and all(
            entry["estimator"] is None
            and entry["fit_scope"] == "EACH_FOLD_TRAIN_ROWS_ONLY"
            for entry in pipelines["pipelines"].values()
        ),
        "Week 3A registry must contain transformer-only fold-safe pipelines",
    )
    require(
        guard["ml_ground_truth"]["signed"] is True
        and guard["ml_ground_truth"]["absolute_value"] is False
        and guard["ml_ground_truth"]["clip_ground_truth"] is False,
        "Week 3A signed ground-truth guard mismatch",
    )


def validate_week3b0_contracts() -> None:
    """Validate small Week 3B evidence and fail-closed closure metadata."""
    audit = load_json(
        "artifacts/manifests/reconstructed_chain_feature_availability_audit_v1.json"
    )
    policy = yaml.safe_load(
        (ROOT / "configs" / "reconstructed_chain_feature_policy.yaml").read_text(
            encoding="utf-8"
        )
    )
    require(
        audit["audit_status"] == "COMPLETED"
        and audit["audit_decision"] == "NO_KEEP_SAFE_FEATURES_YET"
        and audit["summary_counts"]
        == {
            "KEEP_SAFE": 0,
            "REVIEW_REQUIRED": 7,
            "BLOCKED_UNTIL_PROVEN": 11,
            "DROP": 0,
            "IDENTIFIER_ONLY": 4,
        },
        "Week 3B.0 conservative audit outcome mismatch",
    )
    policy_statuses = {
        feature_name: group["status"]
        for group in policy["groups"].values()
        for feature_name in group["features"]
    }
    audit_statuses = {
        feature_name: result["final_status"]
        for feature_name, result in audit["feature_results"].items()
    }
    audit_statuses.update(
        {name: "IDENTIFIER_ONLY" for name in audit["identifier_only_fields"]}
    )
    require(
        policy_statuses == audit_statuses,
        "Week 3B.0 audit manifest and feature policy disagree",
    )
    require(
        audit["approved_keep_safe_features"] == []
        and audit["ml_enablement"] is False
        and audit["arr_b_enabled"] is False
        and audit["diagnostic_materialization_allowed"] is True
        and audit["ml_materialization_allowed"] is False
        and audit["ml_branch_status"] == "BLOCKED_PENDING_NEW_EVIDENCE",
        "Week 3B.0 ML/diagnostic boundary mismatch",
    )
    require(
        audit["external_evidence_used"] is False
        and audit["schedule_publication_snapshot_evidence_found"] is False
        and audit["2023_performance_used"] is False
        and audit["2024_accessed"] is False
        and audit["model_result_used"] is False
        and audit["feature_artifact_generated"] is False
        and audit["reconstruction_modified"] is False
        and audit["raw_pt_opened"] is False,
        "Week 3B.0 audit safety flags mismatch",
    )
    require(
        policy["substage_disposition"]
        == {
            "3B.0": "COMPLETED_PASS",
            "3B.1": "SKIPPED_NOT_REQUIRED_FOR_ML",
            "3B.2": "COMPLETED_THROUGH_E006",
            "3B.3": "SKIPPED_OPTIONAL_DIAGNOSTIC",
            "3B.4": "COMPLETED_PASS",
        }
        and policy["materialization_decision"]
        == {
            "status": "SKIPPED_OPTIONAL_DIAGNOSTIC",
            "reason": "NO_KEEP_SAFE_FEATURES",
        },
        "Week 3B closure disposition mismatch",
    )
    require(
        not (ROOT / "src" / "features" / "reconstructed_chain_features.py").exists()
        and not (
            ROOT / "data" / "processed" / "reconstructed_chain_features_v1"
        ).exists(),
        "Week 3B closure must not create reconstructed feature code/artifacts",
    )


def validate_week3c_contract() -> None:
    """Validate the small Week 3C template without reading Weather data."""

    contract = load_json(
        "artifacts/manifests/weather_point_in_time_contract_v1.json"
    )
    require(
        contract["contract_version"] == "weather_point_in_time_contract_v1"
        and contract["task"] == "departure_auxiliary"
        and contract["provider"] == "TBD"
        and contract["audit_status"] == "AUDIT_REQUIRED"
        and contract["enabled"] is False,
        "Week 3C external Weather must remain TBD, audit-required, and disabled",
    )
    require(
        set(contract["audit_gates"]) == {f"W{index}" for index in range(1, 16)}
        and all(gate["critical"] for gate in contract["audit_gates"].values()),
        "Week 3C W1-W15 gates must all be critical",
    )
    require(
        contract["join_rules"]["availability_condition"]
        == "available_time <= target_prediction_cutoff"
        and contract["join_rules"]["valid_time_alone_is_sufficient"] is False
        and contract["row_parity_required"] is True,
        "Week 3C availability-first join or DEP row parity mismatch",
    )
    require(
        contract["raw_aeolus_weather_allowed"] is False
        and contract["core_arrival_weather_allowed"] is False
        and contract["feeds_optimizer"] is False
        and contract["2024_accessed"] is False,
        "Week 3C Weather boundary or 2024 guard mismatch",
    )


def validate_imports_and_holdout_guard() -> None:
    for package_name in (
        "src.data",
        "src.features",
        "src.features.chain_feature_policy",
        "src.features.tabular_features",
        "src.data.preprocessing",
        "src.data.weather_contract",
        "sklearn",
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
    validate_week3a_contracts()
    validate_week3b0_contracts()
    validate_week3c_contract()
    validate_imports_and_holdout_guard()
    print("SMOKE_TEST: PASS")
    print(
        "Checked preserved Week-1/2 artifacts, V4 dual-task config/docs, "
        "feature-availability audit/Week 3B closure, Week 3A transformer contracts/manifests, "
        "Week 3C point-in-time Weather contract, metadata-only inventories/manifests, "
        "imports, and 2024 guard."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
