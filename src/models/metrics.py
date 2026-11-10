"""Shared, non-tuned metric definitions for Week-4 Core Arrival baselines."""

from __future__ import annotations

import warnings
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
EARLY_ON_TIME_DELAY_LIMIT: Final = 15.0
MODERATE_DELAY_LIMIT: Final = 60.0
PREDICTION_COLLAPSE_SHRINKAGE_THRESHOLD: Final = 0.3


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


@dataclass(frozen=True)
class StratifiedSliceMetrics:
    count: int
    mae: float | None
    rmse: float | None
    mean_bias: float | None
    mean_true: float | None
    mean_pred: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def __getitem__(self, key: str) -> Any:
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(f"Invalid metric key: {key}")


@dataclass(frozen=True)
class StratifiedRegressionMetrics:
    overall: StratifiedSliceMetrics
    early_on_time: StratifiedSliceMetrics
    moderate_delay: StratifiedSliceMetrics
    severe_delay: StratifiedSliceMetrics
    shrinkage_ratio: float
    prediction_collapse_warning: bool
    warning_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def __getitem__(self, key: str) -> Any:
        if hasattr(self, key):
            return getattr(self, key)
        aliases = {
            "early": "early_on_time",
            "moderate": "moderate_delay",
            "severe": "severe_delay",
        }
        if key in aliases:
            return getattr(self, aliases[key])
        raise KeyError(f"Invalid metric key: {key}")


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


def compute_stratified_regression_metrics(
    y_true: object,
    y_pred: object = None,
    *,
    predictions: object = None,
    collapse_threshold: float = PREDICTION_COLLAPSE_SHRINKAGE_THRESHOLD,
) -> StratifiedRegressionMetrics:
    """Compute stratified regression metrics across operational delay strata.

    Strata:
        - Early/On-time: y_true < 15.0
        - Moderate Delay: 15.0 <= y_true < 60.0
        - Severe Delay: y_true >= 60.0
        - Overall: All samples

    Metrics per stratum:
        - count: number of flights in stratum
        - mae: Mean Absolute Error
        - rmse: Root Mean Squared Error
        - mean_bias: mean(y_pred - y_true)
        - mean_true: mean(y_true)
        - mean_pred: mean(y_pred)

    Prediction Shrinkage Ratio:
        shrinkage_ratio = mean(y_pred[y_true >= 60]) / mean(y_true[y_true >= 60])
        If shrinkage_ratio < collapse_threshold, triggers a prediction collapse warning.
    """

    actual_pred = y_pred if y_pred is not None else predictions
    if actual_pred is None:
        raise MetricContractViolation("y_pred or predictions must be provided")

    y = _finite_vector(y_true, name="regression ground truth")
    pred = _finite_vector(actual_pred, name="regression prediction")
    if len(y) != len(pred):
        raise MetricContractViolation("regression target and prediction length differ")

    def _calc_slice(mask: np.ndarray) -> StratifiedSliceMetrics:
        sub_y = y[mask]
        sub_pred = pred[mask]
        count = int(len(sub_y))
        if count == 0:
            return StratifiedSliceMetrics(
                count=0,
                mae=None,
                rmse=None,
                mean_bias=None,
                mean_true=None,
                mean_pred=None,
            )
        mae = float(mean_absolute_error(sub_y, sub_pred))
        rmse = float(np.sqrt(mean_squared_error(sub_y, sub_pred)))
        mean_bias = float(np.mean(sub_pred - sub_y))
        mean_true = float(np.mean(sub_y))
        mean_pred = float(np.mean(sub_pred))
        return StratifiedSliceMetrics(
            count=count,
            mae=mae,
            rmse=rmse,
            mean_bias=mean_bias,
            mean_true=mean_true,
            mean_pred=mean_pred,
        )

    slice_overall = _calc_slice(np.ones(len(y), dtype=bool))
    slice_early = _calc_slice(y < EARLY_ON_TIME_DELAY_LIMIT)
    slice_moderate = _calc_slice((y >= EARLY_ON_TIME_DELAY_LIMIT) & (y < MODERATE_DELAY_LIMIT))
    slice_severe = _calc_slice(y >= MODERATE_DELAY_LIMIT)

    # Shrinkage ratio on severe delay (y >= 60 min)
    if (
        slice_severe.count > 0
        and slice_severe.mean_true is not None
        and abs(slice_severe.mean_true) > 1e-9
    ):
        shrinkage_ratio = float(slice_severe.mean_pred / slice_severe.mean_true)
    else:
        shrinkage_ratio = 0.0

    collapse_warning = bool(shrinkage_ratio < collapse_threshold and slice_severe.count > 0)
    warning_message = None
    if collapse_warning:
        warning_message = (
            f"Prediction collapse warning: shrinkage ratio on severe delay (>= {MODERATE_DELAY_LIMIT:.0f} min) "
            f"is {shrinkage_ratio:.4f} (< {collapse_threshold:.2f}). "
            f"The model severely underpredicts extreme delays."
        )
        warnings.warn(warning_message, UserWarning, stacklevel=2)

    return StratifiedRegressionMetrics(
        overall=slice_overall,
        early_on_time=slice_early,
        moderate_delay=slice_moderate,
        severe_delay=slice_severe,
        shrinkage_ratio=shrinkage_ratio,
        prediction_collapse_warning=collapse_warning,
        warning_message=warning_message,
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


def compute_pinball_loss(y_true: object, q_pred: object, alpha: float) -> float:
    """Compute Pinball / Quantile loss for a given quantile alpha in (0, 1)."""
    if not (0.0 < alpha < 1.0):
        raise MetricContractViolation(f"Quantile alpha must be strictly between 0 and 1, got {alpha}")
    y = _finite_vector(y_true, name="ground truth")
    q = _finite_vector(q_pred, name="quantile prediction")
    if len(y) != len(q):
        raise MetricContractViolation("y_true and q_pred lengths differ")
    err = y - q
    loss = np.maximum(alpha * err, (alpha - 1.0) * err)
    return float(np.mean(loss))


def compute_empirical_coverage(y_true: object, q_pred: object) -> float:
    """Compute empirical percentage (%) of observations falling at or below quantile prediction."""
    y = _finite_vector(y_true, name="ground truth")
    q = _finite_vector(q_pred, name="quantile prediction")
    if len(y) != len(q):
        raise MetricContractViolation("y_true and q_pred lengths differ")
    return float(np.mean(y <= q) * 100.0)


def evaluate_all(
    y_true: object,
    y_pred_point: object,
    *,
    y_prob_delay: object | None = None,
    q_preds: dict[float, object] | None = None,
    collapse_threshold: float = PREDICTION_COLLAPSE_SHRINKAGE_THRESHOLD,
) -> dict[str, Any]:
    """Comprehensive evaluation covering point regression, tail risk, classification, and quantiles."""
    y = _finite_vector(y_true, name="regression ground truth")
    p_point = _finite_vector(y_pred_point, name="point prediction")
    if len(y) != len(p_point):
        raise MetricContractViolation("y_true and y_pred_point lengths differ")

    # 1. Point regression metrics
    point_mae = float(mean_absolute_error(y, p_point))
    point_rmse = float(np.sqrt(mean_squared_error(y, p_point)))
    point_r2 = float(r2_score(y, p_point)) if len(y) >= 2 else None
    point_bias = float(np.mean(p_point - y))

    # 2. Severe delay outcome-conditioned metrics (y >= 60m)
    severe_mask = y >= 60.0
    n_severe = int(severe_mask.sum())
    if n_severe > 0:
        severe_mae = float(mean_absolute_error(y[severe_mask], p_point[severe_mask]))
        severe_rmse = float(np.sqrt(mean_squared_error(y[severe_mask], p_point[severe_mask])))
        severe_bias = float(np.mean(p_point[severe_mask] - y[severe_mask]))
        mean_true_severe = float(np.mean(y[severe_mask]))
        mean_pred_severe = float(np.mean(p_point[severe_mask]))
        shrinkage = float(mean_pred_severe / mean_true_severe) if abs(mean_true_severe) > 1e-9 else 0.0
    else:
        severe_mae, severe_rmse, severe_bias, shrinkage = None, None, None, 0.0

    collapse_warning = bool(shrinkage < collapse_threshold and n_severe > 0)

    # 3. Tail risk ranking (Unconditioned on outcome) - PR-AUC & ROC-AUC for y >= 60
    y_severe_bin = (y >= 60.0).astype(int)
    has_severe_classes = len(np.unique(y_severe_bin)) == 2
    pr_auc_severe = (
        float(average_precision_score(y_severe_bin, p_point))
        if has_severe_classes
        else None
    )
    roc_auc_severe = (
        float(roc_auc_score(y_severe_bin, p_point))
        if has_severe_classes
        else None
    )

    # 4. Binary delay classification gate (y >= 15m)
    cls_gate_metrics: dict[str, float | None] = {}
    if y_prob_delay is not None:
        prob = _probabilities(y_prob_delay, expected_length=len(y))
        y_cls_bin = (y >= 15.0).astype(int)
        has_cls_classes = len(np.unique(y_cls_bin)) == 2
        cls_gate_metrics["roc_auc"] = (
            float(roc_auc_score(y_cls_bin, prob)) if has_cls_classes else None
        )
        cls_gate_metrics["pr_auc"] = (
            float(average_precision_score(y_cls_bin, prob)) if has_cls_classes else None
        )
        cls_gate_metrics["brier_score"] = float(brier_score_loss(y_cls_bin, prob))

    # 5. Quantiles & Coverage
    quantiles_eval: dict[str, float] = {}
    if q_preds is not None:
        for alpha, q_pred in q_preds.items():
            alpha_f = float(alpha)
            quantiles_eval[f"pinball_loss_{alpha_f:.2f}"] = compute_pinball_loss(y, q_pred, alpha_f)
            quantiles_eval[f"coverage_{alpha_f:.2f}"] = compute_empirical_coverage(y, q_pred)

    return {
        "point_regression": {
            "mae": point_mae,
            "rmse": point_rmse,
            "r2": point_r2,
            "mean_bias": point_bias,
        },
        "severe_conditioned": {
            "count": n_severe,
            "severe_mae": severe_mae,
            "severe_rmse": severe_rmse,
            "severe_bias": severe_bias,
            "shrinkage_ratio": shrinkage,
            "collapse_warning": collapse_warning,
        },
        "tail_risk_ranking": {
            "pr_auc_severe": pr_auc_severe,
            "roc_auc_severe": roc_auc_severe,
            "prevalence_severe": float(np.mean(y_severe_bin)),
        },
        "classification_gate": cls_gate_metrics,
        "quantile_coverage": quantiles_eval,
    }

