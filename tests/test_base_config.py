from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def load_base_config() -> dict:
    return yaml.safe_load((ROOT / "configs" / "base.yaml").read_text(encoding="utf-8"))


def test_base_config_locks_v4_dual_prediction_contract() -> None:
    config = load_base_config()
    prediction = config["prediction"]

    assert config["data"]["hub"] == "ATL"
    assert prediction["cutoff_hours_before_crs_dep"] == 2

    arrival = prediction["arrival_core"]
    assert arrival["role"] == "core"
    assert arrival["flow"] == "inbound"
    assert arrival["filter"] == "DEST=ATL"
    assert arrival["classification"] == {
        "target": "ARR_DELAY",
        "label_name": "y_arr_cls",
        "threshold_minutes": 15,
    }
    assert arrival["regression"] == {
        "enabled": True,
        "target": "ARR_DELAY",
        "label_name": "y_arr_reg",
        "signed": True,
    }
    assert arrival["weather"] == {
        "allowed": False,
        "aeolus_raw_policy": "drop",
    }
    assert arrival["reconstructed_chain"] == {
        "artifact_version": "schedule_chain_v1",
        "allowed_for_ablation": True,
        "enabled_by_default": False,
    }

    departure = prediction["departure_auxiliary"]
    assert departure["role"] == "auxiliary"
    assert departure["flow"] == "outbound"
    assert departure["filter"] == "ORIGIN=ATL"
    assert departure["classification"] == {
        "target": "DEP_DELAY",
        "label_name": "y_dep_cls",
        "threshold_minutes": 15,
    }
    assert departure["regression"] == {"enabled": False}
    assert departure["weather"] == {
        "aeolus_raw_policy": "drop",
        "point_in_time_source": {
            "artifact_version": "weather_point_in_time_v1",
            "contract_version": "weather_point_in_time_contract_v1",
            "contract_path": (
                "artifacts/manifests/weather_point_in_time_contract_v1.json"
            ),
            "provider": "TBD",
            "status": "audit_required",
            "enabled": False,
            "row_parity_required": True,
        },
    }


def test_base_config_preserves_temporal_flow_and_model_contracts() -> None:
    config = load_base_config()

    assert config["data"]["raw_tabular_path"] == "data/raw/tabular"
    assert config["data"]["raw_chain_path"] == "data/raw/chain"
    assert config["temporal"]["development_years"] == "2016-2022"
    assert config["temporal"]["model_selection_year"] == 2023
    assert config["temporal"]["final_holdout_year"] == 2024
    assert config["flows"]["inbound"] == {
        "filter": "DEST=ATL",
        "role": "core_arrival_ml",
    }
    assert config["flows"]["outbound"] == {
        "filter": "ORIGIN=ATL",
        "role": ["auxiliary_departure_ml", "synthetic_turn_simulation"],
    }
    assert config["models"]["core_methods"] == [
        "linear",
        "random_forest",
        "hist_gradient_boosting",
        "xgboost",
        "weighted_ensemble",
    ]
    assert config["simulation"]["prediction_source_task"] == "arrival_core"
    assert (
        config["simulation"]["auxiliary_departure_prediction_allowed"] is False
    )


def test_base_config_distinguishes_raw_and_reconstructed_flight_chain() -> None:
    config = load_base_config()
    raw_chain = config["flight_chain"]["raw"]
    reconstructed = config["flight_chain"]["reconstructed"]

    assert raw_chain == {
        "status": "final_no_go",
        "enabled_by_default": False,
        "include_in_core": False,
        "ablation": False,
    }
    assert reconstructed == {
        "version": "schedule_chain_v1",
        "datetime_storage_amendment_version": (
            "canonical_datetime_storage_amendment_v1"
        ),
        "status": "go_for_ablation",
        "enabled_by_default": False,
        "include_in_core": False,
        "ablation": True,
        "ablation_week": 6,
        "source": "canonical_tabular",
        "output_path": "data/processed/flight_chain_reconstructed_v1",
        "physical_aircraft_identity": False,
        "group_fields": [
            "source_year",
            "FL_DATE",
            "OP_CARRIER",
            "OP_CARRIER_FL_NUM",
        ],
        "order_field": "CRS_DEP_TIME",
        "tie_break_fields": ["ORIGIN", "DEST", "flight_key"],
        "max_context_length": 6,
        "feature_engineering": {
            "policy_version": "reconstructed_chain_feature_availability_v1",
            "policy_path": "configs/reconstructed_chain_feature_policy.yaml",
            "audit_status": "completed",
            "audit_result_version": (
                "reconstructed_chain_feature_availability_audit_v1"
            ),
            "audit_result_path": (
                "artifacts/manifests/"
                "reconstructed_chain_feature_availability_audit_v1.json"
            ),
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
    }


def test_base_config_requires_chain_feature_availability_gate() -> None:
    config = load_base_config()
    feature_engineering = config["flight_chain"]["reconstructed"][
        "feature_engineering"
    ]

    assert feature_engineering == {
        "policy_version": "reconstructed_chain_feature_availability_v1",
        "policy_path": "configs/reconstructed_chain_feature_policy.yaml",
        "audit_status": "completed",
        "audit_result_version": (
            "reconstructed_chain_feature_availability_audit_v1"
        ),
        "audit_result_path": (
            "artifacts/manifests/"
            "reconstructed_chain_feature_availability_audit_v1.json"
        ),
        "ml_enabled": False,
        "arr_b_enabled": False,
        "keep_safe_feature_count": 0,
        "diagnostic_materialization_allowed": True,
        "diagnostic_materialization_executed": False,
        "ml_materialization_allowed": False,
        "ml_branch_status": "blocked_pending_new_evidence",
        "closure_status": "completed_with_blocked_ml_branch",
        "availability_gate_required": True,
    }

    policy = yaml.safe_load(
        (
            ROOT / "configs" / "reconstructed_chain_feature_policy.yaml"
        ).read_text(encoding="utf-8")
    )
    assert policy["policy_version"] == feature_engineering["policy_version"]
    assert policy["source_artifact"] == "schedule_chain_v1"
    assert policy["current_status"] == "AUDIT_COMPLETE"
    assert policy["audit_result"] == "NO_KEEP_SAFE_FEATURES"
    assert policy["audit_result_version"] == feature_engineering["audit_result_version"]
    assert policy["audit_result_path"] == feature_engineering["audit_result_path"]
    assert policy["ml_enabled"] is False
    assert policy["arr_b_enabled"] is False
    assert policy["keep_safe_feature_count"] == 0
    assert policy["diagnostic_materialization_allowed"] is True
    assert policy["diagnostic_materialization_executed"] is False
    assert policy["ml_materialization_allowed"] is False
    assert policy["ml_branch_status"] == "BLOCKED_PENDING_NEW_EVIDENCE"
    assert policy["closure_status"] == "COMPLETED_WITH_BLOCKED_ML_BRANCH"
    assert policy["availability_gate_required"] is True
    assert policy["prediction_cutoff_hours_before_target_crs_dep"] == 2
    assert policy["groups"]["target_or_position_local"]["status"] == (
        "REVIEW_REQUIRED"
    )
    assert policy["groups"]["past_context"]["status"] == "REVIEW_REQUIRED"
    assert "is_single_leg_chain" not in policy["groups"][
        "target_or_position_local"
    ]["features"]
    assert policy["groups"]["future_or_full_chain"]["status"] == (
        "BLOCKED_UNTIL_PROVEN"
    )
    assert "is_single_leg_chain" in policy["groups"]["future_or_full_chain"][
        "features"
    ]
    assert policy["groups"]["identifiers"]["status"] == "IDENTIFIER_ONLY"
