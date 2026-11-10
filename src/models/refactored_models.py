"""Refactored Model Family & Loss Functions for Aeolus Gate Optimization.

Addresses Prediction Collapse:
1. Replaces L2 / MSE loss with Huber Loss, Pseudo-Huber Loss, and Absolute Error.
2. Implements a Two-Stage Hurdle Architecture (Classification Gate -> Conditional Delay Regressor).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, Protocol
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin, ClassifierMixin
from sklearn.linear_model import HuberRegressor, LogisticRegression
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from xgboost import XGBClassifier, XGBRegressor

from src.models.rolling import EstimatorBundle


class TwoStageHurdleRegressor(BaseEstimator, RegressorMixin):
    """Hierarchical Two-Stage Hurdle Model for Heavy-Tailed Flight Delays.

    Stage 1: Binary Classifier estimates p = P(delay >= threshold).
    Stage 2: Conditional Regressor trained exclusively on delayed flights (delay >= threshold).
    Inference:
        If p < gate_threshold -> returns median on-time delay (e.g. -7.0 min).
        If p >= gate_threshold -> returns conditional regression prediction.
    """

    def __init__(
        self,
        classifier: Any,
        conditional_regressor: Any,
        *,
        delay_threshold: float = 15.0,
        gate_probability_threshold: float = 0.5,
        default_on_time_value: float = -7.0,
    ) -> None:
        self.classifier = classifier
        self.conditional_regressor = conditional_regressor
        self.delay_threshold = delay_threshold
        self.gate_probability_threshold = gate_probability_threshold
        self.default_on_time_value = default_on_time_value

    def fit(
        self,
        X: np.ndarray,
        y_cls: np.ndarray,
        y_reg: np.ndarray,
        sample_weight: np.ndarray | None = None,
    ) -> "TwoStageHurdleRegressor":
        # Fit stage 1: Classifier
        if sample_weight is not None:
            try:
                self.classifier.fit(X, y_cls, sample_weight=sample_weight)
            except TypeError:
                self.classifier.fit(X, y_cls)
        else:
            self.classifier.fit(X, y_cls)

        # Fit stage 2: Regressor on delayed subset only
        delayed_mask = y_reg >= self.delay_threshold
        if delayed_mask.sum() > 50:
            X_delayed = X[delayed_mask]
            y_delayed = y_reg[delayed_mask]
            w_delayed = sample_weight[delayed_mask] if sample_weight is not None else None
            if w_delayed is not None:
                try:
                    self.conditional_regressor.fit(X_delayed, y_delayed, sample_weight=w_delayed)
                except TypeError:
                    self.conditional_regressor.fit(X_delayed, y_delayed)
            else:
                self.conditional_regressor.fit(X_delayed, y_delayed)
        else:
            # Fallback if too few samples
            if sample_weight is not None:
                try:
                    self.conditional_regressor.fit(X, y_reg, sample_weight=sample_weight)
                except TypeError:
                    self.conditional_regressor.fit(X, y_reg)
            else:
                self.conditional_regressor.fit(X, y_reg)

        # Record empirical median of on-time flights
        on_time_mask = y_reg < self.delay_threshold
        if on_time_mask.sum() > 0:
            self.default_on_time_value = float(np.median(y_reg[on_time_mask]))

        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        probas = self.classifier.predict_proba(X)[:, 1]
        raw_reg = self.conditional_regressor.predict(X)
        
        # Hurdle gate condition
        pred = np.full(len(X), self.default_on_time_value, dtype=np.float64)
        is_delayed = probas >= self.gate_probability_threshold
        pred[is_delayed] = np.maximum(raw_reg[is_delayed], self.delay_threshold)
        return pred


def build_refactored_xgboost_bundle(
    *,
    objective: str = "reg:pseudohubererror",
    huber_slope: float = 15.0,
    quantile_alpha: float = 0.75,
    scale_pos_weight: float = 1.0,
    seed: int = 42,
    n_jobs: int = 1,
) -> EstimatorBundle:
    """Build XGBoost estimators using Pseudo-Huber or Quantile loss for robust regression."""
    clf = XGBClassifier(
        n_estimators=128,
        learning_rate=0.05,
        max_depth=6,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=scale_pos_weight,
        tree_method="hist",
        device="cpu",
        random_state=seed,
        n_jobs=n_jobs,
    )
    reg_params: dict[str, Any] = {
        "n_estimators": 128,
        "learning_rate": 0.05,
        "max_depth": 6,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "tree_method": "hist",
        "device": "cpu",
        "random_state": seed,
        "n_jobs": n_jobs,
    }
    if objective == "reg:pseudohubererror":
        reg_params["objective"] = "reg:pseudohubererror"
        reg_params["eval_metric"] = "mphe"
        reg_params["huber_slope"] = huber_slope
    elif objective == "reg:quantileerror":
        reg_params["objective"] = "reg:quantileerror"
        reg_params["eval_metric"] = "mae"
        reg_params["quantile_alpha"] = quantile_alpha
    else:
        reg_params["objective"] = objective
        reg_params["eval_metric"] = "rmse"

    reg = XGBRegressor(**reg_params)
    return EstimatorBundle(classifier=clf, regressor=reg)


def build_refactored_hgb_bundle(
    *,
    loss: str = "absolute_error",
    quantile: float = 0.75,
    class_weight: str = "balanced",
    seed: int = 42,
) -> EstimatorBundle:
    """Build HistGradientBoosting with absolute_error or quantile loss instead of squared error.

    Note: Scikit-learn HistGradientBoostingRegressor accepts {'absolute_error', 'quantile', 'squared_error'}.
    If loss='huber' is passed, it is mapped to 'absolute_error' (robust L1 median regression).
    """
    effective_loss = "absolute_error" if loss == "huber" else loss
    clf = HistGradientBoostingClassifier(
        learning_rate=0.05,
        max_iter=150,
        max_leaf_nodes=31,
        class_weight=class_weight,
        random_state=seed,
    )
    reg = HistGradientBoostingRegressor(
        loss=effective_loss,
        quantile=quantile if effective_loss == "quantile" else None,
        learning_rate=0.05,
        max_iter=150,
        max_leaf_nodes=31,
        random_state=seed,
    )
    return EstimatorBundle(classifier=clf, regressor=reg)


def build_refactored_linear_bundle(
    *,
    epsilon: float = 1.35,
    alpha: float = 1.0,
    seed: int = 42,
) -> EstimatorBundle:
    """Build Linear bundle with HuberRegressor replacing Ordinary Ridge."""
    clf = LogisticRegression(
        solver="saga",
        C=1.0,
        class_weight="balanced",
        max_iter=300,
        random_state=seed,
    )
    reg = HuberRegressor(
        epsilon=epsilon,
        alpha=alpha,
        max_iter=300,
    )
    return EstimatorBundle(classifier=clf, regressor=reg)


def build_refactored_rf_bundle(
    *,
    seed: int = 42,
    n_jobs: int = 1,
) -> EstimatorBundle:
    """Build Random Forest bundle with absolute error or balanced weights."""
    clf = RandomForestClassifier(
        n_estimators=96,
        max_depth=14,
        class_weight="balanced",
        n_jobs=n_jobs,
        random_state=seed,
    )
    reg = RandomForestRegressor(
        n_estimators=96,
        max_depth=14,
        criterion="squared_error",
        n_jobs=n_jobs,
        random_state=seed,
    )
    return EstimatorBundle(classifier=clf, regressor=reg)


def fit_bundle(
    bundle: EstimatorBundle,
    X: np.ndarray | pd.DataFrame,
    y_cls: np.ndarray | pd.Series,
    y_reg: np.ndarray | pd.Series,
    sample_weight: np.ndarray | None = None,
) -> EstimatorBundle:
    """Fit both classifier and regressor in an EstimatorBundle with optional sample_weight."""
    if sample_weight is not None:
        try:
            bundle.classifier.fit(X, y_cls, sample_weight=sample_weight)
        except TypeError:
            bundle.classifier.fit(X, y_cls)
        try:
            bundle.regressor.fit(X, y_reg, sample_weight=sample_weight)
        except TypeError:
            bundle.regressor.fit(X, y_reg)
    else:
        bundle.classifier.fit(X, y_cls)
        bundle.regressor.fit(X, y_reg)
    return bundle


# Re-exports for convenience
from src.models.hurdle_inference import HurdleDelayPredictor
from src.models.temporal_weighting import compute_temporal_sample_weights
