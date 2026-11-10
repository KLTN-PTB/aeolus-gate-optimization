"""Comprehensive tests for Core Departure Contract, Registry, Leakage Guard & Feature Builder.

Protocol: Aeolus Dual Core Architecture Protocol V2
Phase: P2 Verification Suite
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.data.leakage_rules import (
    CORE_DEPARTURE_APPROVED_FEATURES,
    CORE_DEPARTURE_TASK,
    LeakageRuleViolation,
    assert_candidate_predictors_allowed,
    status_for,
)
from src.features.departure_features import (
    APPROVED_DEPARTURE_PREDICTOR_COLUMNS,
    DepartureFeatureContractViolation,
    DepartureTargetError,
    build_departure_labels,
    prepare_core_departure_features,
)
from src.models.interfaces import (
    ModelCategory,
    ModelSpec,
    ModelStatus,
    ModelTarget,
    ModelTask,
)
from src.models.registry import (
    assert_downstream_eligible,
    get_auxiliary_models,
    get_core_departure_models,
    get_core_point_models,
    get_model_spec,
    is_downstream_eligible,
    list_models,
    register_model,
    unregister_model,
)


# =============================================================================
# 1. ModelSpec & Interface Validation Tests
# =============================================================================

def test_core_departure_spec_rejects_arrival_target() -> None:
    """Core Departure specification must reject Arrival target labels."""
    with pytest.raises(ValueError, match="cannot use Arrival target"):
        ModelSpec(
            model_id="invalid_dep_model",
            family="linear",
            task=ModelTask.CORE_DEPARTURE.value,
            target=ModelTarget.ARRIVAL_DELAY_SIGNED.value,
            probabilistic=False,
            supports_predict=True,
            supports_predict_proba=False,
            supports_distribution=False,
            feature_set="departure_schedule_calendar_carrier_route_v1",
            preprocessing="standard_scaler",
            seed_policy="fixed_seed",
            hpo_policy="none",
            status=ModelStatus.RESEARCH_CANDIDATE.value,
            downstream_eligible=False,
        )


def test_core_departure_spec_rejects_weather_features() -> None:
    """Core Departure specification must reject weather in feature_set."""
    with pytest.raises(ValueError, match="cannot contain weather"):
        ModelSpec(
            model_id="invalid_dep_weather_model",
            family="linear",
            task=ModelTask.CORE_DEPARTURE.value,
            target=ModelTarget.DEPARTURE_DELAY_SIGNED.value,
            probabilistic=False,
            supports_predict=True,
            supports_predict_proba=False,
            supports_distribution=False,
            feature_set="departure_schedule_with_weather_v1",
            preprocessing="standard_scaler",
            seed_policy="fixed_seed",
            hpo_policy="none",
            status=ModelStatus.RESEARCH_CANDIDATE.value,
            downstream_eligible=False,
        )


def test_core_departure_spec_requires_certified_role_for_downstream() -> None:
    """Core Departure model cannot be downstream_eligible without GATE_OUT_PREDICTION role."""
    with pytest.raises(ValueError, match="requires certified role 'GATE_OUT_PREDICTION'"):
        ModelSpec(
            model_id="invalid_dep_downstream_model",
            family="linear",
            task=ModelTask.CORE_DEPARTURE.value,
            target=ModelTarget.DEPARTURE_DELAY_SIGNED.value,
            probabilistic=False,
            supports_predict=True,
            supports_predict_proba=False,
            supports_distribution=False,
            feature_set="departure_schedule_calendar_carrier_route_v1",
            preprocessing="standard_scaler",
            seed_policy="fixed_seed",
            hpo_policy="none",
            status=ModelStatus.CURRENT_CORE.value,
            downstream_eligible=True,
            selection_role="heuristic_role",
        )


# =============================================================================
# 2. Registry Consistency & Downstream Isolation Tests
# =============================================================================

def test_registry_distinguishes_arrival_auxiliary_and_core_departure() -> None:
    """Registry correctly separates Core Arrival, Auxiliary Departure, and Core Departure."""
    arrival_models = list_models(task=ModelTask.CORE_ARRIVAL)
    auxiliary_models = list_models(task=ModelTask.AUXILIARY_DEPARTURE)
    core_departure_models = list_models(task=ModelTask.CORE_DEPARTURE)

    assert len(arrival_models) > 0
    assert len(auxiliary_models) >= 1
    assert len(core_departure_models) >= 1

    arrival_ids = {m.model_id for m in arrival_models}
    aux_ids = {m.model_id for m in auxiliary_models}
    dep_ids = {m.model_id for m in core_departure_models}

    # Strict pairwise disjointness
    assert arrival_ids.isdisjoint(aux_ids)
    assert arrival_ids.isdisjoint(dep_ids)
    assert aux_ids.isdisjoint(dep_ids)


def test_core_point_cap_is_strictly_5_unaffected_by_departure() -> None:
    """Core Point arrival models remain strictly capped at 5 canonical families."""
    core_point_models = get_core_point_models()
    assert len(core_point_models) == 5
    for model in core_point_models:
        assert model.task == ModelTask.CORE_ARRIVAL.value
        assert model.category == ModelCategory.CORE_POINT.value


def test_registered_departure_linear_baseline_invariants() -> None:
    """departure_linear_baseline_v1 is correctly registered and non-downstream in P2."""
    spec = get_model_spec("departure_linear_baseline_v1")
    assert spec.family == "linear"
    assert spec.task == ModelTask.CORE_DEPARTURE.value
    assert spec.target == ModelTarget.DEPARTURE_DELAY_SIGNED.value
    assert spec.category == ModelCategory.CORE_DEPARTURE.value
    assert spec.downstream_eligible is False
    assert is_downstream_eligible("departure_linear_baseline_v1") is False


def test_auxiliary_departure_remains_strictly_blocked_from_downstream() -> None:
    """Auxiliary departure models must never be downstream eligible."""
    for model in get_auxiliary_models():
        assert model.downstream_eligible is False
        assert is_downstream_eligible(model.model_id) is False
        with pytest.raises(ValueError, match="NOT downstream eligible"):
            assert_downstream_eligible(model.model_id)


def test_core_departure_downstream_gatekeeping_logic() -> None:
    """Test dynamic downstream verification for certified vs uncertified departure models."""
    test_model_id = "test_departure_certified_v1"
    try:
        # Certified model with role GATE_OUT_PREDICTION and downstream_eligible=True
        certified_spec = ModelSpec(
            model_id=test_model_id,
            family="linear",
            task=ModelTask.CORE_DEPARTURE.value,
            target=ModelTarget.DEPARTURE_DELAY_SIGNED.value,
            probabilistic=False,
            supports_predict=True,
            supports_predict_proba=False,
            supports_distribution=False,
            feature_set="departure_schedule_calendar_carrier_route_v1",
            preprocessing="standard_scaler",
            seed_policy="fixed_seed",
            hpo_policy="none",
            status=ModelStatus.CURRENT_CORE.value,
            downstream_eligible=True,
            selection_role="GATE_OUT_PREDICTION",
        )
        register_model(certified_spec)
        assert is_downstream_eligible(test_model_id) is True
    finally:
        unregister_model(test_model_id)


# =============================================================================
# 3. Leakage Guard Tests for Core Departure
# =============================================================================

@pytest.mark.parametrize("col", ["ARR_DELAY", "y_arr_reg", "y_arr_cls"])
def test_core_departure_rejects_arrival_target_leakage(col: str) -> None:
    """Core Departure must reject Arrival targets as LEAKAGE."""
    assert status_for(col, task=CORE_DEPARTURE_TASK) == "LEAKAGE"
    with pytest.raises(LeakageRuleViolation, match="forbidden"):
        assert_candidate_predictors_allowed([col], task=CORE_DEPARTURE_TASK)


@pytest.mark.parametrize("col", ["DEP_DELAY", "y_dep_reg", "y_dep_cls"])
def test_core_departure_rejects_departure_target_as_predictors(col: str) -> None:
    """Core Departure must reject its own targets/labels from predictor matrix X."""
    assert status_for(col, task=CORE_DEPARTURE_TASK) == "TARGET"
    with pytest.raises(LeakageRuleViolation, match="forbidden"):
        assert_candidate_predictors_allowed([col], task=CORE_DEPARTURE_TASK)


@pytest.mark.parametrize(
    "col",
    [
        "DEP_TIME",
        "ARR_TIME",
        "WHEELS_OFF",
        "WHEELS_ON",
        "TAXI_OUT",
        "TAXI_IN",
        "AIR_TIME",
        "ACTUAL_ELAPSED_TIME",
    ],
)
def test_core_departure_rejects_realized_operations(col: str) -> None:
    """Core Departure must reject future realized operational fields."""
    assert status_for(col, task=CORE_DEPARTURE_TASK) == "LEAKAGE"
    with pytest.raises(LeakageRuleViolation, match="forbidden"):
        assert_candidate_predictors_allowed([col], task=CORE_DEPARTURE_TASK)


@pytest.mark.parametrize(
    "col",
    ["O_TEMP", "O_PRCP", "O_WSPD", "D_TEMP", "D_PRCP", "D_WSPD"],
)
def test_core_departure_rejects_raw_weather(col: str) -> None:
    """Core Departure must reject all raw weather columns."""
    assert status_for(col, task=CORE_DEPARTURE_TASK) == "INSUFFICIENT_EVIDENCE"
    with pytest.raises(LeakageRuleViolation, match="forbidden"):
        assert_candidate_predictors_allowed([col], task=CORE_DEPARTURE_TASK)


@pytest.mark.parametrize(
    "col",
    ["ORIGIN", "ORIGIN_INDEX", "O_LATITUDE", "O_LONGITUDE"],
)
def test_core_departure_rejects_origin_constants(col: str) -> None:
    """Core Departure must reject constant origin columns."""
    assert status_for(col, task=CORE_DEPARTURE_TASK) == "DROP_CONSTANT"
    with pytest.raises(LeakageRuleViolation, match="forbidden"):
        assert_candidate_predictors_allowed([col], task=CORE_DEPARTURE_TASK)


@pytest.mark.parametrize(
    "col",
    ["flight_key", "chain_id", "source_row_number", "source_year"],
)
def test_core_departure_rejects_identifiers(col: str) -> None:
    """Core Departure must reject trace and identifier columns."""
    assert status_for(col, task=CORE_DEPARTURE_TASK) == "IDENTIFIER_ONLY"
    with pytest.raises(LeakageRuleViolation, match="forbidden"):
        assert_candidate_predictors_allowed([col], task=CORE_DEPARTURE_TASK)


def test_core_departure_rejects_uncertain_and_simulation_columns() -> None:
    """Core Departure must reject FLIGHTS and simulation outcomes."""
    assert status_for("FLIGHTS", task=CORE_DEPARTURE_TASK) == "UNCERTAIN"
    with pytest.raises(LeakageRuleViolation, match="forbidden"):
        assert_candidate_predictors_allowed(["FLIGHTS"], task=CORE_DEPARTURE_TASK)

    for sim_col in ["p_delay", "actual_delay_min", "pred_time_min"]:
        assert status_for(sim_col, task=CORE_DEPARTURE_TASK) == "SIMULATION_LEAKAGE"
        with pytest.raises(LeakageRuleViolation, match="forbidden"):
            assert_candidate_predictors_allowed([sim_col], task=CORE_DEPARTURE_TASK)


def test_core_departure_fails_closed_on_unclassified_columns() -> None:
    """Core Departure must fail closed on unknown columns or calendar_year."""
    for unknown in ["calendar_year", "custom_feature", "unknown_col"]:
        with pytest.raises(LeakageRuleViolation, match="unclassified"):
            assert_candidate_predictors_allowed([unknown], task=CORE_DEPARTURE_TASK)


def test_core_departure_accepts_all_10_approved_features() -> None:
    """Core Departure allows exactly the 10 approved V1 features."""
    assert_candidate_predictors_allowed(
        CORE_DEPARTURE_APPROVED_FEATURES, task=CORE_DEPARTURE_TASK
    )


# =============================================================================
# 4. Feature Builder & Label Construction Tests
# =============================================================================

@pytest.fixture
def sample_outbound_frame() -> pd.DataFrame:
    """Fixture providing clean canonical-like outbound records."""
    return pd.DataFrame(
        {
            "flight_key": ["k1", "k2", "k3", "k4"],
            "source_year": [2024, 2024, 2024, 2024],
            "source_row_number": [1, 2, 3, 4],
            "FL_DATE": [
                "2024-03-15 00:00:00",
                "2024-03-16 00:00:00",
                "2024-03-17 00:00:00",
                "2024-03-18 00:00:00",
            ],
            "CRS_DEP_TIME": [
                "2024-03-15 08:30:00",
                "2024-03-16 14:15:00",
                "2024-03-17 19:45:00",
                "2024-03-18 22:00:00",
            ],
            "CRS_ELAPSED_TIME": [120.0, 95.0, 180.0, 60.0],
            "MONTH": [3, 3, 3, 3],
            "DAY_OF_MONTH": [15, 16, 17, 18],
            "DAY_OF_WEEK": [5, 6, 7, 1],
            "OP_CARRIER": ["DL", "DL", "UA", "AA"],
            "ORIGIN": ["ATL", "ATL", "ATL", "ATL"],
            "DEST": ["LGA", "MCO", "ORD", "DFW"],
            "OP_CARRIER_FL_NUM": [101, 202, 303, 404],
            "DEP_DELAY": [-8.0, 0.0, 14.0, 45.0],
        }
    )


def test_build_departure_labels_preserves_signed_continuous(sample_outbound_frame: pd.DataFrame) -> None:
    """build_departure_labels preserves negative values and constructs binary indicator."""
    labels, report = build_departure_labels(sample_outbound_frame)
    assert report.input_rows == 4
    assert report.eligible_rows == 4
    assert report.dropped_missing_target_rows == 0
    assert report.target_imputation_used is False

    # Negative continuous delay strictly preserved
    assert labels["y_dep_reg"].iloc[0] == -8.0
    assert labels["y_dep_reg"].iloc[1] == 0.0
    assert labels["y_dep_reg"].iloc[2] == 14.0
    assert labels["y_dep_reg"].iloc[3] == 45.0

    # 1[DEP_DELAY >= 15]
    assert labels["y_dep_cls"].tolist() == [0, 0, 0, 1]


def test_build_departure_labels_drops_missing_targets() -> None:
    """build_departure_labels drops missing DEP_DELAY without imputation."""
    frame = pd.DataFrame(
        {
            "DEP_DELAY": [-5.0, None, 20.0],
        }
    )
    labels, report = build_departure_labels(frame)
    assert report.input_rows == 3
    assert report.eligible_rows == 2
    assert report.dropped_missing_target_rows == 1
    assert len(labels) == 2
    assert labels["y_dep_reg"].tolist() == [-5.0, 20.0]
    assert labels["y_dep_cls"].tolist() == [0, 1]


def test_prepare_core_departure_features_end_to_end(sample_outbound_frame: pd.DataFrame) -> None:
    """prepare_core_departure_features builds exact 10 approved features with cutoffs and report."""
    prepared = prepare_core_departure_features(sample_outbound_frame)

    # 1. Exact 10 approved columns
    assert list(prepared.X.columns) == list(APPROVED_DEPARTURE_PREDICTOR_COLUMNS)
    assert len(prepared.X.columns) == 10

    # 2. X excludes ORIGIN, weather, chain, calendar_year, targets
    assert "ORIGIN" not in prepared.X.columns
    assert "calendar_year" not in prepared.X.columns
    assert "DEP_DELAY" not in prepared.X.columns
    assert "ARR_DELAY" not in prepared.X.columns
    assert "O_TEMP" not in prepared.X.columns
    assert "chain_id" not in prepared.X.columns

    # 3. Derived feature correctness
    assert prepared.X["calendar_month"].tolist() == [3, 3, 3, 3]
    assert prepared.X["calendar_day_of_month"].tolist() == [15, 16, 17, 18]
    assert prepared.X["calendar_day_of_week"].tolist() == [5, 6, 7, 1]
    assert prepared.X["is_weekend"].tolist() == [0, 1, 1, 0]
    assert prepared.X["scheduled_departure_hour"].tolist() == [8, 14, 19, 22]
    assert prepared.X["scheduled_departure_minute"].tolist() == [30, 15, 45, 0]
    assert prepared.X["DEST"].tolist() == ["LGA", "MCO", "ORD", "DFW"]
    assert prepared.X["OP_CARRIER"].tolist() == ["DL", "DL", "UA", "AA"]
    assert prepared.X["OP_CARRIER_FL_NUM"].tolist() == ["101", "202", "303", "404"]

    # 4. Target preservation
    assert prepared.y_dep_reg.tolist() == [-8.0, 0.0, 14.0, 45.0]
    assert prepared.y_dep_cls.tolist() == [0, 0, 0, 1]

    # 5. Prediction Cutoff: CRS_DEP_TIME - 2 hours
    expected_cutoffs = [
        pd.Timestamp("2024-03-15 06:30:00"),
        pd.Timestamp("2024-03-16 12:15:00"),
        pd.Timestamp("2024-03-17 17:45:00"),
        pd.Timestamp("2024-03-18 20:00:00"),
    ]
    assert prepared.prediction_cutoff.tolist() == expected_cutoffs

    # 6. Identifiers
    assert list(prepared.identifiers.columns) == ["flight_key", "source_year", "source_row_number"]

    # 7. Eligibility report
    assert prepared.eligibility.input_rows == 4
    assert prepared.eligibility.outbound_rows == 4
    assert prepared.eligibility.eligible_rows == 4
    assert prepared.eligibility.dropped_non_outbound_rows == 0
    assert prepared.eligibility.dropped_missing_target_rows == 0


def test_prepare_core_departure_features_filters_non_atl_origin(sample_outbound_frame: pd.DataFrame) -> None:
    """Non-ATL origin flights are filtered from outbound population and counted in report."""
    frame_with_non_atl = sample_outbound_frame.copy()
    frame_with_non_atl.loc[0, "ORIGIN"] = "JFK"  # Row 0 not outbound ATL

    prepared = prepare_core_departure_features(frame_with_non_atl)
    assert prepared.eligibility.input_rows == 4
    assert prepared.eligibility.outbound_rows == 3
    assert prepared.eligibility.eligible_rows == 3
    assert prepared.eligibility.dropped_non_outbound_rows == 1
    assert len(prepared.X) == 3
    assert prepared.y_dep_reg.tolist() == [0.0, 14.0, 45.0]
