"""Week-4 fixed HistGradientBoosting baseline factory for Core Arrival."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

import yaml
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor

from src.data.load_aeolus import load_base_config, resolve_project_root
from src.models.contracts import (
    CLASSIFICATION_THRESHOLD,
    FEATURE_MANIFEST_VERSION,
    WEEK4_EXPERIMENT_CONTRACT_VERSION,
    Week4ContractViolation,
)
from src.models.rolling import EstimatorBundle, FoldContext


HGB_BASELINE_VERSION: Final = "arrival_hist_gradient_boosting_baseline_v1"
HGB_BASELINE_CONFIG_PATH: Final = Path("configs/week4_hist_gradient_boosting_baseline.yaml")


@dataclass(frozen=True)
class HGBBaselineConfig:
    baseline_version: str
    learning_rate: float
    max_iter: int
    max_leaf_nodes: int
    max_depth: int
    min_samples_leaf: int
    l2_regularization: float


def load_hgb_baseline_config(*, project_root: Path | None = None) -> HGBBaselineConfig:
    """Load the locked, non-HPO HGB baseline configuration."""

    root = resolve_project_root(project_root)
    path = root / HGB_BASELINE_CONFIG_PATH
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise Week4ContractViolation("HGB baseline config is unreadable") from error
    if not isinstance(payload, dict):
        raise Week4ContractViolation("HGB baseline config must be a mapping")
    classification = payload.get("classification")
    regression = payload.get("regression")
    resource_policy = payload.get("resource_policy")
    threshold_policy = payload.get("threshold_policy")
    hpo = payload.get("hpo")
    if not all(
        isinstance(section, dict)
        for section in (classification, regression, resource_policy, threshold_policy, hpo)
    ):
        raise Week4ContractViolation("HGB baseline config sections are malformed")
    if (
        payload.get("baseline_version") != HGB_BASELINE_VERSION
        or payload.get("experiment_contract_version") != WEEK4_EXPERIMENT_CONTRACT_VERSION
        or payload.get("task") != "arrival_core"
        or payload.get("method_id") != "hist_gradient_boosting"
        or payload.get("feature_manifest_version") != FEATURE_MANIFEST_VERSION
        or payload.get("preprocessing_version") != "arrival_preprocessing_v1"
    ):
        raise Week4ContractViolation("HGB config conflicts with the locked Arrival contract")
    common = {
        "learning_rate": 0.05,
        "max_iter": 200,
        "max_leaf_nodes": 31,
        "max_depth": 8,
        "min_samples_leaf": 50,
        "l2_regularization": 1.0,
        "max_features": 1.0,
        "max_bins": 255,
        "categorical_features": None,
        "early_stopping": False,
        "warm_start": False,
        "random_state_source": "configs/base.yaml:reproducibility.project_seed",
    }
    expected_classification = {
        "estimator": "HistGradientBoostingClassifier",
        "loss": "log_loss",
        **common,
        "class_weight_policy": "balanced_from_training_fold_only",
    }
    expected_regression = {
        "estimator": "HistGradientBoostingRegressor",
        "loss": "squared_error",
        **common,
    }
    if classification != expected_classification or regression != expected_regression:
        raise Week4ContractViolation("unexpected HGB baseline configuration")
    expected_rationale = (
        "Fixed capacity-bound baseline: capped boosting iterations, bounded tree "
        "complexity and leaf support, plus no internal validation split. No parameter "
        "was selected from production validation metrics.\n"
    )
    if resource_policy != {
        "target_memory_gib": 16,
        "production_training_rows": "full_eligible_fold_rows",
        "production_sampling_allowed": False,
        "early_stopping_policy": "disabled_no_internal_validation_split",
        "rationale": expected_rationale,
    }:
        raise Week4ContractViolation("HGB resource policy is not locked")
    if threshold_policy != {
        "fixed_probability_threshold": CLASSIFICATION_THRESHOLD,
        "validation_optimization_allowed": False,
    } or hpo.get("allowed") is not False:
        raise Week4ContractViolation("HGB threshold/HPO policy is not locked")
    return HGBBaselineConfig(
        baseline_version=HGB_BASELINE_VERSION,
        learning_rate=0.05,
        max_iter=200,
        max_leaf_nodes=31,
        max_depth=8,
        min_samples_leaf=50,
        l2_regularization=1.0,
    )


def build_hgb_estimators(context: FoldContext, *, config: HGBBaselineConfig) -> EstimatorBundle:
    """Create fixed HGB estimators; all preprocessing remains in the shared runner."""

    if context.spec.method_id != "hist_gradient_boosting":
        raise Week4ContractViolation("HGB factory requires method_id='hist_gradient_boosting'")
    if context.spec.model_version != config.baseline_version:
        raise Week4ContractViolation("experiment model_version must match locked HGB baseline")
    _assert_project_seed(context.spec.seed)
    common = {
        "learning_rate": config.learning_rate,
        "max_iter": config.max_iter,
        "max_leaf_nodes": config.max_leaf_nodes,
        "max_depth": config.max_depth,
        "min_samples_leaf": config.min_samples_leaf,
        "l2_regularization": config.l2_regularization,
        "max_features": 1.0,
        "max_bins": 255,
        "categorical_features": None,
        "early_stopping": False,
        "warm_start": False,
        "random_state": context.spec.seed,
    }
    return EstimatorBundle(
        classifier=HistGradientBoostingClassifier(
            loss="log_loss",
            class_weight=context.class_weights,
            **common,
        ),
        regressor=HistGradientBoostingRegressor(loss="squared_error", **common),
    )


def _assert_project_seed(seed: int, *, project_root: Path | None = None) -> None:
    project = load_base_config(project_root=project_root)
    expected = project.get("reproducibility", {}).get("project_seed")
    if seed != expected:
        raise Week4ContractViolation("HGB randomness must use the configured project seed")
