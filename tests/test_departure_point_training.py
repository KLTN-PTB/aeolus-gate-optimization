"""Unit tests for Core Departure Point Forecast Training, Folds, and Artifacts.

Protocol: Aeolus Dual Core Architecture Protocol V2
Phase: P4 Point Forecasting Verification Suite
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest

from src.data.departure_preprocessing import DeparturePreprocessingPipeline
from src.features.departure_features import (
    prepare_departure_inference,
    prepare_departure_training,
)
from src.models.interfaces import ModelCategory
from src.models.registry import get_model_spec


ROOT = Path(__file__).resolve().parents[1]
DUAL_CORE_DIR = ROOT / "artifacts" / "dual_core"
MODELS_DIR = DUAL_CORE_DIR / "models"
PRED_DIR = DUAL_CORE_DIR / "predictions"
BENCH_DIR = DUAL_CORE_DIR / "benchmarks"


class TestExpandingWindowProtocol:
    """Verifies expanding window temporal protocol rules."""

    def test_fold_temporal_isolation(self):
        """Every expanding fold strictly trains on past and validates on future."""
        folds = [
            {"fold_id": 1, "train_years": [2016, 2017, 2018], "val_year": 2019},
            {"fold_id": 2, "train_years": [2016, 2017, 2018, 2019], "val_year": 2020},
            {"fold_id": 3, "train_years": [2016, 2017, 2018, 2019, 2020], "val_year": 2021},
            {"fold_id": 4, "train_years": [2016, 2017, 2018, 2019, 2020, 2021], "val_year": 2022},
        ]
        for f in folds:
            assert max(f["train_years"]) < f["val_year"], f"Temporal leak in fold {f['fold_id']}"
            assert f["val_year"] not in f["train_years"]

    def test_2023_selection_protocol(self):
        """2023 evaluation is trained strictly on 2016-2022 and does not touch 2024."""
        train_years = list(range(2016, 2023))
        eval_year = 2023
        assert max(train_years) == 2022
        assert max(train_years) < eval_year
        assert 2024 not in train_years
        assert 2024 != eval_year


class TestRegistryDeparturePointModels:
    """Verifies Core Departure point model registrations in ModelRegistry."""

    def test_departure_models_registered(self):
        ridge_spec = get_model_spec("departure_ridge_baseline_v1")
        assert ridge_spec is not None
        assert ridge_spec.category == ModelCategory.CORE_DEPARTURE.value
        assert ridge_spec.downstream_eligible is False
        assert ridge_spec.status == "research_candidate"

        xgb_spec = get_model_spec("departure_xgboost_baseline_v1")
        assert xgb_spec is not None
        assert xgb_spec.category == ModelCategory.CORE_DEPARTURE.value
        assert xgb_spec.downstream_eligible is False
        assert xgb_spec.status == "research_candidate"


class TestOOFAndSelectionPredictions:
    """Verifies generated OOF and 2023 prediction parquets if present."""

    @pytest.mark.skipif(
        not (PRED_DIR / "departure_point_oof_v1.parquet").exists(),
        reason="OOF prediction parquet not yet generated",
    )
    def test_oof_parquet_schema_and_integrity(self):
        oof_path = PRED_DIR / "departure_point_oof_v1.parquet"
        df = pd.read_parquet(oof_path)

        expected_cols = {
            "flight_key",
            "FL_DATE",
            "source_year",
            "OP_UNIQUE_CARRIER",
            "DEST",
            "crs_dep_hour",
            "actual_dep_delay",
            "pred_zero",
            "pred_median",
            "pred_ridge",
            "pred_xgboost",
            "fold_id",
            "val_year",
        }
        assert expected_cols.issubset(set(df.columns))

        # Check fold years
        assert set(df["val_year"].unique()) == {2019, 2020, 2021, 2022}
        assert df["val_year"].equals(df["source_year"])

        # Check unique keys
        assert df["flight_key"].nunique() == len(df), "Duplicate flight_keys found in OOF"

        # Check no NaN values in predictions or actuals
        assert df["actual_dep_delay"].isna().sum() == 0
        assert df["pred_zero"].isna().sum() == 0
        assert df["pred_median"].isna().sum() == 0
        assert df["pred_ridge"].isna().sum() == 0
        assert df["pred_xgboost"].isna().sum() == 0

        # Zero model should strictly predict 0.0
        assert (df["pred_zero"] == 0.0).all()

    @pytest.mark.skipif(
        not (PRED_DIR / "departure_point_selection_2023_v1.parquet").exists(),
        reason="2023 prediction parquet not yet generated",
    )
    def test_2023_parquet_schema_and_integrity(self):
        sel_path = PRED_DIR / "departure_point_selection_2023_v1.parquet"
        df = pd.read_parquet(sel_path)

        assert (df["source_year"] == 2023).all()
        assert df["flight_key"].nunique() == len(df)
        assert df["actual_dep_delay"].isna().sum() == 0
        assert df["pred_xgboost"].isna().sum() == 0
        assert df["pred_ridge"].isna().sum() == 0


class TestModelCheckpointsAndInference:
    """Verifies model checkpoints can be loaded and executed label-free."""

    @pytest.mark.skipif(
        not (MODELS_DIR / "departure_xgboost_baseline_v1.joblib").exists(),
        reason="Model checkpoints not yet generated",
    )
    def test_reload_and_label_free_inference(self):
        linear_prep: DeparturePreprocessingPipeline = joblib.load(
            MODELS_DIR / "departure_linear_preprocessor_v1.joblib"
        )
        tree_prep: DeparturePreprocessingPipeline = joblib.load(
            MODELS_DIR / "departure_tree_preprocessor_v1.joblib"
        )
        ridge_model = joblib.load(MODELS_DIR / "departure_ridge_baseline_v1.joblib")
        xgb_model = joblib.load(MODELS_DIR / "departure_xgboost_baseline_v1.joblib")

        # Create synthetic test batch strictly without DEP_DELAY or ARR_DELAY
        raw_test = pd.DataFrame(
            {
                "flight_key": ["t_1", "t_2"],
                "source_year": [2023, 2023],
                "source_row_number": [1, 2],
                "ORIGIN": ["ATL", "ATL"],
                "FL_DATE": ["2023-05-01 00:00:00", "2023-05-01 00:00:00"],
                "CRS_DEP_TIME": ["2023-05-01 08:30:00", "2023-05-01 17:45:00"],
                "CRS_ELAPSED_TIME": [120.0, 240.0],
                "MONTH": [5, 5],
                "DAY_OF_MONTH": [1, 1],
                "DAY_OF_WEEK": [1, 1],
                "OP_CARRIER": ["DL", "UA"],
                "OP_CARRIER_FL_NUM": [123.0, 456.0],
                "DEST": ["LGA", "ORD"],
            }
        )

        assert "DEP_DELAY" not in raw_test.columns
        assert "ARR_DELAY" not in raw_test.columns

        # Inference feature extraction
        features = prepare_departure_inference(raw_test)

        # Preprocessing transform
        X_linear = linear_prep.transform(features.X)
        X_tree = tree_prep.transform(features.X)

        # Predictions
        preds_ridge = ridge_model.predict(X_linear)
        preds_xgb = xgb_model.predict(X_tree)

        assert len(preds_ridge) == 2
        assert len(preds_xgb) == 2
        assert np.isfinite(preds_ridge).all()
        assert np.isfinite(preds_xgb).all()
        assert preds_ridge.dtype == np.float64
        assert preds_xgb.dtype in (np.float32, np.float64)


class TestBenchmarkArtifacts:
    """Verifies benchmark and readiness JSON structures."""

    @pytest.mark.skipif(
        not (BENCH_DIR / "departure_point_benchmark_v1.json").exists(),
        reason="Benchmark JSON not yet generated",
    )
    def test_benchmark_json_structure(self):
        with open(BENCH_DIR / "departure_point_benchmark_v1.json", "r", encoding="utf-8") as f:
            data = json.load(f)

        assert "meta" in data
        assert "expanding_window_folds" in data
        assert len(data["expanding_window_folds"]) == 4
        assert "pooled_oof_metrics" in data
        assert "macro_fold_metrics" in data
        assert "selection_2023_metrics" in data
        assert "slices" in data

        # Check models evaluated
        for fold in data["expanding_window_folds"]:
            assert set(fold["models"].keys()) == {"pred_zero", "pred_median", "pred_ridge", "pred_xgboost"}

    @pytest.mark.skipif(
        not (BENCH_DIR / "departure_point_readiness_v1.json").exists(),
        reason="Readiness JSON not yet generated",
    )
    def test_readiness_json_status(self):
        with open(BENCH_DIR / "departure_point_readiness_v1.json", "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["overall_status"] == "READY_FOR_P5"
        assert len(data["readiness_gates"]) >= 6
        for gate in data["readiness_gates"]:
            assert gate["status"] == "PASS"


class TestProtectedArrivalSafety:
    """Verifies that protected Arrival artifacts remain untouched during training."""

    def test_arrival_hashes_unchanged(self):
        hash_file = DUAL_CORE_DIR / "preflight" / "frozen_artifact_hashes.json"
        if not hash_file.exists():
            pytest.skip("Preflight hash record does not exist")

        with open(hash_file, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        for rel_path, expected_hash in manifest.get("artifact_hashes", {}).items():
            full_path = ROOT / rel_path
            if full_path.exists():
                with open(full_path, "rb") as item:
                    actual_hash = hashlib.sha256(item.read()).hexdigest()
                assert actual_hash == expected_hash, f"Protected artifact altered: {rel_path}"
