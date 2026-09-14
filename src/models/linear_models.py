"""Week-4 fixed Logistic/Ridge baseline factory for Core Arrival.

The shared runner owns the existing Week-3A linear preprocessor.  This module
only instantiates the two estimators after the runner has derived fold-local
class weights from training labels.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

import yaml
from sklearn.linear_model import LogisticRegression, Ridge

from src.data.load_aeolus import load_base_config, resolve_project_root
from src.models.contracts import (
    CLASSIFICATION_THRESHOLD,
    FEATURE_MANIFEST_VERSION,
    WEEK4_EXPERIMENT_CONTRACT_VERSION,
    Week4ContractViolation,
)
from src.models.rolling import EstimatorBundle, FoldContext


LINEAR_BASELINE_VERSION: Final = "arrival_linear_baseline_v1"
LINEAR_BASELINE_CONFIG_PATH: Final = Path("configs/week4_linear_baseline.yaml")


@dataclass(frozen=True)
class LinearBaselineConfig:
    baseline_version: str
    logistic_solver: str
    logistic_c: float
    logistic_max_iter: int
    logistic_tol: float
    ridge_alpha: float
    ridge_solver: str
    ridge_tol: float


def load_linear_baseline_config(
    *, project_root: Path | None = None
) -> LinearBaselineConfig:
    """Load the locked, non-HPO Week-4 baseline configuration."""

    root = resolve_project_root(project_root)
    path = root / LINEAR_BASELINE_CONFIG_PATH
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise Week4ContractViolation("linear baseline config is unreadable") from error
    if not isinstance(payload, dict):
        raise Week4ContractViolation("linear baseline config must be a mapping")
    classification = payload.get("classification")
    regression = payload.get("regression")
    threshold_policy = payload.get("threshold_policy")
    hpo = payload.get("hpo")
    if not all(isinstance(section, dict) for section in (classification, regression, threshold_policy, hpo)):
        raise Week4ContractViolation("linear baseline config sections are malformed")
    if (
        payload.get("baseline_version") != LINEAR_BASELINE_VERSION
        or payload.get("experiment_contract_version") != WEEK4_EXPERIMENT_CONTRACT_VERSION
        or payload.get("task") != "arrival_core"
        or payload.get("method_id") != "linear"
        or payload.get("feature_manifest_version") != FEATURE_MANIFEST_VERSION
        or payload.get("preprocessing_version") != "arrival_preprocessing_v1"
    ):
        raise Week4ContractViolation("linear baseline config conflicts with the locked Arrival contract")
    if classification != {
        "estimator": "LogisticRegression",
        "solver": "saga",
        "C": 1.0,
        "max_iter": 300,
        "tol": 0.001,
        "fit_intercept": True,
        "class_weight_policy": "balanced_from_training_fold_only",
        "random_state_source": "configs/base.yaml:reproducibility.project_seed",
    }:
        raise Week4ContractViolation("unexpected LogisticRegression baseline configuration")
    if regression != {
        "estimator": "Ridge",
        "alpha": 1.0,
        "solver": "lsqr",
        "tol": 0.001,
        "fit_intercept": True,
    }:
        raise Week4ContractViolation("unexpected Ridge baseline configuration")
    if threshold_policy != {
        "fixed_probability_threshold": CLASSIFICATION_THRESHOLD,
        "validation_optimization_allowed": False,
    } or hpo.get("allowed") is not False:
        raise Week4ContractViolation("Week-4 linear threshold/HPO policy is not locked")
    return LinearBaselineConfig(
        baseline_version=LINEAR_BASELINE_VERSION,
        logistic_solver="saga",
        logistic_c=1.0,
        logistic_max_iter=300,
        logistic_tol=0.001,
        ridge_alpha=1.0,
        ridge_solver="lsqr",
        ridge_tol=0.001,
    )


def build_linear_estimators(
    context: FoldContext, *, config: LinearBaselineConfig
) -> EstimatorBundle:
    """Create deterministic fixed-baseline estimators for one training fold."""

    if context.spec.method_id != "linear":
        raise Week4ContractViolation("linear factory may only serve method_id='linear'")
    if context.spec.model_version != config.baseline_version:
        raise Week4ContractViolation("experiment model_version must match locked linear baseline version")
    _assert_project_seed(context.spec.seed)
    classifier = LogisticRegression(
        solver=config.logistic_solver,
        C=config.logistic_c,
        max_iter=config.logistic_max_iter,
        tol=config.logistic_tol,
        fit_intercept=True,
        class_weight=context.class_weights,
        random_state=context.spec.seed,
    )
    regressor = Ridge(
        alpha=config.ridge_alpha,
        solver=config.ridge_solver,
        tol=config.ridge_tol,
        fit_intercept=True,
    )
    return EstimatorBundle(classifier=classifier, regressor=regressor)


def _assert_project_seed(seed: int, *, project_root: Path | None = None) -> None:
    config = load_base_config(project_root=project_root)
    expected = config.get("reproducibility", {}).get("project_seed")
    if seed != expected:
        raise Week4ContractViolation("linear estimator randomness must use the configured project seed")
