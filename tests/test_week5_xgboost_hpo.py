from __future__ import annotations

from copy import deepcopy

import pytest
from xgboost import XGBClassifier, XGBRegressor

from src.models.contracts import RollingFold
from src.models.hpo import HPOFoldContext
from src.models.week5_hpo_protocol import Week5ProtocolViolation
from src.models.week5_hpo_protocol_v1_1 import load_week5_hpo_protocol_v1_1
from src.models.week5_contracts import load_week5_study_specs
from src.models.week5_xgboost_hpo import build_week5_xgboost_hpo_estimator


def _context(
    task: str, *, fixed_override: dict[str, object] | None = None
) -> HPOFoldContext:
    protocol = load_week5_hpo_protocol_v1_1()
    spec = load_week5_study_specs(protocol)[f"xgboost_{task}"]
    fixed = deepcopy(dict(spec.fixed_parameters))
    if fixed_override:
        fixed.update(fixed_override)
    return HPOFoldContext(
        fold=RollingFold("fold_1", (2016, 2017, 2018), 2019),
        method_id=spec.method_id,
        model_family=spec.model_family,
        task=spec.task,
        params={
            "n_estimators": 200,
            "learning_rate": 0.05,
            "max_depth": 5,
            "min_child_weight": 4.0,
            "subsample": 0.8,
            "colsample_bytree": 0.7,
            "reg_alpha": 1.0,
            "reg_lambda": 2.0,
        },
        fixed_parameters=fixed,
        seed=202601,
        class_weights={0: 0.75, 1: 1.5} if task == "classification" else None,
    )


def test_xgboost_hpo_factory_builds_cpu_classifier_with_train_fold_scale_weight() -> None:
    estimator = build_week5_xgboost_hpo_estimator(_context("classification"))

    assert isinstance(estimator, XGBClassifier)
    params = estimator.get_params()
    assert params["tree_method"] == "hist"
    assert params["device"] == "cpu"
    assert params["n_jobs"] == 1
    assert params["objective"] == "binary:logistic"
    assert params["eval_metric"] == "logloss"
    assert params["scale_pos_weight"] == pytest.approx(2.0)
    assert params["early_stopping_rounds"] is None


def test_xgboost_hpo_factory_builds_cpu_signed_delay_regressor() -> None:
    estimator = build_week5_xgboost_hpo_estimator(_context("regression"))

    assert isinstance(estimator, XGBRegressor)
    params = estimator.get_params()
    assert params["tree_method"] == "hist"
    assert params["device"] == "cpu"
    assert params["n_jobs"] == 1
    assert params["objective"] == "reg:squarederror"
    assert params["eval_metric"] == "mae"
    assert params["early_stopping_rounds"] is None


def test_xgboost_hpo_factory_rejects_gpu_or_nonfrozen_parameters() -> None:
    with pytest.raises(Week5ProtocolViolation, match="fixed parameters"):
        build_week5_xgboost_hpo_estimator(_context("classification", fixed_override={"device": "cuda"}))

    context = _context("regression")
    context.params.pop("reg_lambda")
    with pytest.raises(Week5ProtocolViolation, match="parameters"):
        build_week5_xgboost_hpo_estimator(context)
