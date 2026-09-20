"""Naive baseline models and skill score calculation for flight delay prediction.

Provides reference benchmarks against which machine learning models are compared:
1. Global Median Baseline: Predicts the overall median arrival delay from training data.
2. Carrier Median Baseline: Predicts the median arrival delay per operating carrier.
3. Carrier-Hour Median Baseline: Predicts the median arrival delay per (Carrier x Scheduled Arrival Hour).
"""

from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin


def compute_skill_score(mae_model: float, mae_baseline: float) -> float:
    """Compute percentage skill score relative to a baseline reference.

    Formula:
        Skill_Score = (1.0 - (mae_model / mae_baseline)) * 100.0

    Positive values indicate improvement over baseline; negative indicates worse.
    """
    if mae_baseline <= 1e-9:
        return 0.0
    return float((1.0 - (mae_model / mae_baseline)) * 100.0)


class NaiveDelayBaselines(BaseEstimator, RegressorMixin):
    """Collection of non-parametric naive baselines for Core Arrival delay."""

    def __init__(self) -> None:
        self.global_median_: float = 0.0
        self.carrier_medians_: dict[str, float] = {}
        self.carrier_hour_medians_: dict[tuple[str, int], float] = {}
        self.carrier_col_: str = "OP_CARRIER"

    def _extract_carrier_and_hour(self, X: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        """Extract carrier and scheduled arrival hour consistently."""
        if not isinstance(X, pd.DataFrame):
            raise ValueError("NaiveDelayBaselines requires a pandas DataFrame input with column names.")

        # Identify carrier column
        if "OP_CARRIER" in X.columns:
            carrier = X["OP_CARRIER"].astype(str)
        elif "OP_UNIQUE_CARRIER" in X.columns:
            carrier = X["OP_UNIQUE_CARRIER"].astype(str)
        else:
            raise KeyError("Neither 'OP_CARRIER' nor 'OP_UNIQUE_CARRIER' found in input DataFrame.")

        # Identify scheduled arrival hour
        if "CRS_ARR_HOUR" in X.columns:
            hour = X["CRS_ARR_HOUR"].astype(int)
        elif "scheduled_arrival_hour" in X.columns:
            hour = X["scheduled_arrival_hour"].astype(int)
        elif "scheduled_departure_hour" in X.columns and "CRS_ELAPSED_TIME" in X.columns:
            # Approximate scheduled arrival hour = (dep_hour + elapsed_minutes // 60) % 24
            dep_hour = X["scheduled_departure_hour"].astype(int)
            elapsed_hours = (X["CRS_ELAPSED_TIME"].fillna(120.0).astype(float) // 60).astype(int)
            hour = (dep_hour + elapsed_hours) % 24
        elif "scheduled_departure_hour" in X.columns:
            hour = X["scheduled_departure_hour"].astype(int)
        elif "CRS_DEP_TIME" in X.columns:
            hour = pd.to_datetime(X["CRS_DEP_TIME"]).dt.hour.astype(int)
        else:
            # Fallback default hour 12
            hour = pd.Series(12, index=X.index, dtype=int)

        return carrier, hour

    def fit(self, X: pd.DataFrame, y: pd.Series | np.ndarray) -> "NaiveDelayBaselines":
        """Compute global, carrier, and carrier-hour medians from training observations."""
        if isinstance(y, pd.Series):
            y_arr = y.to_numpy(dtype=np.float64)
        else:
            y_arr = np.asarray(y, dtype=np.float64).reshape(-1)

        self.global_median_ = float(np.median(y_arr))

        carrier, hour = self._extract_carrier_and_hour(X)
        df = pd.DataFrame({
            "carrier": carrier.values,
            "hour": hour.values,
            "y": y_arr,
        })

        # Carrier medians
        self.carrier_medians_ = df.groupby("carrier")["y"].median().to_dict()

        # Carrier x Hour medians
        carrier_hour_series = df.groupby(["carrier", "hour"])["y"].median()
        self.carrier_hour_medians_ = {
            (c, h): float(val) for (c, h), val in carrier_hour_series.items()
        }

        return self

    def predict_global_median(self, X: pd.DataFrame) -> np.ndarray:
        """Predict constant global median for all rows."""
        return np.full(len(X), self.global_median_, dtype=np.float64)

    def predict_carrier_median(self, X: pd.DataFrame) -> np.ndarray:
        """Predict carrier median with fallback to global median."""
        carrier, _ = self._extract_carrier_and_hour(X)
        preds = np.empty(len(X), dtype=np.float64)
        for idx, c in enumerate(carrier.values):
            preds[idx] = self.carrier_medians_.get(c, self.global_median_)
        return preds

    def predict_carrier_hour_median(self, X: pd.DataFrame) -> np.ndarray:
        """Predict (carrier, hour) median with hierarchical fallback:
        (carrier, hour) -> carrier -> global median.
        """
        carrier, hour = self._extract_carrier_and_hour(X)
        c_vals = carrier.values
        h_vals = hour.values
        preds = np.empty(len(X), dtype=np.float64)

        for idx in range(len(X)):
            c = c_vals[idx]
            h = h_vals[idx]
            key = (c, h)
            if key in self.carrier_hour_medians_:
                preds[idx] = self.carrier_hour_medians_[key]
            elif c in self.carrier_medians_:
                preds[idx] = self.carrier_medians_[c]
            else:
                preds[idx] = self.global_median_

        return preds

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Default prediction uses the most specific naive model: carrier-hour median."""
        return self.predict_carrier_hour_median(X)
