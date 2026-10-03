"""Tests for Optimization Domain Objects and Timeline Semantics.

Protocol: docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md
          docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 19 (Stage 9)
Verifies:
1. FlightTimeWindow half-open interval overlap logic [s, e).
2. Timeline semantics:
   arrival -> turnaround/dwell -> gate release.
   Proves whether turnaround=45 and dwell=60 are distinct and NOT double-counted.
3. Gate compatibility (carrier, aircraft) and availability windows.
4. Independent hard-constraint verification engine detects all violation types outside the solver.
"""

from __future__ import annotations

import pytest

from src.optimization.domain import (
    Flight,
    FlightTimeWindow,
    Gate,
    GateAssignment,
    verify_hard_constraints_independently,
)


def test_flight_time_window_overlap() -> None:
    """Verify half-open interval overlap logic: [s1, e1) and [s2, e2)."""
    w1 = FlightTimeWindow(start_min=60, end_min=120)
    w2 = FlightTimeWindow(start_min=100, end_min=150)
    w3 = FlightTimeWindow(start_min=120, end_min=180)  # adjacent, no overlap
    w4 = FlightTimeWindow(start_min=130, end_min=200)  # disjoint

    assert w1.overlaps(w2) is True
    assert w1.overlap_duration(w2) == 20  # [100, 120)

    assert w1.overlaps(w3) is False
    assert w1.overlap_duration(w3) == 0

    assert w1.overlaps(w4) is False
    assert w1.overlap_duration(w4) == 0


def test_timeline_semantics_turnaround_and_dwell_not_double_counted() -> None:
    """Verify that turnaround (45 min) and dwell (60 min) are distinct and NOT double-counted.

    Mathematical contract:
    - Scheduled dwell (60 min): default stay when uncoupled with outbound flight.
    - Minimum physical turnaround (45 min): required time from actual arrival to departure.
    - D_sched = A_sched + dwell (e.g. 100 + 60 = 160)
    - D_min = A_pred + turnaround (e.g. 100 + 45 = 145 if on time)
    - D_pred = max(D_sched, D_min) = max(160, 145) = 160.
      Total stay is 60 min, NOT 45 + 60 = 105 min!
    - If delayed by 30 min (A_pred = 130):
      D_min = 130 + 45 = 175
      D_pred = max(160, 175) = 175.
      Stay is 45 min from actual arrival, respecting minimum turnaround.
    """
    # Case A: On-time arrival (arrival_delay = 0)
    fl_on_time = Flight(
        flight_id="FL_01",
        flight_index=0,
        carrier="DL",
        flight_number="100",
        scheduled_arrival_min=100,
        scheduled_departure_min=160,
        predicted_arrival_min=100,  # 0 delay
        min_turnaround_min=45,
        default_dwell_min=60,
        buffer_min=15,
        is_paired=False,
    )
    # Simulated departure should be max(100+60, 100+45) = 160
    assert fl_on_time.simulated_departure_min == 160
    # Gate stay before buffer is 60 minutes (the scheduled dwell)
    stay_duration = fl_on_time.simulated_departure_min - fl_on_time.predicted_arrival_min
    assert stay_duration == 60
    assert stay_duration != 105  # Proves 45 and 60 are NOT double-counted

    # Gate release with 15 min buffer
    assert fl_on_time.gate_release_min == 175
    assert fl_on_time.time_window.duration_min == 75

    # Case B: Delayed arrival by 30 min (predicted_arrival = 130)
    fl_delayed = Flight(
        flight_id="FL_02",
        flight_index=1,
        carrier="DL",
        flight_number="101",
        scheduled_arrival_min=100,
        scheduled_departure_min=160,
        predicted_arrival_min=130,  # 30 min delay
        min_turnaround_min=45,
        default_dwell_min=60,
        buffer_min=15,
        is_paired=False,
    )
    # Simulated departure must be max(160, 130+45) = max(160, 175) = 175
    assert fl_delayed.simulated_departure_min == 175
    # Stay duration from actual arrival is exactly the 45-minute minimum turnaround
    delayed_stay = fl_delayed.simulated_departure_min - fl_delayed.predicted_arrival_min
    assert delayed_stay == 45
    assert fl_delayed.gate_release_min == 190


def test_gate_compatibility_and_availability() -> None:
    """Verify Gate carrier, aircraft type compatibility, and availability windows."""
    gate = Gate(
        gate_id="G_01",
        gate_index=0,
        is_overflow=False,
        allowed_carriers=frozenset({"DL", "AF"}),
        allowed_aircraft_types=frozenset({"B738", "A321"}),
        available_windows=((60, 360), (420, 720)),
    )

    # Carrier compatibility
    assert gate.is_compatible_carrier("DL") is True
    assert gate.is_compatible_carrier("UA") is False

    # Aircraft compatibility
    assert gate.is_compatible_aircraft("B738") is True
    assert gate.is_compatible_aircraft("B777") is False

    # Availability windows
    w_open = FlightTimeWindow(start_min=100, end_min=200)
    assert gate.is_available_during(w_open) is True

    w_closed = FlightTimeWindow(start_min=350, end_min=400)
    assert gate.is_available_during(w_closed) is False


def test_independent_hard_constraint_verification() -> None:
    """Verify that verify_hard_constraints_independently correctly catches violations."""
    g1 = Gate(gate_id="G1", gate_index=0, is_overflow=False, allowed_carriers=frozenset({"DL"}))
    g2 = Gate(gate_id="G2", gate_index=1, is_overflow=False)
    overflow = Gate(gate_id="OVF", gate_index=2, is_overflow=True)
    gates = [g1, g2, overflow]

    # Two overlapping flights on G1
    f1 = Flight(
        flight_id="F1",
        flight_index=0,
        carrier="DL",
        flight_number="1",
        scheduled_arrival_min=100,
        scheduled_departure_min=160,
        predicted_arrival_min=100,
    )
    f2 = Flight(
        flight_id="F2",
        flight_index=1,
        carrier="UA",  # Incompatible with G1
        flight_number="2",
        scheduled_arrival_min=120,
        scheduled_departure_min=180,
        predicted_arrival_min=120,
    )
    flights = [f1, f2]

    # 1. Invalid assignment: both on G1 (conflict + incompatibility)
    bad_assignments = {
        "F1": GateAssignment("F1", "G1", 0, 0, False, False, 100, 175),
        "F2": GateAssignment("F2", "G1", 1, 0, False, False, 120, 195),
    }
    diag_bad = verify_hard_constraints_independently(flights, gates, bad_assignments)
    assert diag_bad.is_valid is False
    assert diag_bad.no_contact_gate_conflicts is False
    assert diag_bad.conflict_count == 1
    assert diag_bad.gate_compatibility_satisfied is False
    assert len(diag_bad.incompatibility_violations) == 1

    # 2. Valid assignment: F1 on G1, F2 on G2
    good_assignments = {
        "F1": GateAssignment("F1", "G1", 0, 0, False, False, 100, 175),
        "F2": GateAssignment("F2", "G2", 1, 1, False, False, 120, 195),
    }
    diag_good = verify_hard_constraints_independently(flights, gates, good_assignments)
    assert diag_good.is_valid is True
    assert diag_good.no_contact_gate_conflicts is True
    assert diag_good.conflict_count == 0
    assert diag_good.gate_compatibility_satisfied is True
