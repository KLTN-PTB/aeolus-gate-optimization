from __future__ import annotations

from copy import deepcopy

import pytest
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor

from src.models.contracts import RollingFold
from src.models.hpo import HPOFoldContext
from src.models.week5_hist_gradient_boosting_hpo import (
    build_week5_hist_gradient_boosting_estimator,
)
from src.models.week5_hpo_protocol import Week5ProtocolViolation
from src.models.week5_hpo_protocol_v1_1 import load_week5_hpo_protocol_v1_1
from src.models.week5_contracts import load_week5_study_specs


def _context(task: str, *, fixed_override: dict[str, object] | None = None) -> HPOFoldContext:
    protocol = load_week5_hpo_protocol_v1_1()
    spec = load_week5_study_specs(protocol)[f"hist_gradient_boosting_{task}"]
    fixed = deepcopy(dict(spec.fixed_parameters))
    if fixed_override:
        fixed.update(fixed_override)
    return HPOFoldContext(
        fold=RollingFold("fold_1", (2016, 2017, 2018), 2019),
        method_id=spec.method_id,
        model_family=spec.model_family,
        task=spec.task,
        params={
            "learning_rate": 0.05,
            "max_iter": 200,
            "max_leaf_nodes": 31,
            "max_depth": 8,
            "min_samples_leaf": 60,
            "l2_regularization": 1.0,
            "max_features": 0.8,
        },
        fixed_parameters=fixed,
        seed=202601,
        class_weights={0: 0.7, 1: 1.5} if task == "classification" else None,
    )


def test_hgb_factory_builds_frozen_classifier_with_train_fold_weights() -> None:
    estimator = build_week5_hist_gradient_boosting_estimator(_context("classification"))

    assert isinstance(estimator, HistGradientBoostingClassifier)
    assert estimator.early_stopping is False
    assert estimator.random_state == 202601
    assert estimator.class_weight == {0: 0.7, 1: 1.5}
    assert estimator.get_params()["max_features"] == 0.8


def test_hgb_factory_builds_frozen_signed_delay_regressor() -> None:
    estimator = build_week5_hist_gradient_boosting_estimator(_context("regression"))

    assert isinstance(estimator, HistGradientBoostingRegressor)
    assert estimator.early_stopping is False
    assert estimator.random_state == 202601


def test_hgb_factory_rejects_nonfrozen_early_stopping() -> None:
    with pytest.raises(Week5ProtocolViolation, match="early stopping"):
        build_week5_hist_gradient_boosting_estimator(
            _context("classification", fixed_override={"early_stopping": True})
        )


def test_hgb_factory_rejects_parameter_space_drift() -> None:
    context = _context("regression")
    context.params.pop("max_features")

    with pytest.raises(Week5ProtocolViolation, match="parameters"):
        build_week5_hist_gradient_boosting_estimator(context)
