"""Tests for Row Parity across multiple models in MultiModelBenchmarkRunner."""

from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.models.interfaces import BaseModel
from src.pipeline.model_benchmark_runner import (
    BenchmarkConfig,
    BenchmarkProtocolViolation,
    FoldDataset,
    MultiModelBenchmarkRunner,
)
from tests.benchmark.conftest import (
    MockPointRegressor,
    MockProbabilisticModel,
    MockTreeClassifier,
)


class RowInspectionModel(BaseModel):
    """Model that records the exact indices and row counts of data passed to it."""

    def __init__(self, model_id: str) -> None:
        super().__init__(model_id=model_id, capabilities=["point_regression"])
        self.fitted_indices: list[Any] = []
        self.predicted_indices: list[Any] = []
        self.n_fitted: int = 0
        self.n_predicted: int = 0

    def fit(self, X: pd.DataFrame | np.ndarray, y: pd.Series | np.ndarray) -> BaseModel:
        self.n_fitted = len(X)
        if isinstance(X, pd.DataFrame):
            self.fitted_indices = list(X.index)
        self.is_fitted_ = True
        return self

    def predict(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        self.n_predicted = len(X)
        if isinstance(X, pd.DataFrame):
            self.predicted_indices = list(X.index)
        return np.zeros(len(X))


def test_row_parity_across_models(tmp_path: Path, dummy_benchmark_dataset: list[FoldDataset]) -> None:
    """Verify that all models in a benchmark run receive bitwise identical row counts and indices."""
    m1 = RowInspectionModel("model_inspect_1")
    m2 = RowInspectionModel("model_inspect_2")
    m3 = RowInspectionModel("model_inspect_3")

    cfg = BenchmarkConfig(
        experiment_id="test_row_parity_exp",
        run_id="run_parity_001",
        output_dir=tmp_path / "artifacts",
    )

    runner = MultiModelBenchmarkRunner(cfg)
    results = runner.run_benchmark(models=[m1, m2, m3], folds=dummy_benchmark_dataset)

    assert len(results) == 6  # 3 models * 2 folds
    assert all(r.status == "COMPLETED" for r in results)

    # Fold 2 was evaluated last; check that all models received identical row counts and indices
    assert m1.n_fitted == m2.n_fitted == m3.n_fitted == len(dummy_benchmark_dataset[1].X_train)
    assert m1.n_predicted == m2.n_predicted == m3.n_predicted == len(dummy_benchmark_dataset[1].X_val)
    assert m1.fitted_indices == m2.fitted_indices == m3.fitted_indices
    assert m1.predicted_indices == m2.predicted_indices == m3.predicted_indices


def test_mismatched_row_counts_fail_closed() -> None:
    """FoldDataset must fail closed if X and y row counts differ."""
    X = pd.DataFrame({"a": [1, 2, 3]})
    y_short = pd.Series([1.0, 2.0])

    with pytest.raises(BenchmarkProtocolViolation, match="Row mismatch"):
        FoldDataset(
            fold_id="fold_mismatch",
            train_years=[2018],
            val_year=2019,
            X_train=X,
            y_train=y_short,
            X_val=X,
            y_val=y_short,
        )
