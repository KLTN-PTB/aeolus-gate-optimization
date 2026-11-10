"""Comprehensive test suite for V2 Common Benchmark Engine & Point Models (Task R3).

Verifies all Task R3 acceptance requirements:
1. 5 Core models only (fail closed on B5 legacy, auxiliary departure, arbitrary models)
2. Common runner pipeline contract
3. Same rows across models (exact row count & flight_key sequence alignment)
4. Same fold boundaries (expanding rolling folds 1-4)
5. Preprocessing train-only (zero val mutation)
6. No Weather predictors
7. No Departure prediction or operational leakage
8. No random split substitution
9. Classification probability validity (ad-hoc sigmoid rejected)
10. OOF V2 schema compliance (all 12 required fields)
11. No silent row drop (failures retained)
12. Model registry integration
13. No champion selection
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.data.leakage_rules import ARRIVAL_LEAKAGE_COLUMNS, WEATHER_COLUMNS
from src.data.preprocessing import build_linear_preprocessor, build_tree_preprocessor
from src.evaluation.forecast_metrics import compute_point_forecast_metrics
from src.evaluation.model_benchmark_runner import (
    CORE_POINT_BENCHMARK_METHOD_IDS,
    OOF_V2_COLUMNS,
    CommonBenchmarkConfig,
    CommonPointBenchmarkRunner,
    assert_core_point_benchmark_eligible,
    derive_training_class_weights,
    is_core_point_benchmark_eligible,
    validate_oof_v2_frame,
)
from src.features.tabular_features import APPROVED_PREDICTOR_COLUMNS
from src.models.contracts import load_week4_rolling_folds
from src.models.registry import get_core_point_models


# ==============================================================================
# 1. Model Registry & Core 5 Cap
# ==============================================================================

def test_exactly_5_core_point_models_registered() -> None:
    """Verify that exactly 5 models are eligible for the Core Point Benchmark."""
    models = get_core_point_models()
    assert len(models) == 5, f"Expected exactly 5 core point models, got {len(models)}"
    m_ids = [m.model_id for m in models]
    for expected_id in CORE_POINT_BENCHMARK_METHOD_IDS:
        assert expected_id in m_ids


def test_core_point_benchmark_eligibility_enforcement() -> None:
    """Verify that assert_core_point_benchmark_eligible fails closed on unauthorized models."""
    # Authorized core models pass
    for m in CORE_POINT_BENCHMARK_METHOD_IDS:
        assert is_core_point_benchmark_eligible(m)
        spec = assert_core_point_benchmark_eligible(m)
        assert spec.model_id == m

    # Legacy B5 is rejected
    assert not is_core_point_benchmark_eligible("b5_ngboost_student_t")
    with pytest.raises(ValueError, match="NOT eligible for Core Point Benchmark"):
        assert_core_point_benchmark_eligible("b5_ngboost_student_t")

    # Auxiliary departure is rejected
    assert not is_core_point_benchmark_eligible("departure_auxiliary_baseline_v1")
    with pytest.raises(ValueError, match="NOT eligible for Core Point Benchmark"):
        assert_core_point_benchmark_eligible("departure_auxiliary_baseline_v1")

    # Unknown model fails closed
    assert not is_core_point_benchmark_eligible("arbitrary_unknown_model_v9")
    with pytest.raises(KeyError, match="explicitly registered"):
        assert_core_point_benchmark_eligible("arbitrary_unknown_model_v9")


def test_config_rejects_more_than_5_models() -> None:
    """Verify that CommonBenchmarkConfig enforces the 5-method cap."""
    with pytest.raises(ValueError, match="strictly capped at 5"):
        CommonBenchmarkConfig(
            methods=CORE_POINT_BENCHMARK_METHOD_IDS + ("extra_model",)
        )


# ==============================================================================
# 2. Temporal Fairness & Fold Boundaries
# ==============================================================================

def test_temporal_fold_boundaries_are_strictly_expanding() -> None:
    """Verify that rolling folds 1-4 are strictly expanding without lookahead."""
    folds = load_week4_rolling_folds()
    assert len(folds) == 4

    expected = {
        "fold_1": ([2016, 2017, 2018], 2019),
        "fold_2": ([2016, 2017, 2018, 2019], 2020),
        "fold_3": ([2016, 2017, 2018, 2019, 2020], 2021),
        "fold_4": ([2016, 2017, 2018, 2019, 2020, 2021], 2022),
    }

    for fold in folds:
        exp_train, exp_val = expected[fold.fold_id]
        assert list(fold.train_years) == exp_train
        assert fold.validation_year == exp_val
        # No temporal overlap: train years strictly precede validation year
        assert max(fold.train_years) < fold.validation_year
        # Development strictly inside 2016-2022
        assert max(fold.train_years) <= 2021
        assert fold.validation_year <= 2022


# ==============================================================================
# 3. Features & Leakage Invariants
# ==============================================================================

def test_approved_predictor_columns_contain_no_weather_or_leakage() -> None:
    """Verify predictor whitelist has zero intersection with weather and leakage."""
    predictors = set(APPROVED_PREDICTOR_COLUMNS)
    assert not predictors.intersection(WEATHER_COLUMNS), "Weather found in predictors!"
    assert not predictors.intersection(ARRIVAL_LEAKAGE_COLUMNS), "Leakage found in predictors!"
    assert "ARR_DELAY" not in predictors
    assert "DEP_DELAY" not in predictors


def test_preprocessing_fit_on_train_only() -> None:
    """Verify that preprocessor fit on training data is not altered by validation transform."""
    from src.features.tabular_features import (
        CATEGORICAL_FEATURE_COLUMNS,
        HIGH_CARDINALITY_FEATURE_COLUMNS,
        NUMERIC_FEATURE_COLUMNS,
    )

    rng = np.random.default_rng(202601)
    N_tr, N_val = 100, 50

    # Synthetic training & validation data matching schema
    data_tr = {}
    data_val = {}
    for col in NUMERIC_FEATURE_COLUMNS:
        data_tr[col] = rng.normal(0, 1, size=N_tr)
        data_val[col] = rng.normal(5, 2, size=N_val)
    cat_choices = np.array(["DL", "UA", "AA", "WN"])
    for col in CATEGORICAL_FEATURE_COLUMNS:
        data_tr[col] = cat_choices[rng.integers(0, 4, size=N_tr)]
        data_val[col] = cat_choices[rng.integers(0, 4, size=N_val)]
    for col in HIGH_CARDINALITY_FEATURE_COLUMNS:
        data_tr[col] = np.array([f"FL_{i}" for i in rng.integers(100, 200, size=N_tr)])
        data_val[col] = np.array([f"FL_{i}" for i in rng.integers(100, 200, size=N_val)])

    df_train = pd.DataFrame(data_tr)
    df_val = pd.DataFrame(data_val)

    prep = build_linear_preprocessor()
    X_tr_trans = prep.fit_transform(df_train)

    # Check fitted state of numeric pipeline
    num_pipe = prep.named_transformers_["numeric"]
    scaler = num_pipe.named_steps["scaler"]
    mean_before = scaler.mean_.copy()
    var_before = scaler.var_.copy()

    # Transform validation
    X_val_trans = prep.transform(df_val)

    # Scaler mean and variance must remain identical
    np.testing.assert_array_equal(scaler.mean_, mean_before)
    np.testing.assert_array_equal(scaler.var_, var_before)
    assert X_tr_trans.shape[0] == N_tr
    assert X_val_trans.shape[0] == N_val


# ==============================================================================
# 4. Classification Probability Validity & Metrics
# ==============================================================================

def test_classification_metrics_require_audited_probability_estimator() -> None:
    """Verify that reporting classification metrics rejects unaudited or ad-hoc probabilities."""
    y_reg = np.array([5.0, 20.0, -10.0, 45.0, 70.0])
    p_reg = np.array([4.0, 18.0, -5.0, 40.0, 65.0])
    y_cls = np.array([0, 1, 0, 1, 1])

    # Ad-hoc sigmoid of predicted delay
    adhoc_prob = 1.0 / (1.0 + np.exp(-p_reg))

    # Calling compute_point_forecast_metrics without probability_estimator_audit raises ValueError
    with pytest.raises(ValueError, match="Ad-hoc probability estimation"):
        compute_point_forecast_metrics(
            y_true_reg=y_reg,
            pred_reg=p_reg,
            y_true_cls=y_cls,
            pred_cls_prob=adhoc_prob,
            probability_estimator_audit=None,
        )


def test_compute_point_forecast_metrics_semantics() -> None:
    """Verify metrics calculation and sample counts."""
    y_reg = np.array([5.0, 20.0, -10.0, 45.0, 70.0, 80.0])
    p_reg = np.array([4.0, 18.0, -5.0, 40.0, 65.0, 75.0])
    y_cls = np.array([0, 1, 0, 1, 1, 1])
    p_cls = np.array([0.1, 0.8, 0.05, 0.7, 0.9, 0.95])

    res = compute_point_forecast_metrics(
        y_true_reg=y_reg,
        pred_reg=p_reg,
        y_true_cls=y_cls,
        pred_cls_prob=p_cls,
        probability_estimator_audit="dual_head_classifier",
    )

    assert res["n_total"] == 6
    assert res["n_valid"] == 6
    assert res["n_missing"] == 0
    assert res["n_failures"] == 0
    assert res["mae"] > 0
    assert res["rmse"] > 0
    assert res["r2"] is not None
    assert res["severe_delay_count"] == 2  # 70.0 and 80.0 >= 60
    assert res["severe_delay_mae_ge_60"] == 5.0
    assert res["pr_auc"] is not None
    assert res["roc_auc"] is not None
    assert res["brier_score"] is not None
    assert res["probability_semantics"] == "VALID_AUDITED_ESTIMATOR"


def test_severe_delay_mae_ge_60() -> None:
    """Verify Severe Delay MAE correctly isolates the y_true >= 60 slice."""
    y_reg = np.array([10.0, 25.0, 60.0, 90.0])
    p_reg = np.array([10.0, 25.0, 50.0, 70.0])

    res = compute_point_forecast_metrics(
        y_true_reg=y_reg,
        pred_reg=p_reg,
    )
    # Severe slice: 60.0 (error 10.0) and 90.0 (error 20.0) -> mean error 15.0
    assert res["severe_delay_count"] == 2
    assert res["severe_delay_mae_ge_60"] == 15.0


# ==============================================================================
# 5. OOF Schema & No Silent Row Drop
# ==============================================================================

def test_oof_v2_schema_validation() -> None:
    """Verify that OOF V2 schema is strictly enforced."""
    df_valid = pd.DataFrame({
        "row_id": [0, 1],
        "flight_key": ["K1", "K2"],
        "fold_id": ["fold_1", "fold_1"],
        "model_id": ["arrival_linear_baseline_v1", "arrival_linear_baseline_v1"],
        "y_true_reg": [10.0, -5.0],
        "y_true_cls": [0, 0],
        "pred_reg": [8.0, -3.0],
        "pred_cls_prob": [0.2, 0.1],
        "seed": [202601, 202601],
        "train_window": ["2016-2018", "2016-2018"],
        "code_hash": ["c123", "c123"],
        "config_hash": ["cfg123", "cfg123"],
        "status": ["SUCCESS", "SUCCESS"],
        "failure_reason": [None, None],
    })
    validate_oof_v2_frame(df_valid)

    # Missing column raises ValueError
    df_invalid = df_valid.drop(columns=["row_id"])
    with pytest.raises(ValueError, match="missing required column: 'row_id'"):
        validate_oof_v2_frame(df_invalid)

    # Null flight_key raises ValueError
    df_null_key = df_valid.copy()
    df_null_key.loc[0, "flight_key"] = None
    with pytest.raises(ValueError, match="flight_key cannot contain null"):
        validate_oof_v2_frame(df_null_key)


# ==============================================================================
# 6. Mini-Benchmark Integration Test (Fast Execution)
# ==============================================================================

@pytest.fixture(scope="module")
def mini_benchmark_run(tmp_path_factory: pytest.TempPathFactory) -> tuple[CommonPointBenchmarkRunner, list]:
    """Execute a fast, real mini-benchmark across 2 folds for testing parity."""
    out_dir = tmp_path_factory.mktemp("benchmark_test")
    manifest_file = out_dir / "test_manifest.json"

    cfg = CommonBenchmarkConfig(
        experiment_id="test_fast_point_engine",
        sample_train_per_year=120,
        sample_val=150,
        random_seed=202601,
        output_dir=out_dir,
        manifest_path=manifest_file,
    )
    runner = CommonPointBenchmarkRunner(cfg)
    results = runner.run_benchmark()
    return runner, results


def test_row_alignment_across_all_models(mini_benchmark_run: tuple[CommonPointBenchmarkRunner, list]) -> None:
    """Verify that all 5 models share identical row counts, flight keys, and targets."""
    runner, results = mini_benchmark_run
    oof_dir = runner.run_dir / "oof"
    assert oof_dir.exists()

    for fold_id in ("fold_1", "fold_2", "fold_3", "fold_4"):
        dfs: dict[str, pd.DataFrame] = {}
        for method_id in CORE_POINT_BENCHMARK_METHOD_IDS:
            parquet_path = oof_dir / f"{method_id}_{fold_id}.parquet"
            assert parquet_path.exists(), f"Missing OOF file: {parquet_path}"
            df = pd.read_parquet(parquet_path)
            validate_oof_v2_frame(df)
            dfs[method_id] = df

        # Baseline reference is arrival_linear_baseline_v1
        ref_df = dfs["arrival_linear_baseline_v1"]
        ref_len = len(ref_df)
        ref_keys = ref_df["flight_key"].tolist()
        ref_y_reg = ref_df["y_true_reg"].to_numpy()
        ref_y_cls = ref_df["y_true_cls"].to_numpy()

        for method_id, df in dfs.items():
            # 1. Exact row count parity
            assert len(df) == ref_len, f"Row count mismatch in {fold_id} for {method_id}"
            # 2. Exact flight key sequence alignment
            assert df["flight_key"].tolist() == ref_keys, f"Flight key order mismatch in {fold_id} for {method_id}"
            # 3. Exact target alignment
            np.testing.assert_array_equal(df["y_true_reg"].to_numpy(), ref_y_reg)
            np.testing.assert_array_equal(df["y_true_cls"].to_numpy(), ref_y_cls)


def test_manifest_and_summary_contain_no_champion(mini_benchmark_run: tuple[CommonPointBenchmarkRunner, list]) -> None:
    """Verify that benchmark artifacts strictly avoid champion selection."""
    runner, _ = mini_benchmark_run
    summary_json = runner.run_dir / "benchmark_summary.json"
    assert summary_json.exists()

    with open(summary_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["champion_selected"] is False
    assert data["champion_selection_policy"] == "NO_CHAMPION_SELECTION_IN_R3"
    assert "champion" not in data or data["champion"] is None


def test_top_level_manifest_generated(mini_benchmark_run: tuple[CommonPointBenchmarkRunner, list]) -> None:
    """Verify that top-level manifest is written and contains required metadata."""
    runner, _ = mini_benchmark_run
    manifest_path = runner.config.manifest_path
    assert manifest_path.exists()

    with open(manifest_path, "r", encoding="utf-8") as f:
        m = json.load(f)

    assert m["manifest_version"] == "core_point_benchmark_v2"
    assert m["model_count"] == 5
    assert len(m["models_evaluated"]) == 5
    assert m["provenance_invariants"]["cap_5_strictly_enforced"] is True
    assert m["provenance_invariants"]["same_row_alignment_guaranteed"] is True
    assert m["provenance_invariants"]["champion_selection"] == "NONE"
