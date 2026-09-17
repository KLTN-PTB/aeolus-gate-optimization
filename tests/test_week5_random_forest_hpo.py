from __future__ import annotations

from pathlib import Path

import optuna
import pytest

from scripts.run_week5_random_forest_hpo import (
    RF_STUDY_IDS,
    _storage_path,
    mark_study_status,
    open_or_resume_study,
)
from src.models.contracts import RollingFold
from src.models.hpo import HPOFoldContext
from src.models.week5_contracts import load_week5_study_specs
from src.models.week5_hpo_protocol import Week5ProtocolViolation, load_week5_hpo_protocol
from src.models.week5_random_forest_hpo import build_week5_random_forest_estimator


def _context(*, task: str) -> HPOFoldContext:
    protocol = load_week5_hpo_protocol()
    spec = load_week5_study_specs(protocol)[f"random_forest_{task}"]
    return HPOFoldContext(
        fold=RollingFold("fold_1", (2016, 2017, 2018), 2019),
        method_id="random_forest",
        model_family="tree",
        task=task,  # type: ignore[arg-type]
        params={
            "n_estimators": 64,
            "max_depth": 6,
            "min_samples_split": 20,
            "min_samples_leaf": 10,
            "max_features": "sqrt",
            "max_samples": 0.6,
        },
        fixed_parameters=dict(spec.fixed_parameters),
        seed=202601,
        class_weights={0: 1.25, 1: 0.75} if task == "classification" else None,
    )


def test_rf_hpo_factory_builds_fold_local_classifier_with_training_class_weights() -> None:
    """Catches a factory that ignores train-only class weighting or enables parallel trees."""

    estimator = build_week5_random_forest_estimator(_context(task="classification"))

    assert estimator.__class__.__name__ == "RandomForestClassifier"
    assert estimator.get_params()["n_jobs"] == 1
    assert estimator.get_params()["random_state"] == 202601
    assert estimator.get_params()["class_weight"] == {0: 1.25, 1: 0.75}
    assert estimator.get_params()["max_samples"] == 0.6


def test_rf_hpo_factory_builds_signed_delay_regressor_without_class_weights() -> None:
    """Catches a factory that leaks classification weighting into regression."""

    estimator = build_week5_random_forest_estimator(_context(task="regression"))

    assert estimator.__class__.__name__ == "RandomForestRegressor"
    assert estimator.get_params()["criterion"] == "squared_error"
    assert "class_weight" not in estimator.get_params()


def test_rf_hpo_factory_rejects_non_random_forest_context() -> None:
    """Catches accidental reuse of the RF factory by another Week-5 method."""

    context = _context(task="classification")
    invalid = HPOFoldContext(
        fold=context.fold,
        method_id="xgboost",
        model_family="boosting",
        task=context.task,
        params=context.params,
        fixed_parameters=context.fixed_parameters,
        seed=context.seed,
        class_weights=context.class_weights,
    )

    with pytest.raises(Week5ProtocolViolation, match="random_forest"):
        build_week5_random_forest_estimator(invalid)


def test_rf_study_opening_creates_only_the_frozen_two_study_ids(tmp_path: Path) -> None:
    """Catches a runner that can initiate a non-RF Week-5 production study."""

    protocol = load_week5_hpo_protocol()
    specs = load_week5_study_specs(protocol)

    assert RF_STUDY_IDS == (
        "random_forest_classification",
        "random_forest_regression",
    )
    study = open_or_resume_study(
        protocol,
        specs[RF_STUDY_IDS[0]],
        storage_path=tmp_path / "rf_classification.sqlite3",
    )

    assert study.study_name == "week5_hpo_protocol_v1__random_forest_classification"
    assert study.user_attrs["protocol_hash"] == protocol.protocol_hash
    assert study.user_attrs["status"] == "RUNNING"
    assert isinstance(study.sampler, optuna.samplers.TPESampler)
    assert isinstance(study.pruner, optuna.pruners.NopPruner)


def test_rf_storage_path_is_exactly_the_frozen_configured_artifact_location(tmp_path: Path) -> None:
    """Catches a runner that writes an RF study outside the frozen Optuna location."""

    protocol = load_week5_hpo_protocol()
    spec = load_week5_study_specs(protocol)["random_forest_classification"]

    path = _storage_path(tmp_path, protocol, spec)

    assert path == tmp_path / "artifacts" / "optuna_studies" / (
        "week5_hpo_protocol_v1__random_forest_classification.sqlite3"
    )


def test_rf_completed_study_cannot_be_overwritten_or_resumed(tmp_path: Path) -> None:
    """Catches a runner that overwrites a completed production HPO study."""

    protocol = load_week5_hpo_protocol()
    spec = load_week5_study_specs(protocol)["random_forest_regression"]
    storage_path = tmp_path / "rf_regression.sqlite3"
    study = open_or_resume_study(protocol, spec, storage_path=storage_path)
    mark_study_status(study, "COMPLETED")

    with pytest.raises(Week5ProtocolViolation, match="completed study"):
        open_or_resume_study(protocol, spec, storage_path=storage_path)
