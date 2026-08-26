from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def load_base_config() -> dict:
    return yaml.safe_load((ROOT / "configs" / "base.yaml").read_text(encoding="utf-8"))


def test_base_config_locked_values() -> None:
    config = load_base_config()
    assert config["data"]["hub"] == "ATL"
    assert config["prediction"]["cutoff_hours_before_crs_dep"] == 2
    assert config["prediction"]["classification_threshold_minutes"] == 15
    assert config["temporal"]["final_holdout_year"] == 2024
    assert config["data"]["raw_tabular_path"] == "data/raw/tabular"
    assert config["data"]["raw_chain_path"] == "data/raw/chain"


def test_base_config_models_and_flight_chain() -> None:
    config = load_base_config()
    assert config["models"]["core_methods"] == [
        "linear",
        "random_forest",
        "hist_gradient_boosting",
        "xgboost",
        "weighted_ensemble",
    ]
    raw_chain = {
        key: config["flight_chain"][key]
        for key in (
            "enabled_by_default",
            "status",
            "include_in_core",
            "week6_ablation",
        )
    }
    assert raw_chain == {
        "enabled_by_default": False,
        "status": "no_go",
        "include_in_core": False,
        "week6_ablation": False,
    }
    reconstructed = config["flight_chain"]["reconstructed"]
    assert reconstructed == {
        "version": "schedule_chain_v1",
        "datetime_storage_amendment_version": (
            "canonical_datetime_storage_amendment_v1"
        ),
        "status": "go_for_ablation",
        "enabled_by_default": False,
        "include_in_core": False,
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
    }
