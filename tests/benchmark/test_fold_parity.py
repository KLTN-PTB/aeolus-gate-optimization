"""Tests for Fold Parity across models in MultiModelBenchmarkRunner."""

from __future__ import annotations

from pathlib import Path
from typing import Any
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


class FoldTrackingModel(BaseModel):
    """Model that records the exact fold metadata and calendar years observed."""

    def __init__(self, model_id: str) -> None:
        super().__init__(model_id=model_id, capabilities=["point_regression"])
        self.folds_fitted: list[str] = []
        self.folds_predicted: list[str] = []
        self.years_seen_in_fit: list[list[int]] = []
        self.years_seen_in_predict: list[list[int]] = []

    def fit(self, X: pd.DataFrame | np.ndarray, y: pd.Series | np.ndarray) -> BaseModel:
        if isinstance(X, pd.DataFrame) and "calendar_year" in X.columns:
            self.years_seen_in_fit.append(sorted(X["calendar_year"].unique().tolist()))
        self.is_fitted_ = True
        return self

    def predict(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        if isinstance(X, pd.DataFrame) and "calendar_year" in X.columns:
            self.years_seen_in_predict.append(sorted(X["calendar_year"].unique().tolist()))
        return np.zeros(len(X))


def test_fold_parity_identical_temporal_slices(tmp_path: Path, dummy_benchmark_dataset: list[FoldDataset]) -> None:
    """Verify all models evaluate on identical temporal slices across folds."""
    m1 = FoldTrackingModel("model_fold_1")
    m2 = FoldTrackingModel("model_fold_2")
    m3 = FoldTrackingModel("model_fold_3")

    cfg = BenchmarkConfig(
        experiment_id="test_fold_parity_exp",
        run_id="run_fold_001",
        output_dir=tmp_path / "artifacts",
    )

    runner = MultiModelBenchmarkRunner(cfg)
    results = runner.run_benchmark(models=[m1, m2, m3], folds=dummy_benchmark_dataset)

    assert len(results) == 6
    assert all(r.status == "COMPLETED" for r in results)

    # Both folds were processed in exact same order for all models
    assert m1.years_seen_in_fit == m2.years_seen_in_fit == m3.years_seen_in_fit
    assert m1.years_seen_in_predict == m2.years_seen_in_predict == m3.years_seen_in_predict

    # Check temporal ordering: fit years are strictly before predict years
    for fold_fit_years, fold_pred_years in zip(m1.years_seen_in_fit, m1.years_seen_in_predict):
        assert max(fold_fit_years) < min(fold_pred_years)


def test_fold_metadata_in_results(tmp_path: Path, dummy_benchmark_dataset: list[FoldDataset]) -> None:
    """Verify that every result row contains the proper fold_id and val_year."""
    m1 = MockPointRegressor()
    m2 = MockTreeClassifier()
    m3 = MockProbabilisticModel()

    cfg = BenchmarkConfig(
        experiment_id="test_fold_meta_exp",
        run_id="run_fold_002",
        output_dir=tmp_path / "artifacts",
    )

    runner = MultiModelBenchmarkRunner(cfg)
    results = runner.run_benchmark(models=[m1, m2, m3], folds=dummy_benchmark_dataset)

    # 3 models x 2 folds = 6 results
    folds_by_model: dict[str, list[str]] = {}
    years_by_model: dict[str, list[int]] = {}

    for r in results:
        folds_by_model.setdefault(r.model_id, []).append(r.fold_id)
        years_by_model.setdefault(r.model_id, []).append(r.year)

    expected_folds = ["fold_1", "fold_2"]
    expected_years = [2019, 2020]

    for model_id in [m1.model_id, m2.model_id, m3.model_id]:
        assert folds_by_model[model_id] == expected_folds
        assert years_by_model[model_id] == expected_years


def test_empty_folds_rejection(tmp_path: Path) -> None:
    """Runner must reject empty fold lists fail-closed."""
    cfg = BenchmarkConfig(
        experiment_id="test_empty_folds",
        run_id="run_empty_001",
        output_dir=tmp_path / "artifacts",
    )
    runner = MultiModelBenchmarkRunner(cfg)
    with pytest.raises(BenchmarkProtocolViolation, match="Fold list cannot be empty"):
        runner.run_benchmark(models=[MockPointRegressor()], folds=[])


def test_duplicate_fold_ids_rejection(tmp_path: Path, dummy_benchmark_dataset: list[FoldDataset]) -> None:
    """Folds with duplicate fold_ids must be rejected to ensure fold integrity."""
    f1 = dummy_benchmark_dataset[0]
    duplicate_f1 = FoldDataset(
        fold_id=f1.fold_id,
        train_years=f1.train_years,
        val_year=f1.val_year,
        X_train=f1.X_train,
        y_train=f1.y_train,
        X_val=f1.X_val,
        y_val=f1.y_val,
    )
    cfg = BenchmarkConfig(
        experiment_id="test_dup_folds",
        run_id="run_dup_001",
        output_dir=tmp_path / "artifacts",
    )
    runner = MultiModelBenchmarkRunner(cfg)
    with pytest.raises(BenchmarkProtocolViolation, match="Duplicate fold_id"):
        runner.run_benchmark(models=[MockPointRegressor()], folds=[f1, duplicate_f1])
