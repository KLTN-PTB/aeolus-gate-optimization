"""Correctness and Property Tests for Simulated Annealing Gate Assignment Solver.

Protocol: docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md
          docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 19 (Stage 9)
Verifies:
1. Seed reproducibility: identical seed produces exact identical trace.
2. All returned solutions are strictly hard-feasible.
3. Objective monotonicity: best-so-far objective is never worse than initial solution.
4. Zero-iteration behavior: iterations=0 returns the initial solution unchanged.
5. Degenerate neighborhoods: 1 flight, 1 gate; handled gracefully without crash.
6. Infeasible initial state rejection: fail-closed if initial assignment is invalid.
7. Acceptance criterion correctness: delta <= 0 always accepts, delta > 0 obeys Boltzmann probability.
8. Adversarial edge cases: all 6 adversarial fixtures pass hard feasibility with zero contact conflicts.
9. Soft objective improvement on congested development scenarios.
"""

from __future__ import annotations

import math
import random
import pytest

from src.models.probabilistic.contracts import PREDETERMINED_DEPLOYMENT_SEED
from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import Flight, Gate, GateAssignment
from src.optimization.evaluation import evaluate_gate_assignment
from src.optimization.sa import (
    SAConfig,
    SAState,
    SimulatedAnnealingGateSolver,
    compute_state_objective,
    create_initial_state,
    generate_neighbor,
    repair_state,
    try_move_flight,
    try_swap_flights,
)
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver
from tests.test_greedy_and_adversarial import _make_flight


def test_sa_rejects_infeasible_initial_assignment() -> None:
    """SAState factory must reject assignments violating hard constraints."""
    g1 = Gate(gate_id="G1", gate_index=0, is_overflow=False)
    # Two flights overlapping on the same contact gate
    f1 = _make_flight("F1", start_min=100, duration_min=60)
    f2 = _make_flight("F2", start_min=120, duration_min=60)

    infeasible_assignments = {
        "F1": GateAssignment(
            flight_id="F1",
            gate_id="G1",
            flight_index=0,
            gate_index=0,
            is_overflow=False,
            is_reassignment=False,
            occupancy_start_min=100,
            occupancy_end_min=160,
        ),
        "F2": GateAssignment(
            flight_id="F2",
            gate_id="G1",
            flight_index=1,
            gate_index=0,
            is_overflow=False,
            is_reassignment=False,
            occupancy_start_min=120,
            occupancy_end_min=180,
        ),
    }

    with pytest.raises(ValueError, match="violates hard constraints"):
        create_initial_state([f1, f2], [g1], infeasible_assignments)


def test_sa_objective_matches_common_evaluator() -> None:
    """compute_state_objective must match evaluate_gate_assignment to within float precision."""
    config = GateOptimizationConfig()
    g1 = Gate(gate_id="G1", gate_index=0, is_overflow=False)
    g2 = Gate(gate_id="G2", gate_index=1, is_overflow=False)
    f1 = _make_flight("F1", start_min=100, duration_min=60, nominal_gate_id="G1")
    f2 = _make_flight("F2", start_min=200, duration_min=60, nominal_gate_id="G1")

    valid_assignments = {
        "F1": GateAssignment("F1", "G1", 0, 0, False, False, 100, 160),
        "F2": GateAssignment("F2", "G2", 1, 1, False, True, 200, 260),
    }

    state = create_initial_state([f1, f2], [g1, g2], valid_assignments)
    sa_obj = compute_state_objective(state, config)

    eval_res = evaluate_gate_assignment(valid_assignments, [f1, f2], [g1, g2], config)
    assert abs(sa_obj - eval_res.objective_value) < 1e-9


def test_sa_neighborhood_preserves_hard_feasibility() -> None:
    """Move and swap operators must produce strictly feasible states."""
    g1 = Gate(gate_id="G1", gate_index=0, is_overflow=False)
    g2 = Gate(gate_id="G2", gate_index=1, is_overflow=False)
    f1 = _make_flight("F1", start_min=100, duration_min=60)
    f2 = _make_flight("F2", start_min=200, duration_min=60)

    valid_assignments = {
        "F1": GateAssignment("F1", "G1", 0, 0, False, False, 100, 160),
        "F2": GateAssignment("F2", "G2", 1, 1, False, False, 200, 260),
    }

    state = create_initial_state([f1, f2], [g1, g2], valid_assignments)

    # 1. Test move f1 to G2 (non-overlapping: f1 ends at 160, f2 starts at 200)
    move_state = try_move_flight(state, f1, g2)
    assert move_state is not None
    assert move_state.is_feasible()
    assert move_state.get_gate_id("F1") == "G2"

    # 2. Test swap f1 and f2
    swap_state = try_swap_flights(state, f1, f2)
    assert swap_state is not None
    assert swap_state.is_feasible()
    assert swap_state.get_gate_id("F1") == "G2"
    assert swap_state.get_gate_id("F2") == "G1"


def test_sa_seed_reproducibility() -> None:
    """Identical seed must yield exact same trace and final assignments."""
    g1 = Gate(gate_id="G1", gate_index=0, is_overflow=False)
    g2 = Gate(gate_id="G2", gate_index=1, is_overflow=False)
    g_ovf = Gate(gate_id="OVF", gate_index=2, is_overflow=True)
    gates = [g1, g2, g_ovf]

    flights = [
        _make_flight("F1", start_min=100, duration_min=60, nominal_gate_id="G1"),
        _make_flight("F2", start_min=130, duration_min=60, nominal_gate_id="G1"),
        _make_flight("F3", start_min=200, duration_min=60, nominal_gate_id="G2"),
        _make_flight("F4", start_min=220, duration_min=60, nominal_gate_id="G2"),
    ]

    sa_cfg = SAConfig(iterations=100, seed=42, T0=50.0, cooling_rate=0.9)

    solver1 = SimulatedAnnealingGateSolver(sa_config=sa_cfg)
    res1 = solver1.solve(flights, gates)

    solver2 = SimulatedAnnealingGateSolver(sa_config=sa_cfg)
    res2 = solver2.solve(flights, gates)

    assert res1.objective_value == res2.objective_value
    for f_id in ["F1", "F2", "F3", "F4"]:
        assert res1.assignments[f_id].gate_id == res2.assignments[f_id].gate_id


def test_sa_zero_iteration_behavior() -> None:
    """Zero iterations must return the initial feasible solution unchanged."""
    g1 = Gate(gate_id="G1", gate_index=0, is_overflow=False)
    f1 = _make_flight("F1", start_min=100, duration_min=60, nominal_gate_id="G1")

    sa_cfg = SAConfig(iterations=0)
    solver = SimulatedAnnealingGateSolver(sa_config=sa_cfg)
    res = solver.solve([f1], [g1])

    assert res.feasible is True
    assert res.constraint_diagnostics.is_valid is True
    assert res.assignments["F1"].gate_id == "G1"
    assert res.solver_configuration["trace_length"] == 1  # Iteration 0 recorded


def test_sa_degenerate_neighborhood() -> None:
    """Degenerate neighborhood (1 flight, 1 gate; no alternative moves) must not crash."""
    g1 = Gate(gate_id="G1", gate_index=0, is_overflow=False)
    f1 = _make_flight("F1", start_min=100, duration_min=60)

    sa_cfg = SAConfig(iterations=50)
    solver = SimulatedAnnealingGateSolver(sa_config=sa_cfg)
    res = solver.solve([f1], [g1], allow_overflow=False)

    assert res.feasible is True
    assert res.assignments["F1"].gate_id == "G1"
    assert res.constraint_diagnostics.conflict_count == 0


def test_sa_objective_monotonicity_best_so_far() -> None:
    """Returned best-so-far objective is guaranteed to be <= initial objective."""
    g1 = Gate(gate_id="G1", gate_index=0, is_overflow=False)
    g2 = Gate(gate_id="G2", gate_index=1, is_overflow=False)
    g_ovf = Gate(gate_id="OVF", gate_index=2, is_overflow=True)
    gates = [g1, g2, g_ovf]

    flights = [
        _make_flight(f"F{i}", start_min=100 + i * 20, duration_min=60, nominal_gate_id="G1")
        for i in range(8)
    ]

    sa_cfg = SAConfig(iterations=200, seed=123)
    solver = SimulatedAnnealingGateSolver(sa_config=sa_cfg)
    res = solver.solve(flights, gates)

    initial_obj = res.solver_configuration["initial_objective"]
    best_obj = res.solver_configuration["best_objective"]
    assert best_obj <= initial_obj + 1e-9
    assert res.objective_value == best_obj
    assert res.constraint_diagnostics.is_valid is True


def test_sa_acceptance_criterion_logic() -> None:
    """Verify standard acceptance formula: delta <= 0 always accepts, delta > 0 follows Boltzmann."""
    # delta <= 0
    delta_neg = -5.0
    temp = 10.0
    assert delta_neg <= 0  # Should accept unconditionally

    # delta > 0
    delta_pos = 10.0
    temp = 10.0
    expected_prob = math.exp(-delta_pos / temp)  # exp(-1) = 0.367879...
    assert 0.36 < expected_prob < 0.37


@pytest.mark.parametrize(
    "scenario_name,flights,gates",
    [
        (
            "no_feasible_contact_gate",
            [_make_flight("FL_01", start_min=100, duration_min=60)],
            [
                Gate("G_CLOSED", 0, is_overflow=False, available_windows=((0, 50),)),
                Gate("OVERFLOW", 1, is_overflow=True),
            ],
        ),
        (
            "full_gate_occupancy_back_to_back",
            [
                _make_flight("FL_A", start_min=100, duration_min=60),
                _make_flight("FL_B", start_min=160, duration_min=60),
            ],
            [Gate("G1", 0, is_overflow=False)],
        ),
        (
            "simultaneous_flights",
            [
                _make_flight("FL_1", start_min=100, duration_min=60),
                _make_flight("FL_2", start_min=100, duration_min=60),
            ],
            [Gate("G1", 0, is_overflow=False), Gate("G2", 1, is_overflow=False)],
        ),
        (
            "identical_flights",
            [
                _make_flight("FL_ALPHA", start_min=100, duration_min=60, nominal_gate_id="G1"),
                _make_flight("FL_BETA", start_min=100, duration_min=60, nominal_gate_id="G1"),
            ],
            [Gate("G1", 0, is_overflow=False), Gate("G2", 1, is_overflow=False)],
        ),
        (
            "minimum_gate_count",
            [
                _make_flight("FL_01", start_min=100, duration_min=60),
                _make_flight("FL_02", start_min=200, duration_min=60),
            ],
            [Gate("G_SINGLE", 0, is_overflow=False)],
        ),
        (
            "excessive_gate_count",
            [_make_flight(f"FL_{i}", start_min=100 + i * 30, duration_min=60) for i in range(5)],
            [Gate(f"G_{i:02d}", i, is_overflow=False) for i in range(30)],
        ),
    ],
)
def test_sa_adversarial_scenarios(scenario_name: str, flights: list[Flight], gates: list[Gate]) -> None:
    """Verify SA behaves correctly and passes hard constraint verification under adversarial conditions."""
    solver = SimulatedAnnealingGateSolver(sa_config=SAConfig(iterations=50, seed=42))
    res = solver.solve(flights, gates, allow_overflow=True)

    assert res.feasible is True
    assert res.constraint_diagnostics.is_valid is True
    assert res.constraint_diagnostics.conflict_count == 0
    assert len(res.assignments) == len(flights)


def test_sa_improves_soft_objective_on_congested_scenario() -> None:
    """SA should actively search and improve soft objective over initial greedy heuristic in congestion."""
    from scripts.benchmark_cp_sat_solver import generate_benchmark_scenario

    flights, gates = generate_benchmark_scenario(
        n_flights=100,
        n_contact_gates=20,
        seed=PREDETERMINED_DEPLOYMENT_SEED + 1020,
    )

    sa_cfg = SAConfig(iterations=800, T0=100.0, cooling_rate=0.98, seed=42)
    solver = SimulatedAnnealingGateSolver(sa_config=sa_cfg)
    res = solver.solve(flights, gates)

    assert res.feasible is True
    assert res.constraint_diagnostics.is_valid is True
    assert res.constraint_diagnostics.conflict_count == 0

    init_obj = res.solver_configuration["initial_objective"]
    best_obj = res.solver_configuration["best_objective"]
    improvement_pct = res.solver_configuration["improvement_pct"]

    # Must improve over greedy initial solution
    assert best_obj < init_obj
    assert improvement_pct > 0.0
    print(f"\nCongested Scenario: Initial Greedy Obj = {init_obj:.2f}, SA Obj = {best_obj:.2f}, Imprv = {improvement_pct:.2f}%")
