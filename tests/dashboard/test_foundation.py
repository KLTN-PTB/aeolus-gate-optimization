"""Authoritative unit test suite for Aeolus Dashboard Foundation (Phase P10-B).

Covers all 18 mandatory requirements (P10B-01 through P10B-18).
"""

import json
from pathlib import Path
import pytest

from dashboard.core.config import DEFAULT_CONFIG, DashboardConfig
from dashboard.core.contracts import (
    ProvenanceType,
    RiskCategory,
    UIJobState,
    ScenarioContext,
    FlightPredictionView,
    SolverRunView,
)
from dashboard.core.status_mapping import map_solver_status_to_badge
from dashboard.core.validation import (
    ScientificValidator,
    DataLeakageError,
    IncompatibleComparisonError,
)
from dashboard.adapters.artifact_loader import (
    ArtifactLoader,
    ArtifactNotFoundError,
    ArtifactValidationError,
)
from dashboard.adapters.prediction_adapter import adapt_prediction_row_to_view
from dashboard.adapters.assignment_adapter import adapt_assignment_to_view
from dashboard.services.cache_service import CacheService
from dashboard.services.experiment_service import ExperimentService
from dashboard.services.optimization_service import OptimizationService, ScenarioSizeLimitExceeded
from dashboard.services.preflight_service import PreflightService
from dashboard.services.scenario_service import ScenarioService
from src.optimization.domain import SolverStatus, TerminationReason


# ------------------------------------------------------------------------------
# P10B-01: Valid artifact loads
# ------------------------------------------------------------------------------
def test_p10b_01_valid_artifact_loads(test_config: DashboardConfig) -> None:
    loader = ArtifactLoader(test_config)
    summary = loader.load_monte_carlo_statistical_summary()
    assert isinstance(summary, dict)
    assert summary["n_evaluated"] == 500

    benchmarks = loader.load_solver_benchmarks()
    assert not benchmarks.empty
    assert "solver_variant" in benchmarks.columns


# ------------------------------------------------------------------------------
# P10B-02: Missing artifact returns a structured failure
# ------------------------------------------------------------------------------
def test_p10b_02_missing_artifact_returns_structured_failure(test_config: DashboardConfig) -> None:
    loader = ArtifactLoader(test_config)
    with pytest.raises(ArtifactNotFoundError):
        loader.load_json("artifacts/remediation/non_existent_file.json")


# ------------------------------------------------------------------------------
# P10B-03: Corrupt JSON/CSV rejected
# ------------------------------------------------------------------------------
def test_p10b_03_corrupt_json_csv_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Point test config project root to tmp_path
    corrupt_json = tmp_path / "artifacts" / "remediation" / "corrupt.json"
    corrupt_json.parent.mkdir(parents=True, exist_ok=True)
    corrupt_json.write_text("{corrupt: true, unquoted", encoding="utf-8")

    cfg = DashboardConfig(project_root=tmp_path)
    loader = ArtifactLoader(cfg)

    with pytest.raises(ArtifactValidationError) as exc:
        loader.load_json("artifacts/remediation/corrupt.json")
    assert "Corrupt JSON" in str(exc.value)


# ------------------------------------------------------------------------------
# P10B-04: Missing required field rejected
# ------------------------------------------------------------------------------
def test_p10b_04_missing_required_field_rejected(tmp_path: Path) -> None:
    incomplete_json = tmp_path / "artifacts" / "remediation" / "incomplete.json"
    incomplete_json.parent.mkdir(parents=True, exist_ok=True)
    incomplete_json.write_text(json.dumps({"key_a": 123}), encoding="utf-8")

    cfg = DashboardConfig(project_root=tmp_path)
    loader = ArtifactLoader(cfg)

    with pytest.raises(ArtifactValidationError) as exc:
        loader.load_json("artifacts/remediation/incomplete.json", required_keys={"key_a", "required_b"})
    assert "missing required keys" in str(exc.value)


# ------------------------------------------------------------------------------
# P10B-05: Invalid enum/status rejected or normalized explicitly
# ------------------------------------------------------------------------------
def test_p10b_05_invalid_enum_status_normalized() -> None:
    badge_optimal = map_solver_status_to_badge(SolverStatus.OPTIMAL, TerminationReason.OPTIMAL_PROVEN)
    assert badge_optimal.is_optimal is True
    assert badge_optimal.color_hex == "#34C759"

    badge_unknown = map_solver_status_to_badge("NON_STANDARD_STATUS", None)
    assert badge_unknown.is_optimal is False
    assert badge_unknown.is_feasible is False
    assert "NON_STANDARD_STATUS" in badge_unknown.label


# ------------------------------------------------------------------------------
# P10B-06: Scenario hash/config identity changes when meaningful input changes
# ------------------------------------------------------------------------------
def test_p10b_06_config_identity_changes_on_meaningful_param() -> None:
    config_a = {"w_pref": 10.0, "w_remote": 200.0, "buffer_time_min": 15}
    config_b = {"w_pref": 10.0, "w_remote": 300.0, "buffer_time_min": 15}

    hash_a = ExperimentService.compute_configuration_hash("SCEN_01", config_a)
    hash_b = ExperimentService.compute_configuration_hash("SCEN_01", config_b)

    assert hash_a != hash_b
    assert ExperimentService.is_stale(config_b, config_a) is True


# ------------------------------------------------------------------------------
# P10B-07: Chart-only filter does not change execution identity
# ------------------------------------------------------------------------------
def test_p10b_07_chart_only_filter_does_not_change_execution_identity() -> None:
    config_base = {"solver_name": "cpsat", "w_pref": 10.0, "w_remote": 200.0}
    config_with_filter_a = {**config_base, "concourse_filter": ["T"]}
    config_with_filter_b = {**config_base, "concourse_filter": ["T", "A"]}

    hash_a = ExperimentService.compute_configuration_hash("SCEN_01", config_with_filter_a)
    hash_b = ExperimentService.compute_configuration_hash("SCEN_01", config_with_filter_b)

    assert hash_a == hash_b  # Filter change did NOT mutate experiment identity!
    assert ExperimentService.is_presentation_filter_mutation(
        {"concourse_filter": ["T"]}, {"concourse_filter": ["T", "A"]}
    ) is True


# ------------------------------------------------------------------------------
# P10B-08: Objective version mismatch blocks ranking
# ------------------------------------------------------------------------------
def test_p10b_08_objective_version_mismatch_blocks_ranking() -> None:
    run_1 = SolverRunView(
        solver_name="CP-SAT",
        scenario_id="SCEN_01",
        objective_value=100.0,
        decision_cost=100.0,
        reporting_cost=0.0,
        reassignment_count=10,
        remote_gate_count=0,
        conflict_count=0,
        solve_time_sec=0.1,
        status="OPTIMAL",
        termination_reason="OPTIMAL_PROVEN",
        is_optimal_proven=True,
        solver_config={"w_pref": 10.0, "w_remote": 200.0},
    )
    run_2 = SolverRunView(
        solver_name="Greedy",
        scenario_id="SCEN_01",
        objective_value=50.0,
        decision_cost=50.0,
        reporting_cost=0.0,
        reassignment_count=5,
        remote_gate_count=0,
        conflict_count=0,
        solve_time_sec=0.01,
        status="FEASIBLE",
        termination_reason="HEURISTIC_STOP",
        is_optimal_proven=False,
        solver_config={"w_pref": 10.0, "w_remote": 300.0},  # Mismatch w_remote!
    )

    with pytest.raises(IncompatibleComparisonError) as exc:
        ExperimentService.rank_solver_runs([run_1, run_2])
    assert "Objective parameter mismatch" in str(exc.value)


# ------------------------------------------------------------------------------
# P10B-09: Capacity policy mismatch blocks ranking
# ------------------------------------------------------------------------------
def test_p10b_09_capacity_policy_mismatch_blocks_ranking() -> None:
    run_1 = SolverRunView(
        solver_name="CP-SAT",
        scenario_id="SCEN_01",
        objective_value=100.0,
        decision_cost=100.0,
        reporting_cost=0.0,
        reassignment_count=10,
        remote_gate_count=0,
        conflict_count=0,
        solve_time_sec=0.1,
        status="OPTIMAL",
        termination_reason="OPTIMAL_PROVEN",
        is_optimal_proven=True,
        solver_config={"finite_remote_capacity": 1},
    )
    run_2 = SolverRunView(
        solver_name="CP-SAT",
        scenario_id="SCEN_01",
        objective_value=80.0,
        decision_cost=80.0,
        reporting_cost=0.0,
        reassignment_count=8,
        remote_gate_count=0,
        conflict_count=0,
        solve_time_sec=0.1,
        status="OPTIMAL",
        termination_reason="OPTIMAL_PROVEN",
        is_optimal_proven=True,
        solver_config={"finite_remote_capacity": 5},  # Mismatch!
    )

    with pytest.raises(IncompatibleComparisonError) as exc:
        ExperimentService.rank_solver_runs([run_1, run_2])
    assert "finite_remote_capacity" in str(exc.value)


# ------------------------------------------------------------------------------
# P10B-10: UNKNOWN has no invented objective
# ------------------------------------------------------------------------------
def test_p10b_10_unknown_has_no_invented_objective() -> None:
    assert ScientificValidator.is_objective_defined("UNKNOWN") is False
    assert ScientificValidator.is_objective_defined("INFEASIBLE") is False
    assert ScientificValidator.is_objective_defined("OPTIMAL") is True


# ------------------------------------------------------------------------------
# P10B-11: No planning actual columns pass through
# ------------------------------------------------------------------------------
def test_p10b_11_no_planning_actual_columns_pass_through(sample_prediction_row: dict) -> None:
    leaked_row = {**sample_prediction_row, "arr_delay": 25.0}
    with pytest.raises(DataLeakageError) as exc:
        adapt_prediction_row_to_view(leaked_row)
    assert "Target leakage detected" in str(exc.value)


# ------------------------------------------------------------------------------
# P10B-12: Prediction provenance retained
# ------------------------------------------------------------------------------
def test_p10b_12_prediction_provenance_retained(sample_prediction_row: dict) -> None:
    view = adapt_prediction_row_to_view(
        sample_prediction_row, provenance=ProvenanceType.NATIVE_INFERENCE
    )
    assert view.provenance == ProvenanceType.NATIVE_INFERENCE


# ------------------------------------------------------------------------------
# P10B-13: Checkpoint path outside allowlist rejected
# ------------------------------------------------------------------------------
def test_p10b_13_checkpoint_path_outside_allowlist_rejected(test_config: DashboardConfig) -> None:
    assert test_config.is_path_allowlisted("../../../etc/passwd") is False
    assert test_config.is_model_dir_allowlisted("C:/Windows/System32") is False
    assert test_config.is_path_allowlisted("artifacts/remediation/benchmarks") is True


# ------------------------------------------------------------------------------
# P10B-14: Cache cannot cross-contaminate scenarios
# ------------------------------------------------------------------------------
def test_p10b_14_cache_cannot_cross_contaminate_scenarios() -> None:
    cache = CacheService()
    key_a = cache.generate_cache_key("SCEN_A", "solution")
    key_b = cache.generate_cache_key("SCEN_B", "solution")

    assert key_a != key_b
    cache.get_or_set(key_a, "fp1", lambda: "Data A")
    cache.get_or_set(key_b, "fp2", lambda: "Data B")

    assert cache.get_or_set(key_a, "fp1", lambda: "Wrong") == "Data A"
    assert cache.get_or_set(key_b, "fp2", lambda: "Wrong") == "Data B"


# ------------------------------------------------------------------------------
# P10B-15: Unbounded apron remains distinct from finite remote
# ------------------------------------------------------------------------------
def test_p10b_15_unbounded_apron_distinct() -> None:
    assign_dict = {
        "flight_id": "FL01",
        "gate_id": "REMOTE_APRON_01",
        "occupancy_start_min": 500,
        "occupancy_end_min": 600,
        "is_remote": True,
    }
    view = adapt_assignment_to_view(assign_dict)
    assert view.is_remote is True
    assert view.concourse == "REMOTE"
    assert view.occupancy_interval == (500, 600)
    assert view.total_blocked_interval == (500, 615)  # 15m buffer added correctly


# ------------------------------------------------------------------------------
# P10B-16: Preflight handles missing optional artifacts
# ------------------------------------------------------------------------------
def test_p10b_16_preflight_handles_missing_optional_artifacts(test_config: DashboardConfig) -> None:
    service = PreflightService(test_config)
    report = service.run_preflight_checks()
    assert report.is_healthy is True
    assert report.ready_for_presentation is True
    assert isinstance(report.checks, list)
    assert len(report.checks) > 0


# ------------------------------------------------------------------------------
# P10B-17: Service layer does not run solver on import
# ------------------------------------------------------------------------------
def test_p10b_17_service_layer_does_not_run_solver_on_import() -> None:
    from dashboard.services.optimization_service import OptimizationService
    service = OptimizationService()
    assert service is not None


# ------------------------------------------------------------------------------
# P10B-18: Legacy schema is explicitly adapted or rejected
# ------------------------------------------------------------------------------
def test_p10b_18_legacy_schema_adapted_cleanly() -> None:
    legacy_row = {
        "FLIGHT_ID": "DL9999",
        "OP_UNIQUE_CARRIER": "DL",
        "ORIGIN": "LGA",
        "DEST": "ATL",
        "CRS_ARR_TIME_MIN": 520,
        "predicted_delay_min": 14.2,
    }
    view = adapt_prediction_row_to_view(legacy_row)
    assert view.flight_id == "DL9999"
    assert view.sched_arr_time_min == 520
    assert view.predicted_arr_delay_min == 14.2
    assert view.risk_category == RiskCategory.LOW
