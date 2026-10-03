"""Tests for Resource Budget Parity and Timeout Enforcement in MultiModelBenchmarkRunner."""

from __future__ import annotations

from pathlib import Path
import pytest

from src.pipeline.model_benchmark_runner import (
    BenchmarkBudget,
    BenchmarkConfig,
    FoldDataset,
    MultiModelBenchmarkRunner,
)
from tests.benchmark.conftest import (
    MockPointRegressor,
    MockSlowModel,
)


def test_budget_timeout_enforcement(tmp_path: Path, dummy_benchmark_dataset: list[FoldDataset]) -> None:
    """A model exceeding the configured timeout budget receives TIMEOUT status while others complete."""
    # Fast model finishes in ~0.001s, slow model sleeps 0.25s, timeout set to 0.1s
    fast_model = MockPointRegressor(model_id="fast_model")
    slow_model = MockSlowModel(sleep_seconds=0.25, model_id="slow_model")

    budget = BenchmarkBudget(timeout_seconds=0.10, max_memory_mb=1024.0)
    cfg = BenchmarkConfig(
        experiment_id="test_budget_exp",
        run_id="run_budget_001",
        budget=budget,
        output_dir=tmp_path / "artifacts",
    )

    runner = MultiModelBenchmarkRunner(cfg)
    results = runner.run_benchmark(
        models=[fast_model, slow_model],
        folds=[dummy_benchmark_dataset[0]],
    )

    assert len(results) == 2

    # Fast model completed
    fast_res = next(r for r in results if r.model_id == "fast_model")
    assert fast_res.status == "COMPLETED"
    assert fast_res.failure_reason is None
    assert fast_res.metrics != {}

    # Slow model timed out but was retained
    slow_res = next(r for r in results if r.model_id == "slow_model")
    assert slow_res.status == "TIMEOUT"
    assert "exceeded timeout budget" in str(slow_res.failure_reason)
    assert slow_res.runtime_sec >= 0.10


def test_budget_parity_applied_uniformly(tmp_path: Path, dummy_benchmark_dataset: list[FoldDataset]) -> None:
    """All models evaluated under the benchmark share the exact same budget constraints."""
    budget = BenchmarkBudget(timeout_seconds=120.0, max_memory_mb=2048.0)
    cfg = BenchmarkConfig(
        experiment_id="test_budget_parity_exp",
        run_id="run_budget_002",
        budget=budget,
        output_dir=tmp_path / "artifacts",
    )

    runner = MultiModelBenchmarkRunner(cfg)
    assert runner.config.budget.timeout_seconds == 120.0
    assert runner.config.budget.max_memory_mb == 2048.0

    # Config JSON saved to artifact run dir preserves exact budget
    cfg_file = runner.run_dir / "benchmark_config.json"
    assert cfg_file.exists()
    import json
    with open(cfg_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["budget"]["timeout_seconds"] == 120.0
    assert data["budget"]["max_memory_mb"] == 2048.0
