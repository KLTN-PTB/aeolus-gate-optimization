"""Generic, fold-bounded objective engine for the frozen Week-5 HPO protocol."""

from __future__ import annotations

import gc
import pickle
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from hashlib import sha256
from time import perf_counter
from typing import Any, Protocol

import numpy as np

from src.data.preprocessing import build_boosting_preprocessor, build_tree_preprocessor
from src.models.contracts import (
    CLASSIFICATION_THRESHOLD,
    FoldData,
    RollingFold,
    prepared_row_fingerprint,
    validate_fold_data,
)
from src.models.metrics import classification_metrics, regression_metrics
from src.models.rolling import derive_balanced_class_weights
from src.models.week5_contracts import (
    HPOTask,
    Week5StudySpec,
    load_week5_rolling_folds,
    load_week5_study_specs,
    validate_week5_rolling_folds,
)
from src.models.week5_hpo_protocol import (
    Week5HPOProtocol,
    Week5ProtocolViolation,
    aggregate_classification_objective,
    aggregate_regression_objective,
    load_week5_hpo_protocol,
)


class TrialProtocol(Protocol):
    number: int
    params: dict[str, Any]

    def suggest_int(
        self,
        name: str,
        low: int,
        high: int,
        *,
        step: int = 1,
        log: bool = False,
    ) -> int: ...

    def suggest_float(
        self,
        name: str,
        low: float,
        high: float,
        *,
        step: float | None = None,
        log: bool = False,
    ) -> float: ...

    def suggest_categorical(self, name: str, choices: Sequence[Any]) -> Any: ...

    def set_user_attr(self, name: str, value: Any) -> None: ...


class HPOClassifierProtocol(Protocol):
    classes_: object

    def fit(self, X: object, y: object) -> object: ...

    def predict_proba(self, X: object) -> object: ...


class HPORegressorProtocol(Protocol):
    def fit(self, X: object, y: object) -> object: ...

    def predict(self, X: object) -> object: ...


@dataclass(frozen=True)
class HPOFoldContext:
    """Fold-local context supplied to a task-specific estimator factory."""

    fold: RollingFold
    method_id: str
    model_family: str
    task: HPOTask
    params: dict[str, Any]
    fixed_parameters: dict[str, Any]
    seed: int
    class_weights: dict[int, float] | None


@dataclass(frozen=True)
class HPOFoldResult:
    fold_id: str
    validation_year: int
    train_row_fingerprint: str
    validation_row_fingerprint: str
    objective_value: float
    metrics: dict[str, Any]


FoldDataProvider = Callable[[RollingFold], FoldData]
EstimatorFactory = Callable[[HPOFoldContext], HPOClassifierProtocol | HPORegressorProtocol]
PreprocessorFactory = Callable[[], object]


def run_hpo_trial(
    spec: Week5StudySpec,
    *,
    trial: TrialProtocol,
    fold_data_provider: FoldDataProvider,
    estimator_factory: EstimatorFactory,
    protocol: Week5HPOProtocol | None = None,
    folds: Sequence[RollingFold] | None = None,
    preprocessor_factory: PreprocessorFactory | None = None,
) -> float:
    """Evaluate one parameter trial across four equally weighted rolling folds.

    The provider is called inside a fold-local helper, so multi-year matrices
    from one fold become unreachable before the next fold is loaded.
    """

    active_protocol = protocol or load_week5_hpo_protocol()
    if spec.protocol_hash != active_protocol.protocol_hash:
        raise Week5ProtocolViolation("trial spec/protocol hash mismatch")
    registered = load_week5_study_specs(active_protocol).get(spec.study_id)
    if registered is None or spec != registered:
        raise Week5ProtocolViolation("trial spec differs from its frozen study declaration")
    if folds is None:
        active_folds = load_week5_rolling_folds(active_protocol)
    else:
        active_folds = tuple(folds)
        validate_week5_rolling_folds(active_folds)
    params = _suggest_parameters(trial, spec.search_space)
    factory = preprocessor_factory or _default_preprocessor_factory(spec)

    started = perf_counter()
    fold_results: list[HPOFoldResult] = []
    for fold in active_folds:
        try:
            fold_results.append(
                _run_hpo_fold(
                    spec,
                    fold=fold,
                    params=params,
                    fold_data_provider=fold_data_provider,
                    estimator_factory=estimator_factory,
                    preprocessor_factory=factory,
                )
            )
        finally:
            gc.collect()

    values = [result.objective_value for result in fold_results]
    aggregate = (
        aggregate_classification_objective(values)
        if spec.task == "classification"
        else aggregate_regression_objective(values)
    )
    runtime_seconds = perf_counter() - started
    attributes = {
        "trial_number": int(trial.number),
        "params": dict(params),
        "fold_ids": [result.fold_id for result in fold_results],
        "per_fold_objective": values,
        "per_fold_metrics": [result.metrics for result in fold_results],
        "aggregate_objective": aggregate,
        "seed": spec.seed,
        "runtime_seconds": runtime_seconds,
        "model_family": spec.model_family,
        "method_id": spec.method_id,
        "task": spec.task,
        "feature_manifest_version": spec.feature_manifest_version,
        "preprocessing_version": spec.preprocessing_version,
        "protocol_hash": spec.protocol_hash,
        "train_row_fingerprints": {
            result.fold_id: result.train_row_fingerprint for result in fold_results
        },
        "validation_row_fingerprints": {
            result.fold_id: result.validation_row_fingerprint for result in fold_results
        },
    }
    for name, value in attributes.items():
        trial.set_user_attr(name, value)
    return aggregate


def _run_hpo_fold(
    spec: Week5StudySpec,
    *,
    fold: RollingFold,
    params: dict[str, Any],
    fold_data_provider: FoldDataProvider,
    estimator_factory: EstimatorFactory,
    preprocessor_factory: PreprocessorFactory,
) -> HPOFoldResult:
    data = fold_data_provider(fold)
    validate_fold_data(fold, data)
    train_fingerprint = prepared_row_fingerprint(data.train)
    validation_fingerprint = prepared_row_fingerprint(data.validation)
    class_weights = (
        derive_balanced_class_weights(data.train.y_arr_cls)
        if spec.task == "classification"
        else None
    )
    context = HPOFoldContext(
        fold=fold,
        method_id=spec.method_id,
        model_family=spec.model_family,
        task=spec.task,
        params=dict(params),
        fixed_parameters=dict(spec.fixed_parameters),
        seed=spec.seed,
        class_weights=class_weights,
    )
    preprocessor = preprocessor_factory()
    estimator = estimator_factory(context)
    transformed_train = preprocessor.fit_transform(data.train.X)  # type: ignore[attr-defined]
    target = data.train.y_arr_cls if spec.task == "classification" else data.train.y_arr_reg
    estimator.fit(transformed_train, target)
    training_state = _preprocessor_state_digest(preprocessor)
    transformed_validation = preprocessor.transform(data.validation.X)  # type: ignore[attr-defined]
    if training_state != _preprocessor_state_digest(preprocessor):
        raise Week5ProtocolViolation(
            f"{fold.fold_id} validation transform mutated fitted preprocessing state"
        )

    if spec.task == "classification":
        probability = _positive_probability(estimator, transformed_validation)
        measured = classification_metrics(
            data.validation.y_arr_cls,
            probability,
            threshold=CLASSIFICATION_THRESHOLD,
        )
        if measured.pr_auc is None:
            raise Week5ProtocolViolation(
                f"{fold.fold_id} classification objective requires both validation classes"
            )
        objective = measured.pr_auc
        metrics = _without_unavailable(asdict(measured))
    else:
        prediction = np.asarray(estimator.predict(transformed_validation), dtype=float).reshape(-1)  # type: ignore[union-attr]
        if len(prediction) != len(data.validation.X) or not np.isfinite(prediction).all():
            raise Week5ProtocolViolation("regressor returned malformed signed-delay predictions")
        measured = regression_metrics(data.validation.y_arr_reg, prediction)
        objective = measured.mae
        metrics = _without_unavailable(asdict(measured))

    return HPOFoldResult(
        fold_id=fold.fold_id,
        validation_year=fold.validation_year,
        train_row_fingerprint=train_fingerprint,
        validation_row_fingerprint=validation_fingerprint,
        objective_value=float(objective),
        metrics=metrics,
    )


def _suggest_parameters(
    trial: TrialProtocol,
    search_space: Any,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    for name, declaration in search_space.items():
        kind = declaration["type"]
        if kind == "int":
            kwargs = {
                key: declaration[key]
                for key in ("step", "log")
                if key in declaration
            }
            params[name] = trial.suggest_int(
                name,
                int(declaration["low"]),
                int(declaration["high"]),
                **kwargs,
            )
        elif kind == "float":
            kwargs = {
                key: declaration[key]
                for key in ("step", "log")
                if key in declaration
            }
            params[name] = trial.suggest_float(
                name,
                float(declaration["low"]),
                float(declaration["high"]),
                **kwargs,
            )
        elif kind == "categorical":
            params[name] = trial.suggest_categorical(name, list(declaration["choices"]))
        else:
            raise Week5ProtocolViolation(f"unsupported search parameter type {kind!r}")
    return params


def _default_preprocessor_factory(spec: Week5StudySpec) -> PreprocessorFactory:
    if spec.model_family == "tree":
        return build_tree_preprocessor
    if spec.model_family == "boosting":
        return build_boosting_preprocessor
    raise Week5ProtocolViolation(f"unsupported Week-5 model family {spec.model_family!r}")


def _positive_probability(estimator: object, X: object) -> np.ndarray:
    classes = np.asarray(getattr(estimator, "classes_", None)).reshape(-1)
    predict_proba = getattr(estimator, "predict_proba", None)
    if not callable(predict_proba):
        raise Week5ProtocolViolation("classification HPO requires predict_proba")
    probability = np.asarray(predict_proba(X), dtype=float)
    row_count = int(getattr(X, "shape")[0])
    matching = np.flatnonzero(classes == 1)
    if (
        probability.ndim != 2
        or probability.shape[0] != row_count
        or probability.shape[1] != len(classes)
        or len(matching) != 1
    ):
        raise Week5ProtocolViolation("classifier returned malformed probability matrix")
    positive = probability[:, int(matching[0])]
    if not np.isfinite(positive).all() or bool(((positive < 0.0) | (positive > 1.0)).any()):
        raise Week5ProtocolViolation("classifier returned invalid class-1 probabilities")
    return positive


def _preprocessor_state_digest(preprocessor: object) -> str:
    try:
        state = pickle.dumps(preprocessor, protocol=pickle.HIGHEST_PROTOCOL)
    except (pickle.PickleError, TypeError, AttributeError) as error:
        raise Week5ProtocolViolation("fitted preprocessor state is not auditable") from error
    return sha256(state).hexdigest()


def _without_unavailable(value: Any) -> Any:
    """Remove unavailable diagnostics instead of manufacturing numeric values."""

    if isinstance(value, dict):
        return {
            key: _without_unavailable(item)
            for key, item in value.items()
            if item is not None
        }
    if isinstance(value, list):
        return [_without_unavailable(item) for item in value]
    return value
