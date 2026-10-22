"""Versioned T-2h schedule features; historical encodings never see future labels.

This is a new research contract. It deliberately leaves the frozen V1 contracts
unchanged. Model inputs are prepared schedule columns plus ``__date``.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder

from src.data.departure_preprocessing import build_departure_tree_preprocessor
from src.data.preprocessing import build_tree_preprocessor
from src.features.departure_features import prepare_departure_training
from src.features.tabular_features import prepare_arrival_features, _parse_scheduled_arrival_clock

VERSION = "binary_improvement_v2"
TASKS = ("arrival", "departure")
FEATURE_SETS = ("F0", "F1", "F2")
META_COLUMNS = ("__date", "__year", "__key", "__target")


def source_columns(task: str) -> list[str]:
    if task not in TASKS:
        raise ValueError(f"Unknown task: {task}")
    return ["FL_DATE", "OP_CARRIER", "OP_CARRIER_FL_NUM", "ORIGIN", "DEST",
            "CRS_DEP_TIME", "CRS_ARR_TIME", "CRS_ELAPSED_TIME", "MONTH",
            "DAY_OF_MONTH", "DAY_OF_WEEK", "flight_key",
            "ARR_DELAY" if task == "arrival" else "DEP_DELAY"]


def prepare_frame(raw: pd.DataFrame, task: str, *, inference: bool = False) -> pd.DataFrame:
    """Reuse label/population checks; inference discards supplied outcomes first."""
    columns = source_columns(task)
    target = "ARR_DELAY" if task == "arrival" else "DEP_DELAY"
    frame = raw.loc[:, [c for c in columns if c in raw and (not inference or c != target)]].copy()
    if inference:
        frame[target] = 0.0  # Only to reuse schedule validation, never a predictor.
    if "flight_key" not in frame:
        raise ValueError("flight_key is required for duplicate and alignment audits")
    # Preserve CRS_ARR_TIME separately for Departure V2 (not part of V1).
    population = "DEST" if task == "arrival" else "ORIGIN"
    eligible = frame.loc[frame[population].eq("ATL") & frame[target].notna()].reset_index(drop=True)
    if task == "arrival":
        batch = prepare_arrival_features(frame, include_scheduled_arrival_time=True)
        y = batch.y_arr_cls
    else:
        batch = prepare_departure_training(frame)
        y = batch.y_dep_cls
    result = batch.X.copy()
    if task == "departure":
        hour, minute = _parse_scheduled_arrival_clock(eligible)
        result["scheduled_arrival_hour"] = hour.to_numpy()
        result["scheduled_arrival_minute"] = minute.to_numpy()
    # Flight dates, not UTC-converted cutoffs: the Departure contract uses ATL time.
    result["__date"] = pd.to_datetime(eligible["FL_DATE"]).dt.normalize().to_numpy()
    result["__year"] = result["__date"].dt.year
    result["__key"] = batch.identifiers["flight_key"].astype(str).to_numpy()
    if not inference:
        result["__target"] = y.to_numpy(dtype=np.int8)
    return result


class ScheduleHistoryEncoder(BaseEstimator, TransformerMixin):
    """Past-year target encodings for train; frozen train maps at inference.

    The first training year has prior 0.5 (no labels read). Later years use
    strictly earlier years. This is an offline training statistic, not a live
    operational feed. All inference maps remain frozen at the training cutoff.
    """
    def __init__(self, task: str, feature_set: str = "F1", smoothing: float = 50.0):
        self.task = task
        self.feature_set = feature_set
        self.smoothing = smoothing

    def _schedule(self, X: pd.DataFrame) -> pd.DataFrame:
        if self.task not in TASKS or self.feature_set not in FEATURE_SETS:
            raise ValueError("Unknown task or feature set")
        route = "ORIGIN" if self.task == "arrival" else "DEST"
        base = ["CRS_ELAPSED_TIME", "calendar_month", "calendar_day_of_month",
                "calendar_day_of_week", "is_weekend", "scheduled_departure_hour",
                "scheduled_departure_minute", "OP_CARRIER", route, "OP_CARRIER_FL_NUM"]
        if self.task == "arrival":
            base.append("calendar_year")
        out = X.loc[:, base].copy()
        if self.feature_set == "F0":
            return out
        out["scheduled_arrival_hour"] = X["scheduled_arrival_hour"].to_numpy()
        out["scheduled_arrival_minute"] = X["scheduled_arrival_minute"].to_numpy()
        for name, period, offset in [("calendar_month", 12, 1), ("calendar_day_of_week", 7, 1)]:
            angle = 2 * np.pi * (X[name].to_numpy() - offset) / period
            out[name + "_sin"], out[name + "_cos"] = np.sin(angle), np.cos(angle)
        for prefix in ["departure", "arrival"]:
            minutes = X[f"scheduled_{prefix}_hour"] * 60 + X[f"scheduled_{prefix}_minute"]
            angle = 2 * np.pi * minutes / 1440
            out[prefix + "_sin"], out[prefix + "_cos"] = np.sin(angle), np.cos(angle)
        carrier = X["OP_CARRIER"].fillna("__MISSING__").astype(str)
        destination = X[route].fillna("__MISSING__").astype(str)
        out["carrier_route"] = carrier + "|" + destination
        out["carrier_hour"] = carrier + "|" + X["scheduled_departure_hour"].astype(str)
        # Preserve flight identity rather than converting its number to an order.
        out["carrier_flight"] = carrier + "|" + X["OP_CARRIER_FL_NUM"].fillna("__MISSING__").astype(str)
        return out

    def _keys(self, X: pd.DataFrame) -> dict[str, pd.Series]:
        schedule = self._schedule(X)
        route = "ORIGIN" if self.task == "arrival" else "DEST"
        return {c: schedule[c].fillna("__MISSING__").astype(str)
                for c in ["OP_CARRIER", route, "carrier_route", "carrier_flight", "carrier_hour"]}

    def _maps(self, X: pd.DataFrame, y: np.ndarray) -> tuple[float, dict]:
        prior = float(np.mean(y)) if len(y) else 0.5
        maps = {}
        for name, key in self._keys(X).items():
            stats = pd.DataFrame({"key": key.to_numpy(), "y": y}).groupby("key")["y"].agg(["sum", "count"])
            maps[name] = {
                "rate": ((stats["sum"] + self.smoothing * prior) / (stats["count"] + self.smoothing)).to_dict(),
                "frequency": (stats["count"] / max(1, len(y))).to_dict(),
            }
        return prior, maps

    def _history(self, X: pd.DataFrame, prior: float, maps: dict) -> pd.DataFrame:
        result = self._schedule(X)
        for name, keys in self._keys(X).items():
            result[name + "_historical_rate"] = keys.map(maps.get(name, {}).get("rate", {})).fillna(prior).to_numpy()
            result[name + "_frequency"] = keys.map(maps.get(name, {}).get("frequency", {})).fillna(0).to_numpy()
        return result

    def fit(self, X: pd.DataFrame, y=None):
        self.feature_names_in_ = np.asarray(X.columns)
        if self.feature_set == "F2":
            if y is None or len(y) != len(X):
                raise ValueError("Historical training requires aligned labels")
            self.prior_, self.maps_ = self._maps(X, np.asarray(y))
        return self

    def fit_transform(self, X: pd.DataFrame, y=None, **kwargs):
        self.fit(X, y)
        if self.feature_set != "F2":
            return self._schedule(X)
        years = pd.to_datetime(X["__date"]).dt.year.to_numpy()
        result = self._history(X, 0.5, {})
        y = np.asarray(y)
        for year in sorted(np.unique(years)):
            previous, current = years < year, years == year
            prior, maps = self._maps(X.loc[previous], y[previous])
            encoded = self._history(X.loc[current], prior, maps)
            for column in encoded:
                if column.endswith(("_historical_rate", "_frequency")):
                    result.loc[current, column] = encoded[column].to_numpy(dtype=float)
        return result

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        if not hasattr(self, "feature_names_in_"):
            raise ValueError("Encoder is not fitted")
        if self.feature_set == "F2":
            return self._history(X, self.prior_, self.maps_)
        return self._schedule(X)


def make_preprocessor(task: str, feature_set: str, engineered: pd.DataFrame):
    if feature_set == "F0":
        return build_tree_preprocessor() if task == "arrival" else build_departure_tree_preprocessor()
    cats = list(engineered.select_dtypes(include=["object", "string"]).columns)
    nums = [c for c in engineered if c not in cats]
    return ColumnTransformer([
        ("numeric", SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True), nums),
        ("categorical", Pipeline([
            ("imputer", SimpleImputer(strategy="constant", fill_value="__MISSING__")),
            ("encoder", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)),
        ]), cats),
    ], sparse_threshold=0)
