"""Phase G & Stage 9 — Comprehensive Aircraft Turn and Timeline Semantics Test Suite.

Protocol: docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md - Section 4
          docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 19 (Stage 9)
Step: STEP 6 — AIRCRAFT TURN / TIMELINE SEMANTICS

Verifies the complete operational timeline:
scheduled arrival -> sampled delay -> simulated arrival -> gate-in -> turnaround/dwell -> gate-out -> gate-release.

Hand-checkable test coverage:
1. delay = 0: on-time arrival preserves scheduled dwell when dwell >= min_turnaround.
2. delay = 10: small delay absorbed by scheduled turnaround slack without pushing departure.
3. delay exceeding slack: departure pushed by minimum turnaround requirement.
4. scheduled dwell < min turnaround: physical turnaround overrides tight schedule.
5. scheduled dwell > min turnaround: generous schedule provides buffer absorbing arrival delays.
6. buffer > 0 vs buffer = 0: separation buffer prevents consecutive gate encroachment.
7. back-to-back flights:
   - boundary arrival at exact gate release (s2 == e1): zero overlap, zero conflict.
   - arrival 1 minute before gate release (s2 == e1 - 1): detected 1-minute conflict.
   - arrival at pushback (s2 == gate_out): detected buffer-duration conflict.
8. Parity across simulation (AircraftTurn), conflict detector (detect_conflicts),
   hard-constraint verifier (verify_hard_constraints_independently), and CP-SAT solver.
9. Zero double-counting proof:
   - Turnaround and dwell are NOT additive (uses max, not addition).
   - Buffer is applied exactly once to gate release, not double-counted in window overlaps.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import (
    Flight,
    FlightTimeWindow,
    Gate,
    GateAssignment,
    verify_hard_constraints_independently,
)
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
from src.simulation.aircraft_turn import AircraftTurn, AircraftTurnModel
from src.simulation.conflict_detector import detect_conflicts


# =============================================================================
# 1. HAND-CHECKABLE TEST: delay = 0
# =============================================================================

def test_hand_checkable_delay_zero() -> None:
    """Hand-calculated check: delay = 0.

    Inputs:
        A_sched = 100, delay = 0
        min_turnaround = 45, default_dwell = 60, buffer = 15
    Hand-calculated Timeline:
        A_sim = gate_in = 100 + 0 = 100
        D_sched = 100 + 60 = 160
        D_min = 100 + 45 = 145
        gate_out = D_sim = max(160, 145) = 160
        gate_release = 160 + 15 = 175
        physical_dwell = 160 - 100 = 60 min (matches scheduled dwell)
        turnaround_slack = 60 - 45 = 15 min
        occupancy_duration = 175 - 100 = 75 min
    Proof of Zero Double-Counting:
        stay_duration (60) != turnaround (45) + dwell (60) = 105.
    """
    model = AircraftTurnModel(min_turnaround_min=45, default_dwell_min=60, separation_buffer_min=15)
    turn = model.synthesize_turn("FL_01", "DL", "101", scheduled_arrival_min=100, sampled_delay_min=0.0)

    assert turn.gate_in_min == 100
    assert turn.simulated_arrival_min == 100
    assert turn.scheduled_departure_min == 160
    assert turn.gate_out_min == 160
    assert turn.simulated_departure_min == 160
    assert turn.gate_release_min == 175
    assert turn.physical_dwell_min == 60
    assert turn.turnaround_slack_min == 15
    assert turn.occupancy_duration_min == 75
    assert turn.occupancy_duration_min != 105  # Proves no double-counting

    # Verify parity with Flight domain entity
    flight = turn.to_flight(flight_index=0)
    assert flight.gate_in_min == 100
    assert flight.gate_out_min == 160
    assert flight.gate_release_min == 175
    assert flight.physical_dwell_min == 60
    assert flight.turnaround_slack_min == 15
    assert flight.time_window.start_min == 100
    assert flight.time_window.end_min == 175
    assert flight.time_window.duration_min == 75


# =============================================================================
# 2. HAND-CHECKABLE TEST: delay = 10 (absorbed by scheduled slack)
# =============================================================================

def test_hand_checkable_delay_ten_absorbed_by_slack() -> None:
    """Hand-calculated check: delay = 10.

    Inputs:
        A_sched = 100, delay = 10
        min_turnaround = 45, default_dwell = 60, buffer = 15
    Hand-calculated Timeline:
        A_sim = gate_in = 100 + 10 = 110
        D_sched = 160
        D_min = 110 + 45 = 155
        gate_out = D_sim = max(160, 155) = 160 (DEPARTURE NOT PUSHED!)
        gate_release = 160 + 15 = 175
        physical_dwell = 160 - 110 = 50 min (>= 45 min)
        turnaround_slack = 50 - 45 = 5 min
        occupancy_duration = 175 - 110 = 65 min
    """
    model = AircraftTurnModel(min_turnaround_min=45, default_dwell_min=60, separation_buffer_min=15)
    turn = model.synthesize_turn("FL_02", "DL", "102", scheduled_arrival_min=100, sampled_delay_min=10.0)

    assert turn.gate_in_min == 110
    assert turn.scheduled_departure_min == 160
    assert turn.gate_out_min == 160  # On-time departure preserved
    assert turn.gate_release_min == 175
    assert turn.physical_dwell_min == 50
    assert turn.turnaround_slack_min == 5
    assert turn.occupancy_duration_min == 65

    flight = turn.to_flight(flight_index=1)
    assert flight.gate_in_min == 110
    assert flight.gate_out_min == 160
    assert flight.gate_release_min == 175
    assert flight.physical_dwell_min == 50


# =============================================================================
# 3. HAND-CHECKABLE TEST: delay exceeding slack (departure pushed)
# =============================================================================

def test_hand_checkable_delay_exceeding_slack_pushes_departure() -> None:
    """Hand-calculated check: delay = 25 (exceeds 15 min slack).

    Inputs:
        A_sched = 100, delay = 25
        min_turnaround = 45, default_dwell = 60, buffer = 15
    Hand-calculated Timeline:
        A_sim = gate_in = 100 + 25 = 125
        D_sched = 160
        D_min = 125 + 45 = 170
        gate_out = D_sim = max(160, 170) = 170 (DEPARTURE PUSHED BY 10 MIN!)
        gate_release = 170 + 15 = 185
        physical_dwell = 170 - 125 = 45 min (exact minimum turnaround)
        turnaround_slack = 45 - 45 = 0 min
        occupancy_duration = 185 - 125 = 60 min
    """
    model = AircraftTurnModel(min_turnaround_min=45, default_dwell_min=60, separation_buffer_min=15)
    turn = model.synthesize_turn("FL_03", "DL", "103", scheduled_arrival_min=100, sampled_delay_min=25.0)

    assert turn.gate_in_min == 125
    assert turn.gate_out_min == 170  # Departure pushed
    assert turn.gate_release_min == 185
    assert turn.physical_dwell_min == 45
    assert turn.turnaround_slack_min == 0
    assert turn.occupancy_duration_min == 60

    flight = turn.to_flight(flight_index=2)
    assert flight.gate_out_min == 170
    assert flight.gate_release_min == 185


# =============================================================================
# 4. HAND-CHECKABLE TEST: scheduled dwell < min turnaround
# =============================================================================

def test_hand_checkable_scheduled_dwell_less_than_min_turnaround() -> None:
    """Hand-calculated check: scheduled dwell (30 min) < min turnaround (45 min).

    Inputs:
        A_sched = 200, delay = 0
        min_turnaround = 45, default_dwell = 30, buffer = 15
    Hand-calculated Timeline:
        A_sim = 200
        D_sched = 200 + 30 = 230
        D_min = 200 + 45 = 245
        gate_out = D_sim = max(230, 245) = 245 (PHYSICAL TURNAROUND FORCES EXTENSION!)
        gate_release = 245 + 15 = 260
        physical_dwell = 245 - 200 = 45 min
        occupancy_duration = 260 - 200 = 60 min
    Case B (with delay = 10):
        A_sim = 210
        D_min = 210 + 45 = 255
        gate_out = max(230, 255) = 255
        gate_release = 255 + 15 = 270
    """
    model = AircraftTurnModel(min_turnaround_min=45, default_dwell_min=30, separation_buffer_min=15)

    # Subcase A: delay = 0
    turn_a = model.synthesize_turn("FL_TIGHT_0", "AA", "201", scheduled_arrival_min=200, sampled_delay_min=0.0)
    assert turn_a.scheduled_departure_min == 230
    assert turn_a.scheduled_dwell_min == 30
    assert turn_a.gate_out_min == 245  # Extended from 230 to 245
    assert turn_a.physical_dwell_min == 45
    assert turn_a.gate_release_min == 260
    assert turn_a.occupancy_duration_min == 60

    # Subcase B: delay = 10
    turn_b = model.synthesize_turn("FL_TIGHT_10", "AA", "202", scheduled_arrival_min=200, sampled_delay_min=10.0)
    assert turn_b.gate_in_min == 210
    assert turn_b.gate_out_min == 255
    assert turn_b.physical_dwell_min == 45
    assert turn_b.gate_release_min == 270

    # Subcase C: Paired flight with explicit scheduled departure 230
    turn_c = model.synthesize_turn(
        "FL_TIGHT_PAIRED", "AA", "203",
        scheduled_arrival_min=200,
        sampled_delay_min=0.0,
        scheduled_departure_min=230,
        is_paired=True,
    )
    assert turn_c.scheduled_departure_min == 230
    assert turn_c.gate_out_min == 245
    assert turn_c.gate_release_min == 260


# =============================================================================
# 5. HAND-CHECKABLE TEST: scheduled dwell > min turnaround
# =============================================================================

def test_hand_checkable_scheduled_dwell_greater_than_min_turnaround() -> None:
    """Hand-calculated check: generous scheduled dwell (90 min) > min turnaround (45 min).

    Inputs:
        A_sched = 300, delay = 0
        min_turnaround = 45, default_dwell = 90, buffer = 15
    Hand-calculated Timeline:
        D_sched = 300 + 90 = 390
        D_min = 300 + 45 = 345
        gate_out = max(390, 345) = 390
        gate_release = 390 + 15 = 405
        turnaround_slack = 90 - 45 = 45 min buffer absorbing delay!
    With delay = 40 (within 45 min slack):
        A_sim = 340
        D_min = 340 + 45 = 385 <= 390
        gate_out = max(390, 385) = 390 (STILL ON TIME!)
        gate_release = 405
    """
    model = AircraftTurnModel(min_turnaround_min=45, default_dwell_min=90, separation_buffer_min=15)

    # Delay = 0
    turn_0 = model.synthesize_turn("FL_GEN_0", "UA", "301", scheduled_arrival_min=300, sampled_delay_min=0.0)
    assert turn_0.gate_out_min == 390
    assert turn_0.gate_release_min == 405
    assert turn_0.turnaround_slack_min == 45

    # Delay = 40 (absorbed)
    turn_40 = model.synthesize_turn("FL_GEN_40", "UA", "302", scheduled_arrival_min=300, sampled_delay_min=40.0)
    assert turn_40.gate_in_min == 340
    assert turn_40.gate_out_min == 390  # Absorbed
    assert turn_40.gate_release_min == 405
    assert turn_40.physical_dwell_min == 50
    assert turn_40.turnaround_slack_min == 5


# =============================================================================
# 6. HAND-CHECKABLE TEST: buffer > 0 vs buffer = 0
# =============================================================================

def test_hand_checkable_buffer_zero_vs_positive() -> None:
    """Verify that buffer > 0 vs buffer = 0 behaves exactly according to timeline specification."""
    # Flight A: arrives 100, departs 160
    # Flight B: arrives 160 (exact pushback time of Flight A)

    # 1. With buffer = 0
    model_b0 = AircraftTurnModel(min_turnaround_min=45, default_dwell_min=60, separation_buffer_min=0)
    turn_a_b0 = model_b0.synthesize_turn("FL_A", "DL", "1", scheduled_arrival_min=100, sampled_delay_min=0)  # [100, 160)
    turn_b_b0 = model_b0.synthesize_turn("FL_B", "DL", "2", scheduled_arrival_min=160, sampled_delay_min=0)  # [160, 220)

    assert turn_a_b0.gate_release_min == 160
    assert turn_b_b0.gate_in_min == 160
    assert turn_a_b0.time_window.overlaps(turn_b_b0.time_window) is False
    assert turn_a_b0.time_window.overlap_duration(turn_b_b0.time_window) == 0

    # 2. With buffer = 15
    model_b15 = AircraftTurnModel(min_turnaround_min=45, default_dwell_min=60, separation_buffer_min=15)
    turn_a_b15 = model_b15.synthesize_turn("FL_A", "DL", "1", scheduled_arrival_min=100, sampled_delay_min=0)  # [100, 175)
    turn_b_b15 = model_b15.synthesize_turn("FL_B", "DL", "2", scheduled_arrival_min=160, sampled_delay_min=0)  # [160, 235)

    assert turn_a_b15.gate_release_min == 175
    assert turn_b_b15.gate_in_min == 160
    assert turn_a_b15.time_window.overlaps(turn_b_b15.time_window) is True
    # Overlap is min(175, 235) - max(100, 160) = 175 - 160 = 15 minutes (the buffer duration!)
    assert turn_a_b15.time_window.overlap_duration(turn_b_b15.time_window) == 15


# =============================================================================
# 7. HAND-CHECKABLE TEST: back-to-back flights boundary conditions
# =============================================================================

def test_hand_checkable_back_to_back_boundary_conditions() -> None:
    """Verify exact half-open [s, e) boundary conditions on consecutive flights at the same gate."""
    model = AircraftTurnModel(min_turnaround_min=45, default_dwell_min=60, separation_buffer_min=15)

    # Flight 1: occupies [100, 175)
    f1_turn = model.synthesize_turn("F1", "DL", "1", scheduled_arrival_min=100, sampled_delay_min=0)
    gate_g1 = Gate(gate_id="G1", gate_index=0, is_overflow=False)

    # Boundary Case A: Flight 2 arrives at EXACT gate_release (175) -> [175, 250)
    f2_exact = model.synthesize_turn("F2_EXACT", "DL", "2", scheduled_arrival_min=175, sampled_delay_min=0)
    assert f1_turn.time_window.overlaps(f2_exact.time_window) is False
    assert f1_turn.time_window.overlap_duration(f2_exact.time_window) == 0

    conf_exact = detect_conflicts({"F1": "G1", "F2_EXACT": "G1"}, [f1_turn, f2_exact], [gate_g1])
    assert conf_exact.has_conflicts is False
    assert conf_exact.conflict_count == 0
    assert conf_exact.total_conflict_duration_min == 0.0

    diag_exact = verify_hard_constraints_independently(
        [f1_turn.to_flight(0), f2_exact.to_flight(1)],
        [gate_g1],
        {
            "F1": GateAssignment("F1", "G1", 0, 0, False, False, 100, 175),
            "F2_EXACT": GateAssignment("F2_EXACT", "G1", 1, 0, False, False, 175, 250),
        },
    )
    assert diag_exact.is_valid is True
    assert diag_exact.no_contact_gate_conflicts is True
    assert diag_exact.conflict_count == 0

    # Boundary Case B: Flight 2 arrives 1 minute BEFORE gate_release (174) -> [174, 249)
    f2_encroach = model.synthesize_turn("F2_ENCROACH", "DL", "2", scheduled_arrival_min=174, sampled_delay_min=0)
    assert f1_turn.time_window.overlaps(f2_encroach.time_window) is True
    assert f1_turn.time_window.overlap_duration(f2_encroach.time_window) == 1

    conf_encroach = detect_conflicts({"F1": "G1", "F2_ENCROACH": "G1"}, [f1_turn, f2_encroach], [gate_g1])
    assert conf_encroach.has_conflicts is True
    assert conf_encroach.conflict_count == 1
    assert conf_encroach.total_conflict_duration_min == 1.0

    diag_encroach = verify_hard_constraints_independently(
        [f1_turn.to_flight(0), f2_encroach.to_flight(1)],
        [gate_g1],
        {
            "F1": GateAssignment("F1", "G1", 0, 0, False, False, 100, 175),
            "F2_ENCROACH": GateAssignment("F2_ENCROACH", "G1", 1, 0, False, False, 174, 249),
        },
    )
    assert diag_encroach.is_valid is False
    assert diag_encroach.no_contact_gate_conflicts is False
    assert diag_encroach.conflict_count == 1
    assert diag_encroach.conflict_pairs[0]["overlap_min"] == 1


# =============================================================================
# 8. PARITY ACROSS SIMULATION, CONFLICT DETECTOR, VERIFIER, AND CP-SAT
# =============================================================================

def test_parity_across_simulation_conflicts_and_cpsat() -> None:
    """Verify 100% parity of interval logic across Simulation, ConflictDetector, Verifier, and CP-SAT."""
    model = AircraftTurnModel(min_turnaround_min=45, default_dwell_min=60, separation_buffer_min=15)

    # 3 flights:
    # F1: [100, 175)
    # F2: [175, 250) (seamless back-to-back with F1)
    # F3: [150, 225) (overlaps with F1 by 25m, and with F2 by 50m)
    t1 = model.synthesize_turn("F1", "DL", "101", scheduled_arrival_min=100, sampled_delay_min=0)
    t2 = model.synthesize_turn("F2", "DL", "102", scheduled_arrival_min=175, sampled_delay_min=0)
    t3 = model.synthesize_turn("F3", "DL", "103", scheduled_arrival_min=150, sampled_delay_min=0)

    turns = [t1, t2, t3]
    flights = [t.to_flight(i) for i, t in enumerate(turns)]

    # Case 1: Only 1 contact gate available -> F1 and F2 can share G1, but F3 must overflow
    g1 = Gate(gate_id="G1", gate_index=0, is_overflow=False)
    overflow = Gate(gate_id="OVERFLOW", gate_index=1, is_overflow=True)
    gates = [g1, overflow]

    solver = CPSatGateSolver(config=GateOptimizationConfig())
    res = solver.solve(flights, gates)

    assert res.feasible is True
    assert res.status == "OPTIMAL"

    # CP-SAT must assign F1 and F2 to G1, and F3 to OVERFLOW
    assert res.assignments["F1"].gate_id == "G1"
    assert res.assignments["F2"].gate_id == "G1"
    assert res.assignments["F3"].gate_id == "OVERFLOW"

    # Independent Verifier check
    diag = verify_hard_constraints_independently(flights, gates, res.assignments)
    assert diag.is_valid is True
    assert diag.no_contact_gate_conflicts is True
    assert diag.conflict_count == 0

    # Conflict Detector check
    conf = detect_conflicts(res.assignments, turns, gates)
    assert conf.has_conflicts is False
    assert conf.conflict_count == 0
    assert conf.total_conflict_duration_min == 0.0

    # Peak single-gate concurrency on G1 must be exactly 1 (since F1 and F2 do not overlap)
    assert conf.peak_single_gate_concurrency == 1


# =============================================================================
# 9. EXPLICIT SCHEDULED DEPARTURE & PAIRED SEMANTICS
# =============================================================================

def test_explicit_scheduled_departure_and_paired_semantics() -> None:
    """Verify that passing scheduled_departure_min is respected without requiring explicit is_paired=True."""
    model = AircraftTurnModel(min_turnaround_min=45, default_dwell_min=60, separation_buffer_min=15)

    # Caller passes scheduled_departure_min=200 without passing is_paired
    turn = model.synthesize_turn(
        "F_EXPLICIT", "DL", "999",
        scheduled_arrival_min=100,
        sampled_delay_min=0.0,
        scheduled_departure_min=200,
    )
    assert turn.is_paired is True
    assert turn.scheduled_departure_min == 200
    assert turn.gate_out_min == 200
    assert turn.physical_dwell_min == 100
    assert turn.gate_release_min == 215

    flight = turn.to_flight(0)
    assert flight.scheduled_departure_min == 200
    assert flight.gate_out_min == 200
    assert flight.gate_release_min == 215
