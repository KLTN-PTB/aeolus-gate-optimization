"""Shared fixtures and mock models for Multi-Model Benchmark Engine testing."""

from __future__ import annotations

from pathlib import Path
import time
from typing import Any

import numpy as np
import pandas as pd
import pytest

from src.models.interfaces import (
    BaseModel,
    ModelCapability,
    ModelSpec,
    ModelStatus,
    ModelTarget,
    ModelTask,
)
from src.pipeline.model_benchmark_runner import (
    BenchmarkBudget,
    BenchmarkConfig,
    FoldDataset,
)


class MockPointRegressor(BaseModel):
    """Mock regression model predicting linear combination of features."""

    def __init__(self, model_id: str = "mock_point_regressor", random_seed: int = 202601) -> None:
        super().__init__(
            model_id=model_id,
            capabilities=[ModelCapability.POINT_REGRESSION],
            random_seed=random_seed,
            spec=ModelSpec(
                model_id=model_id,
                family="linear",
                task=ModelTask.CORE_ARRIVAL.value,
                target=ModelTarget.ARRIVAL_DELAY_SIGNED.value,
                probabilistic=False,
                supports_predict=True,
                supports_predict_proba=False,
                supports_distribution=False,
                feature_set="schedule_calendar_carrier_route_v1",
                preprocessing="standard_scaler",
                seed_policy="fixed_seed_202601",
                hpo_policy="none",
                status=ModelStatus.RESEARCH_CANDIDATE.value,
                downstream_eligible=True,
            ),
        )
        self.mean_: float = 0.0

    def fit(self, X: pd.DataFrame | np.ndarray, y: pd.Series | np.ndarray) -> BaseModel:
        self.mean_ = float(np.mean(y))
        self.is_fitted_ = True
        return self

    def predict(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        n = len(X)
        rng = np.random.default_rng(self.random_seed)
        # Predict around mean with small deterministic noise
        return np.full(n, self.mean_) + rng.normal(0, 0.5, size=n)


class MockTreeClassifier(BaseModel):
    """Mock classification model predicting arrival delay probability."""

    def __init__(self, model_id: str = "mock_tree_classifier", random_seed: int = 202601) -> None:
        super().__init__(
            model_id=model_id,
            capabilities=[ModelCapability.POINT_CLASSIFICATION, ModelCapability.CALIBRATED_PROBABILITY],
            random_seed=random_seed,
            spec=ModelSpec(
                model_id=model_id,
                family="tree_ensemble",
                task=ModelTask.CORE_ARRIVAL.value,
                target=ModelTarget.ARRIVAL_DELAY_BINARY_15.value,
                probabilistic=False,
                supports_predict=True,
                supports_predict_proba=True,
                supports_distribution=False,
                feature_set="schedule_calendar_carrier_route_v1",
                preprocessing="ordinal_encoder",
                seed_policy="fixed_seed_202601",
                hpo_policy="none",
                status=ModelStatus.RESEARCH_CANDIDATE.value,
                downstream_eligible=True,
            ),
        )
        self.prob_: float = 0.20

    def fit(self, X: pd.DataFrame | np.ndarray, y: pd.Series | np.ndarray) -> BaseModel:
        self.prob_ = float(np.mean(y)) if len(y) > 0 else 0.20
        self.is_fitted_ = True
        return self

    def predict_proba(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        n = len(X)
        rng = np.random.default_rng(self.random_seed)
        probs = np.clip(np.full(n, self.prob_) + rng.uniform(-0.05, 0.05, size=n), 0.0, 1.0)
        return np.column_stack([1.0 - probs, probs])

    def predict(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        proba = self.predict_proba(X)
        return (proba[:, 1] >= 0.5).astype(float)


class MockProbabilisticModel(BaseModel):
    """Mock distribution model predicting parametric normal arrival delay."""

    def __init__(self, model_id: str = "mock_probabilistic_model", random_seed: int = 202601) -> None:
        super().__init__(
            model_id=model_id,
            capabilities=[
                ModelCapability.POINT_REGRESSION,
                ModelCapability.PROBABILISTIC,
                ModelCapability.SAMPLING,
            ],
            random_seed=random_seed,
            spec=ModelSpec(
                model_id=model_id,
                family="ngboost",
                task=ModelTask.CORE_ARRIVAL.value,
                target=ModelTarget.ARRIVAL_DELAY_SIGNED.value,
                probabilistic=True,
                supports_predict=True,
                supports_predict_proba=False,
                supports_distribution=True,
                feature_set="schedule_calendar_carrier_route_v1",
                preprocessing="standard_scaler",
                seed_policy="fixed_seed_202601",
                hpo_policy="none",
                status=ModelStatus.RESEARCH_CANDIDATE.value,
                downstream_eligible=True,
            ),
        )
        self.mu_: float = 0.0
        self.sigma_: float = 15.0

    def fit(self, X: pd.DataFrame | np.ndarray, y: pd.Series | np.ndarray) -> BaseModel:
        self.mu_ = float(np.mean(y))
        self.sigma_ = max(5.0, float(np.std(y)))
        self.is_fitted_ = True
        return self

    def predict(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        n = len(X)
        return np.full(n, self.mu_)

    def predict_distribution(self, X: pd.DataFrame | np.ndarray) -> dict[str, Any]:
        n = len(X)
        return {
            "mu": np.full(n, self.mu_),
            "sigma": np.full(n, self.sigma_),
            "df": np.full(n, 4.0),
        }

    def sample(
        self,
        X: pd.DataFrame | np.ndarray,
        n_samples: int = 100,
        seed: int | None = None,
    ) -> np.ndarray:
        n = len(X)
        rng = np.random.default_rng(seed or self.random_seed)
        return rng.normal(self.mu_, self.sigma_, size=(n_samples, n))


class MockFailingModel(BaseModel):
    """Mock model that raises an exception during fit to verify failure retention."""

    def __init__(self, model_id: str = "mock_failing_model", random_seed: int = 202601) -> None:
        super().__init__(
            model_id=model_id,
            capabilities=[ModelCapability.POINT_REGRESSION],
            random_seed=random_seed,
            spec=ModelSpec(
                model_id=model_id,
                family="linear",
                task=ModelTask.CORE_ARRIVAL.value,
                target=ModelTarget.ARRIVAL_DELAY_SIGNED.value,
                probabilistic=False,
                supports_predict=True,
                supports_predict_proba=False,
                supports_distribution=False,
                feature_set="schedule_calendar_carrier_route_v1",
                preprocessing="standard_scaler",
                seed_policy="fixed_seed_202601",
                hpo_policy="none",
                status=ModelStatus.RESEARCH_CANDIDATE.value,
                downstream_eligible=False,
            ),
        )

    def fit(self, X: pd.DataFrame | np.ndarray, y: pd.Series | np.ndarray) -> BaseModel:
        raise RuntimeError("Simulated model training numerical explosion in MockFailingModel!")

    def predict(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        return np.zeros(len(X))


class MockSlowModel(BaseModel):
    """Mock model that deliberately exceeds budget timeout."""

    def __init__(self, sleep_seconds: float = 0.5, model_id: str = "mock_slow_model") -> None:
        super().__init__(
            model_id=model_id,
            capabilities=[ModelCapability.POINT_REGRESSION],
            spec=ModelSpec(
                model_id=model_id,
                family="slow_ensemble",
                task=ModelTask.CORE_ARRIVAL.value,
                target=ModelTarget.ARRIVAL_DELAY_SIGNED.value,
                probabilistic=False,
                supports_predict=True,
                supports_predict_proba=False,
                supports_distribution=False,
                feature_set="schedule_calendar_carrier_route_v1",
                preprocessing="standard_scaler",
                seed_policy="fixed_seed_202601",
                hpo_policy="none",
                status=ModelStatus.RESEARCH_CANDIDATE.value,
                downstream_eligible=False,
            ),
        )
        self.sleep_seconds = sleep_seconds

    def fit(self, X: pd.DataFrame | np.ndarray, y: pd.Series | np.ndarray) -> BaseModel:
        time.sleep(self.sleep_seconds)
        self.is_fitted_ = True
        return self

    def predict(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        return np.zeros(len(X))


@pytest.fixture
def dummy_benchmark_dataset() -> list[FoldDataset]:
    """Provide 2 standardized rolling development folds with pure schedule features."""
    rng = np.random.default_rng(202601)

    def _make_df(n: int, year: int) -> pd.DataFrame:
        carriers = ["DL", "AA", "UA", "WN", "YX"]
        origins = ["LGA", "ORD", "MCO", "DFW", "BOS"]
        return pd.DataFrame({
            "CRS_ELAPSED_TIME": rng.integers(60, 300, size=n).astype(float),
            "calendar_year": np.full(n, year, dtype=int),
            "calendar_month": rng.integers(1, 13, size=n),
            "calendar_day_of_month": rng.integers(1, 29, size=n),
            "calendar_day_of_week": rng.integers(1, 8, size=n),
            "scheduled_departure_hour": rng.integers(6, 23, size=n),
            "OP_CARRIER": [carriers[i % len(carriers)] for i in range(n)],
            "ORIGIN": [origins[i % len(origins)] for i in range(n)],
        })

    # Fold 1: train 2016-2018 (60 rows), val 2019 (25 rows)
    X_tr1 = _make_df(60, 2018)
    y_tr1 = rng.normal(5.0, 15.0, size=60)
    X_val1 = _make_df(25, 2019)
    y_val1 = rng.normal(5.0, 15.0, size=25)

    # Fold 2: train 2016-2019 (70 rows), val 2020 (30 rows)
    X_tr2 = _make_df(70, 2019)
    y_tr2 = rng.normal(4.0, 14.0, size=70)
    X_val2 = _make_df(30, 2020)
    y_val2 = rng.normal(4.0, 14.0, size=30)

    f1 = FoldDataset(
        fold_id="fold_1",
        train_years=[2016, 2017, 2018],
        val_year=2019,
        X_train=X_tr1,
        y_train=pd.Series(y_tr1),
        X_val=X_val1,
        y_val=pd.Series(y_val1),
    )

    f2 = FoldDataset(
        fold_id="fold_2",
        train_years=[2016, 2017, 2018, 2019],
        val_year=2020,
        X_train=X_tr2,
        y_train=pd.Series(y_tr2),
        X_val=X_val2,
        y_val=pd.Series(y_val2),
    )

    return [f1, f2]
