"""Comprehensive unit tests for Core Departure Feature Engineering & Preprocessing.

Protocol: Aeolus Dual Core Architecture Protocol V2
Phase: P3 Verification Suite
"""

from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.data.departure_preprocessing import (
    DEPARTURE_APPROVED_PREDICTORS,
    DEPARTURE_CATEGORICAL_FEATURES,
    DEPARTURE_HIGH_CARDINALITY_FEATURES,
    DEPARTURE_NUMERIC_FEATURES,
    DEPARTURE_PREPROCESSING_VERSION,
    DeparturePreprocessingError,
    DeparturePreprocessingPipeline,
    build_departure_linear_preprocessor,
    build_departure_tree_preprocessor,
)
from src.features.departure_features import (
    APPROVED_DEPARTURE_PREDICTOR_COLUMNS,
    DepartureFeatureContractViolation,
    DepartureTargetError,
    build_departure_labels,
    prepare_departure_inference,
    prepare_departure_training,
)


@pytest.fixture
def sample_training_outbound_data() -> pd.DataFrame:
    """Fixture providing clean outbound flight records with targets and metadata."""
    return pd.DataFrame(
        {
            "flight_key": ["fl_1", "fl_2", "fl_3", "fl_4", "fl_5"],
            "source_year": [2022, 2022, 2022, 2022, 2022],
            "source_row_number": [10, 20, 30, 40, 50],
            "FL_DATE": [
                "2022-06-10 00:00:00",
                "2022-06-10 00:00:00",
                "2022-06-11 00:00:00",
                "2022-06-11 00:00:00",
                "2022-06-12 00:00:00",
            ],
            "CRS_DEP_TIME": [
                "2022-06-10 06:15:00",
                "2022-06-10 11:30:00",
                "2022-06-11 15:45:00",
                "2022-06-11 20:00:00",
                "2022-06-12 23:30:00",
            ],
            "CRS_ELAPSED_TIME": [115.0, 140.0, 90.0, 210.0, 180.0],
            "MONTH": [6, 6, 6, 6, 6],
            "DAY_OF_MONTH": [10, 10, 11, 11, 12],
            "DAY_OF_WEEK": [5, 5, 6, 6, 7],
            "OP_CARRIER": ["DL", "DL", "AA", "UA", "DL"],
            "ORIGIN": ["ATL", "ATL", "ATL", "ATL", "ATL"],
            "DEST": ["MCO", "LGA", "DFW", "ORD", "LAX"],
            "OP_CARRIER_FL_NUM": [1101, 1102, 2201, 3301, 1101],
            "DEP_DELAY": [-12.0, -3.0, 0.0, 18.0, 65.0],
        }
    )


@pytest.fixture
def sample_validation_outbound_data() -> pd.DataFrame:
    """Fixture providing validation outbound records with unseen categories and missing values."""
    return pd.DataFrame(
        {
            "flight_key": ["val_1", "val_2"],
            "source_year": [2023, 2023],
            "source_row_number": [100, 200],
            "FL_DATE": [
                "2023-01-15 00:00:00",
                "2023-01-16 00:00:00",
            ],
            "CRS_DEP_TIME": [
                "2023-01-15 09:00:00",
                "2023-01-16 14:00:00",
            ],
            "CRS_ELAPSED_TIME": [np.nan, 250.0],  # missing numeric value
            "MONTH": [1, 1],
            "DAY_OF_MONTH": [15, 16],
            "DAY_OF_WEEK": [7, 1],
            "OP_CARRIER": ["UNSEEN_CARRIER", "DL"],  # unseen carrier
            "ORIGIN": ["ATL", "ATL"],
            "DEST": ["UNSEEN_DEST", "MCO"],  # unseen destination
            "OP_CARRIER_FL_NUM": [9999, 1101],  # unseen flight number
            "DEP_DELAY": [-5.0, 25.0],
        }
    )


# =============================================================================
# 1. Feature Engineering: Training vs Inference Parity & Contract Enforcement
# =============================================================================

def test_departure_training_pipeline_builds_exact_features_and_targets(
    sample_training_outbound_data: pd.DataFrame,
) -> None:
    """Training path creates aligned X, signed continuous y_dep_reg, and binary y_dep_cls."""
    prep = prepare_departure_training(sample_training_outbound_data)

    # 1. Exact 10 features in correct order
    assert tuple(prep.X.columns) == APPROVED_DEPARTURE_PREDICTOR_COLUMNS
    assert len(prep.X.columns) == 10

    # 2. Targets: preserves negative delay, no clipping, no imputation
    assert prep.y_dep_reg.tolist() == [-12.0, -3.0, 0.0, 18.0, 65.0]
    assert prep.y_dep_cls.tolist() == [0, 0, 0, 1, 1]

    # 3. Row alignment between X, y, identifiers, cutoffs
    assert len(prep.X) == len(prep.y_dep_reg) == len(prep.y_dep_cls) == len(prep.identifiers) == len(prep.prediction_cutoff)
    assert prep.identifiers["flight_key"].tolist() == ["fl_1", "fl_2", "fl_3", "fl_4", "fl_5"]

    # 4. Excluded columns
    for forbidden in ["ORIGIN", "DEP_DELAY", "ARR_DELAY", "calendar_year", "flight_key"]:
        assert forbidden not in prep.X.columns


def test_departure_inference_pipeline_requires_no_delay_outcomes(
    sample_training_outbound_data: pd.DataFrame,
) -> None:
    """Inference path operates on schedule-only data without requiring DEP_DELAY."""
    inference_input = sample_training_outbound_data.drop(columns=["DEP_DELAY"])
    assert "DEP_DELAY" not in inference_input.columns

    prep_inf = prepare_departure_inference(inference_input)

    assert tuple(prep_inf.X.columns) == APPROVED_DEPARTURE_PREDICTOR_COLUMNS
    assert len(prep_inf.X) == 5
    assert prep_inf.identifiers["flight_key"].tolist() == ["fl_1", "fl_2", "fl_3", "fl_4", "fl_5"]


def test_training_and_inference_feature_matrix_parity(
    sample_training_outbound_data: pd.DataFrame,
) -> None:
    """X matrix produced by training and inference paths has identical schema, order, and values."""
    prep_train = prepare_departure_training(sample_training_outbound_data)
    prep_inf = prepare_departure_inference(sample_training_outbound_data)

    pd.testing.assert_frame_equal(prep_train.X, prep_inf.X)


def test_departure_pipeline_filters_non_atl_origin(
    sample_training_outbound_data: pd.DataFrame,
) -> None:
    """Records outside ORIGIN == 'ATL' are excluded and counted in eligibility report."""
    mixed_data = sample_training_outbound_data.copy()
    mixed_data.loc[1, "ORIGIN"] = "ORD"

    prep = prepare_departure_training(mixed_data)
    assert prep.eligibility.input_rows == 5
    assert prep.eligibility.outbound_rows == 4
    assert prep.eligibility.dropped_non_outbound_rows == 1
    assert len(prep.X) == 4
    assert prep.y_dep_reg.tolist() == [-12.0, 0.0, 18.0, 65.0]


def test_prediction_cutoff_is_crs_dep_time_minus_2_hours(
    sample_training_outbound_data: pd.DataFrame,
) -> None:
    """Prediction cutoff is strictly T-2h before scheduled departure in America/New_York."""
    prep = prepare_departure_training(sample_training_outbound_data)
    expected_cutoffs = [
        pd.Timestamp("2022-06-10 04:15:00"),
        pd.Timestamp("2022-06-10 09:30:00"),
        pd.Timestamp("2022-06-11 13:45:00"),
        pd.Timestamp("2022-06-11 18:00:00"),
        pd.Timestamp("2022-06-12 21:30:00"),
    ]
    assert prep.prediction_cutoff.tolist() == expected_cutoffs


def test_time_parsing_handles_numeric_hhmm_and_rejects_out_of_bounds() -> None:
    """Schedule parser supports numeric HHMM and rejects out-of-range times (e.g. >2400 or >59 min)."""
    valid_numeric = pd.DataFrame(
        {
            "FL_DATE": ["2022-06-10 00:00:00"],
            "CRS_DEP_TIME": [1430],  # 14:30
            "CRS_ELAPSED_TIME": [100.0],
            "MONTH": [6],
            "DAY_OF_MONTH": [10],
            "DAY_OF_WEEK": [5],
            "OP_CARRIER": ["DL"],
            "ORIGIN": ["ATL"],
            "DEST": ["MCO"],
            "OP_CARRIER_FL_NUM": [100],
        }
    )
    prep = prepare_departure_inference(valid_numeric)
    assert prep.X["scheduled_departure_hour"].iloc[0] == 14
    assert prep.X["scheduled_departure_minute"].iloc[0] == 30

    invalid_minute = valid_numeric.copy()
    invalid_minute["CRS_DEP_TIME"] = [1485]  # invalid 85 minutes
    with pytest.raises(DepartureFeatureContractViolation, match="invalid non-missing CRS_DEP_TIME"):
        prepare_departure_inference(invalid_minute)


# =============================================================================
# 2. Fold-Safe Preprocessing: Imputation, Vocabulary & Scaling Isolation
# =============================================================================

def test_numeric_imputation_and_scaling_are_fitted_on_train_only(
    sample_training_outbound_data: pd.DataFrame,
    sample_validation_outbound_data: pd.DataFrame,
) -> None:
    """Median and scale statistics fit on training rows only and remain frozen during transform."""
    train_prep = prepare_departure_training(sample_training_outbound_data)
    val_prep = prepare_departure_training(sample_validation_outbound_data)

    pipeline = DeparturePreprocessingPipeline(preprocessor_type="linear")
    pipeline.fit(train_prep.X)

    # Median of train CRS_ELAPSED_TIME [115, 140, 90, 210, 180] is 140.0
    imputer = pipeline.transformer.named_transformers_["numeric"].named_steps["imputer"]
    scaler = pipeline.transformer.named_transformers_["numeric"].named_steps["scaler"]

    elapsed_idx = list(DEPARTURE_NUMERIC_FEATURES).index("CRS_ELAPSED_TIME")
    assert imputer.statistics_[elapsed_idx] == 140.0
    initial_mean = scaler.mean_[elapsed_idx]

    # Transform validation containing missing CRS_ELAPSED_TIME
    val_transformed = pipeline.transform(val_prep.X)

    # Imputer and scaler statistics MUST NOT mutate during validation transform
    assert imputer.statistics_[elapsed_idx] == 140.0
    assert scaler.mean_[elapsed_idx] == initial_mean
    assert np.isfinite(val_transformed).all()


def test_categorical_vocabulary_does_not_leak_unseen_categories(
    sample_training_outbound_data: pd.DataFrame,
    sample_validation_outbound_data: pd.DataFrame,
) -> None:
    """Validation categories not seen in training are encoded as all-zeros without expanding vocabulary."""
    train_prep = prepare_departure_training(sample_training_outbound_data)
    val_prep = prepare_departure_training(sample_validation_outbound_data)

    pipeline = DeparturePreprocessingPipeline(preprocessor_type="linear")
    pipeline.fit(train_prep.X)

    encoder = pipeline.transformer.named_transformers_["categorical"].named_steps["encoder"]
    carrier_vocab_train = set(encoder.categories_[0])
    dest_vocab_train = set(encoder.categories_[1])

    assert "UNSEEN_CARRIER" not in carrier_vocab_train
    assert "UNSEEN_DEST" not in dest_vocab_train

    # Transform validation
    val_transformed = pipeline.transform(val_prep.X)
    assert val_transformed.shape[1] == len(pipeline.get_feature_names_out())

    # Encoder categories must remain exactly unchanged
    assert set(encoder.categories_[0]) == carrier_vocab_train
    assert set(encoder.categories_[1]) == dest_vocab_train


def test_high_cardinality_frequency_map_is_train_only_with_zero_unknown_fallback(
    sample_training_outbound_data: pd.DataFrame,
    sample_validation_outbound_data: pd.DataFrame,
) -> None:
    """Frequency encoder maps training flight numbers correctly and assigns 0.0 to unseen flight numbers."""
    train_prep = prepare_departure_training(sample_training_outbound_data)
    val_prep = prepare_departure_training(sample_validation_outbound_data)

    pipeline = DeparturePreprocessingPipeline(preprocessor_type="tree")
    pipeline.fit(train_prep.X)

    encoder = pipeline.transformer.named_transformers_["high_cardinality"].named_steps["encoder"]
    mapping = encoder.frequency_maps_["OP_CARRIER_FL_NUM"]

    # Flight 1101 appears 2 times out of 5 training rows -> 2/5 = 0.4
    assert mapping["1101"] == pytest.approx(0.4)
    # Flight 9999 is unseen in training
    assert "9999" not in mapping

    val_transformed = pipeline.transform(val_prep.X)
    flight_num_out_idx = pipeline.get_feature_names_out().index(
        "high_cardinality__OP_CARRIER_FL_NUM__frequency"
    )

    # First row of validation has unseen flight number 9999 -> 0.0
    assert val_transformed[0, flight_num_out_idx] == 0.0
    # Second row of validation has known flight number 1101 -> 0.4
    assert val_transformed[1, flight_num_out_idx] == pytest.approx(0.4)


def test_preprocessing_pipeline_schema_validation_and_fail_closed(
    sample_training_outbound_data: pd.DataFrame,
) -> None:
    """Preprocessing pipeline fails closed when input columns deviate from approved 10 features."""
    train_prep = prepare_departure_training(sample_training_outbound_data)
    pipeline = DeparturePreprocessingPipeline(preprocessor_type="linear")

    # 1. Missing feature
    missing_col = train_prep.X.drop(columns=["DEST"])
    with pytest.raises(DeparturePreprocessingError, match="missing="):
        pipeline.fit(missing_col)

    # 2. Extra unapproved feature
    extra_col = train_prep.X.copy()
    extra_col["calendar_year"] = 2022
    with pytest.raises(DeparturePreprocessingError, match="extra_unapproved="):
        pipeline.fit(extra_col)

    # 3. Column order mismatch
    cols_shuffled = list(train_prep.X.columns)
    cols_shuffled[0], cols_shuffled[1] = cols_shuffled[1], cols_shuffled[0]
    shuffled_df = train_prep.X.loc[:, cols_shuffled]
    with pytest.raises(DeparturePreprocessingError, match="order mismatch"):
        pipeline.fit(shuffled_df)


def test_manifest_export_and_cryptographic_fingerprint(
    sample_training_outbound_data: pd.DataFrame,
    tmp_path: Path,
) -> None:
    """Manifest exports full provenance, statistics, and deterministic SHA256 fingerprint."""
    train_prep = prepare_departure_training(sample_training_outbound_data)
    pipeline = DeparturePreprocessingPipeline(preprocessor_type="linear")
    pipeline.fit(train_prep.X)

    manifest = pipeline.export_manifest()
    assert manifest["transformation_version"] == DEPARTURE_PREPROCESSING_VERSION
    assert manifest["task"] == "core_departure"
    assert manifest["hub"] == "ATL"
    assert manifest["training_samples"] == 5
    assert len(manifest["numeric_medians"]) == len(DEPARTURE_NUMERIC_FEATURES)
    assert len(manifest["numeric_means"]) == len(DEPARTURE_NUMERIC_FEATURES)
    assert len(manifest["numeric_scales"]) == len(DEPARTURE_NUMERIC_FEATURES)
    assert "OP_CARRIER" in manifest["categorical_vocabularies"]
    assert "DEST" in manifest["categorical_vocabularies"]
    assert len(manifest["sha256_fingerprint"]) == 64

    # Save manifest and verify reload
    save_path = tmp_path / "test_manifest.json"
    pipeline.save_manifest(save_path)
    assert save_path.exists()
    reloaded = json.loads(save_path.read_text(encoding="utf-8"))
    assert reloaded["sha256_fingerprint"] == manifest["sha256_fingerprint"]
