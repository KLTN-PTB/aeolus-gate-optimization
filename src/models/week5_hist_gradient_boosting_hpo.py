"""Frozen Week-5 HistGradientBoosting estimator factory."""

from __future__ import annotations

from typing import Any

from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor

from src.models.hpo import HPOFoldContext
from src.models.week5_hpo_protocol import Week5ProtocolViolation


_SEARCH_PARAMETER_NAMES = {
    "learning_rate",
    "max_iter",
    "max_leaf_nodes",
    "max_depth",
    "min_samples_leaf",
    "l2_regularization",
    "max_features",
}


def build_week5_hist_gradient_boosting_estimator(
    context: HPOFoldContext,
) -> HistGradientBoostingClassifier | HistGradientBoostingRegressor:
    """Build one HGB estimator without adding an internal validation split."""

    if (
        context.method_id != "hist_gradient_boosting"
        or context.model_family != "boosting"
    ):
        raise Week5ProtocolViolation("HGB HPO factory requires boosting HGB context")
    if set(context.params) != _SEARCH_PARAMETER_NAMES:
        raise Week5ProtocolViolation("HGB HPO parameters differ from the frozen search space")
    if context.fixed_parameters.get("early_stopping") is not False:
        raise Week5ProtocolViolation("HGB HPO early stopping must remain disabled")
    if context.fixed_parameters.get("random_state") != context.seed:
        raise Week5ProtocolViolation("HGB HPO random state must use the project seed")

    common: dict[str, Any] = {
        **context.params,
        "early_stopping": False,
        "random_state": context.seed,
    }
    if context.task == "classification":
        if context.fixed_parameters.get("class_weight_policy") != (
            "balanced_from_training_fold_only"
        ):
            raise Week5ProtocolViolation("HGB classifier class-weight policy is not frozen")
        if context.class_weights is None:
            raise Week5ProtocolViolation("HGB classifier requires train-fold class weights")
        return HistGradientBoostingClassifier(
            loss="log_loss", class_weight=context.class_weights, **common
        )
    if context.task == "regression":
        if context.class_weights is not None:
            raise Week5ProtocolViolation("HGB regressor must not receive class weights")
        return HistGradientBoostingRegressor(loss="squared_error", **common)
    raise Week5ProtocolViolation(f"unsupported HGB HPO task {context.task!r}")
