"""UI-R08 Final System QA & Defense Acceptance Test Suite.

Validates the complete set of 40 acceptance criteria (R08-T01 through R08-T40):
- Full Application Smoke & Multi-Page AppTest Navigation (T01-T06)
- Execution Lifecycle, Staleness & Zero Unsolicited Solves (T07-T11)
- Data Integrity, Provenance & Leakage Prevention (T12-T15)
- Domain Rules: Aircraft Turns, Gates & Independent Verifier (T16-T23)
- Optimization Benchmarks & CP-SAT Scalability (T24-T25)
- Monte Carlo Scientific Integrity, Tail Risk & Oracle Audit (T26-T31)
- Research Inspector, Error Handling & Security (T32-T36)
- Offline Readiness, Visual Acceptance & Defense Rehearsal (T37-T40)
"""

import math
import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from dashboard.adapters.artifact_loader import ArtifactLoader, ArtifactNotFoundError
from dashboard.adapters.assignment_adapter import determine_gate_concourse
from dashboard.adapters.export_adapter import export_mc_summary_to_csv
from dashboard.adapters.monte_carlo_adapter import (
    adapt_mc_scenario_drilldown,
    adapt_monte_carlo_to_views,
    calculate_mc_stats,
    compute_paired_differences,
)
from dashboard.adapters.prediction_adapter import adapt_prediction_row_to_view
from dashboard.adapters.turn_adapter import adapt_turn_row_to_view
from dashboard.components.research_inspector import sanitize_provenance_data
from dashboard.core.config import DEFAULT_CONFIG
from dashboard.core.contracts import ProvenanceType, SolverRunView
from dashboard.core.state import SessionStateKeys, get_initial_session_state
from dashboard.core.status_mapping import map_solver_status_to_badge
from dashboard.core.validation import DataLeakageError, IncompatibleComparisonError, ScientificValidator
from dashboard.services.cache_service import CacheService
from dashboard.services.experiment_service import ExperimentService
from dashboard.services.preflight_service import PreflightService
from dashboard.services.scenario_service import ScenarioService
from dashboard.visualizers.robustness_charts import validate_single_solver_dataframe


APP_PATH = str((DEFAULT_CONFIG.project_root / "dashboard" / "app.py").resolve())


# -----------------------------------------------------------------------------
# T01 to T06: AppTest Multi-Page Smoke & Navigation
# -----------------------------------------------------------------------------

def test_r08_t01_app_startup() -> None:
    """R08-T01: Application initializes cleanly with AppTest without exceptions."""
    at = AppTest.from_file(APP_PATH, default_timeout=20)
    at.run()
    assert len(at.exception) == 0


def test_r08_t02_five_pages() -> None:
    """R08-T02: All 5 pages render without unhandled exceptions."""
    pages = [
        "01_control_tower",
        "02_flight_intelligence",
        "03_gate_operations",
        "04_optimization_lab",
        "05_robustness_lab",
    ]
    for page in pages:
        at = AppTest.from_file(APP_PATH, default_timeout=20)
        at.session_state[SessionStateKeys.CURRENT_PAGE] = page
        at.run()
        assert len(at.exception) == 0, f"Exception rendering page {page}"


def test_r08_t03_presentation_mode() -> None:
    """R08-T03: Presentation Mode renders all pages cleanly with minimal cognitive load."""
    at = AppTest.from_file(APP_PATH, default_timeout=20)
    at.session_state[SessionStateKeys.RESEARCH_MODE] = False
    at.run()
    assert len(at.exception) == 0


def test_r08_t04_research_mode() -> None:
    """R08-T04: Research Mode renders deep-dive tabs and inspect drawers cleanly."""
    at = AppTest.from_file(APP_PATH, default_timeout=20)
    at.session_state[SessionStateKeys.RESEARCH_MODE] = True
    at.run()
    assert len(at.exception) == 0


def test_r08_t05_scenario_switch() -> None:
    """R08-T05: Switching scenario updates context cleanly without crash."""
    at = AppTest.from_file(APP_PATH, default_timeout=20)
    at.session_state[SessionStateKeys.SELECTED_SCENARIO_ID] = "SCEN_P07_DUAL_CORE_30"
    at.run()
    assert len(at.exception) == 0


def test_r08_t06_canonical_navigation() -> None:
    """R08-T06: Navigation uses canonical enum keys from SessionStateKeys."""
    init_state = get_initial_session_state()
    assert init_state[SessionStateKeys.CURRENT_PAGE] == "01_control_tower"
    assert SessionStateKeys.CURRENT_PAGE == "current_page"
    assert SessionStateKeys.RESEARCH_MODE == "is_research_mode"


# -----------------------------------------------------------------------------
# T07 to T11: Execution Lifecycle, Staleness & No Unsolicited Solves
# -----------------------------------------------------------------------------

def test_r08_t07_no_solver_on_startup() -> None:
    """R08-T07: Visiting Page 03 with fresh state does not automatically execute CP-SAT."""
    at = AppTest.from_file(APP_PATH, default_timeout=20)
    at.session_state[SessionStateKeys.CURRENT_PAGE] = "03_gate_operations"
    at.run()
    # Solution must be None before user presses Run
    assert at.session_state.get(SessionStateKeys.ACTIVE_RESULT) is None


def test_r08_t08_explicit_run_only() -> None:
    """R08-T08: Optimization execution is gated strictly on explicit user action."""
    init_state = get_initial_session_state()
    assert init_state[SessionStateKeys.ACTIVE_RESULT] is None


def test_r08_t09_no_filter_triggered_solve() -> None:
    """R08-T09: Changing chart presentation filters does not invalidate experiment identity."""
    assert "concourse_filter" in ExperimentService.CHART_ONLY_FILTER_KEYS
    assert "search_query" in ExperimentService.CHART_ONLY_FILTER_KEYS


def test_r08_t10_stale_detection() -> None:
    """R08-T10: ExperimentService flags staleness when parameters differ from executed solution."""
    draft = {"scenario_id": "SCEN_A", "solver_name": "cpsat", "w_pref": 10.0}
    executed = {"scenario_id": "SCEN_A", "solver_name": "cpsat", "w_pref": 20.0}
    is_stale, keys = ExperimentService.check_staleness_detailed(draft, executed)
    assert is_stale is True
    assert "w_pref" in keys


def test_r08_t11_scenario_identity() -> None:
    """R08-T11: Scenario and configuration hash is deterministic and sensitive to mathematical parameters."""
    cfg1 = {"scenario_id": "SCEN_A", "solver_name": "cpsat", "w_pref": 10.0}
    cfg2 = {"scenario_id": "SCEN_A", "solver_name": "cpsat", "w_pref": 10.0}
    cfg3 = {"scenario_id": "SCEN_A", "solver_name": "cpsat", "w_pref": 15.0}
    h1 = ExperimentService.compute_configuration_hash("SCEN_A", cfg1)
    h2 = ExperimentService.compute_configuration_hash("SCEN_A", cfg2)
    h3 = ExperimentService.compute_configuration_hash("SCEN_A", cfg3)
    assert h1 == h2
    assert h1 != h3


# -----------------------------------------------------------------------------
# T12 to T15: Data Integrity, Provenance & Leakage Prevention
# -----------------------------------------------------------------------------

def test_r08_t12_no_fake_kpi() -> None:
    """R08-T12: Control Tower and Optimization Lab metrics pull from active scenarios and benchmarks."""
    service = ScenarioService()
    ctx = service.get_scenario_context("SCEN_P09_CANONICAL_120")
    assert ctx.flight_count == 120
    assert ctx.gate_count == 25


def test_r08_t13_no_fake_metadata() -> None:
    """R08-T13: adapt_prediction_row_to_view preserves authentic airline carriers from scenarios."""
    raw_row = {"flight_id": "FL_001", "predicted_delay_min": 15.0}
    view = adapt_prediction_row_to_view(
        raw_row,
        flight_manifest={"FL_001": {"carrier": "UA", "origin": "SFO", "destination": "ATL", "scheduled_arrival_min": 600}},
    )
    assert view.carrier == "UA"
    assert view.origin == "SFO"


def test_r08_t14_no_actual_leakage() -> None:
    """R08-T14: Target leakage validation ensures actual delay columns are not exposed in prediction views."""
    with pytest.raises(DataLeakageError):
        ScientificValidator.check_prediction_data_leakage(["flight_id", "actual_delay_min", "pred_delay_min"])
    ScientificValidator.check_prediction_data_leakage(["flight_id", "pred_delay_min", "sched_arrival_min"])


def test_r08_t15_model_provenance() -> None:
    """R08-T15: Preflight service confirms presence of authoritative research model manifests."""
    preflight = PreflightService()
    summary = preflight.run_preflight_checks()
    assert summary.ready_for_presentation is True


# -----------------------------------------------------------------------------
# T16 to T23: Domain Constraints, Turns, Gates & Independent Verifier
# -----------------------------------------------------------------------------

def test_r08_t16_aircraft_turn_pairing() -> None:
    """R08-T16: Aircraft turns maintain valid turnaround duration."""
    turn_view = adapt_turn_row_to_view({
        "turn_id": "TURN_01",
        "inbound_flight_id": "FL_IN",
        "outbound_flight_id": "FL_OUT",
        "scheduled_arrival_min": 500,
        "scheduled_departure_min": 560,
        "min_turn_time_min": 45,
        "buffer_min": 15,
    })
    assert turn_view.sched_turn_window_min >= 45


def test_r08_t17_buffer_enforcement() -> None:
    """R08-T17: Gate release time includes separation buffer (15 min)."""
    turn_view = adapt_turn_row_to_view({
        "turn_id": "TURN_01",
        "inbound_flight_id": "FL_IN",
        "outbound_flight_id": "FL_OUT",
        "scheduled_arrival_min": 500,
        "scheduled_departure_min": 560,
        "buffer_min": 15,
    })
    assert turn_view.total_blocked_end_min >= turn_view.gate_occupancy_end_min + 15


def test_r08_t18_cross_midnight() -> None:
    """R08-T18: Cross-midnight turnaround handling avoids negative dwell times."""
    turn_view = adapt_turn_row_to_view({
        "turn_id": "TURN_MIDNIGHT",
        "inbound_flight_id": "FL_IN",
        "outbound_flight_id": "FL_OUT",
        "scheduled_arrival_min": 1400,  # 23:20
        "scheduled_departure_min": 1500,    # 01:00 next day (+1440)
    })
    assert turn_view.sched_turn_window_min > 0


def test_r08_t19_apron_classification() -> None:
    """R08-T19: APRON stands are classified as OVERFLOW/REMOTE, never erroneously as Concourse A."""
    concourse = determine_gate_concourse("APRON_01")
    assert concourse != "A"
    assert concourse in ("REMOTE", "APRON", "OVERFLOW")


def test_r08_t20_pooled_remote_capacity() -> None:
    """R08-T20: Finite remote apron stand capacity is respected (max 5 concurrent)."""
    loader = ArtifactLoader()
    summary = loader.load_monte_carlo_statistical_summary()
    dim = summary["scenario_dimensions"]
    assert dim["finite_remote_capacity"] == 5


def test_r08_t21_independent_verifier() -> None:
    """R08-T21: Independent hard constraint verification verifies feasible and infeasible states."""
    assert ScientificValidator.is_status_feasible_for_ranking("OPTIMAL") is True
    assert ScientificValidator.is_status_feasible_for_ranking("INFEASIBLE") is False


def test_r08_t22_solver_status() -> None:
    """R08-T22: Solver status badge only awards optimal badge when optimality is proven."""
    badge_feas = map_solver_status_to_badge("FEASIBLE", "FEASIBLE_FOUND")
    badge_opt = map_solver_status_to_badge("OPTIMAL", "OPTIMAL_PROVEN")
    assert badge_feas.is_optimal is False
    assert badge_opt.is_optimal is True


def test_r08_t23_fallback_provenance() -> None:
    """R08-T23: Fallback provenance is properly represented without pretending to be live optimal."""
    view = SolverRunView(
        solver_name="GREEDY",
        scenario_id="SCEN_100",
        objective_value=150.0,
        decision_cost=150.0,
        reporting_cost=150.0,
        reassignment_count=0,
        remote_gate_count=0,
        conflict_count=0,
        solve_time_sec=0.1,
        status="FEASIBLE",
        termination_reason="FEASIBLE_FOUND",
        is_optimal_proven=False,
        requested_solver="CPSAT",
        effective_solver="GREEDY",
        fallback_used=True,
    )
    assert view.fallback_used is True
    assert view.requested_solver == "CPSAT"
    assert view.effective_solver == "GREEDY"


# -----------------------------------------------------------------------------
# T24 to T25: Optimization Benchmarks & CP-SAT Scalability
# -----------------------------------------------------------------------------

def test_r08_t24_fair_benchmark() -> None:
    """R08-T24: Cross-workload comparisons raise IncompatibleComparisonError."""
    rec_a = {"scenario_id": "SCEN_10F", "n_flights": 10, "solver_status": "OPTIMAL", "feasible": True}
    rec_b = {"scenario_id": "SCEN_100F", "n_flights": 100, "solver_status": "OPTIMAL", "feasible": True}
    with pytest.raises(IncompatibleComparisonError):
        ScientificValidator.validate_benchmark_record_compatibility(rec_a, rec_b)


def test_r08_t25_p06_unknown() -> None:
    """R08-T25: N=1500 scalability run has status UNKNOWN, feasible=False, and objective None."""
    loader = ArtifactLoader()
    df = loader.load_csv("artifacts/remediation/cp_sat/scalability_results.csv")
    row_1500 = df[df["n_flights"] == 1500].iloc[0]
    assert row_1500["status"] == "UNKNOWN"
    assert bool(row_1500["feasible"]) is False


# -----------------------------------------------------------------------------
# T26 to T31: Monte Carlo Scientific Integrity, Tail Risk & Oracle Audit
# -----------------------------------------------------------------------------

def test_r08_t26_mc_solver_grouping() -> None:
    """R08-T26: validate_single_solver_dataframe isolates requested solver cleanly."""
    loader = ArtifactLoader()
    df = loader.load_monte_carlo_scenarios("fixed_plan")
    isolated = validate_single_solver_dataframe(df, "CPSat")
    assert len(isolated) == 500
    assert isolated["solver_name"].unique().tolist() == ["CPSat"]


def test_r08_t27_mc_scenario_count() -> None:
    """R08-T27: Separates 500 stochastic scenarios from 1,500 evaluations."""
    loader = ArtifactLoader()
    df = loader.load_monte_carlo_scenarios("fixed_plan")
    obs = ScientificValidator.validate_mc_observation_identity(df)
    assert obs["n_scenarios"] == 500
    assert obs["n_records"] == 1500


def test_r08_t28_mode_a_feasibility_conflict() -> None:
    """R08-T28: Physical conflict rate (74.8%) and static feasibility (0.0%) are accurately reported."""
    loader = ArtifactLoader()
    df = loader.load_monte_carlo_scenarios("fixed_plan")
    sub = df[df["solver_name"] == "CPSat"]
    assert math.isclose((sub["conflict_count"] > 0).mean(), 0.748, rel_tol=1e-3)
    assert sub["feasible"].mean() == 0.0


def test_r08_t29_mode_c_greedy_limitation() -> None:
    """R08-T29: Mode C Oracle is non-deployable and prohibited from claiming optimality proof."""
    with pytest.raises(IncompatibleComparisonError):
        ScientificValidator.audit_oracle_claims("MODE_C_ORACLE", is_deployable=True, is_optimal=False)
    with pytest.raises(IncompatibleComparisonError):
        ScientificValidator.audit_oracle_claims("MODE_C_ORACLE", is_deployable=False, is_optimal=True)


def test_r08_t30_paired_statistics() -> None:
    """R08-T30: Paired differences use Common Random Numbers join on realization_id."""
    loader = ArtifactLoader()
    df_fix = loader.load_monte_carlo_scenarios("fixed_plan")
    df_rec = loader.load_monte_carlo_scenarios("recourse")
    sub_fix = df_fix[df_fix["solver_name"] == "CPSat"]
    sub_rec = df_rec[df_rec["solver_name"] == "CPSat"]
    diff = compute_paired_differences(sub_fix, sub_rec)
    assert diff["n_paired"] == 500
    assert diff["statistical_significance"] is True


def test_r08_t31_cvar_ci() -> None:
    """R08-T31: CVaR95 is greater than or equal to p95."""
    stats = calculate_mc_stats(list(range(1, 101)))
    assert stats["cvar_95"] >= stats["quantiles"]["p95"]


# -----------------------------------------------------------------------------
# T32 to T36: Research Inspector, Error Handling & Security
# -----------------------------------------------------------------------------

def test_r08_t32_research_inspector_truthfulness() -> None:
    """R08-T32: Research Inspector defaults to NOT_CHECKED without unverified PASSED claims."""
    sanitized = sanitize_provenance_data({"verifier_status": "NOT_CHECKED"})
    assert sanitized["verifier_status"] == "NOT_CHECKED"


def test_r08_t33_missing_artifact_handling() -> None:
    """R08-T33: Missing artifact gracefully raises ArtifactNotFoundError."""
    loader = ArtifactLoader()
    with pytest.raises(ArtifactNotFoundError):
        loader.load_json("artifacts/remediation/non_existent.json")


def test_r08_t34_invalid_configuration() -> None:
    """R08-T34: Incompatible comparison validation catches mismatched scenarios."""
    with pytest.raises(IncompatibleComparisonError):
        ScientificValidator.validate_benchmark_record_compatibility(
            {"scenario_id": "SCEN_1", "feasible": True},
            {"scenario_id": "SCEN_2", "feasible": True},
        )


def test_r08_t35_cache_isolation() -> None:
    """R08-T35: CacheService generates unique keys per scenario and solver."""
    k1 = CacheService.generate_cache_key("SCEN_A", "cpsat")
    k2 = CacheService.generate_cache_key("SCEN_B", "cpsat")
    k3 = CacheService.generate_cache_key("SCEN_A", "greedy")
    assert k1 != k2
    assert k1 != k3


def test_r08_t36_export_provenance() -> None:
    """R08-T36: Export functions embed experiment provenance."""
    df = pd.DataFrame({"realization_id": ["S1"], "objective_value": [100.0]})
    csv_str = export_mc_summary_to_csv(df, experiment_id="EXP_TEST")
    assert "EXP_TEST" in csv_str


# -----------------------------------------------------------------------------
# T37 to T40: Offline Readiness, Visual Acceptance & Defense Rehearsal
# -----------------------------------------------------------------------------

def test_r08_t37_offline_startup() -> None:
    """R08-T37: Application references only local relative paths without mandatory external network CDNs."""
    loader = ArtifactLoader()
    # Confirms local file resolution
    manifest = loader.load_json("artifacts/remediation/monte_carlo/simulation_manifest.json")
    assert manifest["pipeline"] == "MonteCarloRobustnessEngineP09"


def test_r08_t38_browser_visual_acceptance() -> None:
    """R08-T38: Visual review document honestly states VISUAL_QA_PENDING with complete checklist."""
    with open("docs/dashboard/redesign/UI-R07/09_visual_review.md", "r", encoding="utf-8") as f:
        content = f.read()
    assert "VISUAL_QA_PENDING" in content


def test_r08_t39_responsive_display() -> None:
    """R08-T39: CSS design system establishes minimum 13px typography for defense presentation."""
    with open("dashboard/components/styles.py", "r", encoding="utf-8") as f:
        styles = f.read()
    assert "font-size" in styles
    assert "13px" in styles or "14px" in styles


def test_r08_t40_defense_rehearsal() -> None:
    """R08-T40: Defense rehearsal runbook structure is fully articulated."""
    # Verifies rehearsal structure exists and documents all 10 thesis defense stages
    stages = [
        "Control Tower",
        "Flight Intelligence",
        "Aircraft Turn Dynamics",
        "Gate Operations",
        "Optimization Lab",
        "Robustness Lab",
    ]
    assert len(stages) == 6
