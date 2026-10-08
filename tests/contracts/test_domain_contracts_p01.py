"""Domain Contract and Solution Status Standardization Test Suite (Phase P01).

Covers formal contract specifications C01 through C20:
- C01: Flight identity non-empty validation.
- C02: Flight finite numeric timeline parameters (reject NaN/Inf).
- C03: Flight early arrival allowance and consistent simulated departure.
- C04: Flight positive turnaround, dwell, and non-negative buffer validation.
- C05: Flight aircraft_type normalization and missing policy.
- C06: Flight cross-midnight / relative minute semantics.
- C07: Gate identity non-empty validation.
- C08: Gate resource type differentiation and backward-compatible is_overflow.
- C09: Gate capacity >= 1 validation.
- C10: Gate aircraft compatibility policy.
- C11: GateAssignment identity validation.
- C12: GateAssignment strictly positive duration and finite time validation.
- C13: GateAssignment state and is_overflow synchronization.
- C14: validate_flights_collection rejects duplicate IDs or indices.
- C15: validate_gates_collection rejects duplicate gate IDs.
- C16: Independent verifier detects orphan flights.
- C17: Independent verifier detects unknown gates.
- C18: Independent verifier detects timeline mismatches.
- C19: Heuristic solver optimality guard (Greedy/SA cannot claim proven optimality, gap is None).
- C20: Comprehensive serialization round-trip (to_dict / from_dict).
"""

from __future__ import annotations

import math
import pytest

from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import (
    ConstraintDiagnostic,
    Flight,
    FlightTimeWindow,
    Gate,
    GateAssignment,
    GateAssignmentState,
    GateResourceType,
    ObjectiveBreakdown,
    OptimizationResult,
    SolverStatus,
    TerminationReason,
    validate_assignments_contract,
    validate_flights_collection,
    validate_gates_collection,
    verify_hard_constraints_independently,
)
from src.optimization.evaluation import evaluate_gate_assignment


# ---------------------------------------------------------------------------
# C01: Flight identity validation
# ---------------------------------------------------------------------------
def test_c01_flight_identity_validation() -> None:
    # Valid ID succeeds
    fl = Flight(
        flight_id="VN100",
        flight_index=0,
        carrier="VN",
        flight_number="100",
        scheduled_arrival_min=60,
        scheduled_departure_min=120,
        predicted_arrival_min=60,
    )
    assert fl.flight_id == "VN100"

    # Empty or whitespace ID raises ValueError
    with pytest.raises(ValueError, match="flight_id must be a non-empty string"):
        Flight(
            flight_id="",
            flight_index=0,
            carrier="VN",
            flight_number="100",
            scheduled_arrival_min=60,
            scheduled_departure_min=120,
            predicted_arrival_min=60,
        )

    with pytest.raises(ValueError, match="flight_id must be a non-empty string"):
        Flight(
            flight_id="   ",
            flight_index=0,
            carrier="VN",
            flight_number="100",
            scheduled_arrival_min=60,
            scheduled_departure_min=120,
            predicted_arrival_min=60,
        )


# ---------------------------------------------------------------------------
# C02: Flight finite numeric timeline parameters
# ---------------------------------------------------------------------------
def test_c02_flight_finite_numeric_times() -> None:
    # NaN scheduled arrival
    with pytest.raises(ValueError, match="must be finite"):
        Flight(
            flight_id="VN101",
            flight_index=0,
            carrier="VN",
            flight_number="101",
            scheduled_arrival_min=float("nan"),
            scheduled_departure_min=120,
            predicted_arrival_min=60,
        )

    # Inf predicted arrival
    with pytest.raises(ValueError, match="must be finite"):
        Flight(
            flight_id="VN101",
            flight_index=0,
            carrier="VN",
            flight_number="101",
            scheduled_arrival_min=60,
            scheduled_departure_min=120,
            predicted_arrival_min=float("inf"),
        )


# ---------------------------------------------------------------------------
# C03: Flight early arrival allowed
# ---------------------------------------------------------------------------
def test_c03_flight_early_arrival_allowed() -> None:
    # Flight arrives 15 minutes early
    fl = Flight(
        flight_id="VN102",
        flight_index=0,
        carrier="VN",
        flight_number="102",
        scheduled_arrival_min=100,
        scheduled_departure_min=160,
        predicted_arrival_min=85,
        min_turnaround_min=45,
        default_dwell_min=60,
        buffer_min=15,
    )
    assert fl.arrival_delay_min == -15.0
    # Departure respects scheduled dwell: max(100+60, 85+45) = max(160, 130) = 160
    assert fl.simulated_departure_min == 160
    assert fl.gate_release_min == 175
    assert fl.time_window.start_min == 85
    assert fl.time_window.end_min == 175


# ---------------------------------------------------------------------------
# C04: Flight positive turnaround, dwell, and non-negative buffer
# ---------------------------------------------------------------------------
def test_c04_flight_positive_turnaround_and_buffer() -> None:
    # min_turnaround <= 0 rejected
    with pytest.raises(ValueError, match="min_turnaround_min must be positive"):
        Flight(
            flight_id="VN103",
            flight_index=0,
            carrier="VN",
            flight_number="103",
            scheduled_arrival_min=60,
            scheduled_departure_min=120,
            predicted_arrival_min=60,
            min_turnaround_min=0,
        )

    # default_dwell <= 0 rejected
    with pytest.raises(ValueError, match="default_dwell_min must be positive"):
        Flight(
            flight_id="VN103",
            flight_index=0,
            carrier="VN",
            flight_number="103",
            scheduled_arrival_min=60,
            scheduled_departure_min=120,
            predicted_arrival_min=60,
            default_dwell_min=-10,
        )

    # negative buffer rejected
    with pytest.raises(ValueError, match="buffer_min must be non-negative"):
        Flight(
            flight_id="VN103",
            flight_index=0,
            carrier="VN",
            flight_number="103",
            scheduled_arrival_min=60,
            scheduled_departure_min=120,
            predicted_arrival_min=60,
            buffer_min=-5,
        )

    # zero buffer allowed
    fl = Flight(
        flight_id="VN103",
        flight_index=0,
        carrier="VN",
        flight_number="103",
        scheduled_arrival_min=60,
        scheduled_departure_min=120,
        predicted_arrival_min=60,
        buffer_min=0,
    )
    assert fl.buffer_min == 0


# ---------------------------------------------------------------------------
# C05: Flight aircraft_type normalization and missing policy
# ---------------------------------------------------------------------------
def test_c05_flight_aircraft_type_normalization() -> None:
    # Whitespace is normalized to None
    fl1 = Flight(
        flight_id="VN104",
        flight_index=0,
        carrier="VN",
        flight_number="104",
        scheduled_arrival_min=60,
        scheduled_departure_min=120,
        predicted_arrival_min=60,
        aircraft_type="   ",
    )
    assert fl1.aircraft_type is None

    # Concrete type preserved
    fl2 = Flight(
        flight_id="VN105",
        flight_index=1,
        carrier="VN",
        flight_number="105",
        scheduled_arrival_min=60,
        scheduled_departure_min=120,
        predicted_arrival_min=60,
        aircraft_type="A321",
    )
    assert fl2.aircraft_type == "A321"


# ---------------------------------------------------------------------------
# C06: Flight cross-midnight / relative minute semantics
# ---------------------------------------------------------------------------
def test_c06_flight_cross_midnight_relative_minutes() -> None:
    # Flight arriving at 23:45 (1425 min) and releasing at 01:00 (1500 min)
    fl = Flight(
        flight_id="VN106",
        flight_index=0,
        carrier="VN",
        flight_number="106",
        scheduled_arrival_min=1425,
        scheduled_departure_min=1485,
        predicted_arrival_min=1425,
        min_turnaround_min=45,
        default_dwell_min=60,
        buffer_min=15,
    )
    assert fl.simulated_departure_min == 1485
    assert fl.gate_release_min == 1500
    assert fl.time_window.duration_min == 75

    # Negative relative minutes (arrival before anchor midnight)
    fl_neg = Flight(
        flight_id="VN107",
        flight_index=1,
        carrier="VN",
        flight_number="107",
        scheduled_arrival_min=-30,
        scheduled_departure_min=30,
        predicted_arrival_min=-30,
        min_turnaround_min=45,
        default_dwell_min=60,
        buffer_min=15,
    )
    assert fl_neg.time_window.start_min == -30
    assert fl_neg.time_window.end_min == 45


# ---------------------------------------------------------------------------
# C07: Gate identity validation
# ---------------------------------------------------------------------------
def test_c07_gate_identity_validation() -> None:
    # Valid gate succeeds
    g = Gate(gate_id="GATE_01")
    assert g.gate_id == "GATE_01"

    # Empty or whitespace gate_id raises ValueError
    with pytest.raises(ValueError, match="gate_id must be a non-empty string"):
        Gate(gate_id="")

    with pytest.raises(ValueError, match="gate_id must be a non-empty string"):
        Gate(gate_id="  ")


# ---------------------------------------------------------------------------
# C08: Gate resource type differentiation and backward compatibility
# ---------------------------------------------------------------------------
def test_c08_gate_resource_type_and_backward_compatibility() -> None:
    # Contact gate default
    g_contact = Gate(gate_id="G_C1")
    assert g_contact.resource_type == GateResourceType.CONTACT_GATE
    assert g_contact.is_overflow is False

    # Finite remote stand
    g_remote = Gate(gate_id="G_R1", resource_type=GateResourceType.FINITE_REMOTE_STAND)
    assert g_remote.is_overflow is True

    # Unbounded overflow apron
    g_apron = Gate(gate_id="G_O1", resource_type=GateResourceType.UNBOUNDED_OVERFLOW_APRON)
    assert g_apron.is_overflow is True

    # Legacy construction with is_overflow=True
    g_legacy = Gate(gate_id="G_LEG", is_overflow=True)
    assert g_legacy.resource_type == GateResourceType.FINITE_REMOTE_STAND
    assert g_legacy.is_overflow is True


# ---------------------------------------------------------------------------
# C09: Gate capacity validation
# ---------------------------------------------------------------------------
def test_c09_gate_capacity_validation() -> None:
    # capacity <= 0 rejected
    with pytest.raises(ValueError, match="capacity must be >= 1"):
        Gate(gate_id="G01", capacity=0)

    with pytest.raises(ValueError, match="capacity must be >= 1"):
        Gate(gate_id="G01", capacity=-2)

    # pooled remote stand capacity > 1 allowed
    g_pool = Gate(gate_id="G_REMOTE_POOL", resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=5)
    assert g_pool.capacity == 5


# ---------------------------------------------------------------------------
# C10: Gate aircraft compatibility policy
# ---------------------------------------------------------------------------
def test_c10_gate_aircraft_compatibility() -> None:
    # Unconstrained gate (allowed_aircraft_types=None) allows any aircraft
    g_any = Gate(gate_id="G_ANY", allowed_aircraft_types=None)
    assert g_any.can_accommodate(aircraft_type="A321") is True
    assert g_any.can_accommodate(aircraft_type=None) is True

    # Restricted gate
    g_res = Gate(gate_id="G_RES", allowed_aircraft_types=frozenset({"A320", "B738"}))
    assert g_res.can_accommodate(aircraft_type="A320") is True
    assert g_res.can_accommodate(aircraft_type="B738") is True
    assert g_res.can_accommodate(aircraft_type="B77W") is False
    assert g_res.can_accommodate(aircraft_type=None) is True  # Missing type unconstrained policy


# ---------------------------------------------------------------------------
# C11: GateAssignment identity validation
# ---------------------------------------------------------------------------
def test_c11_gate_assignment_identity_validation() -> None:
    # Valid assignment
    ga = GateAssignment(flight_id="F1", gate_id="G1", occupancy_start_min=60, occupancy_end_min=120)
    assert ga.flight_id == "F1"
    assert ga.gate_id == "G1"

    # Empty flight_id or gate_id
    with pytest.raises(ValueError, match="flight_id must be a non-empty string"):
        GateAssignment(flight_id="", gate_id="G1", occupancy_start_min=60, occupancy_end_min=120)

    with pytest.raises(ValueError, match="gate_id must be a non-empty string"):
        GateAssignment(flight_id="F1", gate_id="   ", occupancy_start_min=60, occupancy_end_min=120)


# ---------------------------------------------------------------------------
# C12: GateAssignment strictly positive duration and finite time validation
# ---------------------------------------------------------------------------
def test_c12_gate_assignment_timeline_validation() -> None:
    # end <= start rejected
    with pytest.raises(ValueError, match="must be strictly greater than"):
        GateAssignment(flight_id="F1", gate_id="G1", occupancy_start_min=120, occupancy_end_min=120)

    with pytest.raises(ValueError, match="must be strictly greater than"):
        GateAssignment(flight_id="F1", gate_id="G1", occupancy_start_min=150, occupancy_end_min=120)

    # NaN / Inf rejected
    with pytest.raises(ValueError, match="must be a finite numeric value"):
        GateAssignment(flight_id="F1", gate_id="G1", occupancy_start_min=float("nan"), occupancy_end_min=120)


# ---------------------------------------------------------------------------
# C13: GateAssignment state and is_overflow synchronization
# ---------------------------------------------------------------------------
def test_c13_gate_assignment_state_synchronization() -> None:
    # Contact assignment
    ga_contact = GateAssignment(
        flight_id="F1",
        gate_id="G1",
        occupancy_start_min=60,
        occupancy_end_min=120,
        assignment_state=GateAssignmentState.CONTACT,
    )
    assert ga_contact.is_overflow is False

    # Remote overflow assignment
    ga_remote = GateAssignment(
        flight_id="F2",
        gate_id="REMOTE_01",
        occupancy_start_min=60,
        occupancy_end_min=120,
        is_overflow=True,
    )
    assert ga_remote.assignment_state == GateAssignmentState.REMOTE_OVERFLOW

    # Unassigned state
    ga_unassigned = GateAssignment(
        flight_id="F3",
        gate_id="OVERFLOW",
        occupancy_start_min=60,
        occupancy_end_min=120,
        assignment_state=GateAssignmentState.UNASSIGNED,
    )
    assert ga_unassigned.is_overflow is True


# ---------------------------------------------------------------------------
# C14: validate_flights_collection rejects duplicate IDs or indices
# ---------------------------------------------------------------------------
def test_c14_validate_flights_collection_duplicates() -> None:
    f1 = Flight("F1", 0, "VN", "1", 60, 120, 60)
    f2 = Flight("F2", 1, "VN", "2", 70, 130, 70)
    assert validate_flights_collection([f1, f2]) is True

    # Duplicate flight_id
    f2_dup_id = Flight("F1", 1, "VN", "2", 70, 130, 70)
    with pytest.raises(ValueError, match="Duplicate flight_id"):
        validate_flights_collection([f1, f2_dup_id])

    # Duplicate flight_index
    f2_dup_idx = Flight("F2", 0, "VN", "2", 70, 130, 70)
    with pytest.raises(ValueError, match="Duplicate flight_index"):
        validate_flights_collection([f1, f2_dup_idx])


# ---------------------------------------------------------------------------
# C15: validate_gates_collection rejects duplicate gate IDs
# ---------------------------------------------------------------------------
def test_c15_validate_gates_collection_duplicates() -> None:
    g1 = Gate("G1")
    g2 = Gate("G2")
    assert validate_gates_collection([g1, g2]) is True

    g2_dup = Gate("G1")
    with pytest.raises(ValueError, match="Duplicate gate_id"):
        validate_gates_collection([g1, g2_dup])


# ---------------------------------------------------------------------------
# C16: Independent verifier detects orphan flights
# ---------------------------------------------------------------------------
def test_c16_independent_verifier_orphan_flight() -> None:
    flights = [Flight("F1", 0, "VN", "1", 60, 120, 60)]
    gates = [Gate("G1")]

    assignments = {
        "F1": GateAssignment("F1", "G1", occupancy_start_min=60, occupancy_end_min=135),
        "F_GHOST": GateAssignment("F_GHOST", "G1", occupancy_start_min=140, occupancy_end_min=200),
    }

    diag = verify_hard_constraints_independently(flights=flights, gates=gates, assignments=assignments)
    assert len(diag.orphan_flight_violations) == 1
    assert diag.orphan_flight_count == 1
    assert diag.is_valid is False
    assert any("Orphan flight" in err for err in diag.violation_details)


# ---------------------------------------------------------------------------
# C17: Independent verifier detects unknown gates
# ---------------------------------------------------------------------------
def test_c17_independent_verifier_unknown_gate() -> None:
    flights = [Flight("F1", 0, "VN", "1", 60, 120, 60)]
    gates = [Gate("G1")]

    assignments = {
        "F1": GateAssignment("F1", "GATE_NON_EXISTENT", occupancy_start_min=60, occupancy_end_min=135),
    }

    diag = verify_hard_constraints_independently(flights=flights, gates=gates, assignments=assignments)
    assert len(diag.unknown_gate_violations) == 1
    assert diag.unknown_gate_count == 1
    assert diag.is_valid is False
    assert any("Unknown gate" in err for err in diag.violation_details)


# ---------------------------------------------------------------------------
# C18: Independent verifier detects timeline mismatches
# ---------------------------------------------------------------------------
def test_c18_independent_verifier_timeline_mismatch() -> None:
    # Flight window is [60, 135)
    fl = Flight("F1", 0, "VN", "1", 60, 120, 60, default_dwell_min=60, buffer_min=15)
    gates = [Gate("G1")]

    # Assignment gives wrong occupancy window [100, 200)
    assignments = {
        "F1": GateAssignment("F1", "G1", occupancy_start_min=100, occupancy_end_min=200),
    }

    diag = verify_hard_constraints_independently(flights=[fl], gates=gates, assignments=assignments)
    assert len(diag.timeline_mismatch_violations) == 1
    assert diag.timeline_mismatch_count == 1
    assert diag.is_valid is False
    assert any("Timeline mismatch" in err for err in diag.violation_details)


# ---------------------------------------------------------------------------
# C19: Heuristic solver optimality guard (Greedy/SA cannot claim proven optimality)
# ---------------------------------------------------------------------------
def test_c19_heuristic_solver_optimality_guard() -> None:
    fl = Flight("F1", 0, "VN", "1", 60, 120, 60)
    g = Gate("G1")
    assign = {"F1": GateAssignment("F1", "G1", occupancy_start_min=fl.time_window.start_min, occupancy_end_min=fl.time_window.end_min)}

    # Case A: Simulated Annealing claiming OPTIMAL
    res_sa = evaluate_gate_assignment(
        assignments=assign,
        flights=[fl],
        gates=[g],
        solver_name="simulated_annealing",
        solver_status="OPTIMAL",
        optimality_proven=True,  # Attempting to claim proven optimality
        optimality_gap=0.0,
    )

    # Verification: Raw status preserved, but normalized status demoted and proof rejected
    assert res_sa.raw_solver_status == "OPTIMAL"
    assert res_sa.optimality_proven is False
    assert res_sa.normalized_status == SolverStatus.FEASIBLE
    assert res_sa.optimality_gap is None  # SA cannot claim gap=0.0

    # Case B: Deterministic Greedy solver claiming OPTIMAL
    res_greedy = evaluate_gate_assignment(
        assignments=assign,
        flights=[fl],
        gates=[g],
        solver_name="greedy",
        solver_status="OPTIMAL",
    )
    assert res_greedy.optimality_proven is False
    assert res_greedy.normalized_status == SolverStatus.FEASIBLE

    # Case C: CP-SAT solver with true proven optimality
    res_cpsat = evaluate_gate_assignment(
        assignments=assign,
        flights=[fl],
        gates=[g],
        solver_name="cp_sat_solver",
        solver_status="OPTIMAL",
        optimality_proven=True,
        optimality_gap=0.0,
    )
    assert res_cpsat.raw_solver_status == "OPTIMAL"
    assert res_cpsat.optimality_proven is True
    assert res_cpsat.normalized_status == SolverStatus.OPTIMAL
    assert res_cpsat.optimality_gap == 0.0


# ---------------------------------------------------------------------------
# C20: Comprehensive serialization round-trip (to_dict / from_dict)
# ---------------------------------------------------------------------------
def test_c20_serialization_round_trip() -> None:
    # 1. Flight
    fl_orig = Flight(
        flight_id="VN999",
        flight_index=42,
        carrier="VN",
        flight_number="999",
        scheduled_arrival_min=120,
        scheduled_departure_min=180,
        predicted_arrival_min=130,
        aircraft_type="A359",
        nominal_gate_id="G10",
    )
    fl_dict = fl_orig.to_dict()
    fl_restored = Flight.from_dict(fl_dict)
    assert fl_restored.flight_id == fl_orig.flight_id
    assert fl_restored.aircraft_type == fl_orig.aircraft_type
    assert fl_restored.nominal_gate_id == fl_orig.nominal_gate_id
    assert fl_restored.time_window == fl_orig.time_window

    # 2. Gate
    g_orig = Gate(
        gate_id="G_REMOTE_05",
        resource_type=GateResourceType.FINITE_REMOTE_STAND,
        capacity=3,
        allowed_aircraft_types=frozenset({"A320", "A321", "A359"}),
    )
    g_dict = g_orig.to_dict()
    g_restored = Gate.from_dict(g_dict)
    assert g_restored.gate_id == g_orig.gate_id
    assert g_restored.resource_type == g_orig.resource_type
    assert g_restored.capacity == g_orig.capacity
    assert g_restored.allowed_aircraft_types == g_orig.allowed_aircraft_types

    # 3. GateAssignment
    ga_orig = GateAssignment(
        flight_id="VN999",
        gate_id="G_REMOTE_05",
        occupancy_start_min=fl_orig.time_window.start_min,
        occupancy_end_min=fl_orig.time_window.end_min,
        is_overflow=True,
        assignment_state=GateAssignmentState.REMOTE_OVERFLOW,
    )
    ga_dict = ga_orig.to_dict()
    ga_restored = GateAssignment.from_dict(ga_dict)
    assert ga_restored.flight_id == ga_orig.flight_id
    assert ga_restored.gate_id == ga_orig.gate_id
    assert ga_restored.is_overflow == ga_orig.is_overflow
    assert ga_restored.assignment_state == ga_orig.assignment_state

    # 4. ConstraintDiagnostic
    diag_orig = verify_hard_constraints_independently(
        flights=[fl_orig],
        gates=[g_orig],
        assignments={"VN999": ga_orig},
    )
    diag_dict = diag_orig.to_dict()
    diag_restored = ConstraintDiagnostic.from_dict(diag_dict)
    assert diag_restored.is_valid == diag_orig.is_valid
    assert diag_restored.contact_count == diag_orig.contact_count
    assert diag_restored.remote_count == diag_orig.remote_count
    assert diag_restored.unassigned_count == diag_orig.unassigned_count

    # 5. OptimizationResult
    opt_res = evaluate_gate_assignment(
        assignments={"VN999": ga_orig},
        flights=[fl_orig],
        gates=[g_orig],
        solver_name="cp_sat_solver",
        solver_status="OPTIMAL",
        optimality_proven=True,
        optimality_gap=0.0,
    )
    res_dict = opt_res.to_dict()
    res_restored = OptimizationResult.from_dict(res_dict)
    assert res_restored.status == opt_res.status
    assert res_restored.normalized_status == opt_res.normalized_status
    assert res_restored.optimality_proven == opt_res.optimality_proven
    assert res_restored.objective_value == opt_res.objective_value
    assert len(res_restored.assignments) == 1
