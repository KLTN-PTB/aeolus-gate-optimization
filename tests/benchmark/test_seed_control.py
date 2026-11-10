"""Tests for Seed Control and Determinism in MultiModelBenchmarkRunner."""

from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.pipeline.model_benchmark_runner import (
    BenchmarkConfig,
    FoldDataset,
    MultiModelBenchmarkRunner,
)
from tests.benchmark.conftest import (
    MockPointRegressor,
    MockProbabilisticModel,
    MockTreeClassifier,
)


def test_seed_determinism_identical_runs(tmp_path: Path, dummy_benchmark_dataset: list[FoldDataset]) -> None:
    """Running identical models with identical seed produces identical results and metrics."""
    cfg1 = BenchmarkConfig(
        experiment_id="test_seed_exp",
        run_id="run_seed_001",
        random_seed=202601,
        output_dir=tmp_path / "artifacts_run1",
    )
    runner1 = MultiModelBenchmarkRunner(cfg1)
    results1 = runner1.run_benchmark(
        models=[MockPointRegressor(random_seed=202601), MockTreeClassifier(random_seed=202601)],
        folds=dummy_benchmark_dataset,
    )

    cfg2 = BenchmarkConfig(
        experiment_id="test_seed_exp",
        run_id="run_seed_002",
        random_seed=202601,
        output_dir=tmp_path / "artifacts_run2",
    )
    runner2 = MultiModelBenchmarkRunner(cfg2)
    results2 = runner2.run_benchmark(
        models=[MockPointRegressor(random_seed=202601), MockTreeClassifier(random_seed=202601)],
        folds=dummy_benchmark_dataset,
    )

    assert len(results1) == len(results2) == 4
    for r1, r2 in zip(results1, results2):
        assert r1.model_id == r2.model_id
        assert r1.fold_id == r2.fold_id
        assert r1.seed == r2.seed == 202601
        assert r1.metrics == r2.metrics


def test_different_seeds_produce_different_metrics(tmp_path: Path, dummy_benchmark_dataset: list[FoldDataset]) -> None:
    """Running with distinct seeds alters stochastic predictions and results."""
    # Run with seed A
    cfg_a = BenchmarkConfig(
        experiment_id="test_seed_diff_exp",
        run_id="run_seed_a",
        random_seed=1001,
        output_dir=tmp_path / "artifacts_a",
    )
    runner_a = MultiModelBenchmarkRunner(cfg_a)
    results_a = runner_a.run_benchmark(
        models=[MockPointRegressor(random_seed=1001)],
        folds=[dummy_benchmark_dataset[0]],
    )

    # Run with seed B
    cfg_b = BenchmarkConfig(
        experiment_id="test_seed_diff_exp",
        run_id="run_seed_b",
        random_seed=9999,
        output_dir=tmp_path / "artifacts_b",
    )
    runner_b = MultiModelBenchmarkRunner(cfg_b)
    results_b = runner_b.run_benchmark(
        models=[MockPointRegressor(random_seed=9999)],
        folds=[dummy_benchmark_dataset[0]],
    )

    assert len(results_a) == 1 and len(results_b) == 1
    r_a = results_a[0]
    r_b = results_b[0]
    assert r_a.seed == 1001
    assert r_b.seed == 9999
    # Due to random noise added in MockPointRegressor.predict, metrics should differ
    assert r_a.metrics != r_b.metrics


def test_seed_recorded_in_every_result(tmp_path: Path, dummy_benchmark_dataset: list[FoldDataset]) -> None:
    """All BenchmarkResult objects faithfully record the active run seed."""
    test_seed = 42
    cfg = BenchmarkConfig(
        experiment_id="test_seed_recorded",
        run_id="run_seed_rec",
        random_seed=test_seed,
        output_dir=tmp_path / "artifacts_rec",
    )
    runner = MultiModelBenchmarkRunner(cfg)
    results = runner.run_benchmark(
        models=[MockPointRegressor(), MockTreeClassifier(), MockProbabilisticModel()],
        folds=dummy_benchmark_dataset,
    )

    for r in results:
        assert r.seed == test_seed
