"""Estimator-agnostic, fold-isolated Week-4 Core Arrival experiment runner."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any, Protocol

import numpy as np
import pandas as pd

from src.data.preprocessing import (
    build_boosting_preprocessor,
    build_linear_preprocessor,
    build_tree_preprocessor,
)
from src.models.artifacts import OOF_COLUMNS, validate_oof_frame
from src.models.contracts import (
    CLASSIFICATION_THRESHOLD,
    OOF_SCHEMA_VERSION,
    WEEK4_FRAMEWORK_VERSION,
    ExperimentSpec,
    FoldData,
    RollingFold,
    Week4ContractViolation,
    load_week4_rolling_folds,
    prepared_row_fingerprint,
    validate_fold_data,
)
from src.models.metrics import ClassificationMetrics, RegressionMetrics, classification_metrics, regression_metrics
from src.models.resources import ResourceMeasurement, measure_phase


class ClassifierProtocol(Protocol):
    classes_: object

    def fit(self, X: object, y: object) -> object: ...

    def predict_proba(self, X: object) -> object: ...


class RegressorProtocol(Protocol):
    def fit(self, X: object, y: object) -> object: ...

    def predict(self, X: object) -> object: ...


@dataclass(frozen=True)
class EstimatorBundle:
    """The two estimators supplied by a later method-specific implementation."""

    classifier: ClassifierProtocol
    regressor: RegressorProtocol


@dataclass(frozen=True)
class FoldContext:
    """Training-only context available to an estimator factory."""

    fold: RollingFold
    class_weights: dict[int, float]
    spec: ExperimentSpec


EstimatorFactory = Callable[[FoldContext], EstimatorBundle]
FoldDataProvider = Callable[[RollingFold], FoldData]
OOFSink = Callable[[pd.DataFrame], None]


@dataclass(frozen=True)
class FoldRunResult:
    fold_id: str
    validation_year: int
    validation_rows: int
    train_row_fingerprint: str
    validation_row_fingerprint: str
    class_weights: dict[int, float]
    classification: ClassificationMetrics
    regression: RegressionMetrics
    fit_resources: ResourceMeasurement
    prediction_resources: ResourceMeasurement
    total_runtime_seconds: float
    peak_memory_bytes: int
    preprocessor_state_unchanged_after_validation: bool

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["classification"] = self.classification.to_dict()
        payload["regression"] = self.regression.to_dict()
        payload["fit_resources"] = self.fit_resources.to_dict()
        payload["prediction_resources"] = self.prediction_resources.to_dict()
        return payload


@dataclass(frozen=True)
class ExperimentResult:
    spec: ExperimentSpec
    fold_results: tuple[FoldRunResult, ...]
    oof_rows_written: int
    retained_oof_batches: tuple[pd.DataFrame, ...]

    def manifest(self) -> dict[str, Any]:
        return {
            "framework_version": WEEK4_FRAMEWORK_VERSION,
            "experiment_contract_version": self.spec.experiment_contract_version,
            "task": "arrival_core",
            "flow": "inbound",
            "target_filter": "DEST=ATL",
            "prediction_cutoff": "CRS_DEP_TIME - 2 hours",
            "classification_threshold": CLASSIFICATION_THRESHOLD,
            "probability_calibration": "diagnostics_only_no_posthoc_calibrator",
            "oof_schema_version": OOF_SCHEMA_VERSION,
            "method": {
                "method_id": self.spec.method_id,
                "model_family": self.spec.model_family,
                "model_version": self.spec.model_version,
            },
            "metadata": {
                "config_version": self.spec.config_version,
                "seed": self.spec.seed,
                "feature_manifest_version": self.spec.feature_manifest_version,
                "preprocessing_version": self.spec.preprocessing_version,
            },
            "oof_rows_written": self.oof_rows_written,
            "fold_results": [result.to_dict() for result in self.fold_results],
            "resource_measurement": {
                "method": "tracemalloc_python_allocations",
                "scope": "python_allocations_only_not_process_rss",
            },
        }


def derive_balanced_class_weights(y_train: object) -> dict[int, float]:
    """Derive binary balanced weights from training labels only."""

    y = np.asarray(y_train, dtype=int).reshape(-1)
    if not set(y).issubset({0, 1}) or len(y) == 0:
        raise Week4ContractViolation("training classification labels must be non-empty binary values")
    counts = {label: int((y == label).sum()) for label in (0, 1)}
    if not all(counts.values()):
        raise Week4ContractViolation("each training fold must contain both Arrival classes")
    total = len(y)
    return {label: total / (2.0 * count) for label, count in counts.items()}


def run_rolling_experiment(
    spec: ExperimentSpec,
    *,
    fold_data_provider: FoldDataProvider,
    estimator_factory: EstimatorFactory,
    oof_sink: OOFSink | None = None,
    retain_oof_batches: bool = False,
) -> ExperimentResult:
    """Run one declared Week-4 method across the locked four rolling folds.

    A production caller must provide ``oof_sink`` (normally
    :class:`ParquetOOFSink.append`) so OOF rows are written fold-by-fold.  The
    optional in-memory retention exists only for small synthetic tests/smokes.
    """

    if oof_sink is None and not retain_oof_batches:
        raise Week4ContractViolation("a production rolling run requires an OOF sink")

    retained: list[pd.DataFrame] = []
    fold_results: list[FoldRunResult] = []
    written_rows = 0
    folds = load_week4_rolling_folds()
    if spec.expected_validation_row_fingerprints is not None and set(
        spec.expected_validation_row_fingerprints
    ) != {fold.fold_id for fold in folds}:
        raise Week4ContractViolation(
            "expected validation row fingerprints must cover exactly the locked folds"
        )
    for fold in folds:
        data = fold_data_provider(fold)
        expected = spec.expected_validation_row_fingerprints
        fold_result, oof = run_fold_experiment(
            spec,
            fold=fold,
            data=data,
            estimator_factory=estimator_factory,
            expected_validation_row_fingerprint=(
                expected[fold.fold_id] if expected is not None else None
            ),
        )
        if oof_sink is not None:
            oof_sink(oof)
        if retain_oof_batches:
            retained.append(oof)
        written_rows += len(oof)
        fold_results.append(fold_result)
    return ExperimentResult(
        spec=spec,
        fold_results=tuple(fold_results),
        oof_rows_written=written_rows,
        retained_oof_batches=tuple(retained),
    )


def run_fold_experiment(
    spec: ExperimentSpec,
    *,
    fold: RollingFold,
    data: FoldData,
    estimator_factory: EstimatorFactory,
    expected_validation_row_fingerprint: str | None = None,
) -> tuple[FoldRunResult, pd.DataFrame]:
    """Run one supplied fold, used by the bounded smoke and rolling runner.

    It never selects a fold, opens a partition, or joins years.  The caller is
    responsible for providing bounded, provenance-checked ``FoldData``.
    """

    validate_fold_data(fold, data)
    train_fingerprint = prepared_row_fingerprint(data.train)
    validation_fingerprint = prepared_row_fingerprint(data.validation)
    if (
        expected_validation_row_fingerprint is not None
        and expected_validation_row_fingerprint != validation_fingerprint
    ):
        raise Week4ContractViolation(
            f"{fold.fold_id} validation target rows differ from the declared reference"
        )
    weights = derive_balanced_class_weights(data.train.y_arr_cls)
    context = FoldContext(fold=fold, class_weights=weights, spec=spec)
    preprocessor = _preprocessor_for(spec)
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
    oof = _build_oof_frame(spec, fold, data, probability, prediction)
    validate_oof_frame(oof)
    return (
        FoldRunResult(
            fold_id=fold.fold_id,
            validation_year=fold.validation_year,
            validation_rows=len(oof),
            train_row_fingerprint=train_fingerprint,
            validation_row_fingerprint=validation_fingerprint,
            class_weights=weights,
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


def _preprocessor_for(spec: ExperimentSpec) -> object:
    if spec.model_family == "linear":
        return build_linear_preprocessor()
    if spec.model_family == "tree":
        return build_tree_preprocessor()
    if spec.model_family == "boosting":
        return build_boosting_preprocessor()
    raise Week4ContractViolation(f"unsupported model family {spec.model_family!r}")


def _fitted_preprocessor_signature(preprocessor: object) -> tuple[object, ...]:
    """Capture fitted Week-3A state that validation transforms must not alter."""

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


def _positive_probability(classifier: ClassifierProtocol, X: object) -> np.ndarray:
    classes = np.asarray(classifier.classes_).reshape(-1)
    probability = np.asarray(classifier.predict_proba(X), dtype=float)
    row_count = int(getattr(X, "shape")[0])
    if probability.ndim != 2 or probability.shape[0] != row_count:
        raise Week4ContractViolation("classifier returned malformed probability matrix")
    matching = np.flatnonzero(classes == 1)
    if len(matching) != 1 or probability.shape[1] != len(classes):
        raise Week4ContractViolation("classifier must expose one probability column for class 1")
    positive = probability[:, int(matching[0])]
    if not np.isfinite(positive).all() or bool(((positive < 0.0) | (positive > 1.0)).any()):
        raise Week4ContractViolation("classifier returned invalid class-1 probabilities")
    return positive


def _build_oof_frame(
    spec: ExperimentSpec,
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
            "method_id": spec.method_id,
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
