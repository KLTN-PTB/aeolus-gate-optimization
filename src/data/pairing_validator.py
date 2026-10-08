"""Pairing validation, integrity verification, and synthetic schedule audit for Aeolus.

Protocol: Aeolus Dual Core Architecture Protocol V2
Phase: P6 Time Normalization & Arrival-Departure Pairing
Task: TurnPair validation, cardinality contracts, evidence guards, and CPSAT schedule parsing.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Final
from zoneinfo import ZoneInfo

import pandas as pd

from src.contracts.turn_contracts import (
    FlightLeg,
    LegDirection,
    LinkageSource,
    PairType,
    TurnPair,
    ValidationStatus,
)
from src.data.time_normalization import (
    AIRPORT_IANA_TIMEZONES,
    get_airport_timezone,
    validate_temporal_causality,
)


@dataclass
class PairingValidationSummary:
    """Summary metrics and audit results from validating a set of turn pairs."""

    total_legs: int = 0
    total_pairs: int = 0
    valid_pairs_count: int = 0
    invalid_pairs_count: int = 0
    quarantined_pairs_count: int = 0
    review_required_count: int = 0
    synthetic_pairs_count: int = 0
    verified_pairs_count: int = 0
    unmatched_arr_count: int = 0
    unmatched_dep_count: int = 0
    rejection_reasons_tally: dict[str, int] = field(default_factory=dict)

    @property
    def is_clean(self) -> bool:
        """Returns True if there are zero invalid or quarantined pairs."""
        return self.invalid_pairs_count == 0 and self.quarantined_pairs_count == 0


class PairingValidator:
    """Audits and validates flight leg pairings into aircraft turns."""

    def __init__(self, *, min_turnaround_min: float = 0.0) -> None:
        self.min_turnaround_min = min_turnaround_min

    def validate_pairs(
        self,
        legs: Mapping[str, FlightLeg],
        pairs: Sequence[TurnPair],
    ) -> tuple[list[TurnPair], PairingValidationSummary]:
        """Validates a batch of proposed TurnPairs against legs.

        Enforces:
        1. 1-to-1 Cardinality (no many-to-one or one-to-many across pairs).
        2. Unique pair IDs.
        3. Strict aircraft identity evidence for VERIFIED_PAIR (no heuristic promotion).
        4. Chronological monotonicity at ATL gate (ARR <= DEP).
        5. Valid synthetic scenario provenance.
        6. Operational temporal causality on flight legs.
        7. Unmatched leg schema consistency.
        """
        summary = PairingValidationSummary(
            total_legs=len(legs),
            total_pairs=len(pairs),
        )

        rejection_tally: Counter[str] = Counter()

        # Step 1: Detect duplicate pair_ids
        pair_id_counts = Counter(p.pair_id for p in pairs)
        duplicate_pair_ids = {pid for pid, count in pair_id_counts.items() if count > 1}

        # Step 2: Detect cardinality violations (many-to-one or one-to-many)
        arr_usage = defaultdict(list)
        dep_usage = defaultdict(list)
        for p in pairs:
            if p.arrival_leg_id:
                arr_usage[p.arrival_leg_id].append(p.pair_id)
            if p.departure_leg_id:
                dep_usage[p.departure_leg_id].append(p.pair_id)

        overused_arr = {leg_id for leg_id, pids in arr_usage.items() if len(pids) > 1}
        overused_dep = {leg_id for leg_id, pids in dep_usage.items() if len(pids) > 1}

        validated_pairs: list[TurnPair] = []

        for pair in pairs:
            reasons: list[str] = list(pair.rejection_reasons)
            current_status = pair.validation_status

            # Check 1: Duplicate pair ID
            if pair.pair_id in duplicate_pair_ids:
                reasons.append(f"DUPLICATE_PAIR_ID: pair_id '{pair.pair_id}' appears multiple times.")

            # Check 2: Cardinality violation
            if pair.arrival_leg_id and pair.arrival_leg_id in overused_arr:
                reasons.append(
                    f"CARDINALITY_VIOLATION_MANY_TO_ONE: arrival leg '{pair.arrival_leg_id}' "
                    f"is used in multiple pairs: {arr_usage[pair.arrival_leg_id]}."
                )
            if pair.departure_leg_id and pair.departure_leg_id in overused_dep:
                reasons.append(
                    f"CARDINALITY_VIOLATION_ONE_TO_MANY: departure leg '{pair.departure_leg_id}' "
                    f"is used in multiple pairs: {dep_usage[pair.departure_leg_id]}."
                )

            # Check 3: Leg existence
            arr_leg: FlightLeg | None = None
            dep_leg: FlightLeg | None = None

            if pair.arrival_leg_id:
                if pair.arrival_leg_id not in legs:
                    reasons.append(f"MISSING_LEG_REFERENCE: arrival leg '{pair.arrival_leg_id}' not found.")
                else:
                    arr_leg = legs[pair.arrival_leg_id]
                    if not arr_leg.is_arrival:
                        reasons.append(
                            f"DIRECTION_MISMATCH: arrival leg '{pair.arrival_leg_id}' has direction {arr_leg.direction}."
                        )

            if pair.departure_leg_id:
                if pair.departure_leg_id not in legs:
                    reasons.append(f"MISSING_LEG_REFERENCE: departure leg '{pair.departure_leg_id}' not found.")
                else:
                    dep_leg = legs[pair.departure_leg_id]
                    if not dep_leg.is_departure:
                        reasons.append(
                            f"DIRECTION_MISMATCH: departure leg '{pair.departure_leg_id}' has direction {dep_leg.direction}."
                        )

            # Check 4: Unmatched leg structural consistency
            if pair.pair_type == PairType.UNMATCHED_ARR:
                if pair.departure_leg_id is not None:
                    reasons.append("UNMATCHED_ARR_WITH_DEPARTURE: UNMATCHED_ARR cannot specify departure_leg_id.")
                if pair.arrival_leg_id is None:
                    reasons.append("UNMATCHED_ARR_WITHOUT_ARRIVAL: UNMATCHED_ARR must specify arrival_leg_id.")
            elif pair.pair_type == PairType.UNMATCHED_DEP:
                if pair.arrival_leg_id is not None:
                    reasons.append("UNMATCHED_DEP_WITH_ARRIVAL: UNMATCHED_DEP cannot specify arrival_leg_id.")
                if pair.departure_leg_id is None:
                    reasons.append("UNMATCHED_DEP_WITHOUT_DEPARTURE: UNMATCHED_DEP must specify departure_leg_id.")
            elif pair.is_paired:
                if pair.arrival_leg_id is None or pair.departure_leg_id is None:
                    reasons.append("PAIRED_TURN_INCOMPLETE: Paired turn must have both arrival and departure legs.")

            # Check 5: Strict Aircraft Evidence for VERIFIED_PAIR
            if pair.pair_type == PairType.VERIFIED_PAIR:
                if arr_leg and dep_leg:
                    has_arr_tail = arr_leg.has_verified_aircraft
                    has_dep_tail = dep_leg.has_verified_aircraft
                    tails_match = (
                        has_arr_tail
                        and has_dep_tail
                        and arr_leg.tail_number.strip().upper() == dep_leg.tail_number.strip().upper()  # type: ignore
                    )
                    is_verified_source = pair.linkage_source == LinkageSource.VERIFIED_ROTATION

                    if not (has_arr_tail and has_dep_tail and tails_match and is_verified_source):
                        reasons.append(
                            "UNVERIFIED_AIRCRAFT_EVIDENCE_FOR_VERIFIED_PAIR: Cannot promote pair to VERIFIED_PAIR "
                            "without matching verified tail numbers and authenticated rotation provenance."
                        )
                else:
                    reasons.append("UNVERIFIED_AIRCRAFT_EVIDENCE_FOR_VERIFIED_PAIR: Missing leg references.")

            # Check 6: Chronological Monotonicity (ARR <= DEP at ATL)
            turnaround_min = pair.scheduled_turnaround_min
            if arr_leg and dep_leg:
                # Compare UTC if available, else local
                arr_time = arr_leg.scheduled_event_utc or arr_leg.scheduled_event_local
                dep_time = dep_leg.scheduled_event_utc or dep_leg.scheduled_event_local

                if arr_time > dep_time:
                    reasons.append(
                        f"CHRONOLOGICAL_REVERSAL_DEP_BEFORE_ARR: arrival at {arr_time.isoformat()} "
                        f"is after departure at {dep_time.isoformat()}."
                    )
                else:
                    calculated_turnaround = (dep_time - arr_time).total_seconds() / 60.0
                    if calculated_turnaround < self.min_turnaround_min:
                        reasons.append(
                            f"NEGATIVE_TURNAROUND_TIME: turnaround {calculated_turnaround:.1f}m is below minimum {self.min_turnaround_min}m."
                        )
                    if turnaround_min is None:
                        turnaround_min = calculated_turnaround

            # Check 7: Synthetic pair scenario provenance
            if pair.pair_type == PairType.SYNTHETIC_PAIR:
                if not pair.scenario_id and not pair.session_id:
                    reasons.append(
                        "SYNTHETIC_PAIR_MISSING_SCENARIO_PROVENANCE: Synthetic pair must have scenario_id or session_id."
                    )

            # Check 8: Temporal Causality on individual legs
            for leg in (arr_leg, dep_leg):
                if leg:
                    _, causality_errs = validate_temporal_causality(
                        prediction_generated_at_utc=leg.prediction_generated_at_utc,
                        planning_snapshot_at_utc=leg.planning_snapshot_at_utc,
                        model_prediction_cutoff_utc=leg.model_prediction_cutoff_utc,
                        scheduled_event_utc=leg.scheduled_event_utc,
                    )
                    reasons.extend(causality_errs)

            # Determine final status
            if reasons:
                for r in reasons:
                    base_reason = r.split(":")[0].strip()
                    rejection_tally[base_reason] += 1

                if any("UNVERIFIED_AIRCRAFT_EVIDENCE" in r for r in reasons):
                    current_status = ValidationStatus.QUARANTINED
                else:
                    current_status = ValidationStatus.INVALID
            else:
                current_status = ValidationStatus.VALID

            validated_pair = TurnPair(
                pair_id=pair.pair_id,
                arrival_leg_id=pair.arrival_leg_id,
                departure_leg_id=pair.departure_leg_id,
                pair_type=pair.pair_type,
                linkage_source=pair.linkage_source,
                validation_status=current_status,
                scheduled_turnaround_min=turnaround_min,
                scenario_id=pair.scenario_id,
                session_id=pair.session_id,
                evidence_metadata=pair.evidence_metadata,
                rejection_reasons=tuple(reasons),
            )
            validated_pairs.append(validated_pair)

            # Summary tally
            if current_status == ValidationStatus.VALID:
                summary.valid_pairs_count += 1
            elif current_status == ValidationStatus.INVALID:
                summary.invalid_pairs_count += 1
            elif current_status == ValidationStatus.QUARANTINED:
                summary.quarantined_pairs_count += 1
            elif current_status == ValidationStatus.REVIEW_REQUIRED:
                summary.review_required_count += 1

            if pair.pair_type == PairType.SYNTHETIC_PAIR:
                summary.synthetic_pairs_count += 1
            elif pair.pair_type == PairType.VERIFIED_PAIR:
                summary.verified_pairs_count += 1
            elif pair.pair_type == PairType.UNMATCHED_ARR:
                summary.unmatched_arr_count += 1
            elif pair.pair_type == PairType.UNMATCHED_DEP:
                summary.unmatched_dep_count += 1

        summary.rejection_reasons_tally = dict(rejection_tally)
        return validated_pairs, summary


def validate_cpsat_turnaround_schedule_csv(
    csv_path: Path | str,
) -> dict[str, Any]:
    """Audits and parses the 1,500 flight CPSAT turnaround schedule fixture.

    Enforces:
    - Exactly 1,500 records.
    - 745 ARR, 755 DEP.
    - 649 PAIRED_TURN sessions (1298 records).
    - 96 UNMATCHED_ARR records.
    - 106 UNMATCHED_DEP records.
    - Strictly classifies as SYNTHETIC_PAIR, UNMATCHED_ARR, UNMATCHED_DEP.
    - Confirms simulation outputs are quarantined from ML predictors.
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Fixture CSV not found at {path}")

    df = pd.read_csv(path)
    n_total = len(df)
    if n_total != 1500:
        raise ValueError(f"Expected exactly 1500 records, got {n_total}")

    direction_counts = df["direction"].value_counts().to_dict()
    n_arr = direction_counts.get("ARR", 0)
    n_dep = direction_counts.get("DEP", 0)

    if n_arr != 745 or n_dep != 755:
        raise ValueError(f"Expected 745 ARR and 755 DEP, got ARR={n_arr}, DEP={n_dep}")

    session_counts = df["session_type"].value_counts().to_dict()
    n_paired_rows = session_counts.get("PAIRED_TURN", 0)
    n_unmatched_arr_rows = session_counts.get("UNMATCHED_ARR", 0)
    n_unmatched_dep_rows = session_counts.get("UNMATCHED_DEP", 0)

    if n_paired_rows != 1298 or n_unmatched_arr_rows != 96 or n_unmatched_dep_rows != 106:
        raise ValueError(
            f"Expected 1298 PAIRED_TURN, 96 UNMATCHED_ARR, 106 UNMATCHED_DEP; "
            f"got {n_paired_rows}, {n_unmatched_arr_rows}, {n_unmatched_dep_rows}"
        )

    # Reference operational date for the fixture: 2024-01-01
    ref_date = date(2024, 1, 1)
    ref_epoch_utc = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
    atl_tz = ZoneInfo("America/New_York")

    # Build FlightLegs
    legs: dict[str, FlightLeg] = {}
    for _, row in df.iterrows():
        fkey = str(row["flight_key"])
        direction = LegDirection.ARR if str(row["direction"]).strip().upper() == "ARR" else LegDirection.DEP
        sched_min = int(row["sched_time_min"])
        h = (sched_min // 60) % 24
        m = sched_min % 60
        day_offset = sched_min // 1440
        flight_dt_local = datetime(
            ref_date.year,
            ref_date.month,
            ref_date.day + day_offset,
            h,
            m,
            tzinfo=atl_tz,
        )
        flight_dt_utc = flight_dt_local.astimezone(timezone.utc)

        # Prediction cutoff T-2h
        cutoff_utc = flight_dt_utc - pd.Timedelta(hours=2)
        # Planning snapshot at T-3h
        snapshot_utc = flight_dt_utc - pd.Timedelta(hours=3)
        # Prediction generated at T-3h
        pred_gen_utc = flight_dt_utc - pd.Timedelta(hours=3)

        leg = FlightLeg(
            flight_id=fkey,
            direction=direction,
            carrier=str(row["carrier"]),
            flight_number=str(row["fl_num"]),
            origin=str(row["origin"]),
            destination=str(row["dest"]),
            scheduled_event_local=flight_dt_local,
            scheduled_event_utc=flight_dt_utc,
            event_timezone="America/New_York",
            scheduled_elapsed_min=float(row.get("dwell_time_min", 45.0)),
            model_prediction_cutoff_utc=cutoff_utc,
            planning_snapshot_at_utc=snapshot_utc,
            prediction_generated_at_utc=pred_gen_utc,
            prediction_provenance="synthetic_cpsat_fixture_v1",
            scenario_id="atl_1500_cpsat_turnaround",
            session_id=str(row["session_id"]),
            aircraft_type=str(row.get("aircraft_type", "NARROWBODY")),
            tail_number=None,  # Crucial: sim_aircraft_id is synthetic, not verified physical tail!
            normalized_timeline_min=sched_min,
            raw_metadata={
                "sim_aircraft_id": str(row.get("sim_aircraft_id")),
                "chain_group_id": str(row.get("chain_group_id")),
                "assigned_gate_sim": str(row.get("assigned_gate")),
                "actual_delay_min_sim": float(row.get("actual_delay_min", 0.0)),
                "p_delay_sim": float(row.get("p_delay", 0.0)),
            },
        )
        legs[fkey] = leg

    # Build TurnPairs by session
    pairs: list[TurnPair] = []
    sessions = df.groupby("session_id")
    for sess_id, grp in sessions:
        stype = grp["session_type"].iloc[0]
        if stype == "PAIRED_TURN":
            arr_rows = grp[grp["direction"] == "ARR"]
            dep_rows = grp[grp["direction"] == "DEP"]
            if len(arr_rows) != 1 or len(dep_rows) != 1:
                raise ValueError(f"Session {sess_id} has unexpected leg counts: ARR={len(arr_rows)}, DEP={len(dep_rows)}")
            arr_fkey = str(arr_rows["flight_key"].iloc[0])
            dep_fkey = str(dep_rows["flight_key"].iloc[0])
            arr_sched = int(arr_rows["sched_time_min"].iloc[0])
            dep_sched = int(dep_rows["sched_time_min"].iloc[0])
            turn_min = float(dep_sched - arr_sched)

            tp = TurnPair(
                pair_id=f"PAIR_{sess_id}",
                arrival_leg_id=arr_fkey,
                departure_leg_id=dep_fkey,
                pair_type=PairType.SYNTHETIC_PAIR,
                linkage_source=LinkageSource.SIMULATION_SESSION,
                validation_status=ValidationStatus.VALID,
                scheduled_turnaround_min=turn_min,
                scenario_id="atl_1500_cpsat_turnaround",
                session_id=str(sess_id),
                evidence_metadata={
                    "sim_aircraft_id": str(grp["sim_aircraft_id"].iloc[0]),
                    "chain_group_id": str(grp["chain_group_id"].iloc[0]),
                },
            )
            pairs.append(tp)

        elif stype == "UNMATCHED_ARR":
            for _, r in grp.iterrows():
                fkey = str(r["flight_key"])
                tp = TurnPair(
                    pair_id=f"PAIR_{sess_id}_{fkey}",
                    arrival_leg_id=fkey,
                    departure_leg_id=None,
                    pair_type=PairType.UNMATCHED_ARR,
                    linkage_source=LinkageSource.UNPAIRED,
                    validation_status=ValidationStatus.VALID,
                    scenario_id="atl_1500_cpsat_turnaround",
                    session_id=str(sess_id),
                )
                pairs.append(tp)

        elif stype == "UNMATCHED_DEP":
            for _, r in grp.iterrows():
                fkey = str(r["flight_key"])
                tp = TurnPair(
                    pair_id=f"PAIR_{sess_id}_{fkey}",
                    arrival_leg_id=None,
                    departure_leg_id=fkey,
                    pair_type=PairType.UNMATCHED_DEP,
                    linkage_source=LinkageSource.UNPAIRED,
                    validation_status=ValidationStatus.VALID,
                    scenario_id="atl_1500_cpsat_turnaround",
                    session_id=str(sess_id),
                )
                pairs.append(tp)

    # Validate pairs using PairingValidator
    validator = PairingValidator()
    validated_pairs, summary = validator.validate_pairs(legs, pairs)

    return {
        "status": "PASS" if summary.is_clean else "FAIL",
        "total_records": n_total,
        "total_legs": len(legs),
        "total_pairs": len(pairs),
        "synthetic_pairs": summary.synthetic_pairs_count,
        "verified_pairs": summary.verified_pairs_count,
        "unmatched_arr": summary.unmatched_arr_count,
        "unmatched_dep": summary.unmatched_dep_count,
        "valid_pairs": summary.valid_pairs_count,
        "invalid_pairs": summary.invalid_pairs_count,
        "quarantined_pairs": summary.quarantined_pairs_count,
        "is_clean": summary.is_clean,
        "legs": legs,
        "pairs": validated_pairs,
        "summary": summary,
    }
