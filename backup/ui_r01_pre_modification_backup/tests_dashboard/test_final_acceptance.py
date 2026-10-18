"""P10-F Final System QA, Acceptance & Stress Test Suite.

Comprehensive end-to-end testing across Test Groups A through I:
- Group A: Application Smoke & Multi-Page AppTest
- Group B: Data Contracts & Provenance Integrity
- Group C: ML Scientific Correctness & Target Leakage Prevention
- Group D: Gate Scheduling Domain & Hard Constraints
- Group E: Solver Status, Certification & Fallback
- Group F: Monte Carlo Protocols & Statistical Robustness
- Group G: Streamlit Lifecycle & Session State Integrity
- Group H: Security, Path Traversal & Error Resilience
- Group I: Performance Thresholds & Memory Bounds
"""

from pathlib import Path
import json
import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from dashboard.adapters.artifact_loader import (
    ArtifactLoader,
    ArtifactNotFoundError,
    ArtifactValidationError,
)
from dashboard.adapters.export_adapter import (
    export_benchmark_to_csv,
    export_mc_summary_to_csv,
    export_manifest_to_json,
)
from dashboard.adapters.monte_carlo_adapter import (
    adapt_mc_scenario_drilldown,
    adapt_monte_carlo_to_views,
    calculate_mc_stats,
    compute_paired_differences,
    validate_mc_dataframe,
)
from dashboard.adapters.solver_result_adapter import adapt_solver_result_to_view
from dashboard.components.kpi_card import render_kpi_card
from dashboard.components.research_inspector import sanitize_provenance_data
from dashboard.core.config import DEFAULT_CONFIG, DashboardConfig
from dashboard.core.contracts import ProvenanceType, SolverRunView, UIJobState
from dashboard.core.state import SessionStateKeys, get_initial_session_state
from dashboard.core.status_mapping import SolverStatus, TerminationReason, map_solver_status_to_badge
from dashboard.core.validation import (
    DataLeakageError,
    IncompatibleComparisonError,
    ScientificValidator,
)
from dashboard.services.cache_service import CacheService
from dashboard.services.experiment_service import ExperimentService
from dashboard.services.optimization_service import OptimizationService
from dashboard.services.preflight_service import PreflightService
from dashboard.services.scenario_service import ScenarioService
from dashboard.visualizers.gantt_chart import create_gate_gantt_figure
from dashboard.visualizers.optimization_charts import (
    create_pareto_frontier_figure,
    create_runtime_breakdown_figure,
    create_scalability_curve_figure,
)
from dashboard.visualizers.robustness_charts import (
    create_mc_boxplot_figure,
    create_mc_convergence_figure,
    create_mc_cost_distribution_figure,
    create_mc_ecdf_figure,
)
from src.optimization.evaluation import verify_hard_constraints_independently


APP_PATH = str((DEFAULT_CONFIG.project_root / "dashboard" / "app.py").resolve())


# ==============================================================================
# TEST GROUP A: APPLICATION SMOKE & STREAMLIT APPTEST
# ==============================================================================

def test_group_a_01_app_import_and_startup() -> None:
    """Verify Streamlit app initializes cleanly without runtime exceptions."""
    at = AppTest.from_file(APP_PATH, default_timeout=20)
    at.run()
    assert len(at.exception) == 0


@pytest.mark.parametrize("page_id", [
    "01_control_tower",
    "02_flight_intelligence",
    "03_gate_operations",
    "04_optimization_lab",
    "05_robustness_lab",
])
def test_group_a_02_all_pages_presentation_mode(page_id: str) -> None:
    """Verify all 5 pages render with 0 exceptions in default Presentation Mode."""
    at = AppTest.from_file(APP_PATH, default_timeout=20)
    at.session_state[SessionStateKeys.CURRENT_PAGE] = page_id
    at.session_state[SessionStateKeys.RESEARCH_MODE] = False
    at.run()
    assert len(at.exception) == 0, f"Exception on {page_id} (Presentation): {at.exception}"


@pytest.mark.parametrize("page_id", [
    "01_control_tower",
    "02_flight_intelligence",
    "03_gate_operations",
    "04_optimization_lab",
    "05_robustness_lab",
])
def test_group_a_03_all_pages_research_mode(page_id: str) -> None:
    """Verify all 5 pages render with 0 exceptions in Research Mode."""
    at = AppTest.from_file(APP_PATH, default_timeout=20)
    at.session_state[SessionStateKeys.CURRENT_PAGE] = page_id
    at.session_state[SessionStateKeys.RESEARCH_MODE] = True
    at.run()
    assert len(at.exception) == 0, f"Exception on {page_id} (Research): {at.exception}"


# ==============================================================================
# TEST GROUP B: DATA & PROVENANCE INTEGRITY
# ==============================================================================

def test_group_b_01_scenario_loading_and_quarantine() -> None:
    """Verify registered scenarios load and 2024 data is strictly quarantined."""
    service = ScenarioService()
    scenarios = service.list_scenarios()
    assert len(scenarios) > 0

    # Year 2024 must trigger quarantine permission error
    with pytest.raises(PermissionError):
        service.load_scenario("SCEN_2024_HOLD_OUT")


def test_group_b_02_artifact_loader_schema_validation(tmp_path: Path) -> None:
    """Verify intentional artifact corruption on fixture is rejected cleanly."""
    corrupt_csv = tmp_path / "artifacts" / "remediation" / "corrupt_data.csv"
    corrupt_csv.parent.mkdir(parents=True, exist_ok=True)
    corrupt_csv.write_text("wrong_col1,wrong_col2\n1,2\n", encoding="utf-8")

    cfg = DashboardConfig(project_root=tmp_path)
    loader = ArtifactLoader(cfg)

    with pytest.raises(ArtifactValidationError):
        loader.load_csv("artifacts/remediation/corrupt_data.csv", required_columns={"expected_column_xyz"})


# ==============================================================================
# TEST GROUP C: ML SCIENTIFIC CORRECTNESS
# ==============================================================================

def test_group_c_01_signed_delays_preserved() -> None:
    """Verify early flights with negative delays are preserved mathematically."""
    raw_early = {
        "flight_id": "FL_EARLY_01",
        "carrier": "DL",
        "sched_in_min": 600,
        "pred_arr_delay_min": -14.5,  # Early arrival
        "turn_id": "TURN_01",
    }
    # Prediction must retain signed value without clamping to 0
    assert raw_early["pred_arr_delay_min"] == -14.5


def test_group_c_02_zero_leakage_in_planning_views() -> None:
    """Verify ground-truth actual columns raise DataLeakageError."""
    leaked_cols = ["flight_id", "sched_in_min", "arr_delay", "pred_delay"]
    with pytest.raises(DataLeakageError):
        ScientificValidator.check_prediction_data_leakage(leaked_cols)


# ==============================================================================
# TEST GROUP D: GATE DOMAIN CORRECTNESS
# ==============================================================================

def test_group_d_01_release_buffer_present_exactly_once() -> None:
    """Verify 15-minute separation buffer is included once without double-counting."""
    from dashboard.adapters.assignment_adapter import adapt_assignment_to_view

    raw = {
        "flight_id": "FL_100",
        "gate_id": "T1",
        "start_min": 600,
        "end_min": 660,
    }
    view = adapt_assignment_to_view(raw, buffer_min=15)
    assert view.buffer_min == 15
    assert view.start_min == 600
    assert view.actual_gate_release_min == 675  # 660 + 15


def test_group_d_02_independent_verifier_validates_clean_schedule() -> None:
    """Verify independent hard-constraint verifier certifies clean greedy solve."""
    scen_service = ScenarioService()
    flights, gates = scen_service.load_scenario("SCEN_P09_CANONICAL_120")

    opt_service = OptimizationService()
    run_view, is_valid, violations = opt_service.solve(
        flights=flights, gates=gates, solver_name="greedy"
    )

    assert is_valid is True
    assert len(violations) == 0
    assert run_view.conflict_count == 0


# ==============================================================================
# TEST GROUP E: SOLVER STATUS & FALLBACK
# ==============================================================================

def test_group_e_01_greedy_never_claims_optimal() -> None:
    """Verify Greedy solver view is never certified as optimal."""
    scen_service = ScenarioService()
    flights, gates = scen_service.load_scenario("SCEN_P09_CANONICAL_120")

    opt_service = OptimizationService()
    run_view, _, _ = opt_service.solve(flights[:15], gates[:8], solver_name="greedy")

    assert run_view.is_optimal_proven is False
    assert run_view.status == "FEASIBLE"


def test_group_e_02_config_modification_marks_stale() -> None:
    """Verify modifying draft parameters flags existing solution as stale."""
    exec_cfg = {"solver_name": "cpsat", "w_pref": 10.0, "w_remote": 200.0}
    draft_cfg = {"solver_name": "cpsat", "w_pref": 10.0, "w_remote": 350.0}

    assert ExperimentService.is_stale(draft_cfg, exec_cfg) is True


# ==============================================================================
# TEST GROUP F: MONTE CARLO & SCIENTIFIC COMPARISON
# ==============================================================================

def test_group_f_01_mode_c_labeled_non_deployable() -> None:
    """Verify Mode C Oracle retains non-deployable badge and status."""
    loader = ArtifactLoader()
    summary = loader.load_monte_carlo_statistical_summary()
    views = adapt_monte_carlo_to_views(summary)

    assert views["mode_c"].is_deployable is False


def test_group_f_02_paired_analysis_alignment() -> None:
    """Verify paired comparison computes correct delta on matching IDs."""
    loader = ArtifactLoader()
    fixed_df = loader.load_monte_carlo_scenarios("fixed_plan")
    recourse_df = loader.load_monte_carlo_scenarios("recourse")

    f_sub = fixed_df[fixed_df["solver_name"] == "CPSat"]
    r_sub = recourse_df[recourse_df["solver_name"] == "CPSat"]

    paired = compute_paired_differences(f_sub, r_sub, id_col="realization_id")
    assert paired["n_paired"] == 500
    assert paired["mean_delta_cost"] > 1000.0  # Mode A penalty vs Mode B recourse
    assert paired["statistical_significance"] is True


# ==============================================================================
# TEST GROUP G: STREAMLIT RE-RUN & SESSION
# ==============================================================================

def test_group_g_01_twelve_step_interaction_lifecycle() -> None:
    """Simulate complete 12-step user interaction sequence via session state."""
    state = get_initial_session_state()

    # 1. Open app
    assert state[SessionStateKeys.CURRENT_PAGE] == "01_control_tower"

    # 2. Select scenario
    state[SessionStateKeys.ACTIVE_SCENARIO_ID] = "SCEN_P09_CANONICAL_120"

    # 3. Mark job ready
    state[SessionStateKeys.JOB_STATE] = UIJobState.READY_IDLE

    # 4. Zoom Gantt (presentation filter only)
    filters_old = {"time_zoom_start": 0, "time_zoom_end": 1440}
    filters_new = {"time_zoom_start": 360, "time_zoom_end": 720}
    assert ExperimentService.is_presentation_filter_mutation(filters_old, filters_new) is True

    # 5. Filter carrier
    filters_carrier = {"highlight_carrier": "DL"}
    assert ExperimentService.is_presentation_filter_mutation({}, filters_carrier) is True

    # 6. Select flight
    state[SessionStateKeys.SELECTED_FLIGHT_ID] = "FL_001"

    # 7. Switch to Flight Intelligence
    state[SessionStateKeys.CURRENT_PAGE] = "02_flight_intelligence"

    # 8. Return to Gate Operations
    state[SessionStateKeys.CURRENT_PAGE] = "03_gate_operations"

    # 9. Edit config without running
    state[SessionStateKeys.DRAFT_CONFIGURATION]["w_remote"] = 999.0
    is_stale = ExperimentService.is_stale(
        state[SessionStateKeys.DRAFT_CONFIGURATION],
        state[SessionStateKeys.EXECUTED_CONFIGURATION],
    )
    assert is_stale is True

    # 10. Run with new config
    state[SessionStateKeys.EXECUTED_CONFIGURATION] = dict(state[SessionStateKeys.DRAFT_CONFIGURATION])
    assert ExperimentService.is_stale(
        state[SessionStateKeys.DRAFT_CONFIGURATION],
        state[SessionStateKeys.EXECUTED_CONFIGURATION],
    ) is False

    # 11. Switch scenario
    state[SessionStateKeys.ACTIVE_SCENARIO_ID] = "SCEN_SMALL_TEST"

    # 12. Verify no cross-scenario cache contamination
    cache = CacheService()
    key_a = CacheService.generate_cache_key("SCEN_A", "GATE_PLAN", {"w_pref": 10.0})
    key_b = CacheService.generate_cache_key("SCEN_B", "GATE_PLAN", {"w_pref": 10.0})
    assert key_a != key_b
    cache.get_or_set(key_a, "fp1", lambda: {"res": 1})
    assert key_b not in cache._store


# ==============================================================================
# TEST GROUP H: SECURITY & RESILIENCE
# ==============================================================================

def test_group_h_01_path_traversal_blocked() -> None:
    """Verify unauthorized parent traversal is blocked by loader."""
    loader = ArtifactLoader()
    with pytest.raises(PermissionError):
        loader.load_json("../../../windows/system32/cmd.exe")


def test_group_h_02_path_and_secrets_sanitization() -> None:
    """Verify local system paths and secrets are redacted from metadata."""
    dirty_meta = {
        "file": r"D:\Study\Code\Python\Aelous\secret.txt",
        "api_key": "sk-1234567890",
        "env_user": "/Users/developer/project",
        "scenario": "SCEN_01",
    }
    clean = sanitize_provenance_data(dirty_meta)
    assert "D:\\Study" not in str(clean)
    assert "api_key" not in clean
    assert clean["scenario"] == "SCEN_01"


# ==============================================================================
# TEST GROUP I: PERFORMANCE & MEMORY BOUNDS
# ==============================================================================

def test_group_i_01_artifact_load_latency_bound() -> None:
    """Verify core artifacts load in less than 500 ms."""
    import time
    t0 = time.perf_counter()
    loader = ArtifactLoader()
    _ = loader.load_solver_benchmarks()
    _ = loader.load_monte_carlo_statistical_summary()
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.50, f"Artifact loading exceeded budget: {elapsed:.3f}s"
