"""Synthetic Aircraft Turn Model and Operational Timeline Semantics.

Protocol: docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md - Section 4
          docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 19 (Stage 9)
Specification:
- Explicit operational timeline representation:
  1. scheduled arrival
  2. sampled delay
  3. simulated arrival: A_sim = A_sched + DeltaT_arr
  4. turnaround / dwell: D_min = A_sim + T_turnaround, D_sched = A_sched + dwell (or scheduled departure)
  5. simulated departure: D_sim = max(D_sched, D_min)
  6. gate release: Gate_release = D_sim + B_buffer
- Translates simulated turns into optimization domain Flight entities.
- Zero double-counting between scheduled dwell and physical turnaround.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from src.optimization.domain import Flight, FlightTimeWindow


@dataclass(frozen=True)
class AircraftTurn:
    """Operational aircraft turn entity with explicit timeline attributes."""

    flight_id: str
    carrier: str
    flight_number: str
    scheduled_arrival_min: int
    sampled_delay_min: float
    simulated_arrival_min: int
    scheduled_departure_min: int
    simulated_departure_min: int
    gate_release_min: int
    min_turnaround_min: int = 45
    default_dwell_min: int = 60
    separation_buffer_min: int = 15
    nominal_gate_id: str | None = None
    aircraft_type: str | None = None
    is_paired: bool = False

    @property
    def occupancy_interval(self) -> tuple[int, int]:
        """Half-open gate occupancy interval [simulated_arrival_min, gate_release_min)."""
        return (self.simulated_arrival_min, self.gate_release_min)

    @property
    def gate_in_min(self) -> int:
        """Gate-in time when aircraft enters the gate (alias to simulated_arrival_min)."""
        return self.simulated_arrival_min

    @property
    def gate_out_min(self) -> int:
        """Physical gate-out / pushback time (alias to simulated_departure_min)."""
        return self.simulated_departure_min

    @property
    def physical_dwell_min(self) -> int:
        """Physical turnaround / dwell duration at gate before separation buffer: gate_out - gate_in."""
        return max(0, self.simulated_departure_min - self.simulated_arrival_min)

    @property
    def scheduled_dwell_min(self) -> int:
        """Scheduled turnaround / dwell duration according to timetable: D_sched - A_sched."""
        return max(0, self.scheduled_departure_min - self.scheduled_arrival_min)

    @property
    def turnaround_slack_min(self) -> int:
        """Turnaround slack above minimum physical turnaround: physical_dwell - min_turnaround."""
        return self.physical_dwell_min - self.min_turnaround_min

    @property
    def occupancy_duration_min(self) -> int:
        """Total occupancy duration in minutes including separation buffer."""
        return max(0, self.gate_release_min - self.simulated_arrival_min)

    @property
    def time_window(self) -> FlightTimeWindow:
        """Domain FlightTimeWindow representation."""
        return FlightTimeWindow(
            start_min=self.simulated_arrival_min,
            end_min=self.gate_release_min,
            buffer_min=self.separation_buffer_min,
        )

    def to_flight(self, flight_index: int = 0) -> Flight:
        """Convert this synthetic turn into a solver Flight domain object."""
        return Flight(
            flight_id=self.flight_id,
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
            is_paired=self.is_paired,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "flight_id": self.flight_id,
            "carrier": self.carrier,
            "flight_number": self.flight_number,
            "scheduled_arrival_min": self.scheduled_arrival_min,
            "sampled_delay_min": float(self.sampled_delay_min),
            "simulated_arrival_min": self.simulated_arrival_min,
            "scheduled_departure_min": self.scheduled_departure_min,
            "simulated_departure_min": self.simulated_departure_min,
            "gate_release_min": self.gate_release_min,
            "occupancy_duration_min": self.occupancy_duration_min,
            "nominal_gate_id": self.nominal_gate_id,
            "aircraft_type": self.aircraft_type,
            "is_paired": self.is_paired,
        }


class AircraftTurnModel:
    """Constructs explicit synthetic aircraft turns from scheduled metadata and sampled delays."""

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
        flight_id: str,
        carrier: str,
        flight_number: str,
        scheduled_arrival_min: int,
        sampled_delay_min: float,
        scheduled_departure_min: int | None = None,
        nominal_gate_id: str | None = None,
        aircraft_type: str | None = None,
        is_paired: bool = False,
    ) -> AircraftTurn:
        """Synthesize a single aircraft turn respecting physical turnaround bounds."""
        a_sched = int(scheduled_arrival_min)
        delay = float(sampled_delay_min)
        a_sim = int(round(a_sched + delay))

        if scheduled_departure_min is not None:
            d_sched = int(scheduled_departure_min)
            is_paired = True
        else:
            d_sched = a_sched + self.default_dwell_min

        # Physical turnaround requirement
        d_min = a_sim + self.min_turnaround_min
        d_sim = int(max(d_sched, d_min))
        gate_release = d_sim + self.separation_buffer_min

        return AircraftTurn(
            flight_id=flight_id,
            carrier=carrier,
            flight_number=flight_number,
            scheduled_arrival_min=a_sched,
            sampled_delay_min=delay,
            simulated_arrival_min=a_sim,
            scheduled_departure_min=d_sched,
            simulated_departure_min=d_sim,
            gate_release_min=gate_release,
            min_turnaround_min=self.min_turnaround_min,
            default_dwell_min=self.default_dwell_min,
            separation_buffer_min=self.separation_buffer_min,
            nominal_gate_id=nominal_gate_id,
            aircraft_type=aircraft_type,
            is_paired=is_paired,
        )

    def synthesize_batch(
        self,
        flight_df: pd.DataFrame,
        sampled_delays: Sequence[float] | np.ndarray,
        nominal_gate_mapping: Mapping[str, str] | None = None,
    ) -> list[AircraftTurn]:
        """Synthesize an operational turn batch for a set of flights under a scenario delay vector."""
        n_flights = len(flight_df)
        delays_arr = np.asarray(sampled_delays, dtype=float)
        if len(delays_arr) != n_flights:
            raise ValueError(
                f"Mismatch: flight_df count ({n_flights}) != sampled_delays length ({len(delays_arr)})"
            )

        nominal_map = nominal_gate_mapping or {}
        turns: list[AircraftTurn] = []

        # Extract columns with fallback
        flight_keys = [str(k) for k in flight_df.get("flight_key", flight_df.index)]
        carriers = [str(c) for c in flight_df.get("OP_CARRIER", ["DL"] * n_flights)]
        fl_nums = [str(num) for num in flight_df.get("OP_CARRIER_FL_NUM", ["100"] * n_flights)]

        # Scheduled arrival
        if "CRS_ARR_MIN" in flight_df.columns:
            a_sched_vals = flight_df["CRS_ARR_MIN"].to_numpy(dtype=int)
        elif "scheduled_departure_hour" in flight_df.columns and "CRS_ELAPSED_TIME" in flight_df.columns:
            dep_hours = flight_df["scheduled_departure_hour"].to_numpy(dtype=float)
            dep_mins = flight_df.get("scheduled_departure_minute", 0)
            if isinstance(dep_mins, pd.Series):
                dep_mins = dep_mins.to_numpy(dtype=float)
            elapsed = flight_df["CRS_ELAPSED_TIME"].to_numpy(dtype=float)
            a_sched_vals = (dep_hours * 60.0 + dep_mins + elapsed).round().astype(int)
        else:
            # Fallback sequential spacing
            a_sched_vals = np.array([360 + i * 5 for i in range(n_flights)], dtype=int)

        # Scheduled departure (if paired schedule is available)
        d_sched_vals = None
        if "scheduled_departure_min" in flight_df.columns:
            d_sched_vals = flight_df["scheduled_departure_min"].to_numpy(dtype=int)
        elif "CRS_DEP_MIN" in flight_df.columns:
            d_sched_vals = flight_df["CRS_DEP_MIN"].to_numpy(dtype=int)

        for i in range(n_flights):
            f_key = flight_keys[i]
            dep_min_val = int(d_sched_vals[i]) if d_sched_vals is not None else None
            turn = self.synthesize_turn(
                flight_id=f_key,
                carrier=carriers[i],
                flight_number=fl_nums[i],
                scheduled_arrival_min=int(a_sched_vals[i]),
                sampled_delay_min=float(delays_arr[i]),
                scheduled_departure_min=dep_min_val,
                nominal_gate_id=nominal_map.get(f_key),
            )
            turns.append(turn)

        return turns
