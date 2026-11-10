"""Test Suite for Phase P04: Objective Function Standardization & Metric Semantics.

Verifies:
- O01: Same Flight data, different gate assignments -> exogenous delay cost remains unchanged.
- O02: Reassignment count increases -> reassignment cost changes as configured.
- O03: More finite remote assignments -> remote cost changes correctly.
- O04: Invalid solution -> not ranked as feasible (ranking_cost == inf, ranking_key).
- O05: CP-SAT objective matches evaluator within integer scaling precision.
- O06: Greedy objective matches evaluator.
- O07: SA objective matches evaluator.
- O08: Hybrid final cost matches evaluator.
- O09: Same objective config -> same cost for same assignment.
- O10: Different objective_version -> comparison rejected or explicitly separated.
- O11: Zero baseline cost -> no division-by-zero improvement (compute_improvement_pct).
- O12: NaN/Infinity weights -> reject with ValueError.
- O13: Negative/unsupported weights -> reject with ValueError.
- O14: Large integer scaling -> no overflow in CP-SAT or Python.
- O15: Small hand-calculated example -> exact match within declared tolerance.
- O16: Exogenous constants do not change optimal ranking (arg min invariant).
- O17: Hard-constraint violations remain invalid regardless of penalty weight.
- O18: Objective serialization includes provenance and version.
- O19: Cost breakdown sums match reported total: total == decision + reporting.
- O20: Existing downstream artifact compatibility.
"""

from __future__ import annotations

import math
import pytest

from src.optimization.config import (
    GateOptimizationConfig,
    assert_compatible_objective_version,
    compute_improvement_pct,
)
from src.optimization.domain import (
    ConstraintDiagnostic,
    Flight,
    Gate,
    GateAssignment,
    GateResourceType,
    ObjectiveBreakdown,
    OptimizationResult,
    verify_hard_constraints_independently,
)
from src.optimization.evaluation import evaluate_gate_assignment
from src.optimization.sa import (
    SAConfig,
    SimulatedAnnealingGateSolver,
    compute_state_objective,
    create_initial_state,
)
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver
from src.optimization.solvers.hybrid_solver import HybridGateSolver
from tests.test_greedy_and_adversarial import _make_flight


# =============================================================================
# Helper Fixtures
# =============================================================================

@pytest.fixture
def standard_config():
    return GateOptimizationConfig(
        reassignment_weight=10.0,
        overflow_weight=200.0,
        delay_weight=1.0,
        conflict_weight=1000.0,
        risk_weight=2.0,
        scale_factor=100,
        objective_version="v1",
    )


@pytest.fixture
def two_flight_two_gate():
    gates = [
        Gate(gate_id="G1", gate_index=0, resource_type=GateResourceType.CONTACT_GATE, capacity=1),
        Gate(gate_id="G2", gate_index=1, resource_type=GateResourceType.CONTACT_GATE, capacity=1),
        Gate(gate_id="R1", gate_index=2, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=1, is_overflow=True),
    ]
    f1 = Flight(
        flight_id="F1",
        flight_index=0,
        carrier="DL",
        flight_number="101",
        scheduled_arrival_min=100,
        scheduled_departure_min=160,
        predicted_arrival_min=120,  # 20 min arrival delay
        nominal_gate_id="G1",
        min_turnaround_min=45,
        default_dwell_min=60,
        buffer_min=15,
    )
    f2 = Flight(
        flight_id="F2",
        flight_index=1,
        carrier="DL",
        flight_number="102",
        scheduled_arrival_min=200,
        scheduled_departure_min=260,
        predicted_arrival_min=210,  # 10 min arrival delay
        nominal_gate_id="G2",
        min_turnaround_min=45,
        default_dwell_min=60,
        buffer_min=15,
    )
    return [f1, f2], gates


# =============================================================================
# O01 - O10: Metric Classification, Parity, and Versioning
# =============================================================================

def test_o01_exogenous_delay_cost_invariant_to_assignments(two_flight_two_gate, standard_config):
    """O01: Same flight data with distinct gate assignments preserves identical exogenous delay cost."""
    flights, gates = two_flight_two_gate
    f1, f2 = flights

    # Plan A: Nominal gates (F1->G1, F2->G2)
    plan_a = {
        "F1": GateAssignment("F1", "G1", 0, 0, False, False, f1.time_window.start_min, f1.time_window.end_min),
        "F2": GateAssignment("F2", "G2", 1, 1, False, False, f2.time_window.start_min, f2.time_window.end_min),
    }
    # Plan B: Swapped gates (F1->G2, F2->G1)
    plan_b = {
        "F1": GateAssignment("F1", "G2", 0, 1, False, True, f1.time_window.start_min, f1.time_window.end_min),
        "F2": GateAssignment("F2", "G1", 1, 0, False, True, f2.time_window.start_min, f2.time_window.end_min),
    }
    # Plan C: Remote stand (F1->G1, F2->R1)
    plan_c = {
        "F1": GateAssignment("F1", "G1", 0, 0, False, False, f1.time_window.start_min, f1.time_window.end_min),
        "F2": GateAssignment("F2", "R1", 1, 2, True, True, f2.time_window.start_min, f2.time_window.end_min),
    }

    eval_a = evaluate_gate_assignment(plan_a, flights, gates, standard_config)
    eval_b = evaluate_gate_assignment(plan_b, flights, gates, standard_config)
    eval_c = evaluate_gate_assignment(plan_c, flights, gates, standard_config)

    # Exogenous terms MUST be identical across plans
    assert eval_a.objective_breakdown.delay_cost == eval_b.objective_breakdown.delay_cost == eval_c.objective_breakdown.delay_cost
    assert eval_a.objective_breakdown.risk_cost == eval_b.objective_breakdown.risk_cost == eval_c.objective_breakdown.risk_cost
    assert eval_a.objective_breakdown.reporting_cost == eval_b.objective_breakdown.reporting_cost == eval_c.objective_breakdown.reporting_cost

    # Decision terms MUST differ
    assert eval_a.objective_breakdown.decision_cost == 0.0
    assert eval_b.objective_breakdown.decision_cost == 20.0
    assert eval_c.objective_breakdown.decision_cost == 210.0


def test_o02_reassignment_cost_scales_with_count(two_flight_two_gate, standard_config):
    """O02: Reassignment cost increases linearly with reassignment count."""
    flights, gates = two_flight_two_gate
    f1, f2 = flights

    # 0 reassignments
    plan_0 = {
        "F1": GateAssignment("F1", "G1", 0, 0, False, False, f1.time_window.start_min, f1.time_window.end_min),
        "F2": GateAssignment("F2", "G2", 1, 1, False, False, f2.time_window.start_min, f2.time_window.end_min),
    }
    # 1 reassignment
    plan_1 = {
        "F1": GateAssignment("F1", "G1", 0, 0, False, False, f1.time_window.start_min, f1.time_window.end_min),
        "F2": GateAssignment("F2", "G1", 1, 0, False, True, f2.time_window.start_min, f2.time_window.end_min),
    }
    # 2 reassignments
    plan_2 = {
        "F1": GateAssignment("F1", "G2", 0, 1, False, True, f1.time_window.start_min, f1.time_window.end_min),
        "F2": GateAssignment("F2", "G1", 1, 0, False, True, f2.time_window.start_min, f2.time_window.end_min),
    }

    eval_0 = evaluate_gate_assignment(plan_0, flights, gates, standard_config)
    eval_1 = evaluate_gate_assignment(plan_1, flights, gates, standard_config)
    eval_2 = evaluate_gate_assignment(plan_2, flights, gates, standard_config)

    assert eval_0.objective_breakdown.reassignment_cost == 0.0
    assert eval_1.objective_breakdown.reassignment_cost == 10.0
    assert eval_2.objective_breakdown.reassignment_cost == 20.0


def test_o03_finite_remote_cost_scales_correctly(two_flight_two_gate, standard_config):
    """O03: Finite remote stand assignment incurs overflow cost plus reassignment penalty."""
    flights, gates = two_flight_two_gate
    f1, f2 = flights

    plan_remote = {
        "F1": GateAssignment("F1", "G1", 0, 0, False, False, f1.time_window.start_min, f1.time_window.end_min),
        "F2": GateAssignment("F2", "R1", 1, 2, True, True, f2.time_window.start_min, f2.time_window.end_min),
    }
    eval_res = evaluate_gate_assignment(plan_remote, flights, gates, standard_config)

    assert eval_res.objective_breakdown.overflow_cost == 200.0
    assert eval_res.objective_breakdown.remote_cost == 200.0
    assert eval_res.objective_breakdown.reassignment_cost == 10.0
    assert eval_res.objective_breakdown.decision_cost == 210.0


def test_o04_invalid_solution_not_ranked_as_feasible(two_flight_two_gate, standard_config):
    """O04: Infeasible solutions have ranking_cost == inf and are strictly ranked behind feasible solutions."""
    flights, gates = two_flight_two_gate
    f1, _ = flights

    # Incomplete assignment (only 1 of 2 flights assigned)
    incomplete_plan = {
        "F1": GateAssignment("F1", "G1", 0, 0, False, False, f1.time_window.start_min, f1.time_window.end_min),
    }
    res_infeasible = evaluate_gate_assignment(incomplete_plan, flights, gates, standard_config)
    assert res_infeasible.feasible is False
    assert res_infeasible.ranking_cost == float("inf")
    assert res_infeasible.ranking_key[0] == 1  # 1 indicates infeasible partition in sorting

    # Feasible assignment
    f2 = flights[1]
    complete_plan = {
        "F1": GateAssignment("F1", "G1", 0, 0, False, False, f1.time_window.start_min, f1.time_window.end_min),
        "F2": GateAssignment("F2", "G2", 1, 1, False, False, f2.time_window.start_min, f2.time_window.end_min),
    }
    res_feasible = evaluate_gate_assignment(complete_plan, flights, gates, standard_config)
    assert res_feasible.feasible is True
    assert math.isfinite(res_feasible.ranking_cost)
    assert res_feasible.ranking_key[0] == 0

    # Sorting guarantees feasible beats infeasible regardless of raw objective values
    solutions = [res_infeasible, res_feasible]
    sorted_solutions = sorted(solutions, key=lambda s: s.ranking_key)
    assert sorted_solutions[0].feasible is True
    assert sorted_solutions[1].feasible is False


def test_o05_cpsat_objective_matches_evaluator(two_flight_two_gate, standard_config):
    """O05: CP-SAT decision objective matches common evaluator within integer scaling precision."""
    flights, gates = two_flight_two_gate
    solver = CPSatGateSolver(config=standard_config)
    res = solver.solve(flights, gates)

    assert res.feasible is True
    eval_res = evaluate_gate_assignment(res.assignments, flights, gates, standard_config)

    # Total objective exact match
    assert abs(res.objective_value - eval_res.objective_value) < 1e-5
    # Decision cost exact match
    assert abs(res.objective_breakdown.decision_cost - eval_res.objective_breakdown.decision_cost) < 1e-5
    # Raw decision cost within declared tolerance (1 / scale_factor = 0.01)
    raw_decision = res.solver_configuration["raw_decision_cost"]
    scale_tol = res.solver_configuration["scale_tolerance"]
    assert abs(raw_decision - eval_res.objective_breakdown.decision_cost) <= scale_tol + 1e-9


def test_o06_greedy_objective_matches_evaluator(two_flight_two_gate, standard_config):
    """O06: Greedy objective value strictly matches common evaluator."""
    flights, gates = two_flight_two_gate
    solver = DeterministicGreedyGateSolver(config=standard_config)
    res = solver.solve(flights, gates)

    assert res.feasible is True
    eval_res = evaluate_gate_assignment(res.assignments, flights, gates, standard_config)
    assert abs(res.objective_value - eval_res.objective_value) < 1e-6
    assert abs(res.objective_breakdown.decision_cost - eval_res.objective_breakdown.decision_cost) < 1e-6


def test_o07_sa_objective_matches_evaluator(two_flight_two_gate, standard_config):
    """O07: SA compute_state_objective strictly matches evaluate_gate_assignment."""
    flights, gates = two_flight_two_gate
    greedy_res = DeterministicGreedyGateSolver(config=standard_config).solve(flights, gates)
    sa_state = create_initial_state(flights, gates, greedy_res.assignments)

    sa_obj = compute_state_objective(sa_state, standard_config)
    eval_res = evaluate_gate_assignment(greedy_res.assignments, flights, gates, standard_config)

    assert abs(sa_obj - eval_res.objective_value) < 1e-6


def test_o08_hybrid_final_cost_matches_evaluator(two_flight_two_gate, standard_config):
    """O08: Hybrid solver final cost matches authoritative evaluator."""
    flights, gates = two_flight_two_gate
    solver = HybridGateSolver(config=standard_config, sa_config=SAConfig(iterations=20))
    res = solver.solve(flights, gates)

    assert res.feasible is True
    eval_res = evaluate_gate_assignment(res.assignments, flights, gates, standard_config)
    assert abs(res.objective_value - eval_res.objective_value) < 1e-6


def test_o09_same_config_produces_identical_cost(two_flight_two_gate, standard_config):
    """O09: Exact determinism: evaluating identical assignment under identical config produces identical cost."""
    flights, gates = two_flight_two_gate
    f1, f2 = flights
    plan = {
        "F1": GateAssignment("F1", "G1", 0, 0, False, False, f1.time_window.start_min, f1.time_window.end_min),
        "F2": GateAssignment("F2", "G2", 1, 1, False, False, f2.time_window.start_min, f2.time_window.end_min),
    }
    eval1 = evaluate_gate_assignment(plan, flights, gates, standard_config)
    eval2 = evaluate_gate_assignment(plan, flights, gates, standard_config)

    assert eval1.objective_value == eval2.objective_value
    assert eval1.objective_breakdown.to_dict() == eval2.objective_breakdown.to_dict()


def test_o10_different_objective_version_rejected():
    """O10: Comparing results from different objective versions is strictly rejected."""
    cfg1 = GateOptimizationConfig(objective_version="v1.0")
    cfg2 = GateOptimizationConfig(objective_version="v2.0")

    with pytest.raises(ValueError, match="Cannot compare results with different objective versions"):
        assert_compatible_objective_version(cfg1, cfg2)

    # Identical versions pass
    assert_compatible_objective_version(cfg1, cfg1)


# =============================================================================
# O11 - O20: Numerical Safety, Scale Invariance, and Provenance
# =============================================================================

def test_o11_zero_baseline_cost_safe_improvement():
    """O11: Zero baseline cost does not trigger division by zero."""
    pct = compute_improvement_pct(0.0, 0.0)
    assert pct == 0.0

    pct_neg = compute_improvement_pct(-5.0, 2.0)
    assert pct_neg == 0.0

    pct_nan = compute_improvement_pct(float("nan"), 10.0)
    assert pct_nan == 0.0

    # Normal improvement
    pct_normal = compute_improvement_pct(100.0, 80.0)
    assert pct_normal == 20.0


@pytest.mark.parametrize(
    "bad_val, field_name",
    [
        (float("nan"), "reassignment_weight"),
        (float("inf"), "overflow_weight"),
        (float("-inf"), "delay_weight"),
    ],
)
def test_o12_nan_infinity_weights_rejected(bad_val, field_name):
    """O12: Non-finite/NaN/Infinity weights are rejected at configuration time."""
    with pytest.raises(ValueError, match=f"{field_name} must be a finite float"):
        GateOptimizationConfig(**{field_name: bad_val})


@pytest.mark.parametrize(
    "field_name",
    ["reassignment_weight", "overflow_weight", "delay_weight", "conflict_weight", "risk_weight"],
)
def test_o13_negative_weights_rejected(field_name):
    """O13: Negative penalty weights violate minimization policy and are rejected."""
    with pytest.raises(ValueError, match=f"{field_name} must be non-negative"):
        GateOptimizationConfig(**{field_name: -1.0})


def test_o14_large_integer_scaling_no_overflow(two_flight_two_gate):
    """O14: Large scale factor (10,000) does not cause integer overflow."""
    flights, gates = two_flight_two_gate
    cfg_large_scale = GateOptimizationConfig(scale_factor=10000)
    solver = CPSatGateSolver(config=cfg_large_scale)
    res = solver.solve(flights, gates)

    assert res.feasible is True
    assert res.status == "OPTIMAL"
    raw_scaled = res.solver_configuration["scaled_integer_objective"]
    assert isinstance(raw_scaled, (int, float))
    assert math.isfinite(raw_scaled)


def test_o15_small_hand_calculated_example():
    """O15: Small hand-calculated example matches exact mathematical expectation.

    Hand Calculation:
    - Flight 1: arrival delay = 20 min -> delay_cost = (20/60) * 1.0 = 0.3333333333
                dwell = 60 - 15 = 45 min, min_turnaround = 45 min -> slack = 0 min (< 15)
                risk_cost = ((15 - 0) / 15) * 2.0 = 2.0
                nominal gate = G1, assigned = G2 -> reassignment_cost = 10.0
                overflow = False -> overflow_cost = 0.0
    - Flight 2: arrival delay = 0 min -> delay_cost = 0.0
                dwell = 60 - 15 = 45 min, min_turnaround = 30 min -> slack = 15 min (not < 15)
                risk_cost = 0.0
                nominal gate = G2, assigned = R1 (overflow) -> overflow_cost = 200.0, reassignment_cost = 10.0
    Expected Decision Cost = 10.0 + (200.0 + 10.0) = 220.0
    Expected Reporting Cost = (20/60) + 2.0 = 2.3333333333
    Expected Total Cost = 220.0 + 2.3333333333 = 222.3333333333
    """
    g1 = Gate("G1", 0, resource_type=GateResourceType.CONTACT_GATE, capacity=1)
    g2 = Gate("G2", 1, resource_type=GateResourceType.CONTACT_GATE, capacity=1)
    r1 = Gate("R1", 2, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=1, is_overflow=True)
    gates = [g1, g2, r1]

    f1 = Flight(
        "F1", 0, "DL", "101", 100, 160, 120,
        nominal_gate_id="G1", min_turnaround_min=45, default_dwell_min=45, buffer_min=15,
    )
    f2 = Flight(
        "F2", 1, "DL", "102", 200, 260, 200,
        nominal_gate_id="G2", min_turnaround_min=30, default_dwell_min=45, buffer_min=15,
    )

    plan = {
        "F1": GateAssignment("F1", "G2", 0, 1, False, True, f1.time_window.start_min, f1.time_window.end_min),
        "F2": GateAssignment("F2", "R1", 1, 2, True, True, f2.time_window.start_min, f2.time_window.end_min),
    }

    cfg = GateOptimizationConfig(
        reassignment_weight=10.0,
        overflow_weight=200.0,
        delay_weight=1.0,
        risk_weight=2.0,
        conflict_weight=1000.0,
    )

    eval_res = evaluate_gate_assignment(plan, [f1, f2], gates, cfg)
    bd = eval_res.objective_breakdown

    assert bd.reassignment_cost == pytest.approx(20.0)
    assert bd.overflow_cost == pytest.approx(200.0)
    assert bd.decision_cost == pytest.approx(220.0)

    assert bd.delay_cost == pytest.approx(20.0 / 60.0)
    assert bd.risk_cost == pytest.approx(2.0)
    assert bd.reporting_cost == pytest.approx((20.0 / 60.0) + 2.0)

    assert bd.total_cost == pytest.approx(222.3333333333)


def test_o16_exogenous_constants_do_not_alter_optimal_decision(two_flight_two_gate):
    """O16: Exogenous reporting terms do not change arg min x (optimal gate assignment)."""
    flights, gates = two_flight_two_gate

    # Solve with delay_weight = 1.0, risk_weight = 2.0
    cfg1 = GateOptimizationConfig(delay_weight=1.0, risk_weight=2.0)
    res1 = CPSatGateSolver(config=cfg1).solve(flights, gates)

    # Solve with delay_weight = 50.0, risk_weight = 100.0
    cfg2 = GateOptimizationConfig(delay_weight=50.0, risk_weight=100.0)
    res2 = CPSatGateSolver(config=cfg2).solve(flights, gates)

    # The optimal assignments MUST be identical
    for f_id in res1.assignments:
        assert res1.assignments[f_id].gate_id == res2.assignments[f_id].gate_id


def test_o17_hard_violations_remain_invalid_regardless_of_penalty_weight(two_flight_two_gate):
    """O17: Soft penalty weights never override hard constraint verification."""
    flights, gates = two_flight_two_gate
    f1, f2 = flights

    # Manually assign both overlapping flights to the same contact gate
    overlapping_plan = {
        "F1": GateAssignment("F1", "G1", 0, 0, False, False, 100, 160),
        "F2": GateAssignment("F2", "G1", 1, 0, False, True, 120, 180),  # overlaps F1
    }

    # Even with an infinitesimal conflict penalty
    low_penalty_cfg = GateOptimizationConfig(conflict_weight=0.0001)
    eval_res = evaluate_gate_assignment(overlapping_plan, flights, gates, low_penalty_cfg)

    assert eval_res.feasible is False
    assert eval_res.constraint_diagnostics.is_valid is False
    assert eval_res.constraint_diagnostics.hard_constraint_violations_count > 0


def test_o18_objective_serialization_includes_provenance():
    """O18: ObjectiveBreakdown serialization contains all fields, aliases, and objective_version."""
    bd = ObjectiveBreakdown(
        total_cost=250.0,
        reassignment_cost=10.0,
        overflow_cost=200.0,
        delay_cost=30.0,
        conflict_cost=0.0,
        risk_cost=10.0,
        weights={"reassignment_weight": 10.0},
        objective_version="v1.1",
    )
    d = bd.to_dict()

    assert d["objective_version"] == "v1.1"
    assert d["total_cost"] == 250.0
    assert d["total_reported_cost"] == 250.0
    assert d["decision_cost"] == 210.0
    assert d["reporting_cost"] == 40.0
    assert d["remote_cost"] == 200.0
    assert d["exogenous_delay_cost"] == 30.0
    assert d["exogenous_risk_cost"] == 10.0

    # Round-trip deserialization
    reconstructed = ObjectiveBreakdown.from_dict(d)
    assert reconstructed.objective_version == "v1.1"
    assert reconstructed.total_cost == bd.total_cost
    assert reconstructed.decision_cost == bd.decision_cost
    assert reconstructed.reporting_cost == bd.reporting_cost


def test_o19_cost_breakdown_sums_match_reported_total():
    """O19: ObjectiveBreakdown strictly enforces total_cost == decision_cost + reporting_cost."""
    # Valid breakdown
    bd = ObjectiveBreakdown(
        total_cost=150.0,
        reassignment_cost=20.0,
        overflow_cost=100.0,
        delay_cost=20.0,
        conflict_cost=0.0,
        risk_cost=10.0,
        weights={},
    )
    assert abs(bd.total_cost - (bd.decision_cost + bd.reporting_cost)) < 1e-9

    # Inconsistent total cost raises ValueError
    with pytest.raises(ValueError, match="total_cost .* must equal decision_cost .* \\+ reporting_cost"):
        ObjectiveBreakdown(
            total_cost=999.0,  # Incorrect total
            reassignment_cost=20.0,
            overflow_cost=100.0,
            delay_cost=20.0,
            conflict_cost=0.0,
            risk_cost=10.0,
            weights={},
        )


def test_o20_existing_downstream_artifact_compatibility(two_flight_two_gate, standard_config):
    """O20: OptimizationResult breakdown properties maintain full backward compatibility with downstream comparison records."""
    flights, gates = two_flight_two_gate
    res = CPSatGateSolver(config=standard_config).solve(flights, gates)

    bd = res.objective_breakdown
    assert hasattr(bd, "decision_cost")
    assert hasattr(bd, "reporting_cost")
    assert hasattr(bd, "reassignment_cost")
    assert hasattr(bd, "overflow_cost")
    assert hasattr(bd, "delay_cost")
    assert hasattr(bd, "risk_cost")
    assert hasattr(bd, "total_cost")

    # Downstream record calculation pattern
    extracted_decision = bd.reassignment_cost + bd.overflow_cost
    extracted_reporting = bd.delay_cost + bd.risk_cost
    assert abs(extracted_decision - bd.decision_cost) < 1e-6
    assert abs(extracted_reporting - bd.reporting_cost) < 1e-6
