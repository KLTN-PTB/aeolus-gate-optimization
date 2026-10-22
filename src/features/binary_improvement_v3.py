"""Native categorical schedule features and past-month-only historical encoding."""
from __future__ import annotations

import numpy as np
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar

from src.features.binary_improvement import ScheduleHistoryEncoder, make_preprocessor

VERSION = "binary_improvement_v3"


class NativeScheduleEncoder:
    def __init__(self, task: str, group: str = "native", smoothing: float = 50):
        if task not in ("arrival", "departure") or group not in ("original", "native", "history"):
            raise ValueError("Unknown task/feature group")
        self.task, self.group, self.smoothing = task, group, smoothing

    def _base(self, X):
        route = "ORIGIN" if self.task == "arrival" else "DEST"
        names = ["CRS_ELAPSED_TIME", "calendar_month", "calendar_day_of_month",
                 "calendar_day_of_week", "is_weekend", "scheduled_departure_hour",
                 "scheduled_departure_minute", "OP_CARRIER", route, "OP_CARRIER_FL_NUM"]
        if self.group == "original":
            if self.task == "arrival":
                names.append("calendar_year")
            return X[names].copy()
        result = X[[n for n in names if n != "OP_CARRIER_FL_NUM"]].copy()
        for period in ("departure", "arrival"):
            hour, minute = X[f"scheduled_{period}_hour"], X[f"scheduled_{period}_minute"]
            angle = 2 * np.pi * (hour * 60 + minute) / 1440
            result[period + "_sin"], result[period + "_cos"] = np.sin(angle), np.cos(angle)
        for col, size in [("calendar_month", 12), ("calendar_day_of_week", 7)]:
            angle = 2 * np.pi * (X[col] - 1) / size
            result[col + "_sin"], result[col + "_cos"] = np.sin(angle), np.cos(angle)
        dates = pd.to_datetime(X["__date"])
        if len(dates):
            # Fixed calendar rules, never labels from event days.
            holidays = USFederalHolidayCalendar().holidays(
                dates.min() - pd.Timedelta(days=14), dates.max() + pd.Timedelta(days=14))
            days = dates.to_numpy(dtype="datetime64[D]").astype(np.int64)
            holiday_days = holidays.to_numpy(dtype="datetime64[D]").astype(np.int64)
            if len(holiday_days):
                ix = np.searchsorted(holiday_days, days)
                left = holiday_days[np.clip(ix - 1, 0, len(holiday_days) - 1)]
                right = holiday_days[np.clip(ix, 0, len(holiday_days) - 1)]
                distance = np.minimum(np.abs(days - left), np.abs(days - right))
            else:
                distance = np.full(len(days), 14)
            result["days_to_federal_holiday"] = np.minimum(distance, 14)
            result["holiday_window_3d"] = (distance <= 3).astype(np.int8)
        else:
            result["days_to_federal_holiday"] = pd.Series(dtype=float)
            result["holiday_window_3d"] = pd.Series(dtype=float)
        return result

    def _keys(self, X):
        route = "ORIGIN" if self.task == "arrival" else "DEST"
        carrier = X["OP_CARRIER"].fillna("__MISSING__").astype(str)
        airport = X[route].fillna("__MISSING__").astype(str)
        flight = X["OP_CARRIER_FL_NUM"].fillna("__MISSING__").astype(str)
        hour = X["scheduled_departure_hour"].astype(str)
        return {"carrier": carrier, "route": airport, "carrier_route": carrier + "|" + airport,
                "carrier_hour": carrier + "|" + hour, "carrier_flight": carrier + "|" + flight}

    def _maps(self, X, y):
        prior = float(np.mean(y)) if len(y) else 0.0
        maps = {}
        for col, values in self._keys(X).items():
            stats = pd.DataFrame({"key": values.to_numpy(), "y": np.asarray(y)}).groupby("key").y.agg(["count", "sum"])
            maps[col] = {"rate": ((stats["sum"] + self.smoothing * prior) / (stats["count"] + self.smoothing)).to_dict(),
                         "frequency": (stats["count"] / max(1, len(X))).to_dict()}
        return prior, maps

    def _history(self, X, prior, maps):
        out = self._base(X)
        for col, values in self._keys(X).items():
            out[col + "_rate"] = values.map(maps.get(col, {}).get("rate", {})).fillna(prior).to_numpy(dtype=np.float32)
            out[col + "_frequency"] = values.map(maps.get(col, {}).get("frequency", {})).fillna(0).to_numpy(dtype=np.float32)
        return out

    def fit_transform(self, X, y):
        if self.group == "original":
            self.original_ = ScheduleHistoryEncoder(self.task, "F0")
            frame = self.original_.fit_transform(X, y)
            self.preprocessor_ = make_preprocessor(self.task, "F0", frame)
            return np.asarray(self.preprocessor_.fit_transform(frame), dtype=np.float32)
        y = np.asarray(y)
        if len(X) != len(y):
            raise ValueError("History labels are misaligned")
        self.prior_, self.maps_ = self._maps(X, y)
        # Non-target flight frequency is fitted on train only.
        flight = self._keys(X)["carrier_flight"]
        self.flight_frequency_ = (flight.value_counts() / max(1, len(X))).to_dict()
        if self.group == "history":
            out = self._base(X)
            months = pd.to_datetime(X["__date"]).dt.to_period("M").astype("int64").to_numpy()
            totals = pd.DataFrame({"month": months, "y": y}).groupby("month").y.agg(["count", "sum"])
            totals["past_count"] = totals["count"].cumsum() - totals["count"]
            totals["past_sum"] = totals["sum"].cumsum() - totals["sum"]
            prior = np.divide(totals.past_sum, totals.past_count.replace(0, np.nan)).fillna(0)
            for col, keys in self._keys(X).items():
                stats = pd.DataFrame({"key": keys.to_numpy(), "month": months, "y": y}).groupby(["key", "month"]).y.agg(["count", "sum"])
                counts = stats["count"].groupby(level=0).cumsum() - stats["count"]
                sums = stats["sum"].groupby(level=0).cumsum() - stats["sum"]
                month_index = stats.index.get_level_values(1)
                rates = (sums.to_numpy() + self.smoothing * prior.reindex(month_index).to_numpy()) / (counts.to_numpy() + self.smoothing)
                denominators = totals.past_count.reindex(month_index).to_numpy()
                frequency = np.divide(counts.to_numpy(), denominators, out=np.zeros(len(counts)), where=denominators > 0)
                lookup = pd.MultiIndex.from_arrays([keys.to_numpy(), months])
                out[col + "_rate"] = pd.Series(rates, index=stats.index).reindex(lookup).to_numpy(dtype=np.float32)
                out[col + "_frequency"] = pd.Series(frequency, index=stats.index).reindex(lookup).to_numpy(dtype=np.float32)
        else:
            out = self._base(X)
        out["flight_frequency"] = flight.map(self.flight_frequency_).fillna(0).to_numpy(dtype=np.float32)
        self.categories_ = {col: sorted(out[col].dropna().astype(str).unique())
                            for col in ("OP_CARRIER", "ORIGIN" if self.task == "arrival" else "DEST")}
        return self._types(out)

    def _types(self, out):
        for col in out:
            if col in self.categories_:
                if len(self.categories_[col]) > 255:
                    raise ValueError("Native category count exceeds the HGB contract")
                out[col] = pd.Categorical(out[col], categories=self.categories_[col], ordered=False)
            else:
                out[col] = pd.to_numeric(out[col], errors="raise").astype(np.float32)
        return out

    def transform(self, X):
        if self.group == "original":
            return np.asarray(self.preprocessor_.transform(self.original_.transform(X)), dtype=np.float32)
        out = self._history(X, self.prior_, self.maps_) if self.group == "history" else self._base(X)
        out["flight_frequency"] = self._keys(X)["carrier_flight"].map(self.flight_frequency_).fillna(0).to_numpy(dtype=np.float32)
        return self._types(out)
