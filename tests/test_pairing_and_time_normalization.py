"""Unit and integration tests for time normalization and arrival-departure pairing.

Protocol: Aeolus Dual Core Architecture Protocol V2
Phase: P6 Time Normalization & Arrival-Departure Pairing
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import pytest

from src.contracts.turn_contracts import (
    FlightLeg,
    LegDirection,
    LinkageSource,
    PairType,
    TurnPair,
    ValidationStatus,
)
from src.data.pairing_validator import (
    PairingValidator,
    validate_cpsat_turnaround_schedule_csv,
)
from src.data.time_normalization import (
    DSTGapError,
    UnknownAirportTimezoneError,
    calculate_normalized_timeline_min,
    get_airport_timezone,
    normalize_local_to_utc,
    parse_hhmm_time,
    reconcile_overnight_flight,
    validate_temporal_causality,
)


@pytest.fixture
def atl_tz() -> ZoneInfo:
    return ZoneInfo("America/New_York")


@pytest.fixture
def sample_legs(atl_tz: ZoneInfo) -> dict[str, FlightLeg]:
    """Base sample legs for pairing tests."""
    ref_date = date(2024, 6, 1)

    arr_local = datetime(2024, 6, 1, 8, 0, tzinfo=atl_tz)
    arr_utc = arr_local.astimezone(timezone.utc)
    arr_leg = FlightLeg(
        flight_id="LEG_ARR_001",
        direction=LegDirection.ARR,
        carrier="DL",
        flight_number="100",
        origin="MIA",
        destination="ATL",
        scheduled_event_local=arr_local,
        scheduled_event_utc=arr_utc,
        event_timezone="America/New_York",
        scheduled_elapsed_min=110.0,
        model_prediction_cutoff_utc=arr_utc - timedelta(hours=2),
        planning_snapshot_at_utc=arr_utc - timedelta(hours=3),
        prediction_generated_at_utc=arr_utc - timedelta(hours=3),
        scenario_id="scenario_test_01",
        session_id="SESS_001",
    )

    dep_local = datetime(2024, 6, 1, 9, 30, tzinfo=atl_tz)
    dep_utc = dep_local.astimezone(timezone.utc)
    dep_leg = FlightLeg(
        flight_id="LEG_DEP_001",
        direction=LegDirection.DEP,
        carrier="DL",
        flight_number="101",
        origin="ATL",
        destination="ORD",
        scheduled_event_local=dep_local,
        scheduled_event_utc=dep_utc,
        event_timezone="America/New_York",
        scheduled_elapsed_min=125.0,
        model_prediction_cutoff_utc=dep_utc - timedelta(hours=2),
        planning_snapshot_at_utc=dep_utc - timedelta(hours=3),
        prediction_generated_at_utc=dep_utc - timedelta(hours=3),
        scenario_id="scenario_test_01",
        session_id="SESS_001",
    )

    return {
        "LEG_ARR_001": arr_leg,
        "LEG_DEP_001": dep_leg,
    }


class TestTimeNormalization:
    """Verifies timezone mapping, DST gap/fold, rollover, and timeline alignment."""

    def test_airport_timezone_lookup(self):
        assert get_airport_timezone("ATL") == "America/New_York"
        assert get_airport_timezone("ORD") == "America/Chicago"
        assert get_airport_timezone("DEN") == "America/Denver"
        assert get_airport_timezone("PHX") == "America/Phoenix"
        assert get_airport_timezone("LAX") == "America/Los_Angeles"
        assert get_airport_timezone("HNL") == "Pacific/Honolulu"
        assert get_airport_timezone("SJU") == "America/Puerto_Rico"

    def test_unknown_airport_fails_closed(self):
        with pytest.raises(UnknownAirportTimezoneError, match="Unrecognized airport code 'ZZZ'"):
            get_airport_timezone("ZZZ")

    def test_dst_spring_forward_gap_rejection(self):
        # 2024-03-10 02:30:00 does not exist in America/New_York (clocks jump 01:59 -> 03:00)
        dt_gap = datetime(2024, 3, 10, 2, 30)
        with pytest.raises(DSTGapError, match="does not exist.*DST spring-forward"):
            normalize_local_to_utc(dt_gap, "America/New_York", allow_gap=False)

    def test_dst_fall_back_fold_detected(self):
        # 2024-11-03 01:30:00 occurs twice in America/New_York (EDT then EST)
        dt_fold = datetime(2024, 11, 3, 1, 30)
        utc0, flags0 = normalize_local_to_utc(dt_fold, "America/New_York", fold=0)
        utc1, flags1 = normalize_local_to_utc(dt_fold, "America/New_York", fold=1)
        assert flags0["is_dst_ambiguous"] is True
        assert flags1["is_dst_ambiguous"] is True
        # fold 0 is EDT (UTC-4 -> 05:30 UTC), fold 1 is EST (UTC-5 -> 06:30 UTC)
        assert (utc1 - utc0).total_seconds() == 3600

    def test_parse_hhmm_time(self):
        assert parse_hhmm_time(1835) == (18, 35)
        assert parse_hhmm_time("18:35") == (18, 35)
        assert parse_hhmm_time("1835") == (18, 35)
        assert parse_hhmm_time(25) == (0, 25)
        assert parse_hhmm_time(2400) == (0, 0)
        with pytest.raises(ValueError):
            parse_hhmm_time(-5)
        with pytest.raises(ValueError):
            parse_hhmm_time(2500)

    def test_overnight_flight_reconciliation(self):
        # Departs ATL at 22:30 EDT to SEA (duration 330m)
        dep_dt = datetime(2024, 6, 1, 22, 30)
        res = reconcile_overnight_flight(
            dep_local_dt=dep_dt,
            origin_tz_str="America/New_York",
            dest_tz_str="America/Los_Angeles",
            scheduled_elapsed_min=330.0,
            arr_time_val="01:00",
        )
        assert res["is_overnight"] is True
        assert res["review_required"] is False
        assert res["arr_local"].hour == 1
        assert res["arr_local"].minute == 0
        assert res["arr_local"].date() == date(2024, 6, 2)

    def test_normalized_timeline_minutes(self):
        ref_utc = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
        dt_utc = datetime(2024, 1, 1, 2, 30, tzinfo=timezone.utc)
        minutes = calculate_normalized_timeline_min(dt_utc, ref_utc)
        assert minutes == 150


class TestPairingValidator:
    """Verifies TurnPair cardinality, chronological order, evidence guards, and causality."""

    def test_normal_sameday_pair(self, sample_legs):
        validator = PairingValidator()
        pair = TurnPair(
            pair_id="PAIR_001",
            arrival_leg_id="LEG_ARR_001",
            departure_leg_id="LEG_DEP_001",
            pair_type=PairType.SYNTHETIC_PAIR,
            linkage_source=LinkageSource.SIMULATION_SESSION,
            scenario_id="scenario_test_01",
            session_id="SESS_001",
        )
        val_pairs, summary = validator.validate_pairs(sample_legs, [pair])
        assert summary.is_clean is True
        assert summary.valid_pairs_count == 1
        assert val_pairs[0].scheduled_turnaround_min == 90.0

    def test_overnight_pair(self, atl_tz):
        # Inbound arrives at 23:30 on day 1, Outbound departs at 06:30 on day 2
        arr_local = datetime(2024, 6, 1, 23, 30, tzinfo=atl_tz)
        dep_local = datetime(2024, 6, 2, 6, 30, tzinfo=atl_tz)

        legs = {
            "ARR_NIGHT": FlightLeg(
                flight_id="ARR_NIGHT",
                direction=LegDirection.ARR,
                carrier="DL",
                flight_number="500",
                origin="LAX",
                destination="ATL",
                scheduled_event_local=arr_local,
                scheduled_event_utc=arr_local.astimezone(timezone.utc),
                scenario_id="scen_night",
                session_id="SESS_NIGHT",
            ),
            "DEP_MORNING": FlightLeg(
                flight_id="DEP_MORNING",
                direction=LegDirection.DEP,
                carrier="DL",
                flight_number="501",
                origin="ATL",
                destination="BOS",
                scheduled_event_local=dep_local,
                scheduled_event_utc=dep_local.astimezone(timezone.utc),
                scenario_id="scen_night",
                session_id="SESS_NIGHT",
            ),
        }
        validator = PairingValidator()
        pair = TurnPair(
            pair_id="PAIR_OVERNIGHT",
            arrival_leg_id="ARR_NIGHT",
            departure_leg_id="DEP_MORNING",
            pair_type=PairType.SYNTHETIC_PAIR,
            scenario_id="scen_night",
            session_id="SESS_NIGHT",
        )
        val_pairs, summary = validator.validate_pairs(legs, [pair])
        assert summary.is_clean is True
        assert val_pairs[0].scheduled_turnaround_min == 420.0  # 7 hours

    def test_different_timezones_conversion(self):
        # Flight ARR from SEA (Pacific) arrives at ATL at 14:00 EDT (18:00 UTC)
        # Flight DEP to ORD (Central) departs ATL at 15:30 EDT (19:30 UTC)
        arr_local = datetime(2024, 6, 1, 14, 0, tzinfo=ZoneInfo("America/New_York"))
        dep_local = datetime(2024, 6, 1, 15, 30, tzinfo=ZoneInfo("America/New_York"))

        legs = {
            "ARR_SEA": FlightLeg(
                flight_id="ARR_SEA",
                direction=LegDirection.ARR,
                carrier="DL",
                flight_number="200",
                origin="SEA",
                destination="ATL",
                scheduled_event_local=arr_local,
                scheduled_event_utc=arr_local.astimezone(timezone.utc),
                scenario_id="scen_tz",
                session_id="SESS_TZ",
            ),
            "DEP_ORD": FlightLeg(
                flight_id="DEP_ORD",
                direction=LegDirection.DEP,
                carrier="DL",
                flight_number="201",
                origin="ATL",
                destination="ORD",
                scheduled_event_local=dep_local,
                scheduled_event_utc=dep_local.astimezone(timezone.utc),
                scenario_id="scen_tz",
                session_id="SESS_TZ",
            ),
        }
        validator = PairingValidator()
        pair = TurnPair(
            pair_id="PAIR_TZ",
            arrival_leg_id="ARR_SEA",
            departure_leg_id="DEP_ORD",
            pair_type=PairType.SYNTHETIC_PAIR,
            scenario_id="scen_tz",
            session_id="SESS_TZ",
        )
        val_pairs, summary = validator.validate_pairs(legs, [pair])
        assert summary.is_clean is True
        assert val_pairs[0].scheduled_turnaround_min == 90.0

    def test_duplicate_pair_id_rejected(self, sample_legs):
        validator = PairingValidator()
        p1 = TurnPair(
            pair_id="DUP_PAIR",
            arrival_leg_id="LEG_ARR_001",
            departure_leg_id="LEG_DEP_001",
            scenario_id="scen",
            session_id="sess",
        )
        p2 = TurnPair(
            pair_id="DUP_PAIR",
            arrival_leg_id="LEG_ARR_001",
            departure_leg_id="LEG_DEP_001",
            scenario_id="scen",
            session_id="sess",
        )
        val_pairs, summary = validator.validate_pairs(sample_legs, [p1, p2])
        assert summary.is_clean is False
        assert summary.invalid_pairs_count == 2
        assert any("DUPLICATE_PAIR_ID" in r for r in val_pairs[0].rejection_reasons)

    def test_many_to_one_and_one_to_many_rejected(self, sample_legs, atl_tz):
        # Add another departure
        dep_extra = FlightLeg(
            flight_id="LEG_DEP_EXTRA",
            direction=LegDirection.DEP,
            carrier="DL",
            flight_number="102",
            origin="ATL",
            destination="DFW",
            scheduled_event_local=datetime(2024, 6, 1, 10, 0, tzinfo=atl_tz),
            scheduled_event_utc=datetime(2024, 6, 1, 14, 0, tzinfo=timezone.utc),
            scenario_id="scen",
            session_id="sess",
        )
        legs = dict(sample_legs)
        legs["LEG_DEP_EXTRA"] = dep_extra

        # One ARR paired with two different DEPs
        p1 = TurnPair(
            pair_id="P1",
            arrival_leg_id="LEG_ARR_001",
            departure_leg_id="LEG_DEP_001",
            scenario_id="scen",
            session_id="sess",
        )
        p2 = TurnPair(
            pair_id="P2",
            arrival_leg_id="LEG_ARR_001",
            departure_leg_id="LEG_DEP_EXTRA",
            scenario_id="scen",
            session_id="sess",
        )

        validator = PairingValidator()
        val_pairs, summary = validator.validate_pairs(legs, [p1, p2])
        assert summary.is_clean is False
        assert summary.invalid_pairs_count == 2
        assert any("CARDINALITY_VIOLATION_MANY_TO_ONE" in r for r in val_pairs[0].rejection_reasons)

    def test_dep_before_arr_chronological_reversal_rejected(self, atl_tz):
        # DEP at 08:00, ARR at 09:00 (departure precedes arrival at gate!)
        arr_leg = FlightLeg(
            flight_id="ARR_LATE",
            direction=LegDirection.ARR,
            carrier="DL",
            flight_number="100",
            origin="MIA",
            destination="ATL",
            scheduled_event_local=datetime(2024, 6, 1, 9, 0, tzinfo=atl_tz),
            scheduled_event_utc=datetime(2024, 6, 1, 13, 0, tzinfo=timezone.utc),
            scenario_id="scen",
            session_id="sess",
        )
        dep_leg = FlightLeg(
            flight_id="DEP_EARLY",
            direction=LegDirection.DEP,
            carrier="DL",
            flight_number="101",
            origin="ATL",
            destination="ORD",
            scheduled_event_local=datetime(2024, 6, 1, 8, 0, tzinfo=atl_tz),
            scheduled_event_utc=datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc),
            scenario_id="scen",
            session_id="sess",
        )
        legs = {"ARR_LATE": arr_leg, "DEP_EARLY": dep_leg}
        validator = PairingValidator()
        pair = TurnPair(
            pair_id="P_REVERSED",
            arrival_leg_id="ARR_LATE",
            departure_leg_id="DEP_EARLY",
            scenario_id="scen",
            session_id="sess",
        )
        val_pairs, summary = validator.validate_pairs(legs, [pair])
        assert summary.is_clean is False
        assert summary.invalid_pairs_count == 1
        assert any("CHRONOLOGICAL_REVERSAL" in r for r in val_pairs[0].rejection_reasons)

    def test_unmatched_arr_and_unmatched_dep(self, sample_legs):
        validator = PairingValidator()
        p_arr = TurnPair(
            pair_id="PAIR_UNMATCHED_ARR",
            arrival_leg_id="LEG_ARR_001",
            departure_leg_id=None,
            pair_type=PairType.UNMATCHED_ARR,
            linkage_source=LinkageSource.UNPAIRED,
            scenario_id="scen",
            session_id="sess",
        )
        p_dep = TurnPair(
            pair_id="PAIR_UNMATCHED_DEP",
            arrival_leg_id=None,
            departure_leg_id="LEG_DEP_001",
            pair_type=PairType.UNMATCHED_DEP,
            linkage_source=LinkageSource.UNPAIRED,
            scenario_id="scen",
            session_id="sess",
        )
        val_pairs, summary = validator.validate_pairs(sample_legs, [p_arr, p_dep])
        assert summary.is_clean is True
        assert summary.valid_pairs_count == 2
        assert summary.unmatched_arr_count == 1
        assert summary.unmatched_dep_count == 1

    def test_missing_aircraft_evidence_quarantines_verified_label(self, sample_legs):
        # Trying to label pair as VERIFIED_PAIR when legs have no tail number
        validator = PairingValidator()
        pair = TurnPair(
            pair_id="FALSE_VERIFIED",
            arrival_leg_id="LEG_ARR_001",
            departure_leg_id="LEG_DEP_001",
            pair_type=PairType.VERIFIED_PAIR,
            linkage_source=LinkageSource.VERIFIED_ROTATION,
            scenario_id="scen",
            session_id="sess",
        )
        val_pairs, summary = validator.validate_pairs(sample_legs, [pair])
        assert summary.is_clean is False
        assert summary.quarantined_pairs_count == 1
        assert val_pairs[0].validation_status == ValidationStatus.QUARANTINED
        assert any("UNVERIFIED_AIRCRAFT_EVIDENCE" in r for r in val_pairs[0].rejection_reasons)

    def test_verified_pair_succeeds_with_authenticated_tail(self, atl_tz):
        arr_local = datetime(2024, 6, 1, 8, 0, tzinfo=atl_tz)
        dep_local = datetime(2024, 6, 1, 9, 30, tzinfo=atl_tz)
        legs = {
            "ARR_VERIFIED": FlightLeg(
                flight_id="ARR_VERIFIED",
                direction=LegDirection.ARR,
                carrier="DL",
                flight_number="100",
                origin="MIA",
                destination="ATL",
                scheduled_event_local=arr_local,
                tail_number="N999DL",
                scenario_id="real_flight_ops",
            ),
            "DEP_VERIFIED": FlightLeg(
                flight_id="DEP_VERIFIED",
                direction=LegDirection.DEP,
                carrier="DL",
                flight_number="101",
                origin="ATL",
                destination="ORD",
                scheduled_event_local=dep_local,
                tail_number="N999DL",
                scenario_id="real_flight_ops",
            ),
        }
        pair = TurnPair(
            pair_id="PAIR_VERIFIED_AUTHENTIC",
            arrival_leg_id="ARR_VERIFIED",
            departure_leg_id="DEP_VERIFIED",
            pair_type=PairType.VERIFIED_PAIR,
            linkage_source=LinkageSource.VERIFIED_ROTATION,
            scenario_id="real_flight_ops",
        )
        validator = PairingValidator()
        val_pairs, summary = validator.validate_pairs(legs, [pair])
        assert summary.is_clean is True
        assert summary.verified_pairs_count == 1
        assert val_pairs[0].validation_status == ValidationStatus.VALID

    def test_prediction_generated_after_planning_snapshot_rejected(self, atl_tz):
        # Leg with prediction generated at 10:00 UTC but planning snapshot was at 09:00 UTC
        event_dt = datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc)
        leg_bad = FlightLeg(
            flight_id="LEG_LOOKAHEAD",
            direction=LegDirection.ARR,
            carrier="DL",
            flight_number="100",
            origin="MIA",
            destination="ATL",
            scheduled_event_local=event_dt,
            scheduled_event_utc=event_dt,
            planning_snapshot_at_utc=datetime(2024, 6, 1, 9, 0, tzinfo=timezone.utc),
            prediction_generated_at_utc=datetime(2024, 6, 1, 10, 0, tzinfo=timezone.utc),  # Postdates snapshot!
            scenario_id="scen",
            session_id="sess",
        )
        validator = PairingValidator()
        pair = TurnPair(
            pair_id="P_LOOKAHEAD",
            arrival_leg_id="LEG_LOOKAHEAD",
            departure_leg_id=None,
            pair_type=PairType.UNMATCHED_ARR,
            scenario_id="scen",
            session_id="sess",
        )
        val_pairs, summary = validator.validate_pairs({"LEG_LOOKAHEAD": leg_bad}, [pair])
        assert summary.is_clean is False
        assert summary.invalid_pairs_count == 1
        assert any("PREDICTION_POSTDATES_PLANNING_SNAPSHOT" in r for r in val_pairs[0].rejection_reasons)


class TestCPSATTurnaroundFixtureValidation:
    """Verifies the actual 1,500 flight CPSAT turnaround CSV fixture."""

    def test_cpsat_fixture_audit(self):
        csv_path = Path("src/artifacts/predictions/atl_1500_flights_cpsat_turnaround_schedule.csv")
        assert csv_path.exists()

        res = validate_cpsat_turnaround_schedule_csv(csv_path)
        assert res["status"] == "PASS"
        assert res["total_records"] == 1500
        assert res["total_legs"] == 1500
        assert res["total_pairs"] == 851
        assert res["synthetic_pairs"] == 649
        assert res["unmatched_arr"] == 96
        assert res["unmatched_dep"] == 106
        assert res["valid_pairs"] == 851
        assert res["invalid_pairs"] == 0
        assert res["quarantined_pairs"] == 0
        assert res["verified_pairs"] == 0  # Crucial: 0 verified, all synthetic!
        assert res["is_clean"] is True
