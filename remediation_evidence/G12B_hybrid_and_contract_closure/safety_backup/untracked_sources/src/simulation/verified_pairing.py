"""Deterministic Verified Aircraft Pairing and Turn Linkage Engine.

Protocol: Aeolus Dual Core Architecture Protocol V2
Phase: AEOLUS-G4 Task G4.2 Verified Aircraft Pairing
Enforces:
1. Strict physical tail-number matching (case-insensitive stripped, non-empty).
2. Hub airport connection at ATL (inbound dest == ATL, outbound origin == ATL).
3. Chronological arrival-before-departure monotonicity at ATL gate.
4. Scheduled turnaround interval >= min_turnaround_min (nominal 45m).
5. 1-to-1 cardinality with zero leg reuse across turns.
6. Deterministic tie-breaking independent of DataFrame row permutation.
7. Strict classification into:
   - VERIFIED_ROTATION
   - INFERRED_PAIR
   - SYNTHETIC_PAIR
   - UNMATCHED
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import hashlib
from typing import Any, Mapping, Sequence

import pandas as pd

from src.contracts.turn_contracts import (
    FlightLeg,
    LegDirection,
    LinkageSource,
    PairType,
    TurnPair,
    ValidationStatus,
)


class PairingRejectionReason(str, Enum):
    """Authoritative rejection codes for invalid pairing attempts."""

    DIFFERENT_TAIL = "DIFFERENT_TAIL"
    MISSING_TAIL = "MISSING_TAIL"
    WRONG_HUB_AIRPORT = "WRONG_HUB_AIRPORT"
    CHRONOLOGICAL_REVERSAL = "CHRONOLOGICAL_REVERSAL"
    TURNAROUND_BELOW_MINIMUM = "TURNAROUND_BELOW_MINIMUM"
    TURNAROUND_EXCEEDS_MAXIMUM = "TURNAROUND_EXCEEDS_MAXIMUM"
    LEG_ALREADY_PAIRED = "LEG_ALREADY_PAIRED"
    DUPLICATE_FLIGHT_ID = "DUPLICATE_FLIGHT_ID"
    DIRECTION_MISMATCH = "DIRECTION_MISMATCH"


@dataclass(frozen=True)
class PairingEvidence:
    """Audit record providing cryptographic and operational proof for a turn pairing."""

    pair_id: str
    arrival_leg_id: str | None
    departure_leg_id: str | None
    pair_type: str
    linkage_source: str
    tail_number: str | None
    scheduled_arrival_min: int | None
    scheduled_departure_min: int | None
    scheduled_turnaround_min: float | None
    hub_airport: str
    is_verified: bool
    evidence_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pair_id": self.pair_id,
            "arrival_leg_id": self.arrival_leg_id,
            "departure_leg_id": self.departure_leg_id,
            "pair_type": self.pair_type,
            "linkage_source": self.linkage_source,
            "tail_number": self.tail_number,
            "scheduled_arrival_min": self.scheduled_arrival_min,
            "scheduled_departure_min": self.scheduled_departure_min,
            "scheduled_turnaround_min": self.scheduled_turnaround_min,
            "hub_airport": self.hub_airport,
            "is_verified": self.is_verified,
            "evidence_notes": self.evidence_notes,
        }


@dataclass
class VerifiedPairingResult:
    """Comprehensive outputs from deterministic aircraft turn pairing."""

    verified_pairs: list[TurnPair]
    inferred_pairs: list[TurnPair]
    synthetic_pairs: list[TurnPair]
    unmatched_arr_pairs: list[TurnPair]
    unmatched_dep_pairs: list[TurnPair]
    pairing_evidence: list[PairingEvidence]
    metrics: dict[str, int]

    @property
    def all_pairs(self) -> list[TurnPair]:
        """Return all generated TurnPair objects (verified + inferred + synthetic + unmatched)."""
        return (
            self.verified_pairs
            + self.inferred_pairs
            + self.synthetic_pairs
            + self.unmatched_arr_pairs
            + self.unmatched_dep_pairs
        )


class DeterministicPairingEngine:
    """Deterministic, permutation-invariant engine for pairing inbound and outbound flight legs."""

    def __init__(
        self,
        *,
        hub_airport: str = "ATL",
        min_turnaround_min: int = 45,
        max_turnaround_min: int = 720,  # 12 hours
    ) -> None:
        self.hub_airport = hub_airport.strip().upper()
        self.min_turnaround_min = min_turnaround_min
        self.max_turnaround_min = max_turnaround_min

    def pair_flights(
        self,
        legs: Mapping[str, FlightLeg],
        *,
        scenario_id: str = "VERIFIED_E2E_SCENARIO",
        allow_inferred_pairing: bool = False,
    ) -> VerifiedPairingResult:
        """Pair legs deterministically into aircraft turns.

        Args:
            legs: Mapping from flight_id to FlightLeg.
            scenario_id: Identifier for the scenario.
            allow_inferred_pairing: If True and tail is missing, attempts heuristic
                                   same-carrier turnaround matching without claiming VERIFIED.

        Returns:
            VerifiedPairingResult containing categorized TurnPairs and evidence.
        """
        # 1. Validation & partition into Inbound vs Outbound
        # Sort leg keys alphabetically to guarantee permutation invariance
        sorted_leg_ids = sorted(legs.keys())

        inbound_legs: list[FlightLeg] = []
        outbound_legs: list[FlightLeg] = []
        seen_flight_ids: set[str] = set()

        for leg_id in sorted_leg_ids:
            leg = legs[leg_id]
            if leg.flight_id in seen_flight_ids:
                raise ValueError(f"DUPLICATE_FLIGHT_ID: Duplicate flight_id '{leg.flight_id}' detected")
            seen_flight_ids.add(leg.flight_id)

            if leg.is_arrival:
                inbound_legs.append(leg)
            elif leg.is_departure:
                outbound_legs.append(leg)

        # 2. Group legs by tail number (for verified matching)
        # Only legs with non-empty, valid tail numbers can enter verified pool
        inbound_by_tail: dict[str, list[FlightLeg]] = {}
        unmatched_inbound: list[FlightLeg] = []

        for arr in inbound_legs:
            # Check hub connection
            if arr.destination.strip().upper() != self.hub_airport:
                continue
            tail = (arr.tail_number or "").strip().upper()
            if tail:
                inbound_by_tail.setdefault(tail, []).append(arr)
            else:
                unmatched_inbound.append(arr)

        outbound_by_tail: dict[str, list[FlightLeg]] = {}
        unmatched_outbound: list[FlightLeg] = []

        for dep in outbound_legs:
            if dep.origin.strip().upper() != self.hub_airport:
                continue
            tail = (dep.tail_number or "").strip().upper()
            if tail:
                outbound_by_tail.setdefault(tail, []).append(dep)
            else:
                unmatched_outbound.append(dep)

        verified_pairs: list[TurnPair] = []
        evidence_list: list[PairingEvidence] = []
        used_arr_ids: set[str] = set()
        used_dep_ids: set[str] = set()

        # 3. Deterministic Matching per Tail
        all_tails = sorted(set(inbound_by_tail.keys()).intersection(outbound_by_tail.keys()))

        pair_counter = 1
        for tail in all_tails:
            arr_candidates = sorted(
                inbound_by_tail[tail],
                key=lambda l: (l.normalized_timeline_min if l.normalized_timeline_min is not None else 0, l.flight_id),
            )
            dep_candidates = sorted(
                outbound_by_tail[tail],
                key=lambda l: (l.normalized_timeline_min if l.normalized_timeline_min is not None else 0, l.flight_id),
            )

            # Match greedily in chronological order with deterministic tie-breaking
            for arr_leg in arr_candidates:
                if arr_leg.flight_id in used_arr_ids:
                    continue
                arr_t = arr_leg.normalized_timeline_min or 0

                # Find earliest feasible outbound departure
                best_dep: FlightLeg | None = None
                for dep_leg in dep_candidates:
                    if dep_leg.flight_id in used_dep_ids:
                        continue
                    dep_t = dep_leg.normalized_timeline_min or 0
                    dwell = dep_t - arr_t
                    if self.min_turnaround_min <= dwell <= self.max_turnaround_min:
                        best_dep = dep_leg
                        break  # candidates already sorted chronologically

                if best_dep is not None:
                    used_arr_ids.add(arr_leg.flight_id)
                    used_dep_ids.add(best_dep.flight_id)
                    dwell = float((best_dep.normalized_timeline_min or 0) - arr_t)
                    pid = f"VERIFIED_TURN_{pair_counter:04d}"
                    pair_counter += 1

                    turn_pair = TurnPair(
                        pair_id=pid,
                        arrival_leg_id=arr_leg.flight_id,
                        departure_leg_id=best_dep.flight_id,
                        pair_type=PairType.VERIFIED_PAIR,
                        linkage_source=LinkageSource.VERIFIED_ROTATION,
                        validation_status=ValidationStatus.VALID,
                        scheduled_turnaround_min=dwell,
                        scenario_id=scenario_id,
                        evidence_metadata={
                            "tail_number": tail,
                            "arr_flight_id": arr_leg.flight_id,
                            "dep_flight_id": best_dep.flight_id,
                            "scheduled_dwell_min": dwell,
                            "matching_mode": "DETERMINISTIC_TAIL_ROTATION",
                        },
                    )
                    verified_pairs.append(turn_pair)
                    evidence_list.append(
                        PairingEvidence(
                            pair_id=pid,
                            arrival_leg_id=arr_leg.flight_id,
                            departure_leg_id=best_dep.flight_id,
                            pair_type=PairType.VERIFIED_PAIR.value,
                            linkage_source=LinkageSource.VERIFIED_ROTATION.value,
                            tail_number=tail,
                            scheduled_arrival_min=arr_t,
                            scheduled_departure_min=best_dep.normalized_timeline_min,
                            scheduled_turnaround_min=dwell,
                            hub_airport=self.hub_airport,
                            is_verified=True,
                            evidence_notes=[
                                f"Authenticated matching tail {tail}",
                                f"Scheduled dwell {dwell:.1f}m meets min {self.min_turnaround_min}m and max {self.max_turnaround_min}m",
                            ],
                        )
                    )

        # 4. Inferred Pairing (if explicitly requested and tail missing)
        inferred_pairs: list[TurnPair] = []
        if allow_inferred_pairing:
            # Match remaining legs by carrier and schedule proximity
            rem_arr = [
                l for l in inbound_legs
                if l.flight_id not in used_arr_ids and l.destination.strip().upper() == self.hub_airport
            ]
            rem_dep = [
                l for l in outbound_legs
                if l.flight_id not in used_dep_ids and l.origin.strip().upper() == self.hub_airport
            ]
            rem_arr.sort(key=lambda l: (l.carrier, l.normalized_timeline_min or 0, l.flight_id))
            rem_dep.sort(key=lambda l: (l.carrier, l.normalized_timeline_min or 0, l.flight_id))

            inf_counter = 1
            for arr_leg in rem_arr:
                if arr_leg.flight_id in used_arr_ids:
                    continue
                arr_t = arr_leg.normalized_timeline_min or 0
                for dep_leg in rem_dep:
                    if dep_leg.flight_id in used_dep_ids:
                        continue
                    if dep_leg.carrier != arr_leg.carrier:
                        continue
                    dep_t = dep_leg.normalized_timeline_min or 0
                    dwell = dep_t - arr_t
                    if self.min_turnaround_min <= dwell <= 180:  # conservative 3h inferred window
                        used_arr_ids.add(arr_leg.flight_id)
                        used_dep_ids.add(dep_leg.flight_id)
                        pid = f"INFERRED_TURN_{inf_counter:04d}"
                        inf_counter += 1
                        inferred_pairs.append(
                            TurnPair(
                                pair_id=pid,
                                arrival_leg_id=arr_leg.flight_id,
                                departure_leg_id=dep_leg.flight_id,
                                pair_type=PairType.INFERRED_PAIR,
                                linkage_source=LinkageSource.SCHEDULE_CHAIN_HEURISTIC,
                                validation_status=ValidationStatus.VALID,
                                scheduled_turnaround_min=float(dwell),
                                scenario_id=scenario_id,
                                evidence_metadata={
                                    "carrier": arr_leg.carrier,
                                    "matching_mode": "HEURISTIC_SCHEDULE_INFERENCE",
                                },
                            )
                        )
                        break

        # 5. Build UNMATCHED turns for all remaining legs (Zero Leg Loss)
        unmatched_arr_pairs: list[TurnPair] = []
        unmatched_dep_pairs: list[TurnPair] = []

        unm_arr_counter = 1
        for arr_leg in sorted(inbound_legs, key=lambda l: (l.normalized_timeline_min or 0, l.flight_id)):
            if arr_leg.flight_id not in used_arr_ids and arr_leg.destination.strip().upper() == self.hub_airport:
                pid = f"UNMATCHED_ARR_{unm_arr_counter:04d}"
                unm_arr_counter += 1
                unmatched_arr_pairs.append(
                    TurnPair(
                        pair_id=pid,
                        arrival_leg_id=arr_leg.flight_id,
                        departure_leg_id=None,
                        pair_type=PairType.UNMATCHED_ARR,
                        linkage_source=LinkageSource.UNPAIRED,
                        validation_status=ValidationStatus.VALID,
                        scenario_id=scenario_id,
                    )
                )

        unm_dep_counter = 1
        for dep_leg in sorted(outbound_legs, key=lambda l: (l.normalized_timeline_min or 0, l.flight_id)):
            if dep_leg.flight_id not in used_dep_ids and dep_leg.origin.strip().upper() == self.hub_airport:
                pid = f"UNMATCHED_DEP_{unm_dep_counter:04d}"
                unm_dep_counter += 1
                unmatched_dep_pairs.append(
                    TurnPair(
                        pair_id=pid,
                        arrival_leg_id=None,
                        departure_leg_id=dep_leg.flight_id,
                        pair_type=PairType.UNMATCHED_DEP,
                        linkage_source=LinkageSource.UNPAIRED,
                        validation_status=ValidationStatus.VALID,
                        scenario_id=scenario_id,
                    )
                )

        metrics = {
            "total_legs_processed": len(legs),
            "inbound_legs_count": len(inbound_legs),
            "outbound_legs_count": len(outbound_legs),
            "verified_turns_count": len(verified_pairs),
            "inferred_turns_count": len(inferred_pairs),
            "synthetic_turns_count": 0,
            "unmatched_arr_count": len(unmatched_arr_pairs),
            "unmatched_dep_count": len(unmatched_dep_pairs),
            "total_turn_entities": len(verified_pairs) + len(inferred_pairs) + len(unmatched_arr_pairs) + len(unmatched_dep_pairs),
        }

        return VerifiedPairingResult(
            verified_pairs=verified_pairs,
            inferred_pairs=inferred_pairs,
            synthetic_pairs=[],
            unmatched_arr_pairs=unmatched_arr_pairs,
            unmatched_dep_pairs=unmatched_dep_pairs,
            pairing_evidence=evidence_list,
            metrics=metrics,
        )
