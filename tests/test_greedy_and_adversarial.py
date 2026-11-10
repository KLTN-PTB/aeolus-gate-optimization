"""Adversarial and Edge Case Tests for Greedy Baseline and CP-SAT Gate Assignment.

Protocol: docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md
          docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 19 (Stage 9)
Verifies:
1. No feasible contact gate (all closed / incompatible -> clean overflow without conflicts).
2. Full gate occupancy (exact back-to-back non-overlapping packing).
3. Simultaneous flights arriving at the exact same minute.
4. Identical flights (identical times, carrier, nominal gate).
5. Minimum gate count (1 contact gate).
6. Excessive gate count (50 gates for 5 flights).
7. Common evaluator parity: Greedy and CP-SAT evaluated under exact same metrics & constraints.
"""

from __future__ import annotations

import pytest

from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import Flight, Gate
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver


def _make_flight(
    flight_id: str,
    start_min: int,
    duration_min: int = 60,
    carrier: str = "DL",
    nominal_gate_id: str | None = None,
) -> Flight:
    """Helper to instantiate a valid Flight entity."""
    return Flight(
        flight_id=flight_id,
        flight_index=0,
        carrier=carrier,
        flight_number="100",
        scheduled_arrival_min=start_min,
        scheduled_departure_min=start_min + duration_min - 15,
        predicted_arrival_min=start_min,
        nominal_gate_id=nominal_gate_id,
        min_turnaround_min=30,
        default_dwell_min=duration_min - 15,
        buffer_min=15,
    )


@pytest.mark.parametrize("solver_cls", [DeterministicGreedyGateSolver, CPSatGateSolver])
def test_adversarial_no_feasible_contact_gate(solver_cls) -> None:
    """Adversarial: All contact gates are closed/incompatible; all flights must overflow with 0 conflicts."""
    # Closed contact gate [0, 50) when flight arrives at 100
    g_closed = Gate(gate_id="G_CLOSED", gate_index=0, is_overflow=False, available_windows=((0, 50),))
    g_overflow = Gate(gate_id="OVERFLOW", gate_index=1, is_overflow=True)
    gates = [g_closed, g_overflow]

    fl = _make_flight("FL_01", start_min=100, duration_min=60)

    solver = solver_cls()
    result = solver.solve([fl], gates, allow_overflow=True)

    assert result.feasible is True
    assert result.constraint_diagnostics.is_valid is True
    assert result.constraint_diagnostics.no_contact_gate_conflicts is True
    assert result.assignments["FL_01"].is_overflow is True
    assert result.assignments["FL_01"].gate_id == "OVERFLOW"


@pytest.mark.parametrize("solver_cls", [DeterministicGreedyGateSolver, CPSatGateSolver])
def test_adversarial_full_gate_occupancy_back_to_back(solver_cls) -> None:
    """Adversarial: Exact back-to-back packing with zero idle time between flights on 1 contact gate."""
    g1 = Gate(gate_id="G1", gate_index=0, is_overflow=False)
    gates = [g1]

    # FL1 occupies [100, 160), FL2 occupies [160, 220), FL3 occupies [220, 280)
    fl1 = _make_flight("FL_1", start_min=100, duration_min=60)
    fl2 = _make_flight("FL_2", start_min=160, duration_min=60)
    fl3 = _make_flight("FL_3", start_min=220, duration_min=60)
    flights = [fl1, fl2, fl3]

    solver = solver_cls()
    result = solver.solve(flights, gates, allow_overflow=False)

    assert result.feasible is True
    assert result.constraint_diagnostics.is_valid is True
    assert result.constraint_diagnostics.no_contact_gate_conflicts is True
    assert result.constraint_diagnostics.conflict_count == 0
    # All 3 packed sequentially onto the single contact gate
    for f in flights:
        assert result.assignments[f.flight_id].gate_id == "G1"


@pytest.mark.parametrize("solver_cls", [DeterministicGreedyGateSolver, CPSatGateSolver])
def test_adversarial_simultaneous_flights(solver_cls) -> None:
    """Adversarial: 5 simultaneous flights arriving at the exact same minute with only 2 contact gates."""
    g1 = Gate(gate_id="G1", gate_index=0, is_overflow=False)
    g2 = Gate(gate_id="G2", gate_index=1, is_overflow=False)
    ovf = Gate(gate_id="OVF", gate_index=2, is_overflow=True)
    gates = [g1, g2, ovf]

    # 5 flights all arriving at minute 200, duration 60
    flights = [_make_flight(f"SIM_{i}", start_min=200, duration_min=60) for i in range(5)]

    solver = solver_cls()
    result = solver.solve(flights, gates, allow_overflow=True)

    assert result.feasible is True
    assert result.constraint_diagnostics.is_valid is True
    assert result.constraint_diagnostics.no_contact_gate_conflicts is True
    assert result.constraint_diagnostics.conflict_count == 0

    # At most 2 flights on contact gates, at least 3 flights on overflow
    contact_count = sum(1 for a in result.assignments.values() if not a.is_overflow)
    overflow_count = sum(1 for a in result.assignments.values() if a.is_overflow)
    assert contact_count == 2
    assert overflow_count == 3


@pytest.mark.parametrize("solver_cls", [DeterministicGreedyGateSolver, CPSatGateSolver])
def test_adversarial_identical_flights(solver_cls) -> None:
    """Adversarial: Identical flights with identical schedules and nominal gates."""
    g1 = Gate(gate_id="G1", gate_index=0, is_overflow=False)
    g2 = Gate(gate_id="G2", gate_index=1, is_overflow=False)
    g3 = Gate(gate_id="G3", gate_index=2, is_overflow=False)
    gates = [g1, g2, g3]

    f1 = _make_flight("ID_1", start_min=300, duration_min=60, nominal_gate_id="G1")
    f2 = _make_flight("ID_2", start_min=300, duration_min=60, nominal_gate_id="G1")
    f3 = _make_flight("ID_3", start_min=300, duration_min=60, nominal_gate_id="G1")
    flights = [f1, f2, f3]

    solver = solver_cls()
    result = solver.solve(flights, gates, allow_overflow=False)

    assert result.feasible is True
    assert result.constraint_diagnostics.is_valid is True
    assert result.constraint_diagnostics.no_contact_gate_conflicts is True

    # Must be assigned to 3 distinct contact gates
    assigned_gates = [result.assignments[f.flight_id].gate_id for f in flights]
    assert len(set(assigned_gates)) == 3


@pytest.mark.parametrize("solver_cls", [DeterministicGreedyGateSolver, CPSatGateSolver])
def test_adversarial_minimum_gate_count(solver_cls) -> None:
    """Adversarial: Exactly 1 contact gate available."""
    g1 = Gate(gate_id="ONLY_GATE", gate_index=0, is_overflow=False)
    ovf = Gate(gate_id="OVF", gate_index=1, is_overflow=True)
    gates = [g1, ovf]

    fl1 = _make_flight("FL_1", start_min=100, duration_min=60)
    fl2 = _make_flight("FL_2", start_min=120, duration_min=60)  # overlaps with FL1
    flights = [fl1, fl2]

    solver = solver_cls()
    result = solver.solve(flights, gates, allow_overflow=True)

    assert result.feasible is True
    assert result.constraint_diagnostics.is_valid is True
    assert result.constraint_diagnostics.no_contact_gate_conflicts is True
    # 1 contact, 1 overflow
    gates_used = [result.assignments[f.flight_id].gate_id for f in flights]
    assert "ONLY_GATE" in gates_used
    assert "OVF" in gates_used


@pytest.mark.parametrize("solver_cls", [DeterministicGreedyGateSolver, CPSatGateSolver])
def test_adversarial_excessive_gate_count(solver_cls) -> None:
    """Adversarial: 50 contact gates for only 5 flights."""
    gates = [Gate(gate_id=f"G_{g:02d}", gate_index=g, is_overflow=False) for g in range(50)]
    flights = [_make_flight(f"FL_{i}", start_min=100 + i * 20, duration_min=60) for i in range(5)]

    solver = solver_cls()
    result = solver.solve(flights, gates, allow_overflow=False)

    assert result.feasible is True
    assert result.constraint_diagnostics.is_valid is True
    assert result.constraint_diagnostics.no_contact_gate_conflicts is True
    assert len(result.assignments) == 5


def test_greedy_vs_cpsat_common_evaluator_parity() -> None:
    """Verify Greedy and CP-SAT are evaluated by the EXACT same evaluator and CP-SAT achieves <= objective."""
    g1 = Gate(gate_id="G1", gate_index=0, is_overflow=False)
    g2 = Gate(gate_id="G2", gate_index=1, is_overflow=False)
    ovf = Gate(gate_id="OVF", gate_index=2, is_overflow=True)
    gates = [g1, g2, ovf]

    # Congested instance: 6 flights over 2 contact gates
    f1 = _make_flight("F1", start_min=100, duration_min=50, nominal_gate_id="G1")
    f2 = _make_flight("F2", start_min=110, duration_min=50, nominal_gate_id="G2")
    f3 = _make_flight("F3", start_min=120, duration_min=50, nominal_gate_id="G1")
    f4 = _make_flight("F4", start_min=130, duration_min=50, nominal_gate_id="G2")
    f5 = _make_flight("F5", start_min=140, duration_min=50, nominal_gate_id="G1")
    f6 = _make_flight("F6", start_min=150, duration_min=50, nominal_gate_id="G2")
    flights = [f1, f2, f3, f4, f5, f6]

    config = GateOptimizationConfig(
        reassignment_weight=10.0,
        overflow_weight=200.0,
    )

    greedy_solver = DeterministicGreedyGateSolver(config=config)
    greedy_res = greedy_solver.solve(flights, gates)

    cpsat_solver = CPSatGateSolver(config=config)
    cpsat_res = cpsat_solver.solve(flights, gates)

    # Both must pass all hard constraints
    assert greedy_res.constraint_diagnostics.is_valid is True
    assert cpsat_res.constraint_diagnostics.is_valid is True

    # Both must have zero contact conflicts
    assert greedy_res.constraint_diagnostics.conflict_count == 0
    assert cpsat_res.constraint_diagnostics.conflict_count == 0

    # CP-SAT as exact optimizer must produce an objective <= Greedy heuristic
    assert cpsat_res.objective_value <= greedy_res.objective_value + 1e-4

    # Runtimes must be positive
    assert greedy_res.runtime_ms >= 0.0
    assert cpsat_res.runtime_ms >= 0.0
