from __future__ import annotations

import json
from pathlib import Path

import yaml

from src.features.tabular_features import (
    APPROVED_PREDICTOR_COLUMNS,
    CATEGORICAL_FEATURE_COLUMNS,
    DERIVED_FEATURE_COLUMNS,
    HIGH_CARDINALITY_FEATURE_COLUMNS,
    NUMERIC_FEATURE_COLUMNS,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_ROOT = ROOT / "artifacts" / "manifests"


def _json(name: str) -> dict:
    return json.loads((MANIFEST_ROOT / name).read_text(encoding="utf-8"))


def test_arrival_feature_manifest_matches_code_and_locked_contract() -> None:
    manifest = _json("feature_manifest_arrival_v1.json")

    assert manifest["manifest_version"] == "feature_manifest_arrival_v1"
    assert manifest["task"] == "arrival_core"
    assert manifest["hub"] == "ATL"
    assert manifest["flow"] == "inbound"
    assert manifest["target_filter"] == "DEST=ATL"
    assert manifest["prediction_cutoff"] == "CRS_DEP_TIME - 2 hours"
    assert manifest["labels"]["y_arr_cls"] == "1[ARR_DELAY >= 15]"
    assert manifest["labels"]["y_arr_reg"] == "signed ARR_DELAY"
    assert manifest["source_schema_version"] == "canonical_schema_v1"
    assert manifest["temporal_protocol_version"] == "expanding_window_v1"
    assert tuple(manifest["final_approved_predictor_columns"]) == (
        APPROVED_PREDICTOR_COLUMNS
    )
    assert tuple(manifest["derived_feature_names"]) == DERIVED_FEATURE_COLUMNS
    assert manifest["weather_policy"] == {
        "arrival_allowed": False,
        "aeolus_raw": "DROP",
        "external": "NOT_ALLOWED",
    }
    assert manifest["chain_policy"]["included_in_base_matrix"] is False
    assert manifest["chain_policy"]["arr_b_enabled"] is False
    assert manifest["flights_policy"] == "REVIEW_REQUIRED_BLOCKED"
    assert manifest["fit_boundary"] == "EACH_FOLD_TRAIN_ROWS_ONLY"


def test_arrival_manifest_dropped_columns_cover_forbidden_families() -> None:
    dropped = _json("feature_manifest_arrival_v1.json")["dropped_columns"]

    assert dropped["DEP_DELAY"] == "DROP_LEAKAGE"
    assert dropped["DEP_TIME"] == "DROP_LEAKAGE"
    assert dropped["O_TEMP"] == "DROP_WEATHER"
    assert dropped["flight_key"] == "DROP_IDENTIFIER"
    assert dropped["FLIGHTS"] == "REVIEW_REQUIRED"
    assert dropped["DEST"] == "DROP_CONSTANT"
    assert dropped["DEST_INDEX"] == "DROP_CONSTANT"
    assert dropped["ORIGIN_INDEX"] == "REVIEW_REQUIRED"


def test_pipeline_registry_has_three_transformer_only_families() -> None:
    registry = _json("feature_pipeline_registry_arrival_v1.json")

    assert registry["registry_version"] == "feature_pipeline_registry_arrival_v1"
    assert registry["task"] == "arrival_core"
    assert set(registry["pipelines"]) == {"linear", "tree", "boosting_future_tree"}
    for entry in registry["pipelines"].values():
        assert entry["input_columns"] == list(APPROVED_PREDICTOR_COLUMNS)
        assert entry["fit_scope"] == "EACH_FOLD_TRAIN_ROWS_ONLY"
        assert entry["estimator"] is None
    assert registry["column_groups"] == {
        "numeric": list(NUMERIC_FEATURE_COLUMNS),
        "categorical": list(CATEGORICAL_FEATURE_COLUMNS),
        "high_cardinality": list(HIGH_CARDINALITY_FEATURE_COLUMNS),
    }


def test_outlier_guard_preserves_ml_truth_and_defers_simulation_bounds() -> None:
    guard = yaml.safe_load(
        (ROOT / "configs" / "outlier_and_simulation_guard.yaml").read_text(
            encoding="utf-8"
        )
    )

    assert guard["contract_version"] == "outlier_and_simulation_guard_v1"
    assert guard["ml_ground_truth"] == {
        "target": "ARR_DELAY",
        "signed": True,
        "absolute_value": False,
        "clip_ground_truth": False,
        "target_imputation": False,
    }
    assert guard["future_simulation_guard"]["status"] == "DEFERRED_TO_WEEK_7_PLUS"
    assert guard["future_simulation_guard"]["changes_ml_ground_truth"] is False


def test_requirements_pin_only_activated_dependencies_through_week5_protocol() -> None:
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")

    assert "scikit-learn==1.9.0" in requirements
    assert "xgboost==3.2.0" in requirements
    assert "optuna==5.0.0" in requirements
    for future_dependency in ["shap", "ortools", "streamlit", "plotly"]:
        assert future_dependency not in requirements.lower()
