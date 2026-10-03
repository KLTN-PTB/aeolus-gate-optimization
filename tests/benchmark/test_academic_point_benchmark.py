"""Unit and integration tests for Phase 2 Academic Point Benchmark."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.data.access_guard import DataAccessDenied, assert_data_access_allowed
from src.data.leakage_rules import ARRIVAL_LEAKAGE_COLUMNS, WEATHER_COLUMNS
from src.features.tabular_features import APPROVED_PREDICTOR_COLUMNS
from src.models.artifacts import OOF_COLUMNS, validate_oof_frame
from src.models.contracts import load_week4_rolling_folds
from src.pipeline.academic_point_benchmark import (
    BASE_METHOD_IDS,
    CORE_METHOD_IDS,
    AcademicBenchmarkConfig,
    AcademicPointBenchmarkRunner,
    optimize_ensemble_weights,
)


@pytest.fixture(scope="module")
def executed_benchmark_dir() -> Path:
    """Locate the most recently generated academic benchmark artifact directory."""
    base = Path("artifacts/model_benchmark/core_point")
    run_dirs = sorted([d for d in base.glob("core_point_academic_benchmark_v1*") if d.is_dir()])
    if not run_dirs:
        # If not already executed on disk, run a fast mini-benchmark for test fixture
        cfg = AcademicBenchmarkConfig(
            experiment_id="test_academic_mini_fixture",
            sample_train_per_year=500,
            sample_val=600,
            output_dir=base,
        )
        runner = AcademicPointBenchmarkRunner(cfg)
        runner.run_benchmark()
        return runner.run_dir
    return run_dirs[-1]


def test_row_and_target_parity_across_models(executed_benchmark_dir: Path) -> None:
    """Verify that all 5 models share identical row counts, flight keys, and targets."""
    oof_dir = executed_benchmark_dir / "oof"
    assert oof_dir.exists()

    for fold_id in ("fold_1", "fold_2", "fold_3", "fold_4"):
        dfs: dict[str, pd.DataFrame] = {}
        for method_id in CORE_METHOD_IDS:
            parquet_path = oof_dir / f"{method_id}_{fold_id}.parquet"
            assert parquet_path.exists(), f"Missing OOF artifact: {parquet_path}"
            df = pd.read_parquet(parquet_path)
            validate_oof_frame(df)
            dfs[method_id] = df

        # Reference model is linear baseline
        ref_df = dfs["arrival_linear_baseline_v1"]
        ref_keys = ref_df["flight_key"].tolist()
        ref_y_cls = ref_df["y_arr_cls"].to_numpy()
        ref_y_reg = ref_df["y_arr_reg"].to_numpy()

        for method_id, df in dfs.items():
            # 1. Exact row count parity
            assert len(df) == len(ref_df), f"Row count mismatch in {fold_id} for {method_id}"
            # 2. Exact flight key sequence parity
            assert df["flight_key"].tolist() == ref_keys, f"Flight key order mismatch in {fold_id} for {method_id}"
            # 3. Exact target parity
            np.testing.assert_array_equal(df["y_arr_cls"].to_numpy(), ref_y_cls)
            np.testing.assert_allclose(df["y_arr_reg"].to_numpy(), ref_y_reg)


def test_fold_parity() -> None:
    """Verify temporal fold definitions conform strictly to rolling development 2016-2022."""
    folds = load_week4_rolling_folds()
    assert len(folds) == 4

    expected = {
        "fold_1": ([2016, 2017, 2018], 2019),
        "fold_2": ([2016, 2017, 2018, 2019], 2020),
        "fold_3": ([2016, 2017, 2018, 2019, 2020], 2021),
        "fold_4": ([2016, 2017, 2018, 2019, 2020, 2021], 2022),
    }

    for fold in folds:
        assert fold.fold_id in expected
        exp_train, exp_val = expected[fold.fold_id]
        assert list(fold.train_years) == exp_train
        assert fold.validation_year == exp_val
        # Strict temporal order: max(train) < val
        assert max(fold.train_years) < fold.validation_year
        # Development years strictly within 2016-2022
        assert max(fold.train_years + (fold.validation_year,)) <= 2022


def test_no_forbidden_columns_in_feature_set() -> None:
    """Verify that predictor columns do not contain weather, leakage, or forbidden features."""
    predictors = set(APPROVED_PREDICTOR_COLUMNS)

    # 1. No weather
    weather_overlap = predictors.intersection(WEATHER_COLUMNS)
    assert not weather_overlap, f"Weather features found in approved predictors: {weather_overlap}"

    # 2. No operational leakage
    leakage_overlap = predictors.intersection(ARRIVAL_LEAKAGE_COLUMNS)
    assert not leakage_overlap, f"Leakage features found in approved predictors: {leakage_overlap}"

    # 3. No actual flight operation times
    forbidden_terms = ["ARR_TIME", "DEP_TIME", "TAXI_IN", "TAXI_OUT", "WHEELS_ON", "WHEELS_OFF"]
    for col in predictors:
        assert col not in forbidden_terms, f"Forbidden operational column found: {col}"


def test_2024_access_guard_blocked_for_development() -> None:
    """2024 data access must raise DataAccessDenied during development/model training."""
    with pytest.raises(DataAccessDenied, match="sealed from development"):
        assert_data_access_allowed(2024, "development")

    # Final holdout access without freeze manifest must also fail
    with pytest.raises(DataAccessDenied, match="freeze manifest"):
        assert_data_access_allowed(
            2024,
            "final_evaluation",
            freeze_manifest_path=Path("artifacts/manifests/nonexistent.json"),
        )


def test_ensemble_weight_constraints() -> None:
    """Verify that ensemble weight optimization enforces w >= 0, sum(w) == 1, and determinism."""
    rng = np.random.default_rng(202601)
    N = 200
    y_true_cls = rng.integers(0, 2, size=N)
    y_true_reg = rng.normal(5.0, 15.0, size=N)

    # 4 models predictions
    preds_cls = np.column_stack([
        np.clip(y_true_cls + rng.uniform(-0.3, 0.3, size=N), 0.0, 1.0)
        for _ in range(4)
    ])
    preds_reg = np.column_stack([
        y_true_reg + rng.normal(0.0, 5.0, size=N)
        for _ in range(4)
    ])

    w_cls = optimize_ensemble_weights(y_true_cls, preds_cls, loss_type="brier")
    w_reg = optimize_ensemble_weights(y_true_reg, preds_reg, loss_type="mae")

    # Nonnegative
    assert np.all(w_cls >= 0.0), f"Negative weight in classification: {w_cls}"
    assert np.all(w_reg >= 0.0), f"Negative weight in regression: {w_reg}"

    # Sums to 1
    assert np.isclose(np.sum(w_cls), 1.0, atol=1e-5), f"Weights do not sum to 1: {np.sum(w_cls)}"
    assert np.isclose(np.sum(w_reg), 1.0, atol=1e-5), f"Weights do not sum to 1: {np.sum(w_reg)}"

    # Deterministic under fixed input
    w_cls2 = optimize_ensemble_weights(y_true_cls, preds_cls, loss_type="brier")
    np.testing.assert_allclose(w_cls, w_cls2)


def test_artifact_and_manifest_integrity(executed_benchmark_dir: Path) -> None:
    """Verify config, summary json/csv, and SHA-256 manifest exist and match disk content."""
    cfg_file = executed_benchmark_dir / "benchmark_config.json"
    sum_json = executed_benchmark_dir / "benchmark_summary.json"
    sum_csv = executed_benchmark_dir / "benchmark_summary.csv"
    manifest_file = executed_benchmark_dir / "manifest.sha256"

    assert cfg_file.exists()
    assert sum_json.exists()
    assert sum_csv.exists()
    assert manifest_file.exists()

    with open(sum_json, "r", encoding="utf-8") as f:
        summary = json.load(f)

    # 5 models * 4 folds = 20 total runs
    assert summary["total_runs"] == 20
    assert summary["completed_runs"] == 20
    assert summary["failed_runs"] == 0

    df_csv = pd.read_csv(sum_csv)
    assert len(df_csv) == 20
    assert set(df_csv["model_id"]) == set(CORE_METHOD_IDS)

    # Verify SHA-256 manifest
    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert len(manifest) >= 23  # config, summaries, 20 oof parquets, 20 metrics jsons
    for rel_path, expected_hash in manifest.items():
        file_path = executed_benchmark_dir / rel_path
        assert file_path.exists()
        actual_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
        assert actual_hash == expected_hash, f"Hash mismatch for {rel_path}"
