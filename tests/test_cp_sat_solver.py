"""Tests for Google OR-Tools CP-SAT Gate Assignment Solver.

Protocol: docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md
          docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 19 (Stage 9)
Verifies:
1. Decision variables x[f, g] in {0, 1}.
2. Hard constraint 1: Every flight assigned to exactly one gate.
3. Hard constraint 2: No overlapping occupancy intervals on contact gates.
4. Hard constraint 3: Gate operational availability windows.
5. Hard constraint 4: Carrier and aircraft type compatibility.
6. Soft objective decomposition: reassignment, overflow, delay costs.
7. Independent hard constraint verification passes on all feasible results.
8. Deterministic reproducibility under fixed seed.
9. Infeasible detection when overflow is disallowed under congestion.
"""

from __future__ import annotations

import pytest

from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import Flight, Gate
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver


def _create_sample_problem(
    n_flights: int = 10,
    n_contact_gates: int = 4,
    seed: int = 202601,
) -> tuple[list[Flight], list[Gate]]:
    """Helper to generate a consistent sample gate assignment problem."""
    import numpy as np
    rng = np.random.default_rng(seed)

    gates = [
        Gate(
            gate_id=f"G{g:02d}",
            gate_index=g,
            is_overflow=False,
            allowed_carriers=frozenset({"DL", "AA", "UA", "WN"}) if g < 3 else frozenset({"DL"}),
        )
        for g in range(n_contact_gates)
    ]
    overflow_gate = Gate(gate_id="OVERFLOW", gate_index=n_contact_gates, is_overflow=True)
    gates.append(overflow_gate)

    carriers = ["DL", "AA", "UA", "WN"]
    flights: list[Flight] = []
    for f in range(n_flights):
        arr = int(rng.integers(60, 400))
        fl = Flight(
            flight_id=f"FL_{f:03d}",
            flight_index=f,
            carrier=carriers[f % len(carriers)],
            flight_number=str(1000 + f),
            scheduled_arrival_min=arr,
            scheduled_departure_min=arr + 60,
            predicted_arrival_min=arr + int(rng.integers(0, 30)),
            nominal_gate_id=f"G{(f % n_contact_gates):02d}",
            min_turnaround_min=45,
            default_dwell_min=60,
            buffer_min=15,
        )
        flights.append(fl)

    return flights, gates


def test_cp_sat_solver_basic_feasibility_and_hard_constraints() -> None:
    """Verify CP-SAT solver finds feasible/optimal solution and satisfies all hard constraints."""
    flights, gates = _create_sample_problem(n_flights=8, n_contact_gates=4)
    solver = CPSatGateSolver()
    result = solver.solve(flights, gates)

    assert result.feasible is True
    assert result.status in ("OPTIMAL", "FEASIBLE")
    assert result.runtime_ms > 0.0
    assert len(result.assignments) == len(flights)

    # Independent hard-constraint verification outside solver
    diag = result.constraint_diagnostics
    assert diag.is_valid is True
    assert diag.all_flights_assigned is True
    assert diag.no_contact_gate_conflicts is True
    assert diag.conflict_count == 0
    assert diag.gate_compatibility_satisfied is True
    assert diag.gate_availability_satisfied is True


def test_cp_sat_solver_objective_decomposition() -> None:
    """Verify soft objective cost breakdown decomposes into separate penalties."""
    flights, gates = _create_sample_problem(n_flights=6, n_contact_gates=2)
    config = GateOptimizationConfig(
        reassignment_weight=15.0,
        overflow_weight=300.0,
        delay_weight=2.0,
    )
    solver = CPSatGateSolver(config=config)
    result = solver.solve(flights, gates)

    assert result.feasible is True
    bd = result.objective_breakdown
    assert bd.total_cost >= 0.0
    assert bd.weights["reassignment_weight"] == 15.0
    assert bd.weights["overflow_weight"] == 300.0
    assert bd.conflict_cost == 0.0  # zero conflicts on contact gates


def test_cp_sat_solver_carrier_compatibility_enforced() -> None:
    """Verify flights are never assigned to gates that forbid their carrier."""
    # Gate G0 only allows DL; Flight F_UA is UA
    g_dl_only = Gate(gate_id="G_DL", gate_index=0, is_overflow=False, allowed_carriers=frozenset({"DL"}))
    g_open = Gate(gate_id="G_OPEN", gate_index=1, is_overflow=False, allowed_carriers=frozenset({"DL", "UA"}))
    gates = [g_dl_only, g_open]

    f_ua = Flight(
        flight_id="F_UA",
        flight_index=0,
        carrier="UA",
        flight_number="999",
        scheduled_arrival_min=100,
        scheduled_departure_min=160,
        predicted_arrival_min=100,
    )

    solver = CPSatGateSolver()
    result = solver.solve([f_ua], gates, allow_overflow=False)

    assert result.feasible is True
    assign = result.assignments["F_UA"]
    assert assign.gate_id == "G_OPEN"
    assert assign.gate_id != "G_DL"
    assert result.constraint_diagnostics.gate_compatibility_satisfied is True


def test_cp_sat_solver_availability_window_enforced() -> None:
    """Verify flights are not assigned to gates closed during their occupancy window."""
    # Gate G1 is open [0, 200), Gate G2 is open [0, 500)
    g1 = Gate(gate_id="G1", gate_index=0, is_overflow=False, available_windows=((0, 200),))
    g2 = Gate(gate_id="G2", gate_index=1, is_overflow=False, available_windows=((0, 500),))
    gates = [g1, g2]

    # Flight from 220 to 295
    fl = Flight(
        flight_id="F_LATE",
        flight_index=0,
        carrier="DL",
        flight_number="500",
        scheduled_arrival_min=220,
        scheduled_departure_min=280,
        predicted_arrival_min=220,
    )

    solver = CPSatGateSolver()
    result = solver.solve([fl], gates, allow_overflow=False)

    assert result.feasible is True
    assert result.assignments["F_LATE"].gate_id == "G2"
    assert result.constraint_diagnostics.gate_availability_satisfied is True


def test_cp_sat_solver_infeasible_when_overflow_disallowed() -> None:
    """Verify solver detects infeasibility when capacity is exceeded and overflow is disallowed."""
    # 2 simultaneous flights on 1 contact gate with allow_overflow=False
    g1 = Gate(gate_id="G1", gate_index=0, is_overflow=False)
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
        carrier="DL",
        flight_number="2",
        scheduled_arrival_min=110,
        scheduled_departure_min=170,
        predicted_arrival_min=110,
    )

    solver = CPSatGateSolver()
    result = solver.solve([f1, f2], [g1], allow_overflow=False)

    assert result.feasible is False
    assert result.status == "INFEASIBLE"
    assert len(result.assignments) == 0


def test_cp_sat_solver_determinism() -> None:
    """Verify solver produces identical solutions under same input and configuration."""
    flights, gates = _create_sample_problem(n_flights=12, n_contact_gates=4, seed=202602)
    config = GateOptimizationConfig(
        num_search_workers=1,
        random_seed=202601,
        time_limit_seconds=5.0,
    )

    solver1 = CPSatGateSolver(config=config)
    res1 = solver1.solve(flights, gates)

    solver2 = CPSatGateSolver(config=config)
    res2 = solver2.solve(flights, gates)

    assert res1.feasible is True and res2.feasible is True
    assert res1.objective_value == res2.objective_value
    for f_id in res1.assignments:
        assert res1.assignments[f_id].gate_id == res2.assignments[f_id].gate_id
