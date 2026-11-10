"""Synthetic Aircraft Turn Model for Downstream Gate Simulation.

Protocol: docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md - Section 4
          docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 19 (Stage 9)

Implements the locked Synthetic Aircraft Turn contract:
1. Arrival regression: y_arr_reg = DeltaT_arr (signed arrival delay in minutes)
2. Predicted arrival: A_pred = A_sched + DeltaT_arr
3. Minimum turnaround: T_turnaround (nominal 45 minutes)
4. Earliest departure: D_min = A_pred + T_turnaround
5. Simulated departure: D_pred = max(D_sched, D_min)
6. Paired / Unmatched release: Gate_release = D_pred + B_risk
7. Gate occupancy interval: [A_pred, Gate_release]
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
import pandas as pd

from src.models.probabilistic.contracts import ProbabilisticContractViolation


@dataclass(frozen=True)
class SyntheticTurn:
    """Synthetic aircraft turn and gate occupancy window for one flight."""

    flight_key: str
    carrier: str
    flight_number: str
    scheduled_arrival_min: float
    scheduled_departure_min: float
    simulated_arrival_min: float
    simulated_departure_min: float
    gate_arrival_min: float
    gate_release_min: float
    nominal_dwell_min: float
    realized_turnaround_min: float
    nominal_gate: int | None = None

    @property
    def occupancy_duration_min(self) -> float:
        """Total duration of gate occupancy in minutes."""
        return max(0.0, self.gate_release_min - self.gate_arrival_min)


class SyntheticTurnSynthesizer:
    """Generates synthetic aircraft turns and gate occupancy intervals from arrival delays."""

    def __init__(
        self,
        *,
        min_turnaround_minutes: float = 45.0,
        default_dwell_minutes: float = 60.0,
        risk_buffer_minutes: float = 0.0,
    ) -> None:
        """Initialize the synthetic turn synthesizer.

        Args:
            min_turnaround_minutes: Physical minimum time needed to deplane, service, and board (T_turnaround).
            default_dwell_minutes: Scheduled turnaround buffer when outbound flight is unmatched.
            risk_buffer_minutes: Additional tactical buffer added to gate release (B_risk).
        """
        if min_turnaround_minutes <= 0:
            raise ValueError("min_turnaround_minutes must be strictly positive")
        if default_dwell_minutes <= 0:
            raise ValueError("default_dwell_minutes must be strictly positive")

        self.min_turnaround_minutes = float(min_turnaround_minutes)
        self.default_dwell_minutes = float(default_dwell_minutes)
        self.risk_buffer_minutes = float(risk_buffer_minutes)

    def synthesize_turns(
        self,
        flight_features: pd.DataFrame,
        arrival_delays: np.ndarray,
        *,
        outbound_departures: np.ndarray | None = None,
    ) -> list[SyntheticTurn]:
        """Synthesize aircraft turns for a batch of flights given simulated arrival delays.

        Args:
            flight_features: DataFrame containing flight metadata and strictly pre-cutoff features.
            arrival_delays: Array of arrival delays in minutes (shape: (n_flights,)).
            outbound_departures: Optional array of scheduled departure minutes (if paired).

        Returns:
            List of SyntheticTurn objects with exact gate occupancy intervals [A_pred, Gate_release].
        """
        n_flights = len(flight_features)
        if len(arrival_delays) != n_flights:
            raise ProbabilisticContractViolation(
                f"Mismatch: flight_features count ({n_flights}) != arrival_delays length ({len(arrival_delays)})"
            )

        # 1. Scheduled Arrival Time in minutes from start of day
        # A_sched = (scheduled_departure_hour * 60 + scheduled_departure_minute) + CRS_ELAPSED_TIME
        dep_hours = flight_features["scheduled_departure_hour"].to_numpy(dtype=float)
        dep_mins = flight_features["scheduled_departure_minute"].to_numpy(dtype=float)
        elapsed = flight_features["CRS_ELAPSED_TIME"].to_numpy(dtype=float)
        a_sched = (dep_hours * 60.0 + dep_mins) + elapsed

        # 2. Scheduled Departure Time
        if outbound_departures is not None and len(outbound_departures) == n_flights:
            d_sched = np.asarray(outbound_departures, dtype=float)
        else:
            # Unmatched inbound rotation: D_sched = A_sched + dwell_default
            d_sched = a_sched + self.default_dwell_minutes

        # 3. Simulated Arrival Time: A_pred = A_sched + DeltaT_arr
        a_pred = a_sched + arrival_delays

        # 4. Earliest Departure Time: D_min = A_pred + T_turnaround
        d_min = a_pred + self.min_turnaround_minutes

        # 5. Simulated Departure Time: D_pred = max(D_sched, D_min)
        d_pred = np.maximum(d_sched, d_min)

        # 6. Gate Release Time: Gate_release = D_pred + B_risk
        gate_release = d_pred + self.risk_buffer_minutes

        # 7. Assemble SyntheticTurn records
        carriers = flight_features["OP_CARRIER"].astype(str).tolist()
        fl_nums = flight_features["OP_CARRIER_FL_NUM"].astype(str).tolist()
        keys = flight_features.index.astype(str).tolist()

        turns: list[SyntheticTurn] = []
        for i in range(n_flights):
            turn = SyntheticTurn(
                flight_key=keys[i],
                carrier=carriers[i],
                flight_number=fl_nums[i],
                scheduled_arrival_min=float(a_sched[i]),
                scheduled_departure_min=float(d_sched[i]),
                simulated_arrival_min=float(a_pred[i]),
                simulated_departure_min=float(d_pred[i]),
                gate_arrival_min=float(a_pred[i]),
                gate_release_min=float(gate_release[i]),
                nominal_dwell_min=float(d_sched[i] - a_sched[i]),
                realized_turnaround_min=float(gate_release[i] - a_pred[i]),
                nominal_gate=None,
            )
            turns.append(turn)

        return turns
