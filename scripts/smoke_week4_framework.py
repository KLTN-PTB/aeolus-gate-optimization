"""Synthetic four-fold smoke for the shared Week-4 framework.

It opens no Aeolus row-level data, trains no production estimator, and writes
no artifact.  The tiny synthetic estimators only exercise the shared runner.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.features.tabular_features import prepare_arrival_features  # noqa: E402
from src.models.contracts import ExperimentSpec, FoldData  # noqa: E402
from src.models.rolling import EstimatorBundle, run_rolling_experiment  # noqa: E402


class SyntheticClassifier:
    classes_ = np.asarray([0, 1])

    def fit(self, X: object, y: object) -> "SyntheticClassifier":
        del X, y
        return self

    def predict_proba(self, X: object) -> np.ndarray:
        count = int(getattr(X, "shape")[0])
        positive = np.resize(np.asarray([0.2, 0.8], dtype=float), count)
        return np.column_stack([1.0 - positive, positive])


class SyntheticRegressor:
    def fit(self, X: object, y: object) -> "SyntheticRegressor":
        del X, y
        return self

    def predict(self, X: object) -> np.ndarray:
        return np.resize(np.asarray([-9.0, 19.0], dtype=float), int(getattr(X, "shape")[0]))


def raw_year(year: int) -> pd.DataFrame:
    dates = pd.to_datetime([f"{year}-01-02", f"{year}-01-03"])
    return pd.DataFrame(
        {
            "FL_DATE": [f"{year}-01-02 00:00:00", f"{year}-01-03 00:00:00"],
            "OP_CARRIER": ["AA", "DL"],
            "OP_CARRIER_FL_NUM": [101.0, 202.0],
            "ORIGIN": ["BOS", "JFK"],
            "DEST": ["ATL", "ATL"],
            "CRS_DEP_TIME": [f"{year}-01-02 09:00:00", f"{year}-01-03 23:30:00"],
            "CRS_ELAPSED_TIME": [120.0, 130.0],
            "MONTH": dates.month.tolist(),
            "DAY_OF_MONTH": dates.day.tolist(),
            "DAY_OF_WEEK": (dates.dayofweek + 1).tolist(),
            "ARR_DELAY": [-10.0, 20.0],
            "flight_key": [f"synthetic-{year}-a", f"synthetic-{year}-b"],
            "source_year": [year, year],
            "source_row_number": [1, 2],
        }
    )


def provider(fold: object) -> FoldData:
    train = prepare_arrival_features(
        pd.concat([raw_year(year) for year in getattr(fold, "train_years")])
    )
    validation = prepare_arrival_features(raw_year(getattr(fold, "validation_year")))
    return FoldData(train=train, validation=validation)


def factory(context: object) -> EstimatorBundle:
    del context
    return EstimatorBundle(SyntheticClassifier(), SyntheticRegressor())


def main() -> int:
    result = run_rolling_experiment(
        ExperimentSpec(
            method_id="linear",
            model_version="synthetic_smoke_v1",
            config_version="0.1.0",
            seed=202601,
        ),
        fold_data_provider=provider,
        estimator_factory=factory,
        retain_oof_batches=True,
    )
    if len(result.fold_results) != 4 or result.oof_rows_written != 8:
        raise AssertionError("synthetic rolling framework output is incomplete")
    print("WEEK4_FRAMEWORK_SMOKE: PASS")
    print("folds=4 oof_rows=8 production_models_trained=false row_level_2023_access=false row_level_2024_access=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
