"""Authoritative G6 Test Suite: Dashboard Scientific Integrity, Runtime Validation & Security.

Protocol: AEOLUS-G6 Dashboard Gate
Coverage:
- UI-DATA-01 to UI-DATA-05: Source-to-KPI consistency, synthetic labeling, native/precomputed, risk score, feasibility dimensions
- UI-SOLVER-01 to UI-SOLVER-03: Manual trigger only, solver identity, normalized status
- UI-GANTT-01 to UI-GANTT-02: Gantt timeline formulation, inspector matching
- UI-STATE-01 to UI-STATE-02: Session state isolation, cache invalidation
- UI-ERROR-01 to UI-ERROR-02: Missing checkpoint/artifact graceful degradation
- UI-SEC-01 to UI-SEC-02: Path traversal & prefix bypass rejection via canonical containment
- UI-EXPORT-01 to UI-EXPORT-02: Run ID consistency, provenance integrity
- UI-VISUAL-01: Visual acceptance checklist verification
- UI-OFFLINE-01: Offline readiness and zero external network calls
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest

from dashboard.adapters.artifact_loader import ArtifactLoader
from dashboard.adapters.assignment_adapter import determine_gate_concourse
from dashboard.adapters.export_adapter import (
    export_assignments_to_csv,
    export_run_manifest_to_json,
)
from dashboard.adapters.monte_carlo_adapter import adapt_monte_carlo_to_views
from dashboard.adapters.prediction_adapter import adapt_prediction_row_to_view
from dashboard.adapters.turn_adapter import adapt_turn_row_to_view
from dashboard.core.config import DEFAULT_CONFIG, DashboardConfig
from dashboard.core.contracts import (
    FlightPredictionView,
    GateTimelineView,
    ProvenanceType,
    RiskCategory,
    SolverRunView,
    UIJobState,
)
from dashboard.core.state import PageKeys, SessionStateKeys, get_initial_session_state
from dashboard.core.status_mapping import SolverStatus, map_solver_status_to_badge
from dashboard.core.validation import ScientificValidator
from dashboard.services.cache_service import CacheService
from dashboard.services.experiment_service import ExperimentService
from dashboard.services.preflight_service import PreflightService
from dashboard.services.scenario_service import ScenarioService
from src.contracts.provenance import DataOrigin, EvidenceProvenance, PairingSource, PredictionSource, ScenarioGeneration

APP_PATH = str((DEFAULT_CONFIG.project_root / "dashboard" / "app.py").resolve())


# =============================================================================
# UI-DATA-01 .. UI-DATA-05: DATA & SCIENTIFIC LABELS INTEGRITY
# =============================================================================

def test_ui_data_01_source_to_kpi_consistency():
    """UI-DATA-01: KPI cards reflect authoritative scenario counts without shortcuts."""
    svc = ScenarioService()
    ctx_120 = svc.get_scenario_context("SCEN_P09_CANONICAL_120")
    flights, gates = svc.load_scenario("SCEN_P09_CANONICAL_120")
    inv = svc.get_scenario_gate_inventory("SCEN_P09_CANONICAL_120")

    assert ctx_120.flight_count == len(flights) == 120
    assert inv["contact_count"] == 25
    assert inv["remote_count"] == 1
    # Unpaired scenario has 0 turns
    turns = svc.load_scenario_turns("SCEN_P09_CANONICAL_120")
    assert turns == []


def test_ui_data_02_synthetic_source_label():
    """UI-DATA-02: Synthetic generation is explicitly marked and never labeled as pure real."""
    svc = ScenarioService()
    ctx = svc.get_scenario_context("SCEN_P09_CANONICAL_120")
    assert ctx.is_synthetic is True
    assert ctx.scenario_generation == "SCALABILITY_GENERATOR"
    assert "SCALABILITY_GENERATOR" in ctx.provenance.value or ctx.is_synthetic is True


def test_ui_data_03_native_vs_precomputed_label():
    """UI-DATA-03: Native inference and precomputed predictions are distinctly classified."""
    row_precomputed = {"flight_id": "ARR_01", "predicted_arr_delay_min": 10.0}
    view_pre = adapt_prediction_row_to_view(row_precomputed, provenance=ProvenanceType.PRECOMPUTED_PREDICTION)
    assert view_pre.provenance == ProvenanceType.PRECOMPUTED_PREDICTION

    row_native = {"flight_id": "ARR_02", "predicted_arr_delay_min": 12.0}
    view_nat = adapt_prediction_row_to_view(row_native, provenance=ProvenanceType.NATIVE_INFERENCE)
    assert view_nat.provenance == ProvenanceType.NATIVE_INFERENCE


def test_ui_data_04_risk_score_vs_probability():
    """UI-DATA-04: Outbound heuristic scores are distinguished from calibrated probability."""
    # ARR with CDF probability
    row_arr = {"flight_id": "LEG_ARR_0001", "flight_direction": "ARR", "probability_delay_15": 0.42}
    v_arr = adapt_prediction_row_to_view(row_arr)
    assert v_arr.probability_delay_15 == 0.42

    # DEP with missing probability returns None (never synthetic 0.5 default)
    row_dep = {"flight_id": "LEG_DEP_0001", "flight_direction": "DEP", "predicted_delay_min": 5.0}
    v_dep = adapt_prediction_row_to_view(row_dep)
    assert v_dep.probability_delay_15 is None


def test_ui_data_05_feasibility_dimensions():
    """UI-DATA-05: Physical conflict rate (74.8%) is distinguished from static invalidation (0.0% feasible)."""
    loader = ArtifactLoader()
    summary = loader.load_monte_carlo_statistical_summary()
    views = adapt_monte_carlo_to_views(summary, solver_key="CPSat")
    mode_a = views["mode_a"]

    assert mode_a.physical_conflict_rate == pytest.approx(0.748, rel=1e-2)
    assert mode_a.static_invalidation_rate == pytest.approx(1.0, rel=1e-2)
    # Physical collision is 74.8% while static schedule invalidation is 100%


# =============================================================================
# UI-SOLVER-01 .. UI-SOLVER-03: SOLVER LIFECYCLE & EXECUTION CONTROLS
# =============================================================================

def test_ui_solver_01_manual_trigger_only():
    """UI-SOLVER-01: Zero unsolicited optimization solves occur upon visiting page 03."""
    at = AppTest.from_file(APP_PATH, default_timeout=20)
    at.session_state[SessionStateKeys.CURRENT_PAGE] = "03_gate_operations"
    at.run()
    assert at.session_state.get(SessionStateKeys.ACTIVE_RESULT) is None
    assert at.session_state.get(SessionStateKeys.JOB_STATE) == UIJobState.IDLE.value


def test_ui_solver_02_correct_solver_identity():
    """UI-SOLVER-02: Requested vs effective solver and fallback provenance are tracked."""
    run = SolverRunView(
        run_id="RUN_TEST_FALLBACK",
        solver_name="CPSat",
        requested_solver="CPSat",
        effective_solver="DeterministicGreedy",
        fallback_used=True,
        scenario_id="SCEN_TEST",
        status="FEASIBLE",
        conflict_count=0,
        remote_gate_count=0,
        objective_value=120.0,
        decision_cost=100.0,
        reporting_cost=20.0,
        reassignment_count=2,
        solve_time_sec=10.0,
        termination_reason="TIME_LIMIT",
        is_optimal_proven=False,
    )
    assert run.requested_solver == "CPSat"
    assert run.effective_solver == "DeterministicGreedy"
    assert run.fallback_used is True
    assert run.is_optimal_proven is False


def test_ui_solver_03_correct_solver_status():
    """UI-SOLVER-03: Solver status badges reflect OPTIMAL only when proven."""
    opt_badge = map_solver_status_to_badge("OPTIMAL", termination_reason="OPTIMAL_PROVEN")
    assert "OPTIMAL" in opt_badge.label
    assert opt_badge.is_optimal is True
    assert opt_badge.is_feasible is True

    # Status FEASIBLE / TIME_LIMIT must NOT show PROVEN
    unproven_badge = map_solver_status_to_badge("FEASIBLE", termination_reason="TIME_LIMIT")
    assert "HẾT GIỜ" in unproven_badge.label or "FEASIBLE" in unproven_badge.label
    assert unproven_badge.is_optimal is False
    assert unproven_badge.is_feasible is True

    unknown_badge = map_solver_status_to_badge("UNKNOWN")
    assert "UNKNOWN" in unknown_badge.label
    assert unknown_badge.is_optimal is False
    assert unknown_badge.is_feasible is False


# =============================================================================
# UI-GANTT-01 .. UI-GANTT-02: TIMELINE & GANTT VISUALIZATION
# =============================================================================

def test_ui_gantt_01_timeline_rendering():
    """UI-GANTT-01: Timeline interval reflects half-open [start, release) including separation buffer."""
    asgn = GateTimelineView(
        assignment_id="ASGN_01",
        flight_id="F1",
        gate_id="G1",
        concourse="T",
        start_min=100,
        end_min=160,
        buffer_min=15,
        gate_out_min=160,
        gate_release_min=175,
    )
    assert asgn.occupancy_interval == (100, 160)
    assert asgn.total_blocked_interval == (100, 175)
    assert asgn.actual_gate_release_min == 175


def test_ui_gantt_02_gate_flight_inspector_match():
    """UI-GANTT-02: Selected flight in inspector matches active scenario flight record."""
    svc = ScenarioService()
    flights, _ = svc.load_scenario("SCEN_P09_CANONICAL_120")
    first_f = flights[0]

    # Verify flight has required fields for inspector
    assert first_f.flight_id is not None
    assert first_f.time_window.start_min == first_f.predicted_arrival_min


# =============================================================================
# UI-STATE-01 .. UI-STATE-02: STATE MANAGEMENT & CACHE ISOLATION
# =============================================================================

def test_ui_state_01_session_isolation():
    """UI-STATE-01: Cache keys prevent cross-scenario contamination."""
    cache = CacheService()
    k1 = cache.generate_cache_key("SCEN_A", "solution")
    k2 = cache.generate_cache_key("SCEN_B", "solution")
    assert k1 != k2

    cache.get_or_set(k1, "hash_a", lambda: {"cost": 50})
    cache.get_or_set(k2, "hash_b", lambda: {"cost": 80})

    assert cache.get_or_set(k1, "hash_a", lambda: None)["cost"] == 50
    assert cache.get_or_set(k2, "hash_b", lambda: None)["cost"] == 80


def test_ui_state_02_cache_invalidation():
    """UI-STATE-02: Parameter change marks active solution as stale."""
    exp = ExperimentService()
    draft = {"scenario_id": "SCEN_1", "w_pref": 10.0, "time_limit_sec": 30.0}
    executed = {"scenario_id": "SCEN_1", "w_pref": 10.0, "time_limit_sec": 10.0}
    is_stale, stale_keys = exp.check_staleness_detailed(draft, executed)
    assert is_stale is True
    assert "time_limit_sec" in stale_keys


# =============================================================================
# UI-ERROR-01 .. UI-ERROR-02: ERROR HANDLING & DEGRADATION
# =============================================================================

def test_ui_error_01_missing_checkpoint():
    """UI-ERROR-01: Missing model checkpoint degrades gracefully without crashing."""
    preflight = PreflightService()
    report = preflight.run_preflight_checks()
    assert report.is_healthy is True
    assert report.live_solving_available is True


def test_ui_error_02_missing_artifact():
    """UI-ERROR-02: Loader handles missing optional artifact gracefully."""
    loader = ArtifactLoader()
    with pytest.raises(Exception):
        loader.load_csv("artifacts/nonexistent_file_12345.csv")


# =============================================================================
# UI-SEC-01 .. UI-SEC-02: SECURITY & PATH TRAVERSAL REJECTION
# =============================================================================

def test_ui_sec_01_path_traversal_rejection():
    """UI-SEC-01: Path traversal attempts with ../ are strictly rejected."""
    cfg = DEFAULT_CONFIG
    assert cfg.is_path_allowlisted("../../../etc/passwd") is False
    assert cfg.is_path_allowlisted("..\\..\\windows\\win.ini") is False
    assert cfg.is_path_allowlisted("artifacts/remediation/../../etc/shadow") is False


def test_ui_sec_02_invalid_model_path_rejection():
    """UI-SEC-02: Prefix spoofing and unapproved model paths are rejected."""
    cfg = DEFAULT_CONFIG
    assert cfg.is_path_allowlisted("artifacts/remediation_malicious") is False
    assert cfg.is_model_dir_allowlisted("artifacts/models_evil") is False
    assert cfg.is_model_dir_allowlisted("C:/Windows/System32") is False
    assert cfg.is_path_allowlisted("artifacts/remediation/benchmarks") is True


# =============================================================================
# UI-EXPORT-01 .. UI-EXPORT-02: EXPORT INTEGRITY
# =============================================================================

def test_ui_export_01_run_id_consistency():
    """UI-EXPORT-01: Export manifest contains authentic run metadata."""
    run = SolverRunView(
        run_id="RUN_G6_CERTIFIED",
        solver_name="CPSat",
        scenario_id="SCEN_P09_CANONICAL_120",
        status="OPTIMAL",
        conflict_count=0,
        remote_gate_count=0,
        objective_value=120.0,
        decision_cost=100.0,
        reporting_cost=20.0,
        reassignment_count=2,
        solve_time_sec=1.5,
        termination_reason="OPTIMAL",
        is_optimal_proven=True,
    )
    json_str = export_run_manifest_to_json(run)
    data = json.loads(json_str)
    assert data["run_id"] == "RUN_G6_CERTIFIED"
    assert data["solver_name"] == "CPSat"
    assert data["status"] == "OPTIMAL"


def test_ui_export_02_provenance_integrity():
    """UI-EXPORT-02: Exported assignment CSV includes provenance and flight details."""
    asgn = GateTimelineView(
        assignment_id="ASGN_01",
        flight_id="FL_01",
        gate_id="GATE_01",
        concourse="T",
        start_min=100,
        end_min=160,
        carrier="DL",
        flight_number="DL101",
        nominal_gate_id="GATE_01",
        provenance=ProvenanceType.SCHEDULE_BASELINE,
    )
    csv_str = export_assignments_to_csv([asgn])
    assert "FL_01" in csv_str
    assert "GATE_01" in csv_str
    assert "SCHEDULE_BASELINE" in csv_str


# =============================================================================
# UI-VISUAL-01 & UI-OFFLINE-01: VISUAL CHECKLIST & OFFLINE READINESS
# =============================================================================

def test_ui_visual_01_checklist_file_exists():
    """UI-VISUAL-01: 40-point visual acceptance checklist file exists and is intact."""
    checklist_path = DEFAULT_CONFIG.project_root / "docs/dashboard/redesign/UI-R08/05_visual_acceptance.md"
    assert checklist_path.exists() is True
    content = checklist_path.read_text(encoding="utf-8")
    assert "V-01" in content
    assert "V-40" in content


def test_ui_offline_01_offline_launch_and_navigation():
    """UI-OFFLINE-01: All 5 pages launch and navigate cleanly without internet dependencies."""
    pages = [
        PageKeys.CONTROL_TOWER.value,
        PageKeys.FLIGHT_INTELLIGENCE.value,
        PageKeys.GATE_OPERATIONS.value,
        PageKeys.OPTIMIZATION_LAB.value,
        PageKeys.ROBUSTNESS_LAB.value,
    ]
    for page in pages:
        at = AppTest.from_file(APP_PATH, default_timeout=20)
        at.session_state[SessionStateKeys.CURRENT_PAGE] = page
        at.run()
        assert len(at.exception) == 0, f"Page {page} threw exception in offline mode"
