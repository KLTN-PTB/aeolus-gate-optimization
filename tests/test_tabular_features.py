from __future__ import annotations

import pandas as pd
import pytest

from src.features.chain_feature_policy import ChainFeatureAvailabilityViolation
from src.features.tabular_features import (
    APPROVED_PREDICTOR_COLUMNS,
    ArrivalFeatureContractViolation,
    DROP_CONSTANT,
    DROP_IDENTIFIER,
    DROP_LEAKAGE,
    DROP_WEATHER,
    REVIEW_REQUIRED,
    UNKNOWN_BLOCKED,
    prepare_arrival_features,
    status_for_arrival_feature,
)


def _minimal_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "FL_DATE": ["2016-01-02 00:00:00", "2016-01-03 00:00:00"],
            "OP_CARRIER": ["AA", "DL"],
            "OP_CARRIER_FL_NUM": [101.0, 202.0],
            "ORIGIN": ["BOS", "JFK"],
            "DEST": ["ATL", "ATL"],
            "CRS_DEP_TIME": ["2016-01-02 09:05:00", "2016-01-03 23:45:00"],
            "CRS_ELAPSED_TIME": [150.0, 130.0],
            "MONTH": [1, 1],
            "DAY_OF_MONTH": [2, 3],
            "DAY_OF_WEEK": [6, 7],
            "ARR_DELAY": [-4.0, 15.0],
            "flight_key": ["flight_key_v1_a", "flight_key_v1_b"],
            "source_year": [2016, 2016],
            "source_row_number": [1, 2],
        }
    )


def test_prepare_arrival_features_builds_calendar_cutoff_and_aligned_labels() -> None:
    prepared = prepare_arrival_features(_minimal_frame())

    assert tuple(prepared.X.columns) == APPROVED_PREDICTOR_COLUMNS
    assert prepared.X["calendar_year"].tolist() == [2016, 2016]
    assert prepared.X["calendar_day_of_week"].tolist() == [6, 7]
    assert prepared.X["is_weekend"].tolist() == [1, 1]
    assert prepared.X["scheduled_departure_hour"].tolist() == [9, 23]
    assert prepared.X["scheduled_departure_minute"].tolist() == [5, 45]
    assert prepared.X["OP_CARRIER_FL_NUM"].tolist() == ["101", "202"]
    assert prepared.y_arr_cls.tolist() == [0, 1]
    assert prepared.y_arr_reg.tolist() == [-4.0, 15.0]
    assert prepared.prediction_cutoff.astype(str).tolist() == [
        "2016-01-02 07:05:00",
        "2016-01-03 21:45:00",
    ]
    assert prepared.identifiers["flight_key"].tolist() == [
        "flight_key_v1_a",
        "flight_key_v1_b",
    ]


def test_prepare_arrival_features_reports_flow_and_missing_target_filtering() -> None:
    frame = pd.concat(
        [
            _minimal_frame(),
            pd.DataFrame(
                {
                    "FL_DATE": ["2016-01-04 00:00:00", "2016-01-05 00:00:00"],
                    "OP_CARRIER": ["AA", "AA"],
                    "OP_CARRIER_FL_NUM": [303.0, 404.0],
                    "ORIGIN": ["LAX", "SFO"],
                    "DEST": ["LAX", "ATL"],
                    "CRS_DEP_TIME": ["2016-01-04 08:00:00", "2016-01-05 08:00:00"],
                    "CRS_ELAPSED_TIME": [60.0, 70.0],
                    "MONTH": [1, 1],
                    "DAY_OF_MONTH": [4, 5],
                    "DAY_OF_WEEK": [1, 2],
                    "ARR_DELAY": [2.0, None],
                    "flight_key": ["flight_key_v1_c", "flight_key_v1_d"],
                    "source_year": [2016, 2016],
                    "source_row_number": [3, 4],
                }
            ),
        ],
        ignore_index=True,
    )

    prepared = prepare_arrival_features(frame)

    assert prepared.eligibility.input_rows == 4
    assert prepared.eligibility.inbound_rows == 3
    assert prepared.eligibility.dropped_non_inbound_rows == 1
    assert prepared.eligibility.dropped_missing_target_rows == 1
    assert prepared.eligibility.eligible_rows == 2
    assert prepared.identifiers["flight_key"].tolist() == [
        "flight_key_v1_a",
        "flight_key_v1_b",
    ]


def test_known_forbidden_columns_are_classified_but_never_enter_core_x() -> None:
    frame = _minimal_frame().assign(
        DEP_DELAY=[5.0, 8.0],
        DEP_TIME=["0910", "2350"],
        O_TEMP=[10.0, 11.0],
        FLIGHTS=[1.0, 1.0],
        ORIGIN_INDEX=[1, 2],
        DEST_INDEX=[3, 3],
        D_LATITUDE=[33.64, 33.64],
        D_LONGITUDE=[-84.42, -84.42],
    )

    prepared = prepare_arrival_features(frame)

    assert set(prepared.X) == set(APPROVED_PREDICTOR_COLUMNS)
    assert status_for_arrival_feature("DEP_DELAY") == DROP_LEAKAGE
    assert status_for_arrival_feature("O_TEMP") == DROP_WEATHER
    assert status_for_arrival_feature("flight_key") == DROP_IDENTIFIER
    assert status_for_arrival_feature("DEST_INDEX") == DROP_CONSTANT
    assert status_for_arrival_feature("FLIGHTS") == REVIEW_REQUIRED
    assert status_for_arrival_feature("ORIGIN_INDEX") == REVIEW_REQUIRED


def test_arrival_feature_contract_fails_closed_for_unknown_field() -> None:
    frame = _minimal_frame().assign(UNREGISTERED_FIELD=[1, 2])

    assert status_for_arrival_feature("UNREGISTERED_FIELD") == UNKNOWN_BLOCKED
    with pytest.raises(ArrivalFeatureContractViolation, match="unknown/unclassified"):
        prepare_arrival_features(frame)


def test_crs_arrival_timestamp_is_not_used_for_naive_duration_or_rollover() -> None:
    frame = _minimal_frame().assign(
        CRS_ARR_TIME=["2016-01-02 00:10:00", "2016-01-03 01:10:00"]
    )

    prepared = prepare_arrival_features(frame)

    assert "CRS_ARR_TIME" not in prepared.X
    assert "scheduled_duration_derived" not in prepared.X
    assert "CRS_ELAPSED_TIME" in prepared.X
    assert status_for_arrival_feature("CRS_ARR_TIME") == REVIEW_REQUIRED


def test_calendar_source_columns_must_match_service_date() -> None:
    frame = _minimal_frame()
    frame.loc[0, "DAY_OF_WEEK"] = 2

    with pytest.raises(ArrivalFeatureContractViolation, match="DAY_OF_WEEK"):
        prepare_arrival_features(frame)


def test_ambiguous_exact_midnight_departure_fails_closed() -> None:
    frame = _minimal_frame()
    frame.loc[0, "CRS_DEP_TIME"] = "2016-01-02 00:00:00"

    with pytest.raises(ArrivalFeatureContractViolation, match="0000/2400"):
        prepare_arrival_features(frame)


def test_chain_extension_fails_closed_before_3b_availability_audit() -> None:
    with pytest.raises(ChainFeatureAvailabilityViolation, match="not_ml_admissible"):
        prepare_arrival_features(
            _minimal_frame().assign(chain_position=[0, 1]),
            extra_approved_features=["chain_position"],
        )


def test_prepare_arrival_features_does_not_mutate_input() -> None:
    frame = _minimal_frame()
    before = frame.copy(deep=True)

    prepare_arrival_features(frame)

    pd.testing.assert_frame_equal(frame, before)


def test_prepare_arrival_features_reindexes_duplicate_input_without_row_multiplication() -> None:
    frame = _minimal_frame()
    frame.index = [0, 0]

    prepared = prepare_arrival_features(frame)

    assert len(prepared.X) == len(prepared.y_arr_cls) == len(prepared.y_arr_reg) == 2
    assert prepared.X.index.tolist() == [0, 1]
    assert prepared.X.index.is_unique
    assert prepared.identifiers.index.equals(prepared.X.index)
    assert prepared.prediction_cutoff.index.equals(prepared.X.index)
    assert prepared.identifiers["flight_key"].tolist() == [
        "flight_key_v1_a",
        "flight_key_v1_b",
    ]


def test_duplicate_index_with_missing_target_drops_exactly_one_position() -> None:
    frame = _minimal_frame()
    frame.index = [5, 5]
    frame.iloc[1, frame.columns.get_loc("ARR_DELAY")] = None

    prepared = prepare_arrival_features(frame)

    assert len(prepared.X) == len(prepared.y_arr_cls) == 1
    assert prepared.X.index.tolist() == [0]
    assert prepared.identifiers["flight_key"].tolist() == ["flight_key_v1_a"]
    assert prepared.eligibility.dropped_missing_target_rows == 1


def test_blank_categories_become_missing_and_non_string_categories_fail_closed() -> None:
    blank = _minimal_frame()
    blank.loc[0, "ORIGIN"] = "   "
    blank.loc[1, "OP_CARRIER"] = ""

    prepared = prepare_arrival_features(blank)

    assert pd.isna(prepared.X.loc[0, "ORIGIN"])
    assert pd.isna(prepared.X.loc[1, "OP_CARRIER"])

    invalid = _minimal_frame()
    invalid.loc[0, "ORIGIN"] = 123
    with pytest.raises(ArrivalFeatureContractViolation, match="ORIGIN"):
        prepare_arrival_features(invalid)
