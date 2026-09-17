"""Fixed Week-5 Core Arrival XGBoost baseline without changing Week-4 history."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Final, Mapping

import numpy as np
import pandas as pd
import yaml
from xgboost import XGBClassifier, XGBRegressor

from src.data.load_aeolus import load_base_config, resolve_project_root
from src.data.preprocessing import PREPROCESSING_VERSION, build_boosting_preprocessor
from src.models.artifacts import OOF_COLUMNS, validate_oof_frame
from src.models.contracts import (
    CLASSIFICATION_THRESHOLD,
    FEATURE_MANIFEST_VERSION,
    OOF_SCHEMA_VERSION,
    FoldData,
    RollingFold,
    Week4ContractViolation,
    prepared_row_fingerprint,
    validate_fold_data,
)
from src.models.metrics import classification_metrics, regression_metrics
from src.models.resources import measure_phase
from src.models.rolling import EstimatorBundle, FoldRunResult, derive_balanced_class_weights


XGBOOST_BASELINE_VERSION: Final = "arrival_xgboost_baseline_v1"
WEEK5_XGBOOST_EXPERIMENT_CONTRACT_VERSION: Final = "arrival_week5_xgboost_experiment_v1"
XGBOOST_BASELINE_CONFIG_PATH: Final = Path("configs/week5_xgboost_baseline.yaml")


@dataclass(frozen=True)
class XGBoostBaselineConfig:
    baseline_version: str
    n_estimators: int
    learning_rate: float
    max_depth: int
    min_child_weight: float
    subsample: float
    colsample_bytree: float
    reg_alpha: float
    reg_lambda: float
    max_bin: int
    n_jobs: int


@dataclass(frozen=True)
class Week5XGBoostSpec:
    """Week-5-only experiment identity for the fourth Core Arrival method."""

    model_version: str
    config_version: str
    seed: int
    feature_manifest_version: str = FEATURE_MANIFEST_VERSION
    preprocessing_version: str = PREPROCESSING_VERSION
    experiment_contract_version: str = WEEK5_XGBOOST_EXPERIMENT_CONTRACT_VERSION
    classification_threshold: float = CLASSIFICATION_THRESHOLD
    expected_validation_row_fingerprints: Mapping[str, str] | None = None

    def __post_init__(self) -> None:
        if self.model_version != XGBOOST_BASELINE_VERSION:
            raise Week4ContractViolation("XGBoost model version does not match the fixed baseline")
        if not self.config_version:
            raise Week4ContractViolation("config_version must be non-empty")
        if self.feature_manifest_version != FEATURE_MANIFEST_VERSION:
            raise Week4ContractViolation("unexpected Arrival feature manifest version")
        if self.preprocessing_version != PREPROCESSING_VERSION:
            raise Week4ContractViolation("unexpected Arrival preprocessing version")
        if self.experiment_contract_version != WEEK5_XGBOOST_EXPERIMENT_CONTRACT_VERSION:
            raise Week4ContractViolation("unexpected Week-5 XGBoost experiment contract")
        if self.classification_threshold != CLASSIFICATION_THRESHOLD:
            raise Week4ContractViolation("classification threshold is locked at 0.5")
        if self.expected_validation_row_fingerprints is not None and any(
            not fold_id or not fingerprint
            for fold_id, fingerprint in self.expected_validation_row_fingerprints.items()
        ):
            raise Week4ContractViolation("expected validation row fingerprints must be non-empty")


@dataclass(frozen=True)
class Week5XGBoostFoldContext:
    fold: RollingFold
    class_weights: dict[int, float]
    spec: Week5XGBoostSpec


XGBoostEstimatorFactory = Callable[[Week5XGBoostFoldContext], EstimatorBundle]


def load_xgboost_baseline_config(
    *, project_root: Path | None = None
) -> XGBoostBaselineConfig:
    """Load the fixed, pre-registered CPU-only Week-5 baseline."""

    root = resolve_project_root(project_root)
    path = root / XGBOOST_BASELINE_CONFIG_PATH
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise Week4ContractViolation("XGBoost baseline config is unreadable") from error
    if not isinstance(payload, dict):
        raise Week4ContractViolation("XGBoost baseline config must be a mapping")
    classification = payload.get("classification")
    regression = payload.get("regression")
    resource_policy = payload.get("resource_policy")
    threshold_policy = payload.get("threshold_policy")
    hpo = payload.get("hpo")
    if not all(
        isinstance(section, dict)
        for section in (classification, regression, resource_policy, threshold_policy, hpo)
    ):
        raise Week4ContractViolation("XGBoost baseline config sections are malformed")
    if (
        payload.get("baseline_version") != XGBOOST_BASELINE_VERSION
        or payload.get("experiment_contract_version") != WEEK5_XGBOOST_EXPERIMENT_CONTRACT_VERSION
        or payload.get("task") != "arrival_core"
        or payload.get("method_id") != "xgboost"
        or payload.get("feature_manifest_version") != FEATURE_MANIFEST_VERSION
        or payload.get("preprocessing_version") != PREPROCESSING_VERSION
    ):
        raise Week4ContractViolation("XGBoost config conflicts with the locked Arrival contract")

    common = {
        "n_estimators": 128,
        "learning_rate": 0.05,
        "max_depth": 6,
        "min_child_weight": 20.0,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "reg_alpha": 0.0,
        "reg_lambda": 2.0,
        "tree_method": "hist",
        "device": "cpu",
        "max_bin": 256,
        "n_jobs": 1,
        "early_stopping": False,
        "random_state_source": "configs/base.yaml:reproducibility.project_seed",
    }
    expected_classification = {
        "estimator": "XGBClassifier",
        "objective": "binary:logistic",
        "eval_metric": "logloss",
        **common,
        "class_imbalance_policy": "scale_pos_weight_from_training_fold_only",
    }
    expected_regression = {
        "estimator": "XGBRegressor",
        "objective": "reg:squarederror",
        "eval_metric": "rmse",
        **common,
    }
    if classification != expected_classification or regression != expected_regression:
        raise Week4ContractViolation("unexpected XGBoost baseline configuration")
    if resource_policy != {
        "target_memory_gib": 16,
        "execution_parallelism": 1,
        "production_training_rows": "full_eligible_fold_rows",
        "production_sampling_allowed": False,
        "gpu_allowed": False,
        "early_stopping_policy": "disabled_no_locked_validation_control",
        "rationale": (
            "Fixed CPU-safe baseline pre-registered before production validation metrics: "
            "histogram trees, bounded depth and estimators, conservative row/column sampling, "
            "regularization, single-process execution, and no validation-driven early stopping."
        ),
    }:
        raise Week4ContractViolation("XGBoost resource policy is not locked")
    if threshold_policy != {
        "fixed_probability_threshold": CLASSIFICATION_THRESHOLD,
        "validation_optimization_allowed": False,
    } or hpo.get("allowed") is not False:
        raise Week4ContractViolation("XGBoost threshold/HPO policy is not locked")
    return XGBoostBaselineConfig(
        baseline_version=XGBOOST_BASELINE_VERSION,
        n_estimators=128,
        learning_rate=0.05,
        max_depth=6,
        min_child_weight=20.0,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.0,
        reg_lambda=2.0,
        max_bin=256,
        n_jobs=1,
    )


def build_xgboost_estimators(
    context: Week5XGBoostFoldContext,
    *,
    config: XGBoostBaselineConfig,
) -> EstimatorBundle:
    """Build deterministic CPU XGBoost estimators with train-fold imbalance only."""

    if context.spec.model_version != config.baseline_version:
        raise Week4ContractViolation("experiment model_version must match fixed XGBoost baseline")
    _assert_project_seed(context.spec.seed)
    negative_weight = context.class_weights.get(0)
    positive_weight = context.class_weights.get(1)
    if (
        negative_weight is None
        or positive_weight is None
        or negative_weight <= 0.0
        or positive_weight <= 0.0
    ):
        raise Week4ContractViolation("XGBoost requires positive train-fold class weights")
    scale_pos_weight = positive_weight / negative_weight
    common = {
        "n_estimators": config.n_estimators,
        "learning_rate": config.learning_rate,
        "max_depth": config.max_depth,
        "min_child_weight": config.min_child_weight,
        "subsample": config.subsample,
        "colsample_bytree": config.colsample_bytree,
        "reg_alpha": config.reg_alpha,
        "reg_lambda": config.reg_lambda,
        "tree_method": "hist",
        "device": "cpu",
        "max_bin": config.max_bin,
        "n_jobs": config.n_jobs,
        "random_state": context.spec.seed,
        "verbosity": 0,
        "early_stopping_rounds": None,
    }
    return EstimatorBundle(
        classifier=XGBClassifier(
            objective="binary:logistic",
            eval_metric="logloss",
            scale_pos_weight=scale_pos_weight,
            **common,
        ),
        regressor=XGBRegressor(
            objective="reg:squarederror",
            eval_metric="rmse",
            **common,
        ),
    )


def run_xgboost_fold_experiment(
    spec: Week5XGBoostSpec,
    *,
    fold: RollingFold,
    data: FoldData,
    estimator_factory: XGBoostEstimatorFactory,
    expected_validation_row_fingerprint: str | None = None,
) -> tuple[FoldRunResult, pd.DataFrame]:
    """Run one bounded Week-5 XGBoost fold with the proven Arrival contracts."""

    validate_fold_data(fold, data)
    train_fingerprint = prepared_row_fingerprint(data.train)
    validation_fingerprint = prepared_row_fingerprint(data.validation)
    expected = expected_validation_row_fingerprint
    if expected is None and spec.expected_validation_row_fingerprints is not None:
        expected = spec.expected_validation_row_fingerprints.get(fold.fold_id)
    if expected is not None and expected != validation_fingerprint:
        raise Week4ContractViolation(
            f"{fold.fold_id} validation target rows differ from the declared reference"
        )
    class_weights = derive_balanced_class_weights(data.train.y_arr_cls)
    context = Week5XGBoostFoldContext(fold=fold, class_weights=class_weights, spec=spec)
    preprocessor = build_boosting_preprocessor()
    estimators = estimator_factory(context)

    def fit_phase() -> object:
        transformed_train = preprocessor.fit_transform(data.train.X)
        estimators.classifier.fit(transformed_train, data.train.y_arr_cls)
        estimators.regressor.fit(transformed_train, data.train.y_arr_reg)
        return transformed_train

    _, fit_resources = measure_phase(fit_phase)
    training_state = _fitted_preprocessor_signature(preprocessor)

    def prediction_phase() -> tuple[np.ndarray, np.ndarray]:
        transformed_validation = preprocessor.transform(data.validation.X)
        probability = _positive_probability(estimators.classifier, transformed_validation)
        prediction = np.asarray(estimators.regressor.predict(transformed_validation), dtype=float).reshape(-1)
        if len(prediction) != len(data.validation.X) or not np.isfinite(prediction).all():
            raise Week4ContractViolation("regressor returned malformed signed-delay predictions")
        return probability, prediction

    (probability, prediction), prediction_resources = measure_phase(prediction_phase)
    if training_state != _fitted_preprocessor_signature(preprocessor):
        raise Week4ContractViolation("validation transform mutated fitted training preprocessor state")
    classification = classification_metrics(
        data.validation.y_arr_cls,
        probability,
        threshold=spec.classification_threshold,
    )
    regression = regression_metrics(data.validation.y_arr_reg, prediction)
    oof = _build_xgboost_oof_frame(spec, fold, data, probability, prediction)
    validate_oof_frame(oof)
    return (
        FoldRunResult(
            fold_id=fold.fold_id,
            validation_year=fold.validation_year,
            validation_rows=len(oof),
            train_row_fingerprint=train_fingerprint,
            validation_row_fingerprint=validation_fingerprint,
            class_weights=class_weights,
            classification=classification,
            regression=regression,
            fit_resources=fit_resources,
            prediction_resources=prediction_resources,
            total_runtime_seconds=(fit_resources.runtime_seconds + prediction_resources.runtime_seconds),
            peak_memory_bytes=max(
                fit_resources.peak_memory_bytes,
                prediction_resources.peak_memory_bytes,
            ),
            preprocessor_state_unchanged_after_validation=True,
        ),
        oof,
    )


def _fitted_preprocessor_signature(preprocessor: object) -> tuple[object, ...]:
    named = getattr(preprocessor, "named_transformers_")
    numeric_imputer = named["numeric"].named_steps["imputer"]
    categorical_encoder = named["categorical"].named_steps["encoder"]
    frequency_encoder = named["high_cardinality"].named_steps["encoder"]
    return (
        tuple(getattr(preprocessor, "get_feature_names_out")().tolist()),
        repr(getattr(numeric_imputer, "statistics_")),
        repr(getattr(categorical_encoder, "categories_")),
        repr(getattr(frequency_encoder, "frequency_maps_")),
    )


def _positive_probability(classifier: object, X: object) -> np.ndarray:
    classes = np.asarray(getattr(classifier, "classes_")).reshape(-1)
    probability = np.asarray(getattr(classifier, "predict_proba")(X), dtype=float)
    row_count = int(getattr(X, "shape")[0])
    matching = np.flatnonzero(classes == 1)
    if probability.ndim != 2 or probability.shape[0] != row_count:
        raise Week4ContractViolation("classifier returned malformed probability matrix")
    if len(matching) != 1 or probability.shape[1] != len(classes):
        raise Week4ContractViolation("classifier must expose one probability column for class 1")
    positive = probability[:, int(matching[0])]
    if not np.isfinite(positive).all() or bool(((positive < 0.0) | (positive > 1.0)).any()):
        raise Week4ContractViolation("classifier returned invalid class-1 probabilities")
    return positive


def _build_xgboost_oof_frame(
    spec: Week5XGBoostSpec,
    fold: RollingFold,
    data: FoldData,
    probability: np.ndarray,
    prediction: np.ndarray,
) -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "flight_key": data.validation.identifiers["flight_key"].astype(str).to_numpy(),
            "fold_id": fold.fold_id,
            "validation_year": fold.validation_year,
            "y_arr_cls": data.validation.y_arr_cls.astype("int8").to_numpy(),
            "p_arr_delay_15": probability,
            "y_arr_cls_pred_0_5": (probability >= spec.classification_threshold).astype("int8"),
            "y_arr_reg": data.validation.y_arr_reg.astype("float64").to_numpy(),
            "predicted_arr_delay_min": prediction,
            "method_id": "xgboost",
            "model_version": spec.model_version,
            "preprocessing_version": spec.preprocessing_version,
            "feature_manifest_version": spec.feature_manifest_version,
            "config_version": spec.config_version,
            "seed": spec.seed,
            "experiment_contract_version": spec.experiment_contract_version,
            "oof_schema_version": OOF_SCHEMA_VERSION,
        }
    )
    return frame.loc[:, list(OOF_COLUMNS)]


def _assert_project_seed(seed: int, *, project_root: Path | None = None) -> None:
    project = load_base_config(project_root=project_root)
    expected = project.get("reproducibility", {}).get("project_seed")
    if seed != expected:
        raise Week4ContractViolation("XGBoost randomness must use the configured project seed")
