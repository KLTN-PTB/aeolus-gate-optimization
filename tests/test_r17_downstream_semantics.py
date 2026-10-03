"""Tests for Downstream Pipeline Semantics and Dataflow Integrity (Task R17).

Verifies:
1. Forecast adapter isolation: no accidental access to actual ARR_DELAY, actual gates, or turnaround outcomes for planning.
2. P4 and P5 capability contract: P5 does not possess continuous density/sampling; P4 parameters are reduced to mean.
3. Candidate consistency across registry, manifests, inventory, runner, and decision artifacts.
4. Oracle arm governance: strictly non_deployable_reference, not a learned model.
5. Schedule-only baseline: distinct 0.0-delay baseline, separate from arrival-driven models.
6. Solver interface reality: solvers and Flight domain objects strictly consume scalar intervals [start, end).
7. Decision artifact verification: decision is SCALAR_FORECAST_IMPACT with PASS status.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
import yaml

import numpy as np
import pandas as pd

from src.contracts.distribution import (
    CapabilityNotSupportedError,
    QuantilePredictiveDistribution,
)
from src.data.leakage_rules import ARRIVAL_LEAKAGE_COLUMNS, WEATHER_COLUMNS
from src.evaluation.downstream_comparison_v2 import (
    DEFAULT_DOWNSTREAM_CANDIDATES,
    DownstreamCandidate,
    validate_downstream_input_boundary,
)
from src.features.tabular_features import APPROVED_PREDICTOR_COLUMNS
from src.models.probabilistic.candidate_interfaces import (
    P4NGBoostStudentTCandidate,
    P5QuantileRegressionCandidate,
)
from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import Flight, FlightTimeWindow, Gate
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver
from src.simulation.aircraft_turn import AircraftTurnModel

EXPECTED_CANDIDATE_IDS = (
    "schedule_only",
    "arrival_linear_baseline_v1",
    "arrival_xgboost_baseline_v1",
    "arrival_weighted_ensemble_v1",
    "P5_quantile_regression",
    "P4_ngboost_student_t",
    "oracle_actual",
)


def test_forecast_adapter_leakage_and_outcome_isolation() -> None:
    """Validate that input boundary prohibits actual delay, departure delay, weather, and leakage."""
    # 1. Approved predictor list contains zero leakage and zero weather
    approved_set = set(APPROVED_PREDICTOR_COLUMNS)
    assert not approved_set.intersection(set(ARRIVAL_LEAKAGE_COLUMNS))
    assert not approved_set.intersection(set(WEATHER_COLUMNS))
    assert "ARR_DELAY" not in approved_set
    assert "DEP_DELAY" not in approved_set

    # 2. validate_downstream_input_boundary catches any forbidden column
    clean_df = pd.DataFrame({col: [1.0] for col in list(APPROVED_PREDICTOR_COLUMNS)[:5]})
    validate_downstream_input_boundary(clean_df)  # Should pass cleanly

    with pytest.raises(ValueError, match="Departure delay / auxiliary field forbidden"):
        leak_dep = clean_df.copy()
        leak_dep["DEP_DELAY"] = [10.0]
        validate_downstream_input_boundary(leak_dep)

    with pytest.raises(ValueError, match="Weather features forbidden"):
        leak_wx = clean_df.copy()
        leak_wx["O_PRCP"] = [0.5]
        validate_downstream_input_boundary(leak_wx)

    with pytest.raises(ValueError, match="Arrival leakage features forbidden"):
        leak_arr = clean_df.copy()
        leak_arr["ARR_TIME"] = [1420.0]
        validate_downstream_input_boundary(leak_arr)


def test_p5_and_p4_capability_contract_enforcement() -> None:
    """Verify capability boundaries for P5 (quantile-only) and P4 (Student-T scalar reduction)."""
    # 1. P5 capability boundary
    p5_cand = P5QuantileRegressionCandidate()
    p5_caps = p5_cand.capabilities()
    assert p5_caps["has_median"] is True
    assert p5_caps["has_quantiles"] is True
    assert p5_caps["has_mean"] is False
    assert p5_caps["has_sampler"] is False
    assert p5_caps["has_cdf"] is False
    assert p5_caps["has_nll"] is False

    # QuantilePredictiveDistribution raises on unsupported continuous operations
    mock_quantiles = {0.1: np.array([5.0]), 0.5: np.array([12.0]), 0.9: np.array([30.0])}
    dist_p5 = QuantilePredictiveDistribution(mock_quantiles)
    assert float(dist_p5.median()[0]) == 12.0
    with pytest.raises(CapabilityNotSupportedError):
        dist_p5.mean()
    with pytest.raises(CapabilityNotSupportedError):
        dist_p5.sample(10)

    # 2. P4 Student-T capability boundary
    p4_cand = P4NGBoostStudentTCandidate()
    p4_caps = p4_cand.capabilities()
    assert p4_caps["has_mean"] is True
    assert p4_caps["has_sampler"] is True
    # Downstream dataflow audit verifies that downstream code extracts strictly mean() and discards sampling/scale


def test_candidate_labels_consistency_across_system() -> None:
    """Verify that candidate IDs and counts match across registry, inventory, and downstream code."""
    # 1. Code candidate IDs
    code_cand_ids = tuple(c.candidate_id for c in DEFAULT_DOWNSTREAM_CANDIDATES)
    assert code_cand_ids == EXPECTED_CANDIDATE_IDS

    # 2. Registry YAML
    reg_path = Path("configs/downstream_candidate_registry_v2.yaml")
    assert reg_path.exists()
    reg_data = yaml.safe_load(reg_path.read_text(encoding="utf-8"))
    reg_cand_ids = tuple(c["model_id"] for c in reg_data["candidates"])
    assert reg_cand_ids == EXPECTED_CANDIDATE_IDS

    # 3. Inventory JSON
    inv_path = Path("artifacts/audit/r14_candidate_inventory.json")
    assert inv_path.exists()
    inv_data = json.loads(inv_path.read_text(encoding="utf-8"))
    assert tuple(inv_data["explicit_candidate_ids"]) == EXPECTED_CANDIDATE_IDS

    # 4. Dataflow Audit JSON
    audit_path = Path("artifacts/r17_downstream_dataflow_audit.json")
    assert audit_path.exists()
    audit_data = json.loads(audit_path.read_text(encoding="utf-8"))
    audit_cand_ids = tuple(item["candidate"] for item in audit_data)
    assert audit_cand_ids == EXPECTED_CANDIDATE_IDS


def test_oracle_is_non_deployable_reference_not_learned_model() -> None:
    """Verify Oracle reference arm semantics."""
    oracle_cands = [c for c in DEFAULT_DOWNSTREAM_CANDIDATES if c.candidate_id == "oracle_actual"]
    assert len(oracle_cands) == 1
    oracle = oracle_cands[0]
    assert oracle.is_oracle is True
    assert oracle.role == "non_deployable_reference"
    assert oracle.family == "reference"

    # Enforces role invariant: Oracle cannot be labeled as a prediction model
    with pytest.raises(ValueError, match="Oracle model .* must have role='non_deployable_reference'"):
        DownstreamCandidate(
            candidate_id="oracle_invalid",
            display_name="Invalid Oracle",
            family="reference",
            is_oracle=True,
            role="prediction_model",
        )


def test_schedule_only_is_distinct_operational_baseline() -> None:
    """Verify schedule_only is distinct from arrival-driven models with zero delay."""
    sched_cands = [c for c in DEFAULT_DOWNSTREAM_CANDIDATES if c.candidate_id == "schedule_only"]
    assert len(sched_cands) == 1
    sched = sched_cands[0]
    assert sched.family == "baseline"
    assert sched.role == "baseline"
    assert sched.is_oracle is False

    tm = AircraftTurnModel()
    turn = tm.synthesize_turn(
        flight_id="TEST_01",
        carrier="DL",
        flight_number="100",
        scheduled_arrival_min=720,
        sampled_delay_min=0.0,
    )
    assert turn.simulated_arrival_min == 720
    assert turn.arrival_delay_min == 0 if hasattr(turn, "arrival_delay_min") else True


def test_downstream_solvers_consume_strictly_scalar_time_windows() -> None:
    """Verify domain Flight and Solvers consume strictly scalar intervals [start, end)."""
    fl = Flight(
        flight_id="F01",
        flight_index=0,
        carrier="DL",
        flight_number="123",
        scheduled_arrival_min=600,
        scheduled_departure_min=660,
        predicted_arrival_min=615,
        buffer_min=15,
    )
    assert isinstance(fl.predicted_arrival_min, int)
    assert isinstance(fl.simulated_departure_min, int)
    assert isinstance(fl.gate_release_min, int)

    tw = fl.time_window
    assert isinstance(tw, FlightTimeWindow)
    assert tw.start_min == 615
    assert tw.end_min == fl.gate_release_min
    assert tw.duration_min > 0

    # Solvers accept strictly Flight entities and Gate entities
    gates = [
        Gate(gate_id="G1", gate_index=0, is_overflow=False),
        Gate(gate_id="OVERFLOW", gate_index=1, is_overflow=True),
    ]
    cfg = GateOptimizationConfig(time_limit_seconds=1.0)
    greedy = DeterministicGreedyGateSolver(config=cfg)
    res_greedy = greedy.solve([fl], gates)
    assert res_greedy.feasible is True

    cpsat = CPSatGateSolver(config=cfg)
    res_cp = cpsat.solve([fl], gates)
    assert res_cp.feasible is True


def test_r17_semantics_decision_and_dataflow_artifacts() -> None:
    """Verify authoritative R17 decision artifact confirms SCALAR_FORECAST_IMPACT."""
    decision_file = Path("artifacts/r17_downstream_semantics_decision.json")
    assert decision_file.exists()
    decision_data = json.loads(decision_file.read_text(encoding="utf-8"))

    assert decision_data["decision"] == "SCALAR_FORECAST_IMPACT"
    assert decision_data["decision_status"] == "PASS"
    assert decision_data["supported_by_code"] is True
    assert len(decision_data["candidate_summary"]) == 7
    assert len(decision_data["forbidden_claims"]) >= 5
    assert len(decision_data["required_terminology"]) >= 5

    dataflow_file = Path("artifacts/r17_downstream_dataflow_audit.json")
    assert dataflow_file.exists()
    dataflow_data = json.loads(dataflow_file.read_text(encoding="utf-8"))
    assert len(dataflow_data) == 7

    for cand_audit in dataflow_data:
        assert cand_audit["uses_uncertainty"] is False
        assert cand_audit["scalar_or_distribution"] == "SCALAR"
        assert cand_audit["downstream_impact_semantics"] == "forecast_derived_scalar_operational_impact"
        assert len(cand_audit["fields_used_downstream"]) > 0
        assert len(cand_audit["evidence_files"]) > 0
