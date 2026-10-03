"""Tests for Durable Failure Retention in MultiModelBenchmarkRunner."""

from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.models.interfaces import BaseModel
from src.pipeline.model_benchmark_runner import (
    BenchmarkConfig,
    FoldDataset,
    MultiModelBenchmarkRunner,
)
from tests.benchmark.conftest import (
    MockFailingModel,
    MockPointRegressor,
    MockTreeClassifier,
)


def test_failure_is_retained_and_not_dropped(
    tmp_path: Path, dummy_benchmark_dataset: list[FoldDataset]
) -> None:
    """When a model crashes during fit, its failure must be durably recorded, not silently dropped."""
    failing_model = MockFailingModel("mock_failing_model")
    cfg = BenchmarkConfig(
        experiment_id="test_fail_retention",
        run_id="run_fail_001",
        output_dir=tmp_path / "artifacts",
    )

    runner = MultiModelBenchmarkRunner(cfg)
    results = runner.run_benchmark(
        models=[failing_model],
        folds=[dummy_benchmark_dataset[0]],
    )

    assert len(results) == 1
    res = results[0]
    assert res.status == "FAILED"
    assert res.failure_reason is not None
    assert "numerical explosion" in res.failure_reason
    assert res.metrics == {}
    assert res.artifact_path is None

    # Check individual JSON result exists and matches
    res_file = runner.run_dir / "results" / f"{failing_model.model_id}_{dummy_benchmark_dataset[0].fold_id}.json"
    assert res_file.exists()
    with open(res_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["status"] == "FAILED"
    assert "numerical explosion" in data["failure_reason"]


def test_multi_model_resilience_with_failure(
    tmp_path: Path, dummy_benchmark_dataset: list[FoldDataset]
) -> None:
    """Runner must execute all models across folds; failure of one model must not abort others."""
    m_ok1 = MockPointRegressor("model_ok1")
    m_fail = MockFailingModel("model_fail")
    m_ok2 = MockTreeClassifier("model_ok2")

    cfg = BenchmarkConfig(
        experiment_id="test_multi_resilience",
        run_id="run_multi_001",
        output_dir=tmp_path / "artifacts",
    )

    runner = MultiModelBenchmarkRunner(cfg)
    results = runner.run_benchmark(
        models=[m_ok1, m_fail, m_ok2],
        folds=dummy_benchmark_dataset,  # 2 folds
    )

    # 3 models * 2 folds = 6 results
    assert len(results) == 6

    # Verify status breakdown
    statuses = {r.model_id: [] for r in results}
    for r in results:
        statuses[r.model_id].append(r.status)

    assert statuses["model_ok1"] == ["COMPLETED", "COMPLETED"]
    assert statuses["model_ok2"] == ["COMPLETED", "COMPLETED"]
    assert statuses["model_fail"] == ["FAILED", "FAILED"]

    # Verify summary files reflect all 6 results
    summary_json = runner.run_dir / "benchmark_summary.json"
    assert summary_json.exists()
    with open(summary_json, "r", encoding="utf-8") as f:
        summary_data = json.load(f)
    assert len(summary_data["results"]) == 6
    assert summary_data["total_runs"] == 6
    assert summary_data["completed_runs"] == 4
    assert summary_data["failed_runs"] == 2

    summary_csv = runner.run_dir / "benchmark_summary.csv"
    assert summary_csv.exists()
    df_summary = pd.read_csv(summary_csv)
    assert len(df_summary) == 6
    assert set(df_summary["status"]) == {"COMPLETED", "FAILED"}


class PredictCrashingModel(BaseModel):
    """Model that passes fit but crashes in predict."""

    def __init__(self, model_id: str = "predict_crash") -> None:
        super().__init__(model_id=model_id, capabilities=["point_regression"])

    def fit(self, X: pd.DataFrame | np.ndarray, y: pd.Series | np.ndarray) -> BaseModel:
        self.is_fitted_ = True
        return self

    def predict(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        raise ValueError("Predict dimension collapse error!")


def test_predict_failure_retention(
    tmp_path: Path, dummy_benchmark_dataset: list[FoldDataset]
) -> None:
    """Exception during predict phase is captured as failure with reason."""
    model = PredictCrashingModel()
    cfg = BenchmarkConfig(
        experiment_id="test_pred_fail",
        run_id="run_pred_fail_001",
        output_dir=tmp_path / "artifacts",
    )
    runner = MultiModelBenchmarkRunner(cfg)
    results = runner.run_benchmark(models=[model], folds=[dummy_benchmark_dataset[0]])

    assert len(results) == 1
    assert results[0].status == "FAILED"
    assert "Predict dimension collapse error" in str(results[0].failure_reason)
