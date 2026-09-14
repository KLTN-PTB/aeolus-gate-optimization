"""Shared, non-tuned metric definitions for Week-4 Core Arrival baselines."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Final

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    recall_score,
    roc_auc_score,
)


CALIBRATION_BIN_COUNT: Final = 10


class MetricContractViolation(ValueError):
    """Raised for malformed predictions rather than producing misleading metrics."""


@dataclass(frozen=True)
class ClassificationMetrics:
    roc_auc: float | None
    pr_auc: float | None
    recall: float
    f1: float
    brier_score: float
    threshold: float
    calibration: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RegressionMetrics:
    mae: float
    rmse: float
    r2: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def classification_metrics(
    y_true: object, probabilities: object, *, threshold: float
) -> ClassificationMetrics:
    """Compute fixed-threshold and probability metrics without calibration fitting."""

    y = _binary_target(y_true)
    probability = _probabilities(probabilities, expected_length=len(y))
    if threshold != 0.5:
        raise MetricContractViolation("Week-4 classification threshold is fixed at 0.5")
    predicted = (probability >= threshold).astype(int)
    has_both_classes = len(np.unique(y)) == 2
    return ClassificationMetrics(
        roc_auc=float(roc_auc_score(y, probability)) if has_both_classes else None,
        pr_auc=float(average_precision_score(y, probability)) if has_both_classes else None,
        recall=float(recall_score(y, predicted, zero_division=0)),
        f1=float(f1_score(y, predicted, zero_division=0)),
        brier_score=float(brier_score_loss(y, probability)),
        threshold=threshold,
        calibration=calibration_diagnostics(y, probability),
    )


def regression_metrics(y_true: object, predictions: object) -> RegressionMetrics:
    """Score signed ARR_DELAY directly; neither truth nor predictions are clipped."""

    y = _finite_vector(y_true, name="regression ground truth")
    prediction = _finite_vector(predictions, name="regression prediction")
    if len(y) != len(prediction):
        raise MetricContractViolation("regression target and prediction length differ")
    return RegressionMetrics(
        mae=float(mean_absolute_error(y, prediction)),
        rmse=float(np.sqrt(mean_squared_error(y, prediction))),
        r2=float(r2_score(y, prediction)) if len(y) >= 2 else None,
    )


def calibration_diagnostics(y_true: np.ndarray, probabilities: np.ndarray) -> dict[str, Any]:
    """Return fixed-width reliability bins; this does not fit a calibrator."""

    bins: list[dict[str, float | int | None]] = []
    ece = 0.0
    total = len(y_true)
    for index in range(CALIBRATION_BIN_COUNT):
        lower = index / CALIBRATION_BIN_COUNT
        upper = (index + 1) / CALIBRATION_BIN_COUNT
        mask = (
            (probabilities >= lower) & (probabilities < upper)
            if index < CALIBRATION_BIN_COUNT - 1
            else (probabilities >= lower) & (probabilities <= upper)
        )
        count = int(mask.sum())
        mean_probability = float(probabilities[mask].mean()) if count else None
        observed_rate = float(y_true[mask].mean()) if count else None
        if count:
            ece += (count / total) * abs(mean_probability - observed_rate)  # type: ignore[operator]
        bins.append(
            {
                "lower": lower,
                "upper": upper,
                "count": count,
                "mean_predicted_probability": mean_probability,
                "observed_positive_rate": observed_rate,
            }
        )
    return {
        "method": "fixed_width_10_bins_no_posthoc_calibrator",
        "bin_count": CALIBRATION_BIN_COUNT,
        "expected_calibration_error": float(ece),
        "bins": bins,
    }


def _binary_target(values: object) -> np.ndarray:
    array = _finite_vector(values, name="classification ground truth").astype(int)
    if not set(array).issubset({0, 1}):
        raise MetricContractViolation("classification ground truth must contain only 0/1")
    return array


def _probabilities(values: object, *, expected_length: int) -> np.ndarray:
    array = _finite_vector(values, name="classification probability")
    if len(array) != expected_length:
        raise MetricContractViolation("classification target and probability length differ")
    if bool(((array < 0.0) | (array > 1.0)).any()):
        raise MetricContractViolation("classification probabilities must be within [0, 1]")
    return array


def _finite_vector(values: object, *, name: str) -> np.ndarray:
    array = np.asarray(values, dtype=float).reshape(-1)
    if len(array) == 0 or not np.isfinite(array).all():
        raise MetricContractViolation(f"{name} must be a non-empty finite vector")
    return array
