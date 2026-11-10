from __future__ import annotations

import importlib
import importlib.util
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

import pytest
import yaml
from optuna.pruners import NopPruner
from optuna.samplers import TPESampler

from src.data.access_guard import DataAccessDenied


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_STUDIES = {
    "random_forest_classification",
    "random_forest_regression",
    "hist_gradient_boosting_classification",
    "hist_gradient_boosting_regression",
    "xgboost_classification",
    "xgboost_regression",
}


def _api(name: str) -> Callable[..., Any]:
    spec = importlib.util.find_spec("src.models.week5_hpo_protocol")
    assert spec is not None, "Week-5 HPO protocol module is missing"
    module = importlib.import_module("src.models.week5_hpo_protocol")
    assert hasattr(module, name), f"Week-5 HPO protocol API {name!r} is missing"
    return getattr(module, name)


def _load_protocol() -> Any:
    return _api("load_week5_hpo_protocol")(project_root=ROOT)


def _write_protocol_pair(
    tmp_path: Path,
    *,
    config: dict[str, Any],
    manifest: dict[str, Any],
) -> tuple[Path, Path]:
    config_path = tmp_path / "week5_hpo.yaml"
    manifest_path = tmp_path / "week5_hpo_protocol_v1.json"
    manifest = deepcopy(manifest)
    manifest["protocol_sha256"] = _api("canonical_protocol_hash")(config)
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return config_path, manifest_path


def test_frozen_protocol_matches_core_arrival_and_locked_week4_folds() -> None:
    protocol = _load_protocol()
    config = protocol.config

    assert protocol.protocol_version == "week5_hpo_protocol_v1"
    assert config["status"] == "FROZEN_PRE_PRODUCTION"
    assert config["task_contract"] == {
        "task": "arrival_core",
        "flow": "inbound",
        "population": "DEST=ATL",
        "classification_target": "y_arr_cls = 1[ARR_DELAY >= 15]",
        "regression_target": "y_arr_reg = signed ARR_DELAY minutes",
        "prediction_cutoff": "CRS_DEP_TIME - 2 hours",
        "feature_manifest_version": "feature_manifest_arrival_v1",
        "preprocessing_version": "arrival_preprocessing_v1",
    }
    assert config["folds"] == [
        {"id": "fold_1", "train_years": [2016, 2017, 2018], "validation_year": 2019},
        {"id": "fold_2", "train_years": [2016, 2017, 2018, 2019], "validation_year": 2020},
        {"id": "fold_3", "train_years": [2016, 2017, 2018, 2019, 2020], "validation_year": 2021},
        {"id": "fold_4", "train_years": [2016, 2017, 2018, 2019, 2020, 2021], "validation_year": 2022},
    ]
    assert config["data_contract"]["allowed_hpo_years"] == list(range(2016, 2023))
    assert config["data_contract"]["blocked_hpo_years"] == [2023, 2024]
    assert config["data_contract"]["access_guard_purpose"] == "hpo"
    assert config["data_contract"]["preprocessing_fit_scope"] == "EACH_FOLD_TRAIN_ROWS_ONLY"
    assert config["scope_guards"] == {
        "weather_allowed": False,
        "departure_target_allowed": False,
        "predicted_departure_delay_allowed": False,
        "actual_operational_outcomes_allowed": False,
        "chain_features_allowed": False,
        "arr_b_enabled": False,
        "auxiliary_weather_enabled": False,
        "shap_allowed": False,
        "ensemble_allowed": False,
        "champion_selection_allowed": False,
        "production_hpo_allowed_in_this_step": False,
    }


def test_protocol_freezes_six_independent_fixed_budget_studies() -> None:
    protocol = _load_protocol()
    config = protocol.config
    studies = config["studies"]

    assert set(studies) == EXPECTED_STUDIES
    assert len({entry["study_name"] for entry in studies.values()}) == 6
    assert all(
        entry["study_name"] == f"week5_hpo_protocol_v1__{study_id}"
        for study_id, entry in studies.items()
    )
    assert config["budget"] == {
        "n_trials_per_study": 10,
        "execution_parallelism": 1,
        "timeout_seconds_per_study": 14400,
        "timeout_role": "SAFETY_CEILING_ONLY",
        "incomplete_timeout_status": "BLOCKED_INCOMPLETE",
        "completed_trials_required": 10,
        "automatic_trial_reduction_allowed": False,
    }
    assert config["randomness"] == {
        "sampler": "TPESampler",
        "sampler_seed": 202601,
        "sampler_seed_source": "configs/base.yaml:reproducibility.project_seed",
        "pruner": "NopPruner",
        "model_random_state": 202601,
        "model_random_state_source": "configs/base.yaml:reproducibility.project_seed",
        "parallel_optuna_trials": False,
    }
    sampler, pruner = _api("build_optuna_components")(protocol)
    assert isinstance(sampler, TPESampler)
    assert isinstance(pruner, NopPruner)


def test_loaded_protocol_state_cannot_be_mutated_after_hash_validation() -> None:
    protocol = _load_protocol()
    exposed_config = protocol.config
    exposed_manifest = protocol.manifest

    exposed_config["randomness"]["sampler_seed"] = 1
    exposed_config["studies"].clear()
    exposed_manifest["protocol_sha256"] = "mutated"

    assert protocol.config["randomness"]["sampler_seed"] == 202601
    assert set(protocol.config["studies"]) == EXPECTED_STUDIES
    assert protocol.manifest["protocol_sha256"] == protocol.protocol_hash


def test_objectives_are_equal_fold_probability_pr_auc_and_signed_mae() -> None:
    protocol = _load_protocol()
    objectives = protocol.config["objectives"]

    assert objectives["classification"] == {
        "direction": "maximize",
        "metric": "mean_pr_auc_across_locked_folds",
        "fold_weighting": "equal",
        "prediction_method": "predict_proba",
        "positive_class": 1,
        "fixed_threshold": 0.5,
        "threshold_tuning_allowed": False,
        "secondary_diagnostics": [
            "roc_auc",
            "pr_auc",
            "brier_score",
            "recall_at_0_5",
            "f1_at_0_5",
            "ece_10_bins",
        ],
    }
    assert objectives["regression"] == {
        "direction": "minimize",
        "metric": "mean_mae_across_locked_folds",
        "fold_weighting": "equal",
        "signed_target": True,
        "secondary_diagnostics": ["mae", "rmse", "r2"],
    }
    classification_value = _api("aggregate_classification_objective")(
        [0.10, 0.20, 0.30, 0.40]
    )
    regression_value = _api("aggregate_regression_objective")(
        [10.0, 20.0, 30.0, 40.0]
    )
    assert classification_value == pytest.approx(0.25)
    assert regression_value == pytest.approx(25.0)


def test_search_spaces_are_bounded_and_preserve_model_safety_constraints() -> None:
    config = _load_protocol().config
    studies = config["studies"]

    for study_id, entry in studies.items():
        assert entry["search_space"]
        assert entry["direction"] in {"maximize", "minimize"}
        assert entry["objective_metric"] in {
            "mean_pr_auc_across_locked_folds",
            "mean_mae_across_locked_folds",
        }
        for parameter in entry["search_space"].values():
            if parameter["type"] in {"int", "float"}:
                assert parameter["low"] < parameter["high"]
            else:
                assert parameter["type"] == "categorical"
                assert parameter["choices"]

        assert "class_weight" not in entry["search_space"]
        if study_id.startswith("hist_gradient_boosting"):
            assert entry["fixed_parameters"]["early_stopping"] is False
        if study_id.startswith("xgboost"):
            assert entry["fixed_parameters"]["tree_method"] == "hist"
            assert entry["fixed_parameters"]["device"] == "cpu"
            assert entry["fixed_parameters"]["max_bin"] == 256
            assert entry["fixed_parameters"]["n_jobs"] == 1

    assert studies["xgboost_classification"]["fixed_parameters"]["objective"] == (
        "binary:logistic"
    )
    assert studies["xgboost_regression"]["fixed_parameters"]["objective"] == (
        "reg:squarederror"
    )
    assert config["forbidden_tuning_dimensions"] == [
        "feature_set",
        "target_definition",
        "rolling_folds",
        "prediction_cutoff",
        "classification_threshold",
        "row_population",
        "class_weight",
    ]


def test_hpo_access_uses_fail_closed_guard_for_2023_and_2024() -> None:
    assert_year = _api("assert_hpo_year_allowed")

    assert_year(2016)
    assert_year(2022)
    with pytest.raises(DataAccessDenied, match="HPO is blocked"):
        assert_year(2023)
    with pytest.raises(DataAccessDenied, match="HPO is blocked"):
        assert_year(2024)


def test_protocol_loading_uses_only_hpo_access_purpose(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.data import access_guard

    access_events: list[dict[str, Any]] = []
    monkeypatch.setattr(
        access_guard,
        "log_data_access",
        lambda **event: access_events.append(event),
    )

    _load_protocol()

    assert access_events
    assert all(event["purpose"] == "hpo" for event in access_events)
    assert {event["year"] for event in access_events} == set(range(2016, 2023))


def test_resume_requires_matching_hash_and_refuses_completed_study() -> None:
    protocol = _load_protocol()
    assert_resume = _api("assert_study_resume_allowed")
    study_name = "week5_hpo_protocol_v1__xgboost_classification"

    assert_resume(
        protocol,
        study_name=study_name,
        stored_protocol_hash=protocol.protocol_hash,
        study_status="INTERRUPTED",
        completed_trials=4,
    )
    assert_resume(
        protocol,
        study_name=study_name,
        stored_protocol_hash=protocol.protocol_hash,
        study_status="BLOCKED_INCOMPLETE",
        completed_trials=9,
    )
    with pytest.raises(ValueError, match="hash mismatch"):
        assert_resume(
            protocol,
            study_name=study_name,
            stored_protocol_hash="wrong-hash",
            study_status="INTERRUPTED",
            completed_trials=4,
        )
    with pytest.raises(ValueError, match="completed study"):
        assert_resume(
            protocol,
            study_name=study_name,
            stored_protocol_hash=protocol.protocol_hash,
            study_status="COMPLETED",
            completed_trials=10,
        )
    with pytest.raises(ValueError, match="already has 10 completed trials"):
        assert_resume(
            protocol,
            study_name=study_name,
            stored_protocol_hash=protocol.protocol_hash,
            study_status="INTERRUPTED",
            completed_trials=10,
        )


def test_manifest_hash_and_runtime_dependencies_match_frozen_config(tmp_path: Path) -> None:
    protocol = _load_protocol()
    manifest = protocol.manifest

    assert manifest["status"] == "PROTOCOL_FROZEN"
    assert manifest["production_hpo_started"] is False
    assert manifest["row_level_2023_accessed"] is False
    assert manifest["row_level_2024_accessed"] is False
    assert manifest["protocol_sha256"] == protocol.protocol_hash
    assert manifest["dependencies"] == {
        "python": "3.11.15",
        "xgboost": "3.2.0",
        "optuna": "5.0.0",
        "numpy": "2.2.6",
        "pandas": "2.3.3",
        "pyarrow": "25.0.1",
        "scikit_learn": "1.9.0",
    }
    assert protocol.config["storage"] == {
        "directory": "artifacts/optuna_studies",
        "url_template": "sqlite:///artifacts/optuna_studies/{study_name}.sqlite3",
        "gitignored": True,
        "overwrite_completed_study": False,
        "resume_requires_matching_protocol_hash": True,
    }

    tampered = dict(protocol.config)
    tampered["budget"] = dict(tampered["budget"])
    tampered["budget"]["n_trials_per_study"] = 9
    tampered_path = tmp_path / "tampered.yaml"
    tampered_path.write_text(yaml.safe_dump(tampered), encoding="utf-8")
    manifest_path = ROOT / "artifacts" / "manifests" / "week5_hpo_protocol_v1.json"
    with pytest.raises(ValueError, match="hash mismatch"):
        _api("load_week5_hpo_protocol")(
            project_root=ROOT,
            config_path=tampered_path,
            manifest_path=manifest_path,
        )


def test_coordinated_config_and_manifest_edits_cannot_redefine_frozen_protocol(
    tmp_path: Path,
) -> None:
    protocol = _load_protocol()
    mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        (
            "unsafe_search_bound",
            lambda config: config["studies"]["xgboost_classification"]["search_space"][
                "n_estimators"
            ].__setitem__("high", 5000),
        ),
        (
            "swapped_sampler_pruner",
            lambda config: config["randomness"].update(
                {"sampler": "NopPruner", "pruner": "TPESampler"}
            ),
        ),
        (
            "extra_disabled_scope",
            lambda config: config["scope_guards"].__setitem__(
                "unregistered_scope", False
            ),
        ),
        (
            "weakened_resume_policy",
            lambda config: config["resume_policy"]["resumable_statuses"].append(
                "COMPLETED"
            ),
        ),
    ]

    for name, mutate in mutations:
        case_root = tmp_path / name
        case_root.mkdir()
        config = protocol.config
        mutate(config)
        config_path, manifest_path = _write_protocol_pair(
            case_root,
            config=config,
            manifest=protocol.manifest,
        )
        with pytest.raises(ValueError, match="frozen protocol hash mismatch"):
            _api("load_week5_hpo_protocol")(
                project_root=ROOT,
                config_path=config_path,
                manifest_path=manifest_path,
            )


def test_manifest_projection_cannot_disagree_with_frozen_config(tmp_path: Path) -> None:
    protocol = _load_protocol()
    mutations = [
        ("n_studies", 5),
        ("manifest_version", "wrong_manifest_version"),
        ("protocol_hash_algorithm", "unregistered_hash_algorithm"),
        ("task", "departure_auxiliary"),
        ("classification_target", "y_dep_cls = 1[DEP_DELAY >= 15]"),
        ("regression_target", "absolute ARR_DELAY"),
        ("prediction_cutoff", "CRS_DEP_TIME"),
    ]

    for field, value in mutations:
        case_root = tmp_path / field
        case_root.mkdir()
        manifest = protocol.manifest
        manifest[field] = value
        config_path, manifest_path = _write_protocol_pair(
            case_root,
            config=protocol.config,
            manifest=manifest,
        )

        with pytest.raises(ValueError, match="manifest projection mismatch"):
            _api("load_week5_hpo_protocol")(
                project_root=ROOT,
                config_path=config_path,
                manifest_path=manifest_path,
            )


def test_week4_historical_contract_still_rejects_xgboost() -> None:
    from src.models.contracts import ExperimentSpec, Week4ContractViolation

    with pytest.raises(Week4ContractViolation, match="Week 4 does not permit"):
        ExperimentSpec(
            method_id="xgboost",  # type: ignore[arg-type]
            model_version="week5_must_not_reuse_week4_contract",
            config_version="0.1.0",
            seed=202601,
        )


def test_manifest_declares_all_source_artifacts_and_no_study_results() -> None:
    manifest_path = ROOT / "artifacts" / "manifests" / "week5_hpo_protocol_v1.json"
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["source_config"] == "configs/week5_hpo.yaml"
    assert manifest["source_contracts"] == [
        "configs/base.yaml",
        "artifacts/manifests/feature_manifest_arrival_v1.json",
        "artifacts/manifests/temporal_folds_manifest.json",
        "artifacts/manifests/split_manifest.json",
    ]
    assert manifest["n_studies"] == 6
    assert manifest["trials_per_study"] == 10
    assert manifest["study_results"] == []
