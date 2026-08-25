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
    assert config["flight_chain"] == {
        "enabled_by_default": False,
        "status": "no_go",
        "include_in_core": False,
        "week6_ablation": False,
    }
