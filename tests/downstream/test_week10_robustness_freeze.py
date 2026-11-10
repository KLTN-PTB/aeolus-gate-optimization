"""Unit and integration tests for Week 10 Robustness, Recourse, and Full System Freeze (P10-B)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import pytest

from src.data.access_guard import (
    DataAccessDenied,
    assert_data_access_allowed,
    is_system_freeze_confirmed,
)
from src.evaluation.native_downstream_p4 import (
    P4_CERTIFIED_CHECKPOINT_PATH,
    P4_CERTIFIED_SHA256,
    verify_and_load_p4_checkpoint,
)
from src.evaluation.week10_robustness_recourse import (
    WEEK10_ARTIFACTS_DIR,
    ModeAFixedPlanRecord,
    ModeBRecourseRecord,
    evaluate_mode_a_fixed_plan,
    evaluate_mode_b_recourse,
)
from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import Flight, FlightTimeWindow, Gate, GateAssignment
from src.optimization.evaluation import evaluate_gate_assignment

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "artifacts" / "manifests" / "system_freeze_manifest.json"
CHECKSUM_PATH = ROOT / "artifacts" / "manifests" / "system_freeze_manifest.sha256"
ROOT_MANIFEST_PATH = ROOT / "system_freeze_manifest.json"


def test_2024_holdout_guard_remains_strictly_sealed() -> None:
    """Verify that 2024 access for development and HPO raises DataAccessDenied."""
    with pytest.raises(DataAccessDenied, match="2024 is sealed from development access"):
        assert_data_access_allowed(2024, "development")

    with pytest.raises(DataAccessDenied, match="HPO is blocked"):
        assert_data_access_allowed(2024, "hpo")


def test_certified_p4_checkpoint_integrity() -> None:
    """Verify that the frozen P4 checkpoint exists, has expected SHA-256, and loads cleanly."""
    model, meta = verify_and_load_p4_checkpoint(
        checkpoint_path=P4_CERTIFIED_CHECKPOINT_PATH,
        expected_sha256=P4_CERTIFIED_SHA256,
    )
    assert meta["sha256"] == P4_CERTIFIED_SHA256
    assert meta["verification_status"] == "CERTIFIED_VALID"
    assert model.is_fitted_ is True


def test_mode_a_and_mode_b_semantic_separation() -> None:
    """Verify that Mode A (Fixed-Plan) and Mode B (Recourse) have distinct semantics."""
    # Synthetic two-flight setup that conflicts under delay
    f1 = Flight(
        flight_id="FL1",
        flight_index=0,
        carrier="DL",
        flight_number="101",
        scheduled_arrival_min=100,
        scheduled_departure_min=160,
        predicted_arrival_min=100,
        nominal_gate_id="G1",
        default_dwell_min=60,
        min_turnaround_min=45,
        buffer_min=15,
    )
    # Flight 2 originally scheduled later: arrival 200, departure 260
    f2_nominal = Flight(
        flight_id="FL2",
        flight_index=1,
        carrier="DL",
        flight_number="102",
        scheduled_arrival_min=200,
        scheduled_departure_min=260,
        predicted_arrival_min=200,
        nominal_gate_id="G1",
        default_dwell_min=60,
        min_turnaround_min=45,
        buffer_min=15,
    )
    # Realized flight 2 arrived early: predicted/realized arrival 120, departure 180, gate release 195 -> overlaps FL1 [100, 175)
    f2_realized = Flight(
        flight_id="FL2",
        flight_index=1,
        carrier="DL",
        flight_number="102",
        scheduled_arrival_min=200,
        scheduled_departure_min=260,
        predicted_arrival_min=120,
        nominal_gate_id="G1",
        default_dwell_min=60,
        min_turnaround_min=45,
        buffer_min=15,
    )

    g1 = Gate(gate_id="G1", gate_index=0, is_overflow=False)
    overflow = Gate(gate_id="OVERFLOW", gate_index=1, is_overflow=True)
    gates = [g1, overflow]

    cfg = GateOptimizationConfig(conflict_weight=1000.0, overflow_weight=200.0, reassignment_weight=10.0)

    # Planned assignment: both assigned to G1 (since under nominal schedule they were disjoint)
    planned_assigns = {
        "FL1": GateAssignment(
            flight_id="FL1",
            gate_id="G1",
            flight_index=0,
            gate_index=0,
            is_overflow=False,
            is_reassignment=False,
            occupancy_start_min=100,
            occupancy_end_min=175,
        ),
        "FL2": GateAssignment(
            flight_id="FL2",
            gate_id="G1",
            flight_index=1,
            gate_index=0,
            is_overflow=False,
            is_reassignment=False,
            occupancy_start_min=200,
            occupancy_end_min=275,
        ),
    }

    # Mode A: Hold plan fixed -> Must detect conflict on G1!
    realized_flights = [f1, f2_realized]
    rec_a, fail_a = evaluate_mode_a_fixed_plan(
        planned_assignments=planned_assigns,
        realized_flights=realized_flights,
        gates=gates,
        config=cfg,
        realization_id="TEST_REAL_001",
        scenario_index=0,
        model_id="P4_test",
    )
    assert rec_a.conflict_count == 1
    assert rec_a.feasible is False
    assert rec_a.realized_objective >= 1000.0
    assert fail_a.failure_class == "CONFLICT_VIOLATION"

    # Mode B: Recourse -> Re-optimize -> Must resolve conflict by moving FL2 to overflow or free gate!
    rec_b, fail_b = evaluate_mode_b_recourse(
        nominal_schedule_assignments=planned_assigns,
        realized_flights=realized_flights,
        gates=gates,
        config=cfg,
        realization_id="TEST_REAL_001",
        scenario_index=0,
        model_id="P4_test",
        fixed_conflicts=rec_a.conflict_count,
        recourse_solver_name="DeterministicGreedy",
    )
    assert rec_b.resolved_conflicts == 1
    assert rec_b.post_recourse_conflicts == 0
    assert rec_b.recourse_feasible is True
    assert rec_b.recourse_objective < rec_a.realized_objective
    assert fail_b.failure_class == "SUCCESS"


def test_pilot_robustness_results_artifact() -> None:
    """Verify pilot results artifact contains Pilot 20 and Pilot 50 data."""
    pilot_path = WEEK10_ARTIFACTS_DIR / "pilot_robustness_results.json"
    assert pilot_path.exists(), f"Missing pilot results at {pilot_path}"
    data = json.loads(pilot_path.read_text(encoding="utf-8"))

    assert "pilot_20" in data
    assert "pilot_50" in data
    assert data["pilot_20"]["pilot_count"] == 20
    assert data["pilot_50"]["pilot_count"] == 50
    assert data["pilot_20"]["zero_truncation_verified"] is True
    assert data["pilot_50"]["zero_truncation_verified"] is True
    assert data["pilot_20"]["mode_a_fixed_plan"]["feasibility_rate"] == 1.0
    assert data["pilot_50"]["mode_a_fixed_plan"]["feasibility_rate"] == 1.0


def test_sensitivity_results_artifact() -> None:
    """Verify sensitivity results artifact contains all 7 registered dimensions."""
    sens_path = WEEK10_ARTIFACTS_DIR / "sensitivity_results.json"
    assert sens_path.exists(), f"Missing sensitivity results at {sens_path}"
    records = json.loads(sens_path.read_text(encoding="utf-8"))

    dimensions = set(r["dimension"] for r in records)
    expected_dimensions = {
        "pairing",
        "turnaround_parameters",
        "arrival_risk_buffer",
        "gate_mix",
        "compute_budget",
        "objective_weights",
        "robustness_distribution",
    }
    assert expected_dimensions.issubset(dimensions), f"Missing dimensions: {expected_dimensions - dimensions}"
    assert len(records) >= 15


def test_failure_accounting_artifact() -> None:
    """Verify failure accounting artifact tracks all realizations with zero dropping."""
    fail_path = WEEK10_ARTIFACTS_DIR / "failure_accounting.json"
    assert fail_path.exists(), f"Missing failure accounting at {fail_path}"
    data = json.loads(fail_path.read_text(encoding="utf-8"))

    assert data["zero_dropped_cases_verified"] is True
    assert data["total_records_tracked"] >= 1000
    assert "MODE_A_FIXED_PLAN" in data["failure_breakdown_by_mode"]
    assert "MODE_B_RECOURSE" in data["failure_breakdown_by_mode"]


def test_system_freeze_manifest_28_dimensions() -> None:
    """Verify that system_freeze_manifest.json contains all 28 dimensions and certified declarations."""
    assert MANIFEST_PATH.exists(), f"Missing freeze manifest at {MANIFEST_PATH}"
    assert CHECKSUM_PATH.exists(), f"Missing checksum at {CHECKSUM_PATH}"
    assert ROOT_MANIFEST_PATH.exists(), f"Missing root freeze manifest at {ROOT_MANIFEST_PATH}"

    # Verify SHA-256 match
    raw_bytes = MANIFEST_PATH.read_bytes()
    computed_hash = hashlib.sha256(raw_bytes).hexdigest()
    checksum_content = CHECKSUM_PATH.read_text(encoding="utf-8").strip()
    recorded_hash = checksum_content.split()[0]
    assert computed_hash == recorded_hash, f"Checksum mismatch: {computed_hash} != {recorded_hash}"

    payload = json.loads(raw_bytes.decode("utf-8"))

    # Mandatory declarations
    assert payload["freeze_status"] == "FROZEN"
    assert payload["P5_downstream_role"] == "FORECAST_ONLY"
    assert payload["P4_downstream_role"] == "CONTINUOUS_STOCHASTIC_SIMULATION"
    assert payload["P5_reconstruction"] == "NOT_REQUIRED"
    assert payload["2024_status"] == "SEALED"
    assert payload["scientific_claim_scope"] == "SYNTHETIC_SIMULATION"
    assert payload["git_commit"] == "7ba0aba92d366f712977faaaa5a73cba65a32a55"

    # Verify 28 frozen dimensions block
    dim_block = payload["twenty_eight_frozen_dimensions"]
    assert len(dim_block) == 28

    expected_dim_prefixes = [
        "01_core_arrival_feature_set",
        "02_target_definitions",
        "03_prediction_cutoff",
        "04_preprocessing",
        "05_model_architecture",
        "06_p4_checkpoint_hash",
        "07_p5_role_declaration",
        "08_training_policy",
        "09_seed_policy",
        "10_calibration_status",
        "11_distribution_family",
        "12_dependence_mechanism",
        "13_dependence_parameters",
        "14_sampling_procedure",
        "15_monte_carlo_count",
        "16_simulation_configuration",
        "17_gate_configuration",
        "18_objective_function",
        "19_solver_configurations",
        "20_solver_compute_budget",
        "21_sa_parameters",
        "22_robustness_parameters",
        "23_recourse_parameters",
        "24_scenario_generation_policy",
        "25_candidate_selection_rule",
        "26_software_runtime_versions",
        "27_git_commit",
        "28_artifact_hashes",
    ]
    for dim_name in expected_dim_prefixes:
        assert dim_name in dim_block, f"Missing frozen dimension: {dim_name}"

    assert dim_block["06_p4_checkpoint_hash"] == P4_CERTIFIED_SHA256
    assert dim_block["07_p5_role_declaration"]["downstream_role"] == "FORECAST_ONLY"
    assert dim_block["07_p5_role_declaration"]["reconstruction_status"] == "NOT_REQUIRED"
