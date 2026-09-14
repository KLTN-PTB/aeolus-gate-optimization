"""Week-4 fixed Random Forest baseline factory for Core Arrival.

The shared runner owns the Week-3A tree preprocessor and fold-local class
weight derivation.  This module only validates the locked baseline config and
creates deterministic sklearn estimators.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

import yaml
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

from src.data.load_aeolus import load_base_config, resolve_project_root
from src.models.contracts import (
    CLASSIFICATION_THRESHOLD,
    FEATURE_MANIFEST_VERSION,
    WEEK4_EXPERIMENT_CONTRACT_VERSION,
    Week4ContractViolation,
)
from src.models.rolling import EstimatorBundle, FoldContext


RANDOM_FOREST_BASELINE_VERSION: Final = "arrival_random_forest_baseline_v1"
RANDOM_FOREST_BASELINE_CONFIG_PATH: Final = Path("configs/week4_random_forest_baseline.yaml")


@dataclass(frozen=True)
class RandomForestBaselineConfig:
    baseline_version: str
    n_estimators: int
    max_depth: int
    min_samples_split: int
    min_samples_leaf: int
    max_features: str
    n_jobs: int


def load_random_forest_baseline_config(
    *, project_root: Path | None = None
) -> RandomForestBaselineConfig:
    """Load the locked, non-HPO, full-training-row RF configuration."""

    root = resolve_project_root(project_root)
    path = root / RANDOM_FOREST_BASELINE_CONFIG_PATH
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise Week4ContractViolation("Random Forest baseline config is unreadable") from error
    if not isinstance(payload, dict):
        raise Week4ContractViolation("Random Forest baseline config must be a mapping")

    classification = payload.get("classification")
    regression = payload.get("regression")
    resource_policy = payload.get("resource_policy")
    threshold_policy = payload.get("threshold_policy")
    hpo = payload.get("hpo")
    if not all(
        isinstance(section, dict)
        for section in (classification, regression, resource_policy, threshold_policy, hpo)
    ):
        raise Week4ContractViolation("Random Forest baseline config sections are malformed")
    if (
        payload.get("baseline_version") != RANDOM_FOREST_BASELINE_VERSION
        or payload.get("experiment_contract_version") != WEEK4_EXPERIMENT_CONTRACT_VERSION
        or payload.get("task") != "arrival_core"
        or payload.get("method_id") != "random_forest"
        or payload.get("feature_manifest_version") != FEATURE_MANIFEST_VERSION
        or payload.get("preprocessing_version") != "arrival_preprocessing_v1"
    ):
        raise Week4ContractViolation("Random Forest config conflicts with the locked Arrival contract")

    common = {
        "n_estimators": 96,
        "max_depth": 14,
        "min_samples_split": 40,
        "min_samples_leaf": 20,
        "max_features": "sqrt",
        "bootstrap": True,
        "max_samples": None,
        "n_jobs": 1,
        "random_state_source": "configs/base.yaml:reproducibility.project_seed",
    }
    expected_classification = {
        "estimator": "RandomForestClassifier",
        "criterion": "gini",
        **common,
        "class_weight_policy": "balanced_from_training_fold_only",
    }
    expected_regression = {
        "estimator": "RandomForestRegressor",
        "criterion": "squared_error",
        **common,
    }
    if classification != expected_classification or regression != expected_regression:
        raise Week4ContractViolation("unexpected Random Forest baseline configuration")
    if resource_policy != {
        "target_memory_gib": 16,
        "execution_parallelism": 1,
        "production_training_rows": "full_eligible_fold_rows",
        "production_sampling_allowed": False,
        "max_samples_policy": "null_means_full_bootstrap_draw_size",
            "rationale": (
                "Fixed capacity-bound baseline: shallow-enough trees, minimum leaf support, "
                "feature subsampling, and single-process execution cap concurrent forest "
                "memory. No parameter was selected from validation metrics.\n"
            ),
    }:
        raise Week4ContractViolation("Random Forest resource policy is not locked")
    if threshold_policy != {
        "fixed_probability_threshold": CLASSIFICATION_THRESHOLD,
        "validation_optimization_allowed": False,
    } or hpo.get("allowed") is not False:
        raise Week4ContractViolation("Random Forest threshold/HPO policy is not locked")

    return RandomForestBaselineConfig(
        baseline_version=RANDOM_FOREST_BASELINE_VERSION,
        n_estimators=96,
        max_depth=14,
        min_samples_split=40,
        min_samples_leaf=20,
        max_features="sqrt",
        n_jobs=1,
    )


def build_random_forest_estimators(
    context: FoldContext, *, config: RandomForestBaselineConfig
) -> EstimatorBundle:
    """Create RF estimators without altering shared features, targets, or folds."""

    if context.spec.method_id != "random_forest":
        raise Week4ContractViolation("Random Forest factory requires method_id='random_forest'")
    if context.spec.model_version != config.baseline_version:
        raise Week4ContractViolation("experiment model_version must match locked Random Forest baseline")
    _assert_project_seed(context.spec.seed)
    common = {
        "n_estimators": config.n_estimators,
        "max_depth": config.max_depth,
        "min_samples_split": config.min_samples_split,
        "min_samples_leaf": config.min_samples_leaf,
        "max_features": config.max_features,
        "bootstrap": True,
        "max_samples": None,
        "n_jobs": config.n_jobs,
        "random_state": context.spec.seed,
    }
    return EstimatorBundle(
        classifier=RandomForestClassifier(
            criterion="gini",
            class_weight=context.class_weights,
            **common,
        ),
        regressor=RandomForestRegressor(
            criterion="squared_error",
            **common,
        ),
    )


def _assert_project_seed(seed: int, *, project_root: Path | None = None) -> None:
    project = load_base_config(project_root=project_root)
    expected = project.get("reproducibility", {}).get("project_seed")
    if seed != expected:
        raise Week4ContractViolation("Random Forest randomness must use the configured project seed")
