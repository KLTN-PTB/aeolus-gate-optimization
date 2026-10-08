"""Dual prediction aircraft turn engine with legacy parity.

Protocol: Aeolus Dual Core Architecture Protocol V2
Phase: P7 Dual Prediction Turn Engine with Legacy Parity
Task: Turn synthesis integrating Core Arrival and Core Departure with legacy bit-for-bit parity,
      sensitivity coupling, and operational causality firewalls.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import math
from typing import Any, Final

import numpy as np
import pandas as pd

from src.contracts.distribution import PredictiveDistribution
from src.contracts.turn_contracts import (
    FlightLeg,
    LegDirection,
    PairType,
    TurnPair,
    ValidationStatus,
)
from src.optimization.domain import Flight, FlightTimeWindow


class SimulationMode(str, Enum):
    """Operational simulation modes for turn synthesis."""

    ARRIVAL_ONLY_LEGACY = "ARRIVAL_ONLY_LEGACY"
    DUAL_POINT = "DUAL_POINT"
    DUAL_PROBABILISTIC = "DUAL_PROBABILISTIC"


class CouplingAssumption(str, Enum):
    """Coupling assumptions for joint arrival-departure delay uncertainty.

    Note: These are explicitly labeled as sensitivity scenarios, NOT empirically
    validated joint models from historical data without physical aircraft tracking.
    """

    INDEPENDENT = "INDEPENDENT"
    COMONOTONIC = "COMONOTONIC"
    COUNTERMONOTONIC = "COUNTERMONOTONIC"


@dataclass(frozen=True)
class LegPrediction:
    """Immutable single-leg signed delay prediction with complete provenance."""

    leg_id: str
    direction: LegDirection
    task: str
    predicted_delay_min: float
    unit: str = "minutes"
    model_id: str = ""
    model_version: str = "v1"
    prediction_cutoff_utc: datetime | None = None
    prediction_generated_at_utc: datetime | None = None
    feature_manifest_hash: str | None = None
    sample_seed: int | None = None
    provenance_metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self, planning_snapshot_at_utc: datetime | None = None) -> list[str]:
        """Validates prediction integrity, causality, and provenance."""
        errors: list[str] = []

        if not self.leg_id:
            errors.append("EMPTY_LEG_ID: Prediction leg_id cannot be empty.")

        if not math.isfinite(self.predicted_delay_min):
            errors.append(f"NON_FINITE_DELAY: Predicted delay {self.predicted_delay_min} is not finite.")

        if self.unit.lower() not in ("minutes", "min", "m"):
            errors.append(f"INVALID_UNIT: Prediction unit must be minutes, got '{self.unit}'.")

        if not self.model_id:
            errors.append("MISSING_MODEL_ID: Prediction must specify model_id.")

        # Task and direction alignment
        if self.direction == LegDirection.ARR and "arrival" not in self.task.lower():
            errors.append(f"TASK_DIRECTION_MISMATCH: Arrival leg has non-arrival task '{self.task}'.")
        elif self.direction == LegDirection.DEP and "departure" not in self.task.lower():
            errors.append(f"TASK_DIRECTION_MISMATCH: Departure leg has non-departure task '{self.task}'.")

        # Operational causality
        if (
            planning_snapshot_at_utc is not None
            and self.prediction_generated_at_utc is not None
            and self.prediction_generated_at_utc > planning_snapshot_at_utc
        ):
            errors.append(
                f"PREDICTION_POSTDATES_PLANNING_SNAPSHOT: Prediction generated at {self.prediction_generated_at_utc.isoformat()} "
                f"after planning snapshot at {planning_snapshot_at_utc.isoformat()}."
            )

        return errors


@dataclass(frozen=True)
class DualAircraftTurn:
    """Synthesized operational aircraft turn entity at the hub gate.

    Represents half-open gate occupancy interval [simulated_arrival_min, gate_release_min).
    """

    turn_id: str
    arrival_leg_id: str | None
    departure_leg_id: str | None
    carrier: str
    flight_number: str
    mode: SimulationMode
    pair_type: PairType

    scheduled_arrival_min: int
    scheduled_departure_min: int
    predicted_arrival_delay_min: float
    predicted_departure_delay_min: float | None

    simulated_arrival_min: int
    departure_ml_min: int | None
    earliest_physical_departure_min: int
    simulated_departure_min: int
    gate_release_min: int

    min_turnaround_min: int = 45
    default_dwell_min: int = 60
    separation_buffer_min: int = 15
    nominal_gate_id: str | None = None
    aircraft_type: str | None = None

    unmatched_status: str | None = None
    coupling_assumption: str | None = None
    provenance_metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def occupancy_interval(self) -> tuple[int, int]:
        """Half-open gate occupancy interval [simulated_arrival_min, gate_release_min)."""
        return (self.simulated_arrival_min, self.gate_release_min)

    @property
    def gate_in_min(self) -> int:
        return self.simulated_arrival_min

    @property
    def gate_out_min(self) -> int:
        return self.simulated_departure_min

    @property
    def physical_dwell_min(self) -> int:
        return max(0, self.simulated_departure_min - self.simulated_arrival_min)

    @property
    def turnaround_slack_min(self) -> int:
        return self.physical_dwell_min - self.min_turnaround_min

    @property
    def occupancy_duration_min(self) -> int:
        return max(0, self.gate_release_min - self.simulated_arrival_min)

    @property
    def time_window(self) -> FlightTimeWindow:
        return FlightTimeWindow(
            start_min=self.simulated_arrival_min,
            end_min=self.gate_release_min,
            buffer_min=self.separation_buffer_min,
        )

    def to_flight(self, flight_index: int = 0, *, dual_core_enabled: bool = False) -> Flight:
        """Converts this turn entity to an optimization domain Flight object.

        If dual_core_enabled is True and mode is not ARRIVAL_ONLY_LEGACY,
        passes precomputed_gate_out_min to inform solver of validated departure ML pushback.
        Otherwise (default), sets precomputed_gate_out_min=None to maintain 100% legacy parity.
        """
        gate_out = (
            self.simulated_departure_min
            if (dual_core_enabled and self.mode != SimulationMode.ARRIVAL_ONLY_LEGACY)
            else None
        )
        return Flight(
            flight_id=self.turn_id,
            flight_index=flight_index,
            carrier=self.carrier,
            flight_number=self.flight_number,
            scheduled_arrival_min=self.scheduled_arrival_min,
            scheduled_departure_min=self.scheduled_departure_min,
            predicted_arrival_min=self.simulated_arrival_min,
            nominal_gate_id=self.nominal_gate_id,
            aircraft_type=self.aircraft_type,
            min_turnaround_min=self.min_turnaround_min,
            default_dwell_min=self.default_dwell_min,
            buffer_min=self.separation_buffer_min,
            is_paired=self.pair_type in (PairType.VERIFIED_PAIR, PairType.SYNTHETIC_PAIR),
            precomputed_gate_out_min=gate_out,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "arrival_leg_id": self.arrival_leg_id,
            "departure_leg_id": self.departure_leg_id,
            "carrier": self.carrier,
            "flight_number": self.flight_number,
            "mode": self.mode.value,
            "pair_type": self.pair_type.value,
            "scheduled_arrival_min": self.scheduled_arrival_min,
            "scheduled_departure_min": self.scheduled_departure_min,
            "predicted_arrival_delay_min": self.predicted_arrival_delay_min,
            "predicted_departure_delay_min": self.predicted_departure_delay_min,
            "simulated_arrival_min": self.simulated_arrival_min,
            "departure_ml_min": self.departure_ml_min,
            "earliest_physical_departure_min": self.earliest_physical_departure_min,
            "simulated_departure_min": self.simulated_departure_min,
            "gate_release_min": self.gate_release_min,
            "occupancy_duration_min": self.occupancy_duration_min,
            "min_turnaround_min": self.min_turnaround_min,
            "separation_buffer_min": self.separation_buffer_min,
            "unmatched_status": self.unmatched_status,
            "coupling_assumption": self.coupling_assumption,
        }


class DualTurnEngine:
    """Engine for synthesizing aircraft turns under legacy and dual prediction regimes."""

    def __init__(
        self,
        *,
        min_turnaround_min: int = 45,
        default_dwell_min: int = 60,
        separation_buffer_min: int = 15,
    ) -> None:
        if min_turnaround_min <= 0:
            raise ValueError("min_turnaround_min must be positive")
        if default_dwell_min <= 0:
            raise ValueError("default_dwell_min must be positive")
        if separation_buffer_min < 0:
            raise ValueError("separation_buffer_min cannot be negative")

        self.min_turnaround_min = min_turnaround_min
        self.default_dwell_min = default_dwell_min
        self.separation_buffer_min = separation_buffer_min

    def synthesize_turn(
        self,
        pair: TurnPair,
        legs: Mapping[str, FlightLeg],
        arrival_prediction: LegPrediction | float,
        departure_prediction: LegPrediction | float | None = None,
        *,
        mode: SimulationMode = SimulationMode.DUAL_POINT,
        planning_snapshot_at_utc: datetime | None = None,
        nominal_gate_id: str | None = None,
        coupling_assumption: CouplingAssumption | None = None,
    ) -> DualAircraftTurn:
        """Synthesizes an operational aircraft turn respecting physical constraints."""
        arr_leg = legs.get(pair.arrival_leg_id) if pair.arrival_leg_id else None
        dep_leg = legs.get(pair.departure_leg_id) if pair.departure_leg_id else None

        # Resolve arrival delay value and validate
        if isinstance(arrival_prediction, LegPrediction):
            errs = arrival_prediction.validate(planning_snapshot_at_utc)
            if errs:
                raise ValueError(f"Invalid arrival prediction for {arrival_prediction.leg_id}: {'; '.join(errs)}")
            delta_arr = float(arrival_prediction.predicted_delay_min)
            arr_pred_obj = arrival_prediction
        else:
            delta_arr = float(arrival_prediction)
            arr_pred_obj = None

        # Resolve departure delay value and validate
        if isinstance(departure_prediction, LegPrediction):
            errs = departure_prediction.validate(planning_snapshot_at_utc)
            if errs:
                raise ValueError(f"Invalid departure prediction for {departure_prediction.leg_id}: {'; '.join(errs)}")
            delta_dep = float(departure_prediction.predicted_delay_min)
            dep_pred_obj = departure_prediction
        elif departure_prediction is not None:
            delta_dep = float(departure_prediction)
            dep_pred_obj = None
        else:
            delta_dep = None
            dep_pred_obj = None

        carrier = (arr_leg.carrier if arr_leg else (dep_leg.carrier if dep_leg else "UNK"))
        flight_number = (arr_leg.flight_number if arr_leg else (dep_leg.flight_number if dep_leg else "000"))
        aircraft_type = (arr_leg.aircraft_type if arr_leg else (dep_leg.aircraft_type if dep_leg else "NARROWBODY"))

        # Scheduled arrival clock (timeline minutes)
        if arr_leg and arr_leg.normalized_timeline_min is not None:
            a_sched = int(arr_leg.normalized_timeline_min)
        else:
            a_sched = 0

        # Scheduled departure clock
        if dep_leg and dep_leg.normalized_timeline_min is not None:
            d_sched = int(dep_leg.normalized_timeline_min)
        else:
            d_sched = a_sched + self.default_dwell_min

        # -------------------------------------------------------------
        # 1. ARRIVAL_ONLY_LEGACY MODE (Bit-for-bit parity with legacy)
        # -------------------------------------------------------------
        if mode == SimulationMode.ARRIVAL_ONLY_LEGACY:
            a_sim = int(round(a_sched + delta_arr))
            if pair.is_paired:
                effective_d_sched = d_sched
            else:
                effective_d_sched = a_sched + self.default_dwell_min

            d_min = a_sim + self.min_turnaround_min
            d_sim = int(max(effective_d_sched, d_min))
            gate_release = d_sim + self.separation_buffer_min

            return DualAircraftTurn(
                turn_id=pair.pair_id,
                arrival_leg_id=pair.arrival_leg_id,
                departure_leg_id=pair.departure_leg_id,
                carrier=carrier,
                flight_number=flight_number,
                mode=mode,
                pair_type=pair.pair_type,
                scheduled_arrival_min=a_sched,
                scheduled_departure_min=effective_d_sched,
                predicted_arrival_delay_min=delta_arr,
                predicted_departure_delay_min=None,
                simulated_arrival_min=a_sim,
                departure_ml_min=None,
                earliest_physical_departure_min=d_min,
                simulated_departure_min=d_sim,
                gate_release_min=gate_release,
                min_turnaround_min=self.min_turnaround_min,
                default_dwell_min=self.default_dwell_min,
                separation_buffer_min=self.separation_buffer_min,
                nominal_gate_id=nominal_gate_id,
                aircraft_type=aircraft_type,
                unmatched_status=None if pair.is_paired else "SYNTHETIC_DWELL",
            )

        # -------------------------------------------------------------
        # 2. DUAL_POINT & DUAL_PROBABILISTIC MODES
        # -------------------------------------------------------------
        # Case A: UNMATCHED_ARR
        if pair.pair_type == PairType.UNMATCHED_ARR:
            a_sim = int(round(a_sched + delta_arr))
            effective_d_sched = a_sched + self.default_dwell_min
            d_min = a_sim + self.min_turnaround_min
            d_sim = int(max(effective_d_sched, d_min))
            gate_release = d_sim + self.separation_buffer_min

            return DualAircraftTurn(
                turn_id=pair.pair_id,
                arrival_leg_id=pair.arrival_leg_id,
                departure_leg_id=None,
                carrier=carrier,
                flight_number=flight_number,
                mode=mode,
                pair_type=pair.pair_type,
                scheduled_arrival_min=a_sched,
                scheduled_departure_min=effective_d_sched,
                predicted_arrival_delay_min=delta_arr,
                predicted_departure_delay_min=None,
                simulated_arrival_min=a_sim,
                departure_ml_min=None,
                earliest_physical_departure_min=d_min,
                simulated_departure_min=d_sim,
                gate_release_min=gate_release,
                min_turnaround_min=self.min_turnaround_min,
                default_dwell_min=self.default_dwell_min,
                separation_buffer_min=self.separation_buffer_min,
                nominal_gate_id=nominal_gate_id,
                aircraft_type=aircraft_type,
                unmatched_status="SYNTHETIC_DWELL",
            )

        # Case B: UNMATCHED_DEP
        if pair.pair_type == PairType.UNMATCHED_DEP:
            # Departure leg without prior inbound arrival
            if delta_dep is None:
                raise ValueError(f"UNMATCHED_DEP {pair.pair_id} requires departure prediction.")
            d_ml = int(round(d_sched + delta_dep))
            # Stand start assumption: default dwell before scheduled departure
            a_pseudo = d_sched - self.default_dwell_min
            d_phys = a_pseudo + self.min_turnaround_min
            d_sim = int(max(d_ml, d_phys))
            gate_release = d_sim + self.separation_buffer_min

            return DualAircraftTurn(
                turn_id=pair.pair_id,
                arrival_leg_id=None,
                departure_leg_id=pair.departure_leg_id,
                carrier=carrier,
                flight_number=flight_number,
                mode=mode,
                pair_type=pair.pair_type,
                scheduled_arrival_min=a_pseudo,
                scheduled_departure_min=d_sched,
                predicted_arrival_delay_min=0.0,
                predicted_departure_delay_min=delta_dep,
                simulated_arrival_min=a_pseudo,
                departure_ml_min=d_ml,
                earliest_physical_departure_min=d_phys,
                simulated_departure_min=d_sim,
                gate_release_min=gate_release,
                min_turnaround_min=self.min_turnaround_min,
                default_dwell_min=self.default_dwell_min,
                separation_buffer_min=self.separation_buffer_min,
                nominal_gate_id=nominal_gate_id,
                aircraft_type=aircraft_type,
                unmatched_status="UNSCHEDULABLE_WITH_CURRENT_INPUT",
            )

        # Case C: PAIRED TURN (Dual Prediction Coupling)
        if delta_dep is None:
            raise ValueError(f"Paired turn {pair.pair_id} missing departure prediction in {mode} mode.")

        # Formula:
        # A_pred = A_sched + delta_arr
        # D_ml   = D_sched + delta_dep
        # D_min  = A_pred + T_min
        # D_gate_out = max(D_ml, D_min)
        # Gate_release = D_gate_out + B_buffer
        a_pred = int(round(a_sched + delta_arr))
        d_ml = int(round(d_sched + delta_dep))
        d_min = a_pred + self.min_turnaround_min
        d_gate_out = int(max(d_ml, d_min))
        gate_release = d_gate_out + self.separation_buffer_min

        return DualAircraftTurn(
            turn_id=pair.pair_id,
            arrival_leg_id=pair.arrival_leg_id,
            departure_leg_id=pair.departure_leg_id,
            carrier=carrier,
            flight_number=flight_number,
            mode=mode,
            pair_type=pair.pair_type,
            scheduled_arrival_min=a_sched,
            scheduled_departure_min=d_sched,
            predicted_arrival_delay_min=delta_arr,
            predicted_departure_delay_min=delta_dep,
            simulated_arrival_min=a_pred,
            departure_ml_min=d_ml,
            earliest_physical_departure_min=d_min,
            simulated_departure_min=d_gate_out,
            gate_release_min=gate_release,
            min_turnaround_min=self.min_turnaround_min,
            default_dwell_min=self.default_dwell_min,
            separation_buffer_min=self.separation_buffer_min,
            nominal_gate_id=nominal_gate_id,
            aircraft_type=aircraft_type,
            unmatched_status=None,
            coupling_assumption=coupling_assumption.value if coupling_assumption else None,
        )

    def synthesize_probabilistic_scenarios(
        self,
        pair: TurnPair,
        legs: Mapping[str, FlightLeg],
        arr_dist: PredictiveDistribution,
        dep_dist: PredictiveDistribution,
        *,
        n_scenarios: int = 100,
        seed: int = 202601,
        coupling_assumption: CouplingAssumption = CouplingAssumption.INDEPENDENT,
        nominal_gate_id: str | None = None,
    ) -> list[DualAircraftTurn]:
        """Synthesizes scenario-wise turns under explicit sensitivity coupling assumptions.

        Guarantees:
        1. Buffer added exactly once.
        2. D_gate_out computed per-scenario as max(D_ml(s), D_min(s)).
        3. Coupling assumption explicitly tracked in turn metadata.
        """
        rng = np.random.RandomState(seed)

        # Generate scenario probability draws
        if coupling_assumption == CouplingAssumption.INDEPENDENT:
            u_arr = rng.uniform(0.001, 0.999, size=n_scenarios)
            u_dep = rng.uniform(0.001, 0.999, size=n_scenarios)
        elif coupling_assumption == CouplingAssumption.COMONOTONIC:
            u = rng.uniform(0.001, 0.999, size=n_scenarios)
            u_arr = u
            u_dep = u
        elif coupling_assumption == CouplingAssumption.COUNTERMONOTONIC:
            u = rng.uniform(0.001, 0.999, size=n_scenarios)
            u_arr = u
            u_dep = 1.0 - u
        else:
            raise ValueError(f"Unsupported coupling assumption: {coupling_assumption}")

        delays_arr = np.asarray(arr_dist.quantile(u_arr), dtype=float).flatten()
        delays_dep = np.asarray(dep_dist.quantile(u_dep), dtype=float).flatten()

        scenario_turns: list[DualAircraftTurn] = []
        for s in range(n_scenarios):
            turn = self.synthesize_turn(
                pair=pair,
                legs=legs,
                arrival_prediction=float(delays_arr[s]),
                departure_prediction=float(delays_dep[s]),
                mode=SimulationMode.DUAL_PROBABILISTIC,
                nominal_gate_id=nominal_gate_id,
                coupling_assumption=coupling_assumption,
            )
            scenario_turns.append(turn)

        return scenario_turns
