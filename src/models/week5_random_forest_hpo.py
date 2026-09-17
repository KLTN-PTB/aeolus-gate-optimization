"""Week-5 Random Forest estimator factory for the frozen HPO protocol.

This is intentionally separate from the historical Week-4 baseline factory:
the latter remains evidence of the fixed Week-4 method boundary, while this
factory consumes only a validated Week-5 ``HPOFoldContext``.
"""

from __future__ import annotations

from typing import Any

from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

from src.models.hpo import HPOFoldContext
from src.models.week5_hpo_protocol import Week5ProtocolViolation


_SEARCH_PARAMETER_NAMES = {
    "n_estimators",
    "max_depth",
    "min_samples_split",
    "min_samples_leaf",
    "max_features",
    "max_samples",
}


def build_week5_random_forest_estimator(
    context: HPOFoldContext,
) -> RandomForestClassifier | RandomForestRegressor:
    """Build one deterministic RF estimator from a validated fold context."""

    if context.method_id != "random_forest" or context.model_family != "tree":
        raise Week5ProtocolViolation("RF HPO factory requires random_forest tree context")
    if set(context.params) != _SEARCH_PARAMETER_NAMES:
        raise Week5ProtocolViolation("RF HPO parameters differ from the frozen search space")
    if context.fixed_parameters.get("n_jobs") != 1:
        raise Week5ProtocolViolation("RF HPO requires n_jobs=1")
    if context.fixed_parameters.get("bootstrap") is not True:
        raise Week5ProtocolViolation("RF HPO requires bootstrap=True")
    if context.fixed_parameters.get("random_state") != context.seed:
        raise Week5ProtocolViolation("RF HPO random state must use the project seed")

    common: dict[str, Any] = {
        **context.params,
        "bootstrap": True,
        "n_jobs": 1,
        "random_state": context.seed,
    }
    if context.task == "classification":
        if context.fixed_parameters.get("class_weight_policy") != (
            "balanced_from_training_fold_only"
        ):
            raise Week5ProtocolViolation("RF classifier class-weight policy is not frozen")
        if context.class_weights is None:
            raise Week5ProtocolViolation("RF classifier requires train-fold class weights")
        return RandomForestClassifier(
            criterion="gini",
            class_weight=context.class_weights,
            **common,
        )
    if context.task == "regression":
        if context.class_weights is not None:
            raise Week5ProtocolViolation("RF regressor must not receive class weights")
        return RandomForestRegressor(criterion="squared_error", **common)
    raise Week5ProtocolViolation(f"unsupported RF HPO task {context.task!r}")
