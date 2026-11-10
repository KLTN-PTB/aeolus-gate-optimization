"""Frozen CPU XGBoost estimator factory for Week-5 HPO protocol v1.1."""

from __future__ import annotations

from typing import Any

from xgboost import XGBClassifier, XGBRegressor

from src.models.hpo import HPOFoldContext
from src.models.week5_hpo_protocol import Week5ProtocolViolation


_SEARCH_PARAMETER_NAMES = {
    "n_estimators",
    "learning_rate",
    "max_depth",
    "min_child_weight",
    "subsample",
    "colsample_bytree",
    "reg_alpha",
    "reg_lambda",
}


def build_week5_xgboost_hpo_estimator(
    context: HPOFoldContext,
) -> XGBClassifier | XGBRegressor:
    """Build one CPU-only frozen XGBoost HPO estimator for one temporal fold."""

    if context.method_id != "xgboost" or context.model_family != "boosting":
        raise Week5ProtocolViolation("XGBoost HPO factory requires boosting XGBoost context")
    if set(context.params) != _SEARCH_PARAMETER_NAMES:
        raise Week5ProtocolViolation("XGBoost HPO parameters differ from the frozen search space")

    fixed = context.fixed_parameters
    required_common = {
        "tree_method": "hist",
        "device": "cpu",
        "max_bin": 256,
        "n_jobs": 1,
        "random_state": context.seed,
    }
    if any(fixed.get(name) != value for name, value in required_common.items()):
        raise Week5ProtocolViolation("XGBoost HPO fixed parameters are not frozen CPU settings")

    common: dict[str, Any] = {
        **context.params,
        **required_common,
        "verbosity": 0,
        "early_stopping_rounds": None,
    }
    if context.task == "classification":
        if fixed.get("objective") != "binary:logistic" or fixed.get("eval_metric") != "logloss":
            raise Week5ProtocolViolation("XGBoost HPO classification objective is not frozen")
        if fixed.get("class_weight_policy") != "balanced_from_training_fold_only":
            raise Week5ProtocolViolation("XGBoost HPO class-weight policy is not frozen")
        if context.class_weights is None:
            raise Week5ProtocolViolation("XGBoost HPO classifier requires train-fold class weights")
        negative_weight = context.class_weights.get(0)
        positive_weight = context.class_weights.get(1)
        if (
            negative_weight is None
            or positive_weight is None
            or negative_weight <= 0.0
            or positive_weight <= 0.0
        ):
            raise Week5ProtocolViolation("XGBoost HPO classifier requires positive train-fold weights")
        return XGBClassifier(
            objective="binary:logistic",
            eval_metric="logloss",
            scale_pos_weight=float(positive_weight / negative_weight),
            **common,
        )
    if context.task == "regression":
        if fixed.get("objective") != "reg:squarederror" or fixed.get("eval_metric") != "mae":
            raise Week5ProtocolViolation("XGBoost HPO regression objective is not frozen")
        if context.class_weights is not None:
            raise Week5ProtocolViolation("XGBoost HPO regressor must not receive class weights")
        return XGBRegressor(
            objective="reg:squarederror",
            eval_metric="mae",
            **common,
        )
    raise Week5ProtocolViolation(f"unsupported XGBoost HPO task {context.task!r}")
