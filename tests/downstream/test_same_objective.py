"""Tests for common objective formulation and identical evaluator across models (Phase 8)."""

from __future__ import annotations

import pytest

from src.evaluation.downstream_comparison import (
    DEFAULT_DOWNSTREAM_CANDIDATES,
    evaluate_candidate_on_scenario,
    extract_scenario_from_raw,
    DownstreamScenarioSpec,
)
from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import verify_hard_constraints_independently
from src.optimization.evaluation import evaluate_gate_assignment
from tests.downstream.test_same_scenario import _make_dummy_raw_df


def test_standard_objective_weights_invariant() -> None:
    """Standard soft objective weights must remain strictly invariant across all evaluations."""
    cfg = GateOptimizationConfig()
    assert cfg.reassignment_weight == 10.0
    assert cfg.overflow_weight == 200.0
    assert cfg.delay_weight == 1.0
    assert cfg.conflict_weight == 1000.0
    assert cfg.risk_weight == 2.0


def test_evaluator_produces_identical_objective_for_identical_assignment() -> None:
    """The common evaluator must produce bitwise identical objective for identical assignments."""
    spec = DownstreamScenarioSpec(
        scenario_id="SCEN_OBJ_TEST",
        day_id="2023-07-03",
        date_str="2023-07-03",
        n_flights=10,
        n_contact_gates=4,
    )
    raw_df = _make_dummy_raw_df("2023-07-03", n_rows=20)
    scenario = extract_scenario_from_raw(spec, raw_df)

    cfg = GateOptimizationConfig()
    preds_zero = [0.0] * 10

    # Evaluate schedule_only candidate
    rec1 = evaluate_candidate_on_scenario(
        candidate=DEFAULT_DOWNSTREAM_CANDIDATES[0],  # schedule_only
        scenario=scenario,
        predicted_delays=preds_zero,
        solver_name="DeterministicGreedy",
        config=cfg,
    )

    # Evaluate another candidate with same predictions and same config
    rec2 = evaluate_candidate_on_scenario(
        candidate=DEFAULT_DOWNSTREAM_CANDIDATES[1],  # linear baseline
        scenario=scenario,
        predicted_delays=preds_zero,
        solver_name="DeterministicGreedy",
        config=cfg,
    )

    assert rec1.objective_value == rec2.objective_value
    assert rec1.decision_cost == rec2.decision_cost
    assert rec1.reporting_cost == rec2.reporting_cost
    assert rec1.reassignment_count == rec2.reassignment_count
    assert rec1.conflict_count == rec2.conflict_count


def test_no_model_can_modify_objective_weights() -> None:
    """GateOptimizationConfig must be frozen and immutable."""
    cfg = GateOptimizationConfig()
    with pytest.raises(Exception):
        cfg.reassignment_weight = 5.0  # type: ignore[misc]

    with pytest.raises(Exception):
        cfg.conflict_weight = 0.0  # type: ignore[misc]
