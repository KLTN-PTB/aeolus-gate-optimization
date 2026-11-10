"""Tests for Artifact Versioning, Output Schema, and Manifest Integrity."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import pandas as pd
import pytest

from src.pipeline.model_benchmark_runner import (
    BenchmarkConfig,
    FoldDataset,
    MultiModelBenchmarkRunner,
)
from tests.benchmark.conftest import (
    MockPointRegressor,
    MockTreeClassifier,
)


REQUIRED_RESULT_KEYS = {
    "experiment_id",
    "run_id",
    "model_id",
    "fold_id",
    "year",
    "seed",
    "n_rows",
    "feature_version",
    "preprocessing_version",
    "metrics",
    "runtime_sec",
    "memory_mb",
    "status",
    "failure_reason",
    "artifact_path",
    "created_at_utc",
    "config_hash",
}


def test_result_schema_completeness(tmp_path: Path, dummy_benchmark_dataset: list[FoldDataset]) -> None:
    """Verify that every result file and record adheres strictly to the benchmark schema."""
    cfg = BenchmarkConfig(
        experiment_id="test_schema_exp",
        run_id="run_schema_001",
        output_dir=tmp_path / "artifacts",
    )
    runner = MultiModelBenchmarkRunner(cfg)
    results = runner.run_benchmark(
        models=[MockPointRegressor("model_reg"), MockTreeClassifier("model_clf")],
        folds=dummy_benchmark_dataset,
    )

    assert len(results) == 4

    for r in results:
        d = r.to_dict()
        # 1. Check all required keys exist
        missing = REQUIRED_RESULT_KEYS - set(d.keys())
        assert not missing, f"Missing required keys in BenchmarkResult: {missing}"

        # 2. Check types
        assert isinstance(d["experiment_id"], str)
        assert isinstance(d["run_id"], str)
        assert isinstance(d["model_id"], str)
        assert isinstance(d["fold_id"], str)
        assert isinstance(d["year"], int)
        assert isinstance(d["seed"], int)
        assert isinstance(d["n_rows"], int)
        assert isinstance(d["metrics"], dict)
        assert isinstance(d["runtime_sec"], float)
        assert isinstance(d["memory_mb"], float)
        assert d["status"] in {"COMPLETED", "FAILED", "TIMEOUT"}
        assert len(d["config_hash"]) == 64

        # 3. Check corresponding JSON file on disk
        res_file = runner.run_dir / "results" / f"{r.model_id}_{r.fold_id}.json"
        assert res_file.exists()
        with open(res_file, "r", encoding="utf-8") as f:
            disk_data = json.load(f)
        assert disk_data == d


def test_non_destructive_artifact_versioning(
    tmp_path: Path, dummy_benchmark_dataset: list[FoldDataset]
) -> None:
    """Re-running with identical experiment_id and run_id must not overwrite previous artifacts."""
    out_dir = tmp_path / "artifacts"
    cfg1 = BenchmarkConfig(
        experiment_id="test_non_overwrite",
        run_id="run_001",
        output_dir=out_dir,
    )
    runner1 = MultiModelBenchmarkRunner(cfg1)
    runner1.run_benchmark(models=[MockPointRegressor("m1")], folds=[dummy_benchmark_dataset[0]])

    dir1 = runner1.run_dir
    assert dir1.exists()

    # Create second runner with same experiment_id and run_id
    cfg2 = BenchmarkConfig(
        experiment_id="test_non_overwrite",
        run_id="run_001",
        output_dir=out_dir,
    )
    runner2 = MultiModelBenchmarkRunner(cfg2)
    dir2 = runner2.run_dir

    # dir2 must be a distinct path, not overwriting dir1
    assert dir2 != dir1
    assert dir2.exists()
    assert dir1.exists()
    assert str(dir2).startswith(str(dir1))


def test_sha256_manifest_integrity(tmp_path: Path, dummy_benchmark_dataset: list[FoldDataset]) -> None:
    """Verify manifest.sha256 records valid cryptographic hashes for all run artifacts."""
    cfg = BenchmarkConfig(
        experiment_id="test_manifest_exp",
        run_id="run_manifest_001",
        output_dir=tmp_path / "artifacts",
    )
    runner = MultiModelBenchmarkRunner(cfg)
    runner.run_benchmark(
        models=[MockPointRegressor("m1")],
        folds=[dummy_benchmark_dataset[0]],
    )

    manifest_file = runner.run_dir / "manifest.sha256"
    assert manifest_file.exists()

    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert len(manifest) >= 3  # config, result json, summary json, summary csv, model joblib
    for rel_path, expected_hash in manifest.items():
        artifact_path = runner.run_dir / rel_path
        assert artifact_path.exists(), f"Artifact in manifest missing on disk: {rel_path}"
        actual_hash = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
        assert actual_hash == expected_hash, f"Hash mismatch for {rel_path}"


def test_config_artifact_content(tmp_path: Path) -> None:
    """Verify benchmark_config.json contains complete run configuration and hash."""
    cfg = BenchmarkConfig(
        experiment_id="test_cfg_art",
        run_id="run_cfg_001",
        cutoff="CRS_DEP_TIME - 2h",
        random_seed=202601,
        feature_version="schedule_v1",
        preprocessing_version="prep_v1",
        data_role="rolling_development",
        output_dir=tmp_path / "artifacts",
    )
    runner = MultiModelBenchmarkRunner(cfg)

    cfg_file = runner.run_dir / "benchmark_config.json"
    assert cfg_file.exists()
    with open(cfg_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["experiment_id"] == "test_cfg_art"
    assert data["run_id"] == "run_cfg_001"
    assert data["cutoff"] == "CRS_DEP_TIME - 2h"
    assert data["random_seed"] == 202601
    assert data["data_role"] == "rolling_development"
    assert data["config_hash"] == cfg.compute_sha256()
