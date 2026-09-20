"""Two-Stage Hurdle Architecture and Inference for Flight Delay Prediction.

Combines:
1. Stage 1 Binary Classifier: Estimates calibrated P(arr_delay >= 15m) using standard
   binary logistic loss (no artificial scale_pos_weight inflation) and CalibratedClassifierCV.
2. Stage 2 Conditional Regressor: Trained exclusively on delayed flights (arr_delay >= 15m)
   using robust loss (Pseudo-Huber or Quantile).
3. Soft-Gated Expected Delay Inference:
   y_hat = P(delay >= 15m) * y_hat_delay + (1 - P(delay >= 15m)) * early_median
   where y_hat_delay >= 15m and early_median = median(y_train[y_train < 15m]).
4. Safety buffer generation (75th / 90th percentile quantile) for CP-SAT gate assignment.
"""

from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import train_test_split

from src.models.temporal_weighting import compute_temporal_sample_weights


class HurdleDelayPredictor(BaseEstimator, RegressorMixin):
    """Hierarchical Two-Stage Calibrated Hurdle Model for Heavy-Tailed Flight Delays."""

    def __init__(
        self,
        classifier_bundle: Any,
        regressor_bundle: Any,
        *,
        gating_mode: str = "soft",
        threshold: float = 0.30,
        delay_threshold: float = 15.0,
        quantile_regressor_bundle: Any | None = None,
        calibrate: bool = True,
        calibration_method: str = "isotonic",
        calibration_fraction: float = 0.20,
        random_state: int = 42,
    ) -> None:
        if gating_mode not in {"soft", "hard"}:
            raise ValueError(f"gating_mode must be 'soft' or 'hard', got {gating_mode!r}")

        self.classifier_bundle = classifier_bundle
        self.regressor_bundle = regressor_bundle
        self.gating_mode = gating_mode
        self.threshold = threshold
        self.delay_threshold = delay_threshold
        self.quantile_regressor_bundle = quantile_regressor_bundle
        self.calibrate = calibrate
        self.calibration_method = calibration_method
        self.calibration_fraction = calibration_fraction
        self.random_state = random_state

        # Extract underlying estimators if passed as EstimatorBundle
        self.classifier_ = getattr(classifier_bundle, "classifier", classifier_bundle)
        self.regressor_ = getattr(regressor_bundle, "regressor", regressor_bundle)
        self.quantile_regressor_ = (
            getattr(quantile_regressor_bundle, "regressor", quantile_regressor_bundle)
            if quantile_regressor_bundle is not None
            else None
        )
        self.calibrated_classifier_: Any = self.classifier_
        self.early_median_: float = -7.0

    def _calibrate_prefit(
        self,
        base_clf: Any,
        X_calib: Any,
        y_calib: np.ndarray,
        method: str = "isotonic",
    ) -> Any:
        """Calibrate an already-fitted classifier using holdout calibration samples."""
        try:
            from sklearn.frozen import FrozenEstimator
            cal = CalibratedClassifierCV(FrozenEstimator(base_clf), method=method)
            cal.fit(X_calib, y_calib)
            return cal
        except (ImportError, ValueError):
            try:
                cal = CalibratedClassifierCV(base_clf, method=method, cv="prefit")
                cal.fit(X_calib, y_calib)
                return cal
            except Exception:
                try:
                    cal = CalibratedClassifierCV(base_clf, method=method, cv=3)
                    cal.fit(X_calib, y_calib)
                    return cal
                except Exception:
                    return base_clf

    def fit(
        self,
        X_train: Any,
        y_train: pd.Series | np.ndarray,
        sample_weight: np.ndarray | None = None,
        years: pd.Series | np.ndarray | None = None,
    ) -> "HurdleDelayPredictor":
        """Fit the calibrated classifier and conditional regressor stages.

        Args:
            X_train: Predictor matrix.
            y_train: Ground truth signed ARR_DELAY minutes.
            sample_weight: Optional temporal sample weights.
            years: Optional calendar year per row.
        """
        if isinstance(y_train, pd.Series):
            y_arr = y_train.to_numpy(dtype=np.float64)
        else:
            y_arr = np.asarray(y_train, dtype=np.float64).reshape(-1)

        # Compute sample weights from years if not provided
        if sample_weight is None and years is not None:
            sample_weight = compute_temporal_sample_weights(years)

        # 1. Compute empirical median of on-time / early flights (y < delay_threshold)
        early_mask = y_arr < self.delay_threshold
        if early_mask.sum() > 0:
            self.early_median_ = float(np.median(y_arr[early_mask]))
        else:
            self.early_median_ = float(np.median(y_arr))

        # 2. Stage 1: Binary Classifier for P(y >= delay_threshold)
        y_cls = (y_arr >= self.delay_threshold).astype(np.int32)
        n_samples = len(y_cls)
        n_pos = int(y_cls.sum())
        n_neg = n_samples - n_pos

        if self.calibrate and n_pos >= 10 and n_neg >= 10 and n_samples >= 80:
            indices = np.arange(n_samples)
            idx_tr, idx_cal = train_test_split(
                indices,
                test_size=self.calibration_fraction,
                stratify=y_cls,
                random_state=self.random_state,
            )

            X_sub_tr = X_train.iloc[idx_tr] if hasattr(X_train, "iloc") else X_train[idx_tr]
            y_cls_sub_tr = y_cls[idx_tr]
            w_sub_tr = sample_weight[idx_tr] if sample_weight is not None else None

            X_sub_cal = X_train.iloc[idx_cal] if hasattr(X_train, "iloc") else X_train[idx_cal]
            y_cls_sub_cal = y_cls[idx_cal]

            if w_sub_tr is not None:
                try:
                    self.classifier_.fit(X_sub_tr, y_cls_sub_tr, sample_weight=w_sub_tr)
                except TypeError:
                    self.classifier_.fit(X_sub_tr, y_cls_sub_tr)
            else:
                self.classifier_.fit(X_sub_tr, y_cls_sub_tr)

            self.calibrated_classifier_ = self._calibrate_prefit(
                self.classifier_,
                X_sub_cal,
                y_cls_sub_cal,
                method=self.calibration_method,
            )
        else:
            if sample_weight is not None:
                try:
                    self.classifier_.fit(X_train, y_cls, sample_weight=sample_weight)
                except TypeError:
                    self.classifier_.fit(X_train, y_cls)
            else:
                self.classifier_.fit(X_train, y_cls)
            self.calibrated_classifier_ = self.classifier_

        # 3. Stage 2: Fit Conditional Regressor exclusively on delayed subset (y >= delay_threshold)
        delay_mask = y_arr >= self.delay_threshold
        if delay_mask.sum() >= 20:
            X_delayed = X_train.iloc[delay_mask] if hasattr(X_train, "iloc") else X_train[delay_mask]
            y_delayed = y_arr[delay_mask]
            w_delayed = sample_weight[delay_mask] if sample_weight is not None else None
        else:
            X_delayed = X_train
            y_delayed = y_arr
            w_delayed = sample_weight

        if w_delayed is not None:
            try:
                self.regressor_.fit(X_delayed, y_delayed, sample_weight=w_delayed)
            except TypeError:
                self.regressor_.fit(X_delayed, y_delayed)
        else:
            self.regressor_.fit(X_delayed, y_delayed)

        # 4. Optional Quantile Regressor on delayed subset
        if self.quantile_regressor_ is not None:
            if w_delayed is not None:
                try:
                    self.quantile_regressor_.fit(X_delayed, y_delayed, sample_weight=w_delayed)
                except TypeError:
                    self.quantile_regressor_.fit(X_delayed, y_delayed)
            else:
                self.quantile_regressor_.fit(X_delayed, y_delayed)

        return self

    def predict_proba(self, X: Any) -> np.ndarray:
        """Predict calibrated probability of delay >= 15 minutes."""
        clf = getattr(self, "calibrated_classifier_", self.classifier_)
        if hasattr(clf, "predict_proba"):
            return clf.predict_proba(X)
        pred = clf.predict(X).astype(float)
        return np.column_stack([1.0 - pred, pred])

    def predict(self, X: Any) -> np.ndarray:
        """Compute point prediction using expected soft gating or hard gating."""
        clf = getattr(self, "calibrated_classifier_", self.classifier_)
        if hasattr(clf, "predict_proba"):
            probas = clf.predict_proba(X)
            p_delay = probas[:, 1] if probas.ndim == 2 else probas.reshape(-1)
        else:
            p_delay = clf.predict(X).astype(float)

        y_cond = self.regressor_.predict(X)
        # Conditional delay is bounded below by delay_threshold (15.0 min)
        y_cond_bounded = np.maximum(y_cond, self.delay_threshold)

        if self.gating_mode == "soft":
            # Expected delay: E[y|X] = P(delay) * E[y|delay, X] + (1 - P(delay)) * early_median
            pred = p_delay * y_cond_bounded + (1.0 - p_delay) * self.early_median_
        elif self.gating_mode == "hard":
            pred = np.where(p_delay >= self.threshold, y_cond_bounded, self.early_median_)
        else:
            raise ValueError(f"Unknown gating mode: {self.gating_mode}")

        return np.asarray(pred, dtype=np.float64)

    def predict_quantile(self, X: Any, alpha: float = 0.75) -> np.ndarray:
        """Compute safety buffer prediction (upper quantile) for CP-SAT gate scheduling."""
        clf = getattr(self, "calibrated_classifier_", self.classifier_)
        if hasattr(clf, "predict_proba"):
            probas = clf.predict_proba(X)
            p_delay = probas[:, 1] if probas.ndim == 2 else probas.reshape(-1)
        else:
            p_delay = clf.predict(X).astype(float)

        if self.quantile_regressor_ is not None:
            q_cond = self.quantile_regressor_.predict(X)
            q_cond_bounded = np.maximum(q_cond, self.delay_threshold)
            if self.gating_mode == "soft":
                buffer = p_delay * q_cond_bounded + (1.0 - p_delay) * max(self.early_median_, 0.0)
            else:
                buffer = np.where(
                    p_delay >= self.threshold, q_cond_bounded, max(self.early_median_, 0.0)
                )
        else:
            point = self.predict(X)
            buffer = np.maximum(point, 0.0) + p_delay * 15.0

        return np.asarray(buffer, dtype=np.float64)

    def predict_point_and_buffer(
        self, X: Any, alpha: float = 0.75
    ) -> tuple[np.ndarray, np.ndarray]:
        """Convenience method returning both point prediction and safety buffer."""
        point = self.predict(X)
        buffer = self.predict_quantile(X, alpha=alpha)
        return point, buffer
