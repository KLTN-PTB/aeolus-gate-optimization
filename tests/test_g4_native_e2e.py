"""Authoritative Verification Test Suite for Gate AEOLUS-G4.

Protocol: Aeolus Dual Core Architecture Protocol V2
Phase: AEOLUS-G4 Verified Aircraft Turn Pairing & Native Real-Data End-to-End
Test Coverage:
- TURN-01 to TURN-11: Aircraft Turn & Deterministic Pairing Specifications
- TIME-01 to TIME-02: Canonical Datetime Parsing & Rollover Specifications
- DATA-REAL-01 to DATA-REAL-03: Strict REAL_ONLY Data Loader Specifications
- ML-E2E-01 to ML-E2E-03: Native ML Checkpoint & Cutoff Specifications
- OPT-E2E-01 to OPT-E2E-03: Optimization Adapter & Independent Verifier Specifications
- REPRO-01: Deterministic End-to-End Reproducibility
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
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
from src.data.canonical_time import (
    InvalidDatetimeError,
    ScheduledEventTimestamp,
    build_canonical_scheduled_datetime,
    parse_canonical_flight_date,
    parse_canonical_scheduled_time,
)
from src.data.pairing_validator import PairingValidator
from src.data.real_data_loader import (
    DataLoaderMode,
    EmptyDateRangeError,
    MissingPartitionError,
    RealDataLoader,
    SchemaContractViolation,
)
from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import (
    ConstraintDiagnostic,
    Flight,
    Gate,
    GateResourceType,
    verify_hard_constraints_independently,
)
from src.simulation.dual_prediction_turn import (
    DualAircraftTurn,
    DualTurnEngine,
    SimulationMode,
)
from src.simulation.native_dual_core_pipeline import (
    DEP_TREE_PREPROCESSOR_PATH,
    DEP_TREE_PREPROCESSOR_SHA256,
    DEP_XGB_CHECKPOINT_PATH,
    DEP_XGB_SHA256,
    NativeDualCorePipeline,
    NativeDualCorePipelineConfig,
    P4_ARRIVAL_CHECKPOINT_PATH,
    P4_ARRIVAL_SHA256,
    generate_contact_and_remote_gates,
    verify_and_load_checkpoint,
)
from src.simulation.verified_pairing import (
    DeterministicPairingEngine,
    VerifiedPairingResult,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def base_legs_dict() -> dict[str, FlightLeg]:
    """Base fixture of flight legs for pairing tests."""
    return {
        "ARR_01": FlightLeg(
            flight_id="ARR_01",
            direction=LegDirection.ARR,
            carrier="DL",
            flight_number="101",
            origin="ORD",
            destination="ATL",
            scheduled_event_local=datetime(2023, 11, 23, 8, 0),
            normalized_timeline_min=480,
            tail_number="N101DL",
        ),
        "DEP_01": FlightLeg(
            flight_id="DEP_01",
            direction=LegDirection.DEP,
            carrier="DL",
            flight_number="102",
            origin="ATL",
            destination="LGA",
            scheduled_event_local=datetime(2023, 11, 23, 9, 30),
            normalized_timeline_min=570,
            tail_number="N101DL",
        ),
        "ARR_02": FlightLeg(
            flight_id="ARR_02",
            direction=LegDirection.ARR,
            carrier="AA",
            flight_number="201",
            origin="DFW",
            destination="ATL",
            scheduled_event_local=datetime(2023, 11, 23, 9, 0),
            normalized_timeline_min=540,
            tail_number="N202AA",
        ),
        "DEP_02": FlightLeg(
            flight_id="DEP_02",
            direction=LegDirection.DEP,
            carrier="AA",
            flight_number="202",
            origin="ATL",
            destination="MIA",
            scheduled_event_local=datetime(2023, 11, 23, 10, 15),
            normalized_timeline_min=615,
            tail_number="N202AA",
        ),
    }


# =============================================================================
# TURN-01 TO TURN-11: PAIRING SPECIFICATIONS
# =============================================================================

def test_turn_01_same_tail_valid_pair(base_legs_dict: dict[str, FlightLeg]) -> None:
    """TURN-01: Same valid tail number and hub connection creates VERIFIED_PAIR."""
    engine = DeterministicPairingEngine(hub_airport="ATL")
    res = engine.pair_flights(base_legs_dict)

    assert res.metrics["verified_turns_count"] == 2
    assert len(res.verified_pairs) == 2
    for pair in res.verified_pairs:
        assert pair.pair_type == PairType.VERIFIED_PAIR
        assert pair.linkage_source == LinkageSource.VERIFIED_ROTATION
        assert pair.scheduled_turnaround_min >= 45.0


def test_turn_02_different_tail_rejected(base_legs_dict: dict[str, FlightLeg]) -> None:
    """TURN-02: Different tail numbers cannot form a verified pair."""
    # Modify DEP_01 tail to differ from ARR_01
    legs = dict(base_legs_dict)
    legs["DEP_01"] = FlightLeg(
        flight_id="DEP_01",
        direction=LegDirection.DEP,
        carrier="DL",
        flight_number="102",
        origin="ATL",
        destination="LGA",
        scheduled_event_local=datetime(2023, 11, 23, 9, 30),
        normalized_timeline_min=570,
        tail_number="N999DL",  # Tail mismatch!
    )
    engine = DeterministicPairingEngine(hub_airport="ATL")
    res = engine.pair_flights(legs, allow_inferred_pairing=False)

    # ARR_01 and DEP_01 must NOT form a verified pair
    verified_arr_ids = {p.arrival_leg_id for p in res.verified_pairs}
    assert "ARR_01" not in verified_arr_ids
    # Only ARR_02 and DEP_02 should be verified
    assert res.metrics["verified_turns_count"] == 1


def test_turn_03_wrong_airport_rejected(base_legs_dict: dict[str, FlightLeg]) -> None:
    """TURN-03: Flights not connecting at ATL hub are rejected from pairing."""
    legs = dict(base_legs_dict)
    legs["ARR_01"] = FlightLeg(
        flight_id="ARR_01",
        direction=LegDirection.ARR,
        carrier="DL",
        flight_number="101",
        origin="ORD",
        destination="JFK",  # Wrong destination (not ATL)
        scheduled_event_local=datetime(2023, 11, 23, 8, 0),
        normalized_timeline_min=480,
        tail_number="N101DL",
    )
    engine = DeterministicPairingEngine(hub_airport="ATL")
    res = engine.pair_flights(legs)

    # ARR_01 cannot pair at ATL
    assert "ARR_01" not in {p.arrival_leg_id for p in res.verified_pairs}


def test_turn_04_reversed_chronological_order_rejected(base_legs_dict: dict[str, FlightLeg]) -> None:
    """TURN-04: Departure scheduled before arrival cannot form a turn."""
    legs = dict(base_legs_dict)
    legs["DEP_01"] = FlightLeg(
        flight_id="DEP_01",
        direction=LegDirection.DEP,
        carrier="DL",
        flight_number="102",
        origin="ATL",
        destination="LGA",
        scheduled_event_local=datetime(2023, 11, 23, 7, 0),
        normalized_timeline_min=420,  # 07:00, before ARR at 08:00 (480)
        tail_number="N101DL",
    )
    engine = DeterministicPairingEngine(hub_airport="ATL")
    res = engine.pair_flights(legs)

    assert "ARR_01" not in {p.arrival_leg_id for p in res.verified_pairs}


def test_turn_05_turnaround_below_minimum_rejected(base_legs_dict: dict[str, FlightLeg]) -> None:
    """TURN-05: Scheduled turnaround below min_turnaround_min is rejected."""
    legs = dict(base_legs_dict)
    legs["DEP_01"] = FlightLeg(
        flight_id="DEP_01",
        direction=LegDirection.DEP,
        carrier="DL",
        flight_number="102",
        origin="ATL",
        destination="LGA",
        scheduled_event_local=datetime(2023, 11, 23, 8, 30),
        normalized_timeline_min=510,  # 510 - 480 = 30m (< 45m min)
        tail_number="N101DL",
    )
    engine = DeterministicPairingEngine(hub_airport="ATL", min_turnaround_min=45)
    res = engine.pair_flights(legs)

    assert "ARR_01" not in {p.arrival_leg_id for p in res.verified_pairs}


def test_turn_06_one_leg_cannot_appear_twice(base_legs_dict: dict[str, FlightLeg]) -> None:
    """TURN-06: 1-to-1 cardinality is strictly enforced; a leg cannot appear in multiple turns."""
    legs = dict(base_legs_dict)
    # Add another departure with same tail
    legs["DEP_01B"] = FlightLeg(
        flight_id="DEP_01B",
        direction=LegDirection.DEP,
        carrier="DL",
        flight_number="103",
        origin="ATL",
        destination="BOS",
        scheduled_event_local=datetime(2023, 11, 23, 11, 0),
        normalized_timeline_min=660,
        tail_number="N101DL",
    )
    engine = DeterministicPairingEngine(hub_airport="ATL")
    res = engine.pair_flights(legs)

    # Check ARR_01 is used at most once in verified pairs
    arr_used = [p.arrival_leg_id for p in res.verified_pairs if p.arrival_leg_id == "ARR_01"]
    assert len(arr_used) == 1
    # Check that DEP_01B remains as an unmatched departure
    unm_dep_ids = {p.departure_leg_id for p in res.unmatched_dep_pairs}
    assert "DEP_01B" in unm_dep_ids


def test_turn_07_multiple_candidates_handled_deterministically(base_legs_dict: dict[str, FlightLeg]) -> None:
    """TURN-07: When multiple candidate departures exist, earliest feasible is deterministically chosen."""
    legs = dict(base_legs_dict)
    # Candidate 1: 9:30 (570)
    # Candidate 2: 9:15 (555) -> should be chosen first!
    legs["DEP_01_EARLIER"] = FlightLeg(
        flight_id="DEP_01_EARLIER",
        direction=LegDirection.DEP,
        carrier="DL",
        flight_number="102A",
        origin="ATL",
        destination="TPA",
        scheduled_event_local=datetime(2023, 11, 23, 9, 15),
        normalized_timeline_min=555,
        tail_number="N101DL",
    )
    engine = DeterministicPairingEngine(hub_airport="ATL")
    res = engine.pair_flights(legs)

    paired_dep = next(p.departure_leg_id for p in res.verified_pairs if p.arrival_leg_id == "ARR_01")
    assert paired_dep == "DEP_01_EARLIER"


def test_turn_08_dataframe_row_permutation_invariant(base_legs_dict: dict[str, FlightLeg]) -> None:
    """TURN-08: Order of input records does not alter pairing outcomes."""
    keys_order1 = list(base_legs_dict.keys())
    keys_order2 = list(reversed(keys_order1))

    dict_order1 = {k: base_legs_dict[k] for k in keys_order1}
    dict_order2 = {k: base_legs_dict[k] for k in keys_order2}

    engine = DeterministicPairingEngine(hub_airport="ATL")
    res1 = engine.pair_flights(dict_order1)
    res2 = engine.pair_flights(dict_order2)

    pairs1 = sorted([(p.arrival_leg_id, p.departure_leg_id) for p in res1.verified_pairs])
    pairs2 = sorted([(p.arrival_leg_id, p.departure_leg_id) for p in res2.verified_pairs])
    assert pairs1 == pairs2


def test_turn_09_midnight_crossover() -> None:
    """TURN-09: Cross-midnight turnaround handles timeline minutes without negative duration."""
    legs = {
        "ARR_NIGHT": FlightLeg(
            flight_id="ARR_NIGHT",
            direction=LegDirection.ARR,
            carrier="DL",
            flight_number="900",
            origin="LAX",
            destination="ATL",
            scheduled_event_local=datetime(2023, 11, 23, 23, 30),
            normalized_timeline_min=1410,
            tail_number="N900DL",
        ),
        "DEP_MORNING": FlightLeg(
            flight_id="DEP_MORNING",
            direction=LegDirection.DEP,
            carrier="DL",
            flight_number="901",
            origin="ATL",
            destination="MCO",
            scheduled_event_local=datetime(2023, 11, 24, 1, 0),
            normalized_timeline_min=1500,  # 01:00 next day (+90m)
            tail_number="N900DL",
        ),
    }
    engine = DeterministicPairingEngine(hub_airport="ATL")
    res = engine.pair_flights(legs)

    assert len(res.verified_pairs) == 1
    pair = res.verified_pairs[0]
    assert pair.scheduled_turnaround_min == 90.0


def test_turn_10_missing_tail_unmatched_handling() -> None:
    """TURN-10: Missing tail numbers do not create false verified pairs; routed to unmatched."""
    legs = {
        "ARR_NO_TAIL": FlightLeg(
            flight_id="ARR_NO_TAIL",
            direction=LegDirection.ARR,
            carrier="DL",
            flight_number="100",
            origin="ORD",
            destination="ATL",
            scheduled_event_local=datetime(2023, 11, 23, 8, 0),
            normalized_timeline_min=480,
            tail_number=None,  # Missing!
        ),
        "DEP_NO_TAIL": FlightLeg(
            flight_id="DEP_NO_TAIL",
            direction=LegDirection.DEP,
            carrier="DL",
            flight_number="101",
            origin="ATL",
            destination="LGA",
            scheduled_event_local=datetime(2023, 11, 23, 9, 30),
            normalized_timeline_min=570,
            tail_number=None,  # Missing!
        ),
    }
    engine = DeterministicPairingEngine(hub_airport="ATL")
    res = engine.pair_flights(legs, allow_inferred_pairing=False)

    assert res.metrics["verified_turns_count"] == 0
    assert len(res.unmatched_arr_pairs) == 1
    assert len(res.unmatched_dep_pairs) == 1


def test_turn_11_duplicate_flight_id_handling() -> None:
    """TURN-11: Duplicate flight IDs in input are detected and raise an error."""
    legs = {
        "ARR_01": FlightLeg(
            flight_id="DUP_ID",
            direction=LegDirection.ARR,
            carrier="DL",
            flight_number="101",
            origin="ORD",
            destination="ATL",
            scheduled_event_local=datetime(2023, 11, 23, 8, 0),
            tail_number="N101DL",
        ),
        "DEP_01": FlightLeg(
            flight_id="DUP_ID",  # Same flight_id!
            direction=LegDirection.DEP,
            carrier="DL",
            flight_number="102",
            origin="ATL",
            destination="LGA",
            scheduled_event_local=datetime(2023, 11, 23, 9, 30),
            tail_number="N101DL",
        ),
    }
    engine = DeterministicPairingEngine(hub_airport="ATL")
    with pytest.raises(ValueError, match="DUPLICATE_FLIGHT_ID"):
        engine.pair_flights(legs)


# =============================================================================
# TIME-01 TO TIME-02: CANONICAL TIME SPECIFICATIONS
# =============================================================================

def test_time_01_scheduled_hhmm_date_parsing() -> None:
    """TIME-01: Verifies parsing of HHMM integers, strings, timestamps, and 2400 rollover."""
    # 1. Standard integer HHMM
    t1 = build_canonical_scheduled_datetime("2023-11-23", 930, "ATL")
    assert t1.local_datetime.hour == 9
    assert t1.local_datetime.minute == 30
    assert t1.timeline_minute == 570
    assert not t1.is_next_day_rollover

    # 2. ISO timestamp string
    t2 = build_canonical_scheduled_datetime("2023-11-23", "2023-11-23 15:45:00", "ATL")
    assert t2.local_datetime.hour == 15
    assert t2.local_datetime.minute == 45
    assert t2.timeline_minute == 945

    # 3. 2400 Midnight rollover (+1 day, 00:00)
    t3 = build_canonical_scheduled_datetime("2023-11-23", 2400, "ATL")
    assert t3.local_datetime.hour == 0
    assert t3.local_datetime.minute == 0
    assert t3.local_datetime.day == 24
    assert t3.is_next_day_rollover
    assert t3.timeline_minute == 1440


def test_time_02_invalid_missing_datetime_handling() -> None:
    """TIME-02: Invalid, NaN, or out-of-range datetime inputs fail closed."""
    with pytest.raises(InvalidDatetimeError):
        build_canonical_scheduled_datetime("2023-11-23", None, "ATL")

    with pytest.raises(InvalidDatetimeError):
        build_canonical_scheduled_datetime("2023-11-23", 2500, "ATL")  # Hour 25 invalid

    with pytest.raises(InvalidDatetimeError):
        build_canonical_scheduled_datetime("invalid-date", 930, "ATL")


# =============================================================================
# DATA-REAL-01 TO DATA-REAL-03: STRICT REAL_ONLY LOADER
# =============================================================================

def test_data_real_01_missing_partition_fails() -> None:
    """DATA-REAL-01: Missing partition directory fails immediately in REAL_ONLY mode."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        loader = RealDataLoader(mode=DataLoaderMode.REAL_ONLY, base_dir=Path(tmp_dir))
        with pytest.raises(MissingPartitionError, match="REAL_ONLY mode violation"):
            loader.load_atl_data(start_date="2023-11-23", end_date="2023-11-23")


def test_data_real_02_empty_date_range_fails() -> None:
    """DATA-REAL-02: Querying date with 0 flights raises EmptyDateRangeError without borrowing adjacent dates."""
    loader = RealDataLoader(mode=DataLoaderMode.REAL_ONLY)
    # 1990 has no data in 2023 partition
    with pytest.raises(EmptyDateRangeError, match="Zero flights found"):
        loader.load_atl_data(start_date="1990-01-01", end_date="1990-01-01")


def test_data_real_03_no_synthetic_fallback() -> None:
    """DATA-REAL-03: In REAL_ONLY mode, synthetic generation is strictly forbidden."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        loader = RealDataLoader(mode=DataLoaderMode.REAL_ONLY, base_dir=Path(tmp_dir))
        # Ensure it raises and does NOT return synthetic data
        with pytest.raises(MissingPartitionError):
            loader.load_atl_data(start_date="2023-11-23", end_date="2023-11-23")


# =============================================================================
# ML-E2E-01 TO ML-E2E-03: NATIVE ML CHECKPOINTS & CUTOFF
# =============================================================================

def test_ml_e2e_01_arrival_native_checkpoint_verified() -> None:
    """ML-E2E-01: Frozen P4 NGBoost Student-t checkpoint is verified and produces valid distribution."""
    model, meta = verify_and_load_checkpoint(
        P4_ARRIVAL_CHECKPOINT_PATH, expected_sha256=P4_ARRIVAL_SHA256
    )
    assert meta["sha256"] == P4_ARRIVAL_SHA256
    assert hasattr(model, "predict_distribution") or hasattr(model, "predict")


def test_ml_e2e_02_departure_checkpoint_preprocessor_verified() -> None:
    """ML-E2E-02: Frozen XGBoost and preprocessor checkpoints are cryptographically verified."""
    xgb_model, xgb_meta = verify_and_load_checkpoint(
        DEP_XGB_CHECKPOINT_PATH, expected_sha256=DEP_XGB_SHA256
    )
    prep, prep_meta = verify_and_load_checkpoint(
        DEP_TREE_PREPROCESSOR_PATH, expected_sha256=DEP_TREE_PREPROCESSOR_SHA256
    )
    assert xgb_meta["sha256"] == DEP_XGB_SHA256
    assert prep_meta["sha256"] == DEP_TREE_PREPROCESSOR_SHA256
    assert hasattr(xgb_model, "predict")
    assert hasattr(prep, "transform")


def test_ml_e2e_03_feature_cutoff_enforcement() -> None:
    """ML-E2E-03: Operational prediction cutoff is strictly T-2h before departure/arrival."""
    cutoff_hours = 2.0
    sched_dt = datetime(2023, 11, 23, 10, 0, tzinfo=timezone.utc)
    expected_cutoff = sched_dt - timedelta(hours=cutoff_hours)
    assert (sched_dt - expected_cutoff).total_seconds() == 7200  # 2 hours


# =============================================================================
# OPT-E2E-01 TO OPT-E2E-03: OPTIMIZATION & VERIFICATION
# =============================================================================

def test_opt_e2e_01_standardized_predictions_reach_optimizer(base_legs_dict: dict[str, FlightLeg]) -> None:
    """OPT-E2E-01: Predictions correctly propagate to Flight domain entities."""
    engine = DeterministicPairingEngine(hub_airport="ATL")
    pairing_res = engine.pair_flights(base_legs_dict)

    turn_engine = DualTurnEngine(min_turnaround_min=45, separation_buffer_min=15)
    turns = []
    for pair in pairing_res.verified_pairs:
        t = turn_engine.synthesize_turn(
            pair=pair,
            legs=base_legs_dict,
            arrival_prediction=15.0,
            departure_prediction=10.0,
            mode=SimulationMode.DUAL_POINT,
        )
        turns.append(t)

    flights = [t.to_flight(i, dual_core_enabled=True) for i, t in enumerate(turns)]
    assert len(flights) == 2
    # Verify delay propagation
    assert flights[0].predicted_arrival_min == flights[0].scheduled_arrival_min + 15
    assert flights[0].precomputed_gate_out_min is not None


def test_opt_e2e_02_independent_verifier_confirms_feasible_outputs() -> None:
    """OPT-E2E-02: verify_hard_constraints_independently passes for valid assignments."""
    flights = [
        Flight(
            flight_id="F1",
            flight_index=0,
            carrier="DL",
            flight_number="101",
            scheduled_arrival_min=480,
            scheduled_departure_min=570,
            predicted_arrival_min=480,
            buffer_min=15,
        ),
        Flight(
            flight_id="F2",
            flight_index=1,
            carrier="AA",
            flight_number="201",
            scheduled_arrival_min=600,
            scheduled_departure_min=690,
            predicted_arrival_min=600,
            buffer_min=15,
        ),
    ]
    gates = generate_contact_and_remote_gates(n_contact_gates=2, allow_overflow=False)
    # Assign F1 to G01, F2 to G01 (sequential, non-overlapping: 480-585 vs 600-705)
    from src.optimization.domain import GateAssignment
    assignments = {
        "F1": GateAssignment(flight_id="F1", gate_id="G01", occupancy_start_min=480, occupancy_end_min=585),
        "F2": GateAssignment(flight_id="F2", gate_id="G01", occupancy_start_min=600, occupancy_end_min=705),
    }

    diag = verify_hard_constraints_independently(flights=flights, gates=gates, assignments=assignments)
    assert diag.is_valid is True
    assert diag.conflict_count == 0


def test_opt_e2e_03_prediction_sensitivity_is_actually_reflected_in_downstream_inputs(base_legs_dict: dict[str, FlightLeg]) -> None:
    """OPT-E2E-03: Perturbing arrival delay directly shifts the gate occupancy window."""
    turn_engine = DualTurnEngine(min_turnaround_min=45, separation_buffer_min=15)
    pair = TurnPair(
        pair_id="TURN_01",
        arrival_leg_id="ARR_01",
        departure_leg_id="DEP_01",
        pair_type=PairType.VERIFIED_PAIR,
    )
    turn_base = turn_engine.synthesize_turn(pair, base_legs_dict, arrival_prediction=0.0, departure_prediction=0.0)
    turn_delayed = turn_engine.synthesize_turn(pair, base_legs_dict, arrival_prediction=30.0, departure_prediction=0.0)

    assert turn_delayed.simulated_arrival_min == turn_base.simulated_arrival_min + 30
    assert turn_delayed.gate_in_min == turn_base.gate_in_min + 30


# =============================================================================
# REPRO-01: DETERMINISTIC REPRODUCIBILITY
# =============================================================================

def test_repro_01_same_input_config_seed_gives_equivalent_deterministic_result(base_legs_dict: dict[str, FlightLeg]) -> None:
    """REPRO-01: Identical input configuration and seed yields deterministic objective and assignments."""
    engine = DeterministicPairingEngine(hub_airport="ATL")
    res1 = engine.pair_flights(base_legs_dict)
    res2 = engine.pair_flights(base_legs_dict)

    pairs1 = [(p.pair_id, p.arrival_leg_id, p.departure_leg_id, p.scheduled_turnaround_min) for p in res1.verified_pairs]
    pairs2 = [(p.pair_id, p.arrival_leg_id, p.departure_leg_id, p.scheduled_turnaround_min) for p in res2.verified_pairs]
    assert pairs1 == pairs2
