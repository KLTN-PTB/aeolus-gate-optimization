"""Tests for CP-SAT and Common Evaluator Objective Component Audit.

Protocol: docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md - Section 4
          docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 19 (Stage 9)
Requirements:
1. Audit decision-dependence vs constant-reporting classification for all objective terms.
2. Development micro-test with identical flights/delays but distinct feasible assignments.
3. Verify units and weights are explicit and stored in config.
4. Verify solver objective and common evaluator agree.
5. Verify decomposition into decision_cost and reporting_cost.
"""

from __future__ import annotations

import pytest

from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import (
    Flight,
    Gate,
    GateAssignment,
    ObjectiveBreakdown,
)
from src.optimization.evaluation import evaluate_gate_assignment
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver


@pytest.fixture
def micro_test_environment():
    """Construct minimal operational micro-test problem with 2 flights, 2 contact gates, 1 overflow."""
    f1 = Flight(
        flight_id="FL001",
        flight_index=0,
        carrier="DL",
        flight_number="101",
        scheduled_arrival_min=600,
        scheduled_departure_min=660,
        predicted_arrival_min=620,  # 20 min arrival delay
        nominal_gate_id="G_01",
        min_turnaround_min=45,
        default_dwell_min=60,
        buffer_min=15,
    )
    f2 = Flight(
        flight_id="FL002",
        flight_index=1,
        carrier="DL",
        flight_number="102",
        scheduled_arrival_min=700,
        scheduled_departure_min=760,
        predicted_arrival_min=710,  # 10 min arrival delay
        nominal_gate_id="G_02",
        min_turnaround_min=45,
        default_dwell_min=60,
        buffer_min=15,
    )
    flights = [f1, f2]

    g1 = Gate(gate_id="G_01", gate_index=0, is_overflow=False)
    g2 = Gate(gate_id="G_02", gate_index=1, is_overflow=False)
    g_over = Gate(gate_id="OVERFLOW_APRON", gate_index=2, is_overflow=True)
    gates = [g1, g2, g_over]

    config = GateOptimizationConfig(
        reassignment_weight=10.0,
        overflow_weight=200.0,
        delay_weight=1.0,
        conflict_weight=1000.0,
        risk_weight=2.0,
    )

    return flights, gates, config


def test_micro_test_decision_dependent_vs_constant_reporting_terms(micro_test_environment):
    """Verify which terms change with gate decisions and which terms remain constant."""
    flights, gates, config = micro_test_environment
    f1, f2 = flights

    # Plan A: Nominal assignment (f1 -> G_01, f2 -> G_02)
    assign_A = {
        "FL001": GateAssignment(
            flight_id="FL001", gate_id="G_01", flight_index=0, gate_index=0,
            is_overflow=False, is_reassignment=False,
            occupancy_start_min=f1.time_window.start_min, occupancy_end_min=f1.time_window.end_min,
        ),
        "FL002": GateAssignment(
            flight_id="FL002", gate_id="G_02", flight_index=1, gate_index=1,
            is_overflow=False, is_reassignment=False,
            occupancy_start_min=f2.time_window.start_min, occupancy_end_min=f2.time_window.end_min,
        ),
    }

    # Plan B: Swapped contact gates (f1 -> G_02, f2 -> G_01)
    assign_B = {
        "FL001": GateAssignment(
            flight_id="FL001", gate_id="G_02", flight_index=0, gate_index=1,
            is_overflow=False, is_reassignment=True,
            occupancy_start_min=f1.time_window.start_min, occupancy_end_min=f1.time_window.end_min,
        ),
        "FL002": GateAssignment(
            flight_id="FL002", gate_id="G_01", flight_index=1, gate_index=0,
            is_overflow=False, is_reassignment=True,
            occupancy_start_min=f2.time_window.start_min, occupancy_end_min=f2.time_window.end_min,
        ),
    }

    # Plan C: Overflow apron for flight 2 (f1 -> G_01, f2 -> OVERFLOW_APRON)
    assign_C = {
        "FL001": GateAssignment(
            flight_id="FL001", gate_id="G_01", flight_index=0, gate_index=0,
            is_overflow=False, is_reassignment=False,
            occupancy_start_min=f1.time_window.start_min, occupancy_end_min=f1.time_window.end_min,
        ),
        "FL002": GateAssignment(
            flight_id="FL002", gate_id="OVERFLOW_APRON", flight_index=1, gate_index=2,
            is_overflow=True, is_reassignment=True,
            occupancy_start_min=f2.time_window.start_min, occupancy_end_min=f2.time_window.end_min,
        ),
    }

    eval_A = evaluate_gate_assignment(assign_A, flights, gates, config)
    eval_B = evaluate_gate_assignment(assign_B, flights, gates, config)
    eval_C = evaluate_gate_assignment(assign_C, flights, gates, config)

    # 1. DECISION-DEPENDENT TERMS: MUST change across plans
    # reassignment_cost: A=0, B=20, C=10
    assert eval_A.objective_breakdown.reassignment_cost == 0.0
    assert eval_B.objective_breakdown.reassignment_cost == 20.0
    assert eval_C.objective_breakdown.reassignment_cost == 10.0

    # overflow_cost: A=0, B=0, C=200
    assert eval_A.objective_breakdown.overflow_cost == 0.0
    assert eval_B.objective_breakdown.overflow_cost == 0.0
    assert eval_C.objective_breakdown.overflow_cost == 200.0

    # decision_cost: reflects the decision-dependent sum
    assert eval_A.objective_breakdown.decision_cost == 0.0
    assert eval_B.objective_breakdown.decision_cost == 20.0
    assert eval_C.objective_breakdown.decision_cost == 210.0

    # 2. CONSTANT REPORTING TERMS: MUST be invariant to gate assignment decisions
    # delay_cost: identical across Plan A, B, C (exogenous arrival delay)
    assert eval_A.objective_breakdown.delay_cost == pytest.approx(0.50)
    assert eval_B.objective_breakdown.delay_cost == pytest.approx(0.50)
    assert eval_C.objective_breakdown.delay_cost == pytest.approx(0.50)

    # risk_cost: identical across Plan A, B, C (exogenous turnaround slack)
    assert eval_A.objective_breakdown.risk_cost == pytest.approx(3.3333333333)
    assert eval_B.objective_breakdown.risk_cost == pytest.approx(3.3333333333)
    assert eval_C.objective_breakdown.risk_cost == pytest.approx(3.3333333333)

    # reporting_cost: invariant sum of delay and risk
    assert eval_A.objective_breakdown.reporting_cost == pytest.approx(eval_B.objective_breakdown.reporting_cost)
    assert eval_A.objective_breakdown.reporting_cost == pytest.approx(eval_C.objective_breakdown.reporting_cost)

    # 3. TOTAL COST: correctly equals decision_cost + reporting_cost
    for ev in [eval_A, eval_B, eval_C]:
        bd = ev.objective_breakdown
        assert bd.total_cost == pytest.approx(bd.decision_cost + bd.reporting_cost)


def test_solver_objective_and_common_evaluator_agree(micro_test_environment):
    """Verify that CP-SAT solver's internal objective and common evaluator agree within integer scale precision."""
    flights, gates, config = micro_test_environment

    solver = CPSatGateSolver(config=config)
    sol_res = solver.solve(flights, gates)

    assert sol_res.feasible is True
    assert sol_res.status == "OPTIMAL"

    # Evaluate via common evaluator independently
    eval_res = evaluate_gate_assignment(sol_res.assignments, flights, gates, config)

    # Total objective must match
    assert sol_res.objective_value == pytest.approx(eval_res.objective_value, rel=1e-5)
    # Decision cost must match
    assert sol_res.objective_breakdown.decision_cost == pytest.approx(eval_res.objective_breakdown.decision_cost)
    # Reporting cost must match
    assert sol_res.objective_breakdown.reporting_cost == pytest.approx(eval_res.objective_breakdown.reporting_cost)


def test_weights_and_units_explicit_in_config():
    """Verify all penalty weights and operational timeline settings are explicitly defined in config."""
    cfg = GateOptimizationConfig()
    cfg_dict = cfg.to_dict()

    expected_weights = {
        "reassignment_weight": 10.0,
        "overflow_weight": 200.0,
        "delay_weight": 1.0,
        "conflict_weight": 1000.0,
        "risk_weight": 2.0,
    }
    for k, v in expected_weights.items():
        assert k in cfg_dict
        assert cfg_dict[k] == v

    # Custom weights test
    custom_cfg = GateOptimizationConfig(
        reassignment_weight=25.0,
        overflow_weight=500.0,
        delay_weight=0.0,
        risk_weight=0.0,
    )
    assert custom_cfg.reassignment_weight == 25.0
    assert custom_cfg.overflow_weight == 500.0
    assert custom_cfg.delay_weight == 0.0
    assert custom_cfg.risk_weight == 0.0
