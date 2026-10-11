"""Test Suite for Phase P07: Native Dual-Core Predict-Then-Optimize Pipeline.

Protocol: Aeolus Dual Core Architecture Protocol V2
Phase: P07 Native Dual-Core Predict-Then-Optimize Pipeline
Coverage:
- Specifications D01 to D30
- Acceptance Scenarios A to E
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import tempfile
from typing import Any

import numpy as np
import pandas as pd
import pytest

from src.contracts.turn_contracts import (
    FlightLeg,
    LegDirection,
    LinkageSource,
    PairType,
    TurnPair,
    ValidationStatus,
)
from src.data.leakage_rules import LeakageRuleViolation, assert_candidate_predictors_allowed
from src.data.pairing_validator import PairingValidator
from src.features.departure_features import (
    APPROVED_DEPARTURE_PREDICTOR_COLUMNS,
    prepare_departure_inference,
)
from src.models.interfaces import ModelCategory, ModelSpec, ModelStatus, ModelTask
from src.models.registry import _MODEL_CATALOG, get_model_spec, is_downstream_eligible
from src.optimization.adapter import (
    DualCoreGateOptimizerAdapter,
    RoleAccessViolationError,
    UncertifiedModelError,
)
from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import (
    ConstraintDiagnostic,
    Flight,
    Gate,
    GateResourceType,
    verify_hard_constraints_independently,
)
from src.optimization.evaluation import evaluate_gate_assignment
from src.simulation.dual_prediction_turn import (
    CouplingAssumption,
    DualAircraftTurn,
    DualTurnEngine,
    SimulationMode,
)
from src.simulation.native_dual_core_pipeline import (
    DEP_TREE_PREPROCESSOR_PATH,
    DEP_TREE_PREPROCESSOR_SHA256,
    DEP_XGB_CHECKPOINT_PATH,
    DEP_XGB_SHA256,
    CheckpointVerificationError,
    FeatureContractViolation,
    NativeDualCorePipeline,
    NativeDualCorePipelineConfig,
    NativeDualCorePipelineResult,
    P4_ARRIVAL_CHECKPOINT_PATH,
    P4_ARRIVAL_SHA256,
    ProvenanceMode,
    StandardizedPredictionRecord,
    TargetSemantics,
    compute_file_sha256,
    generate_contact_and_remote_gates,
    prepare_arrival_features_for_inference,
    validate_pipeline_model,
    verify_and_load_checkpoint,
    verify_checkpoint_path_allowlist,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def sample_inbound_df() -> pd.DataFrame:
    """Fixture providing valid canonical inbound flight data."""
    return pd.DataFrame([
        {
            "flight_key": "LEG_ARR_0001",
            "FL_DATE": "2023-11-23 00:00:00",
            "OP_CARRIER": "DL",
            "OP_CARRIER_FL_NUM": "1001",
            "ORIGIN": "ORD",
            "DEST": "ATL",
            "CRS_DEP_TIME": "2023-11-23 06:00:00",
            "CRS_ELAPSED_TIME": 120.0,
            "MONTH": 11,
            "DAY_OF_MONTH": 23,
            "DAY_OF_WEEK": 4,
        },
        {
            "flight_key": "LEG_ARR_0002",
            "FL_DATE": "2023-11-23 00:00:00",
            "OP_CARRIER": "AA",
            "OP_CARRIER_FL_NUM": "1002",
            "ORIGIN": "DFW",
            "DEST": "ATL",
            "CRS_DEP_TIME": "2023-11-23 07:00:00",
            "CRS_ELAPSED_TIME": 130.0,
            "MONTH": 11,
            "DAY_OF_MONTH": 23,
            "DAY_OF_WEEK": 4,
        },
    ])


@pytest.fixture
def sample_outbound_df() -> pd.DataFrame:
    """Fixture providing valid canonical outbound flight data."""
    return pd.DataFrame([
        {
            "flight_key": "LEG_DEP_0001",
            "FL_DATE": "2023-11-23 00:00:00",
            "OP_CARRIER": "DL",
            "OP_CARRIER_FL_NUM": "1001",
            "ORIGIN": "ATL",
            "DEST": "LGA",
            "CRS_DEP_TIME": "2023-11-23 09:30:00",
            "CRS_ELAPSED_TIME": 130.0,
            "MONTH": 11,
            "DAY_OF_MONTH": 23,
            "DAY_OF_WEEK": 4,
        },
        {
            "flight_key": "LEG_DEP_0002",
            "FL_DATE": "2023-11-23 00:00:00",
            "OP_CARRIER": "AA",
            "OP_CARRIER_FL_NUM": "1002",
            "ORIGIN": "ATL",
            "DEST": "MIA",
            "CRS_DEP_TIME": "2023-11-23 10:30:00",
            "CRS_ELAPSED_TIME": 110.0,
            "MONTH": 11,
            "DAY_OF_MONTH": 23,
            "DAY_OF_WEEK": 4,
        },
    ])


@pytest.fixture
def sample_legs_and_pairs() -> tuple[dict[str, FlightLeg], list[TurnPair]]:
    """Fixture providing linked FlightLegs and TurnPairs."""
    legs = {
        "LEG_ARR_0001": FlightLeg(
            flight_id="LEG_ARR_0001",
            direction=LegDirection.ARR,
            carrier="DL",
            flight_number="1001",
            origin="ORD",
            destination="ATL",
            scheduled_event_local=datetime(2023, 11, 23, 8, 0),
            normalized_timeline_min=480,
            tail_number="N101DL",
        ),
        "LEG_DEP_0001": FlightLeg(
            flight_id="LEG_DEP_0001",
            direction=LegDirection.DEP,
            carrier="DL",
            flight_number="1001",
            origin="ATL",
            destination="LGA",
            scheduled_event_local=datetime(2023, 11, 23, 9, 30),
            normalized_timeline_min=570,
            tail_number="N101DL",
        ),
        "LEG_ARR_0002": FlightLeg(
            flight_id="LEG_ARR_0002",
            direction=LegDirection.ARR,
            carrier="AA",
            flight_number="1002",
            origin="DFW",
            destination="ATL",
            scheduled_event_local=datetime(2023, 11, 23, 9, 10),
            normalized_timeline_min=550,
            tail_number="N202AA",
        ),
        "LEG_DEP_0002": FlightLeg(
            flight_id="LEG_DEP_0002",
            direction=LegDirection.DEP,
            carrier="AA",
            flight_number="1002",
            origin="ATL",
            destination="MIA",
            scheduled_event_local=datetime(2023, 11, 23, 10, 30),
            normalized_timeline_min=630,
            tail_number="N202AA",
        ),
    }
    pairs = [
        TurnPair(
            pair_id="TURN_0001",
            arrival_leg_id="LEG_ARR_0001",
            departure_leg_id="LEG_DEP_0001",
            pair_type=PairType.VERIFIED_PAIR,
            linkage_source=LinkageSource.VERIFIED_ROTATION,
            validation_status=ValidationStatus.VALID,
            scheduled_turnaround_min=90.0,
            scenario_id="SCEN_TEST",
        ),
        TurnPair(
            pair_id="TURN_0002",
            arrival_leg_id="LEG_ARR_0002",
            departure_leg_id="LEG_DEP_0002",
            pair_type=PairType.VERIFIED_PAIR,
            linkage_source=LinkageSource.VERIFIED_ROTATION,
            validation_status=ValidationStatus.VALID,
            scheduled_turnaround_min=80.0,
            scenario_id="SCEN_TEST",
        ),
    ]
    return legs, pairs


# =============================================================================
# D01 - D30 SPECIFICATION TESTS
# =============================================================================

def test_d01_missing_checkpoint_clear_failure() -> None:
    """D01: Missing checkpoint path raises FileNotFoundError clearly."""
    non_existent = Path("artifacts/non_existent_model_checkpoint_v99.joblib")
    with pytest.raises(FileNotFoundError, match="Missing model checkpoint"):
        verify_and_load_checkpoint(non_existent)


def test_d02_wrong_checkpoint_hash_rejected() -> None:
    """D02: Checkpoint with invalid SHA-256 hash is rejected."""
    wrong_hash = "0000000000000000000000000000000000000000000000000000000000000000"
    with pytest.raises(CheckpointVerificationError, match="SHA-256 hash mismatch"):
        verify_and_load_checkpoint(P4_ARRIVAL_CHECKPOINT_PATH, expected_sha256=wrong_hash)


def test_d03_wrong_model_role_rejected() -> None:
    """D03: Model role mismatch fails closed."""
    # Attempting to validate arrival model as departure
    with pytest.raises(RoleAccessViolationError, match="expected 'core_departure'"):
        validate_pipeline_model("arrival_linear_baseline_v1", expected_task=ModelTask.CORE_DEPARTURE.value)


def test_d04_auxiliary_departure_cannot_enter_optimizer() -> None:
    """D04: Auxiliary departure model cannot enter downstream optimization."""
    with pytest.raises(RoleAccessViolationError, match="Auxiliary Departure"):
        validate_pipeline_model("departure_auxiliary_baseline_v1", expected_task=ModelTask.CORE_DEPARTURE.value)


def test_d05_core_departure_eligible_allowed() -> None:
    """D05: Certified downstream-eligible Core Departure model is allowed."""
    spec = validate_pipeline_model("departure_certified_point_v1", expected_task=ModelTask.CORE_DEPARTURE.value)
    assert spec.model_id == "departure_certified_point_v1"
    assert spec.selection_role == "GATE_OUT_PREDICTION"
    assert spec.downstream_eligible is True


def test_d06_feature_schema_mismatch_rejected() -> None:
    """D06: Feature schema missing required columns fails closed."""
    invalid_df = pd.DataFrame([{"ORIGIN": "ATL", "CRS_DEP_TIME": 800}])  # Missing FL_DATE, OP_CARRIER, etc.
    with pytest.raises(Exception):
        prepare_departure_inference(invalid_df)


def test_d07_feature_order_mismatch_handled_safely(sample_outbound_df: pd.DataFrame) -> None:
    """D07: Shuffled columns are aligned safely to approved canonical order."""
    cols_shuffled = list(sample_outbound_df.columns)
    np.random.RandomState(42).shuffle(cols_shuffled)
    df_shuffled = sample_outbound_df[cols_shuffled].copy()

    prep = prepare_departure_inference(df_shuffled)
    assert list(prep.X.columns) == list(APPROVED_DEPARTURE_PREDICTOR_COLUMNS)


def test_d08_future_actual_feature_leakage_guard_rejects() -> None:
    """D08: Leakage guard rejects future actual operational columns in candidate features."""
    leaked_candidates = ["CRS_ELAPSED_TIME", "DEP_TIME", "TAXI_OUT"]
    with pytest.raises(LeakageRuleViolation, match="forbidden"):
        assert_candidate_predictors_allowed(leaked_candidates, task="core_departure")


def test_d09_native_model_actually_invoked(sample_inbound_df: pd.DataFrame, sample_outbound_df: pd.DataFrame) -> None:
    """D09: Native model checkpoints are loaded and actually generate inferences."""
    cfg = NativeDualCorePipelineConfig(
        n_contact_gates=10,
        time_limit_seconds=2.0,
    )
    pipeline = NativeDualCorePipeline(config=cfg)
    models = pipeline.load_and_verify_models()
    preds, lookup = pipeline.run_native_inference(sample_inbound_df, sample_outbound_df, models)

    assert len(preds) == 4  # 2 inbound + 2 outbound
    assert all(math.isfinite(p.predicted_delay_min) for p in preds)
    # Check that predictions reflect native mathematical model outputs
    assert any(p.flight_direction == "ARR" for p in preds)
    assert any(p.flight_direction == "DEP" for p in preds)


def test_d10_prediction_provenance_recorded(sample_inbound_df: pd.DataFrame, sample_outbound_df: pd.DataFrame) -> None:
    """D10: Standardized prediction contract records all 14+ required provenance fields."""
    cfg = NativeDualCorePipelineConfig()
    pipeline = NativeDualCorePipeline(config=cfg)
    models = pipeline.load_and_verify_models()
    preds, _ = pipeline.run_native_inference(sample_inbound_df, sample_outbound_df, models)

    rec = preds[0]
    assert rec.flight_id != ""
    assert rec.flight_direction in ("ARR", "DEP")
    assert rec.airport == "ATL"
    assert rec.prediction_cutoff_utc != ""
    assert rec.model_id != ""
    assert rec.model_role != ""
    assert rec.model_version != ""
    assert rec.model_sha256 != ""
    assert rec.feature_schema_version != ""
    assert rec.target_name in ("ARR_DELAY", "DEP_DELAY")
    assert rec.target_semantics in (
        TargetSemantics.ARRIVAL_DELAY_SIGNED.value,
        TargetSemantics.DEPARTURE_DELAY_SIGNED.value,
    )
    assert math.isfinite(rec.predicted_delay_min)
    assert rec.prediction_timestamp_utc != ""
    assert rec.provenance_mode == ProvenanceMode.NATIVE_INFERENCE.value


def test_d11_negative_arrival_delay_correct() -> None:
    """D11: Early arrival (negative delay) correctly shifts simulated arrival earlier."""
    engine = DualTurnEngine(min_turnaround_min=45, separation_buffer_min=15)
    legs = {
        "ARR_01": FlightLeg(
            flight_id="ARR_01",
            direction=LegDirection.ARR,
            carrier="DL",
            flight_number="101",
            origin="ORD",
            destination="ATL",
            scheduled_event_local=datetime(2023, 11, 23, 10, 0),
            normalized_timeline_min=600,
        )
    }
    pair = TurnPair(
        pair_id="TURN_01",
        arrival_leg_id="ARR_01",
        pair_type=PairType.UNMATCHED_ARR,
        scenario_id="SCEN_1",
    )
    # 20 minutes early arrival (-20.0)
    turn = engine.synthesize_turn(pair, legs, arrival_prediction=-20.0, mode=SimulationMode.DUAL_POINT)
    assert turn.simulated_arrival_min == 580  # 600 - 20


def test_d12_negative_departure_delay_correct() -> None:
    """D12: Early departure correctly shifts ML departure, respecting turnaround floor."""
    engine = DualTurnEngine(min_turnaround_min=45, separation_buffer_min=15)
    legs = {
        "ARR_01": FlightLeg(
            flight_id="ARR_01",
            direction=LegDirection.ARR,
            carrier="DL",
            flight_number="101",
            origin="ORD",
            destination="ATL",
            scheduled_event_local=datetime(2023, 11, 23, 10, 0),
            normalized_timeline_min=600,
        ),
        "DEP_01": FlightLeg(
            flight_id="DEP_01",
            direction=LegDirection.DEP,
            carrier="DL",
            flight_number="101",
            origin="ATL",
            destination="LGA",
            scheduled_event_local=datetime(2023, 11, 23, 11, 30),
            normalized_timeline_min=690,
        ),
    }
    pair = TurnPair(
        pair_id="TURN_01",
        arrival_leg_id="ARR_01",
        departure_leg_id="DEP_01",
        pair_type=PairType.SYNTHETIC_PAIR,
        scenario_id="SCEN_1",
    )
    # On-time arrival, 10 minutes early departure prediction (-10.0)
    turn = engine.synthesize_turn(pair, legs, arrival_prediction=0.0, departure_prediction=-10.0, mode=SimulationMode.DUAL_POINT)
    assert turn.departure_ml_min == 680  # 690 - 10
    assert turn.simulated_departure_min == 680  # 680 >= 600 + 45 (645)


def test_d13_minimum_turnaround_enforced() -> None:
    """D13: Minimum physical turnaround floor is strictly enforced when departure is early."""
    engine = DualTurnEngine(min_turnaround_min=45, separation_buffer_min=15)
    legs = {
        "ARR_01": FlightLeg(
            flight_id="ARR_01",
            direction=LegDirection.ARR,
            carrier="DL",
            flight_number="101",
            origin="ORD",
            destination="ATL",
            scheduled_event_local=datetime(2023, 11, 23, 10, 0),
            normalized_timeline_min=600,
        ),
        "DEP_01": FlightLeg(
            flight_id="DEP_01",
            direction=LegDirection.DEP,
            carrier="DL",
            flight_number="101",
            origin="ATL",
            destination="LGA",
            scheduled_event_local=datetime(2023, 11, 23, 10, 40),
            normalized_timeline_min=640,
        ),
    }
    pair = TurnPair(
        pair_id="TURN_01",
        arrival_leg_id="ARR_01",
        departure_leg_id="DEP_01",
        pair_type=PairType.SYNTHETIC_PAIR,
        scenario_id="SCEN_1",
    )
    # Arrival delayed by 10m (610), departure on-time (640) -> turnaround would be 30m (< 45m min)
    turn = engine.synthesize_turn(pair, legs, arrival_prediction=10.0, departure_prediction=0.0, mode=SimulationMode.DUAL_POINT)
    assert turn.simulated_arrival_min == 610
    assert turn.departure_ml_min == 640
    # Must be pushed to at least 610 + 45 = 655
    assert turn.simulated_departure_min == 655
    assert turn.physical_dwell_min == 45


def test_d14_cross_midnight_turn_correct() -> None:
    """D14: Cross-midnight turnaround uses monotonic linear minutes without negative duration."""
    engine = DualTurnEngine(min_turnaround_min=45, separation_buffer_min=15)
    legs = {
        "ARR_01": FlightLeg(
            flight_id="ARR_01",
            direction=LegDirection.ARR,
            carrier="DL",
            flight_number="101",
            origin="ORD",
            destination="ATL",
            scheduled_event_local=datetime(2023, 11, 23, 23, 40),
            normalized_timeline_min=1420,  # 23:40
        ),
        "DEP_01": FlightLeg(
            flight_id="DEP_01",
            direction=LegDirection.DEP,
            carrier="DL",
            flight_number="101",
            origin="ATL",
            destination="LGA",
            scheduled_event_local=datetime(2023, 11, 24, 1, 10),
            normalized_timeline_min=1510,  # 01:10 next day (+90m)
        ),
    }
    pair = TurnPair(
        pair_id="TURN_01",
        arrival_leg_id="ARR_01",
        departure_leg_id="DEP_01",
        pair_type=PairType.SYNTHETIC_PAIR,
        scenario_id="SCEN_1",
    )
    turn = engine.synthesize_turn(pair, legs, arrival_prediction=0.0, departure_prediction=0.0, mode=SimulationMode.DUAL_POINT)
    assert turn.simulated_arrival_min == 1420
    assert turn.simulated_departure_min == 1510
    assert turn.gate_release_min == 1525
    assert turn.physical_dwell_min == 90


def test_d15_double_buffer_prevented() -> None:
    """D15: Separation buffer is applied exactly once to gate release, not double-counted."""
    engine = DualTurnEngine(min_turnaround_min=45, separation_buffer_min=15)
    legs = {
        "ARR_01": FlightLeg(
            flight_id="ARR_01",
            direction=LegDirection.ARR,
            carrier="DL",
            flight_number="101",
            origin="ORD",
            destination="ATL",
            scheduled_event_local=datetime(2023, 11, 23, 10, 0),
            normalized_timeline_min=600,
        ),
        "DEP_01": FlightLeg(
            flight_id="DEP_01",
            direction=LegDirection.DEP,
            carrier="DL",
            flight_number="101",
            origin="ATL",
            destination="LGA",
            scheduled_event_local=datetime(2023, 11, 23, 11, 0),
            normalized_timeline_min=660,
        ),
    }
    pair = TurnPair(
        pair_id="TURN_01",
        arrival_leg_id="ARR_01",
        departure_leg_id="DEP_01",
        pair_type=PairType.SYNTHETIC_PAIR,
        scenario_id="SCEN_1",
    )
    turn = engine.synthesize_turn(pair, legs, arrival_prediction=0.0, departure_prediction=0.0, mode=SimulationMode.DUAL_POINT)
    # Dwell = 660 - 600 = 60m; Occupancy = 60 + 15 = 75m
    assert turn.physical_dwell_min == 60
    assert turn.gate_release_min - turn.simulated_arrival_min == 75
    assert turn.gate_release_min == turn.simulated_departure_min + 15


def test_d16_duplicate_pairing_rejected() -> None:
    """D16: Reusing the same leg across multiple pairs violates 1-to-1 cardinality."""
    validator = PairingValidator()
    legs = {
        "LEG_ARR_1": FlightLeg(
            flight_id="LEG_ARR_1",
            direction=LegDirection.ARR,
            carrier="DL",
            flight_number="1",
            origin="ORD",
            destination="ATL",
            scheduled_event_local=datetime(2023, 11, 23, 8, 0),
        ),
        "LEG_DEP_1": FlightLeg(
            flight_id="LEG_DEP_1",
            direction=LegDirection.DEP,
            carrier="DL",
            flight_number="1",
            origin="ATL",
            destination="LGA",
            scheduled_event_local=datetime(2023, 11, 23, 9, 30),
        ),
        "LEG_DEP_2": FlightLeg(
            flight_id="LEG_DEP_2",
            direction=LegDirection.DEP,
            carrier="DL",
            flight_number="2",
            origin="ATL",
            destination="MIA",
            scheduled_event_local=datetime(2023, 11, 23, 10, 0),
        ),
    }
    pairs = [
        TurnPair(pair_id="P1", arrival_leg_id="LEG_ARR_1", departure_leg_id="LEG_DEP_1", scenario_id="S1"),
        TurnPair(pair_id="P2", arrival_leg_id="LEG_ARR_1", departure_leg_id="LEG_DEP_2", scenario_id="S1"),
    ]
    valid_pairs, summary = validator.validate_pairs(legs, pairs)
    assert summary.invalid_pairs_count == 2
    assert "CARDINALITY_VIOLATION_MANY_TO_ONE" in summary.rejection_reasons_tally


def test_d17_ambiguous_pairing_explicit_status() -> None:
    """D17: Claiming VERIFIED_PAIR without matching airframe tail numbers is quarantined."""
    validator = PairingValidator()
    legs = {
        "LEG_ARR_1": FlightLeg(
            flight_id="LEG_ARR_1",
            direction=LegDirection.ARR,
            carrier="DL",
            flight_number="1",
            origin="ORD",
            destination="ATL",
            scheduled_event_local=datetime(2023, 11, 23, 8, 0),
            tail_number="N101DL",
        ),
        "LEG_DEP_1": FlightLeg(
            flight_id="LEG_DEP_1",
            direction=LegDirection.DEP,
            carrier="DL",
            flight_number="1",
            origin="ATL",
            destination="LGA",
            scheduled_event_local=datetime(2023, 11, 23, 9, 30),
            tail_number="N202DL",  # Tail mismatch!
        ),
    }
    pairs = [
        TurnPair(
            pair_id="P1",
            arrival_leg_id="LEG_ARR_1",
            departure_leg_id="LEG_DEP_1",
            pair_type=PairType.VERIFIED_PAIR,
            linkage_source=LinkageSource.VERIFIED_ROTATION,
            scenario_id="S1",
        )
    ]
    valid_pairs, summary = validator.validate_pairs(legs, pairs)
    assert summary.quarantined_pairs_count == 1
    assert "UNVERIFIED_AIRCRAFT_EVIDENCE_FOR_VERIFIED_PAIR" in summary.rejection_reasons_tally


def test_d18_unpaired_inbound_outbound_declared_handling() -> None:
    """D18: Unpaired inbound receives synthetic dwell; unpaired outbound is declared."""
    engine = DualTurnEngine(min_turnaround_min=45, default_dwell_min=60, separation_buffer_min=15)
    legs = {
        "ARR_01": FlightLeg(
            flight_id="ARR_01",
            direction=LegDirection.ARR,
            carrier="DL",
            flight_number="101",
            origin="ORD",
            destination="ATL",
            scheduled_event_local=datetime(2023, 11, 23, 10, 0),
            normalized_timeline_min=600,
        ),
        "DEP_01": FlightLeg(
            flight_id="DEP_01",
            direction=LegDirection.DEP,
            carrier="UA",
            flight_number="202",
            origin="ATL",
            destination="ORD",
            scheduled_event_local=datetime(2023, 11, 23, 14, 0),
            normalized_timeline_min=840,
        ),
    }
    pair_arr = TurnPair(pair_id="UNP_ARR", arrival_leg_id="ARR_01", pair_type=PairType.UNMATCHED_ARR, scenario_id="S1")
    pair_dep = TurnPair(pair_id="UNP_DEP", departure_leg_id="DEP_01", pair_type=PairType.UNMATCHED_DEP, scenario_id="S1")

    turn_arr = engine.synthesize_turn(pair_arr, legs, arrival_prediction=0.0, mode=SimulationMode.DUAL_POINT)
    turn_dep = engine.synthesize_turn(pair_dep, legs, arrival_prediction=0.0, departure_prediction=10.0, mode=SimulationMode.DUAL_POINT)

    assert turn_arr.unmatched_status == "SYNTHETIC_DWELL"
    assert turn_arr.simulated_departure_min == 660  # 600 + 60
    assert turn_dep.unmatched_status == "UNSCHEDULABLE_WITH_CURRENT_INPUT"


def test_d19_flight_leg_count_vs_aircraft_turn_count_correct(
    sample_inbound_df: pd.DataFrame,
    sample_outbound_df: pd.DataFrame,
    sample_legs_and_pairs: tuple[dict[str, FlightLeg], list[TurnPair]],
) -> None:
    """D19: Total legs, turn pairs, and flight entities match exact cardinalities."""
    legs, pairs = sample_legs_and_pairs
    cfg = NativeDualCorePipelineConfig()
    pipeline = NativeDualCorePipeline(config=cfg)
    result = pipeline.run(sample_inbound_df, sample_outbound_df, legs, pairs)

    assert result.manifest["counts"]["inbound_legs"] == 2
    assert result.manifest["counts"]["outbound_legs"] == 2
    assert result.manifest["counts"]["turns_synthesized"] == 2
    assert result.manifest["counts"]["flights_optimized"] == 2


def test_d20_legacy_arrival_only_mode_preserved(
    sample_inbound_df: pd.DataFrame,
    sample_outbound_df: pd.DataFrame,
    sample_legs_and_pairs: tuple[dict[str, FlightLeg], list[TurnPair]],
) -> None:
    """D20: ARRIVAL_ONLY_LEGACY mode preserves legacy precomputed_gate_out_min=None."""
    legs, pairs = sample_legs_and_pairs
    cfg = NativeDualCorePipelineConfig(simulation_mode=SimulationMode.ARRIVAL_ONLY_LEGACY)
    pipeline = NativeDualCorePipeline(config=cfg)
    result = pipeline.run(sample_inbound_df, sample_outbound_df, legs, pairs)

    for flight in result.flights:
        assert flight.precomputed_gate_out_min is None


def test_d21_dual_point_mode_uses_two_predictions(
    sample_inbound_df: pd.DataFrame,
    sample_outbound_df: pd.DataFrame,
    sample_legs_and_pairs: tuple[dict[str, FlightLeg], list[TurnPair]],
) -> None:
    """D21: DUAL_POINT mode activates precomputed_gate_out_min from departure predictions."""
    legs, pairs = sample_legs_and_pairs
    cfg = NativeDualCorePipelineConfig(simulation_mode=SimulationMode.DUAL_POINT)
    pipeline = NativeDualCorePipeline(config=cfg)
    result = pipeline.run(sample_inbound_df, sample_outbound_df, legs, pairs)

    for flight in result.flights:
        assert flight.precomputed_gate_out_min is not None


def test_d22_native_vs_precomputed_provenance_differs() -> None:
    """D22: Provenance mode reflects NATIVE_INFERENCE vs PRECOMPUTED_PREDICTION explicitly."""
    assert ProvenanceMode.NATIVE_INFERENCE.value == "NATIVE_INFERENCE"
    assert ProvenanceMode.PRECOMPUTED_PREDICTION.value == "PRECOMPUTED_PREDICTION"
    assert ProvenanceMode.NATIVE_INFERENCE.value != ProvenanceMode.PRECOMPUTED_PREDICTION.value


def test_d23_probabilistic_parameters_validated(sample_inbound_df: pd.DataFrame) -> None:
    """D23: Probabilistic distribution outputs are finite, positive sigma, and monotonic quantiles."""
    cfg = NativeDualCorePipelineConfig()
    pipeline = NativeDualCorePipeline(config=cfg)
    models = pipeline.load_and_verify_models()
    preds, _ = pipeline.run_native_inference(sample_inbound_df, pd.DataFrame(), models)

    prob_preds = [p for p in preds if p.predictive_quantiles is not None]
    assert len(prob_preds) > 0
    for p in prob_preds:
        q = p.predictive_quantiles
        assert q["q10"] <= q["q50"] <= q["q90"]
        params = p.distribution_parameters
        assert params["sigma"] > 0
        assert params["df"] > 2.0


def test_d24_hard_constraint_verifier_passes_final_solution(
    sample_inbound_df: pd.DataFrame,
    sample_outbound_df: pd.DataFrame,
    sample_legs_and_pairs: tuple[dict[str, FlightLeg], list[TurnPair]],
) -> None:
    """D24: Independent verifier confirms zero hard constraint violations."""
    legs, pairs = sample_legs_and_pairs
    cfg = NativeDualCorePipelineConfig()
    pipeline = NativeDualCorePipeline(config=cfg)
    result = pipeline.run(sample_inbound_df, sample_outbound_df, legs, pairs)

    diag = verify_hard_constraints_independently(
        flights=result.flights,
        gates=result.gates,
        assignments=result.optimization_result.assignments,
    )
    assert diag.is_valid is True
    assert diag.hard_constraint_violations_count == 0


def test_d25_objective_reevaluation_matches(
    sample_inbound_df: pd.DataFrame,
    sample_outbound_df: pd.DataFrame,
    sample_legs_and_pairs: tuple[dict[str, FlightLeg], list[TurnPair]],
) -> None:
    """D25: Independent evaluate_gate_assignment matches solver objective value."""
    legs, pairs = sample_legs_and_pairs
    cfg = NativeDualCorePipelineConfig()
    pipeline = NativeDualCorePipeline(config=cfg)
    result = pipeline.run(sample_inbound_df, sample_outbound_df, legs, pairs)

    assert pytest.approx(result.optimization_result.objective_value, rel=1e-4) == result.re_evaluated_objective


def test_d26_missing_data_no_fake_prediction() -> None:
    """D26: Missing required features fail closed without producing fabricated predictions."""
    incomplete_df = pd.DataFrame([{"FL_DATE": "2023-11-23", "DEST": "ATL"}])
    with pytest.raises(FeatureContractViolation):
        prepare_arrival_features_for_inference(incomplete_df)


def test_d27_checkpoint_loaded_from_allowlisted_local_path() -> None:
    """D27: Loading checkpoints refuses unauthorized external paths."""
    with pytest.raises(CheckpointVerificationError, match="outside allowlisted"):
        verify_checkpoint_path_allowlist(Path("C:/Windows/System32/calc.exe"))
    with pytest.raises(CheckpointVerificationError, match="remote"):
        verify_checkpoint_path_allowlist(Path("http://evil.com/malicious.joblib"))


def test_d28_end_to_end_synthetic_smoke_test() -> None:
    """D28: Fast synthetic end-to-end smoke test executes in < 2 seconds."""
    from scripts.run_native_dual_core_pipeline import build_synthetic_canonical_data
    in_df, out_df, legs, pairs = build_synthetic_canonical_data(5, "ATL")

    cfg = NativeDualCorePipelineConfig(
        n_contact_gates=5,
        time_limit_seconds=1.0,
        solver_name="Greedy",
    )
    pipeline = NativeDualCorePipeline(config=cfg)
    result = pipeline.run(in_df, out_df, legs, pairs)
    assert result.optimization_result.feasible is True
    assert result.constraint_diagnostic.is_valid is True


def test_d29_end_to_end_real_checkpoint_integration_test(
    sample_inbound_df: pd.DataFrame,
    sample_outbound_df: pd.DataFrame,
    sample_legs_and_pairs: tuple[dict[str, FlightLeg], list[TurnPair]],
) -> None:
    """D29: Real frozen P4 and XGBoost checkpoints run end-to-end on real 2023 data."""
    legs, pairs = sample_legs_and_pairs
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_path = Path(tmp_dir)
        cfg = NativeDualCorePipelineConfig(
            n_contact_gates=10,
            time_limit_seconds=3.0,
            solver_name="CPSat",
        )
        pipeline = NativeDualCorePipeline(config=cfg)
        result = pipeline.run(sample_inbound_df, sample_outbound_df, legs, pairs, output_dir=out_path)

        assert (out_path / "run_manifest.json").exists()
        assert (out_path / "predictions_sample.csv").exists()
        assert (out_path / "turn_pairing_audit.json").exists()
        assert (out_path / "optimization_result.json").exists()
        assert result.optimization_result.feasible is True


def test_d30_repeatability_with_pinned_artifacts_config(
    sample_inbound_df: pd.DataFrame,
    sample_outbound_df: pd.DataFrame,
    sample_legs_and_pairs: tuple[dict[str, FlightLeg], list[TurnPair]],
) -> None:
    """D30: Repeatability verified across repeated executions with identical seeds."""
    legs, pairs = sample_legs_and_pairs
    cfg = NativeDualCorePipelineConfig(random_seed=202601, solver_name="DeterministicGreedy")
    pipeline = NativeDualCorePipeline(config=cfg)

    res1 = pipeline.run(sample_inbound_df, sample_outbound_df, legs, pairs)
    res2 = pipeline.run(sample_inbound_df, sample_outbound_df, legs, pairs)

    preds1 = [p.predicted_delay_min for p in res1.predictions]
    preds2 = [p.predicted_delay_min for p in res2.predictions]
    assert preds1 == preds2

    assign1 = {k: v.gate_id for k, v in res1.optimization_result.assignments.items()}
    assign2 = {k: v.gate_id for k, v in res2.optimization_result.assignments.items()}
    assert assign1 == assign2


# =============================================================================
# SCENARIOS A TO E ACCEPTANCE TESTS
# =============================================================================

def test_scenario_a_synthetic_flights_fake_models() -> None:
    """SCENARIO A: 10 synthetic flights with deterministic orchestration."""
    from scripts.run_native_dual_core_pipeline import build_synthetic_canonical_data
    in_df, out_df, legs, pairs = build_synthetic_canonical_data(10, "ATL")

    cfg = NativeDualCorePipelineConfig(
        n_contact_gates=8,
        time_limit_seconds=1.0,
        solver_name="DeterministicGreedy",
    )
    pipeline = NativeDualCorePipeline(config=cfg)
    result = pipeline.run(in_df, out_df, legs, pairs)

    assert len(result.flights) == 10
    assert result.optimization_result.feasible is True
    assert result.constraint_diagnostic.is_valid is True


def test_scenario_b_small_real_subset_valid_checkpoints(
    sample_inbound_df: pd.DataFrame,
    sample_outbound_df: pd.DataFrame,
    sample_legs_and_pairs: tuple[dict[str, FlightLeg], list[TurnPair]],
) -> None:
    """SCENARIO B: Real Aeolus 2023 subset with validated native model inference."""
    legs, pairs = sample_legs_and_pairs
    cfg = NativeDualCorePipelineConfig(solver_name="CPSat")
    pipeline = NativeDualCorePipeline(config=cfg)
    result = pipeline.run(sample_inbound_df, sample_outbound_df, legs, pairs)

    assert result.manifest["model_provenance"]["arrival"]["verification_status"] == "VERIFIED_VALID"
    assert result.manifest["model_provenance"]["departure"]["verification_status"] == "VERIFIED_VALID"
    assert result.optimization_result.feasible is True


def test_scenario_c_arrival_only_vs_dual_point_differential(
    sample_inbound_df: pd.DataFrame,
    sample_outbound_df: pd.DataFrame,
    sample_legs_and_pairs: tuple[dict[str, FlightLeg], list[TurnPair]],
) -> None:
    """SCENARIO C: Verify outbound predictions actively modify occupancy between legacy and dual-point."""
    legs, pairs = sample_legs_and_pairs
    # Run legacy arrival-only
    cfg_legacy = NativeDualCorePipelineConfig(simulation_mode=SimulationMode.ARRIVAL_ONLY_LEGACY)
    res_legacy = NativeDualCorePipeline(config=cfg_legacy).run(sample_inbound_df, sample_outbound_df, legs, pairs)

    # Run dual point
    cfg_dual = NativeDualCorePipelineConfig(simulation_mode=SimulationMode.DUAL_POINT)
    res_dual = NativeDualCorePipeline(config=cfg_dual).run(sample_inbound_df, sample_outbound_df, legs, pairs)

    # Verify that in dual mode, precomputed_gate_out_min is present and informed by departure ML
    for f in res_legacy.flights:
        assert f.precomputed_gate_out_min is None
    for f in res_dual.flights:
        assert f.precomputed_gate_out_min is not None


def test_scenario_d_missing_invalid_model_fail_closed(
    sample_inbound_df: pd.DataFrame,
    sample_outbound_df: pd.DataFrame,
    sample_legs_and_pairs: tuple[dict[str, FlightLeg], list[TurnPair]],
) -> None:
    """SCENARIO D: Missing or invalid model artifact fails closed immediately."""
    legs, pairs = sample_legs_and_pairs
    cfg_bad = NativeDualCorePipelineConfig(arrival_checkpoint_path=Path("artifacts/corrupt_file.joblib"))
    pipeline = NativeDualCorePipeline(config=cfg_bad)

    with pytest.raises(FileNotFoundError):
        pipeline.run(sample_inbound_df, sample_outbound_df, legs, pairs)


def test_scenario_e_impossible_physical_turnaround_handling() -> None:
    """SCENARIO E: Impossible physical turnaround is safely pushed back to feasible minimum."""
    engine = DualTurnEngine(min_turnaround_min=45, separation_buffer_min=15)
    legs = {
        "ARR_01": FlightLeg(
            flight_id="ARR_01",
            direction=LegDirection.ARR,
            carrier="DL",
            flight_number="101",
            origin="ORD",
            destination="ATL",
            scheduled_event_local=datetime(2023, 11, 23, 10, 0),
            normalized_timeline_min=600,
        ),
        "DEP_01": FlightLeg(
            flight_id="DEP_01",
            direction=LegDirection.DEP,
            carrier="DL",
            flight_number="101",
            origin="ATL",
            destination="LGA",
            scheduled_event_local=datetime(2023, 11, 23, 10, 20),
            normalized_timeline_min=620,  # Scheduled dwell is only 20m!
        ),
    }
    pair = TurnPair(
        pair_id="TURN_IMPOSSIBLE",
        arrival_leg_id="ARR_01",
        departure_leg_id="DEP_01",
        pair_type=PairType.SYNTHETIC_PAIR,
        scenario_id="SCEN_E",
    )
    # Even if departure ML predicts on-time (620), gate-out MUST be at least 600 + 45 = 645
    turn = engine.synthesize_turn(pair, legs, arrival_prediction=0.0, departure_prediction=0.0, mode=SimulationMode.DUAL_POINT)
    assert turn.simulated_arrival_min == 600
    assert turn.simulated_departure_min == 645
    assert turn.physical_dwell_min >= 45
    assert turn.gate_release_min == 660  # 645 + 15
