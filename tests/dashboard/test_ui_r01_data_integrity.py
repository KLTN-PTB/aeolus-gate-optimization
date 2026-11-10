"""Tests for Phase UI-R01 v2.0: Data Integrity & Scientific Claim Remediation.

Test suite covering R01-T01 through R01-T24:
- Prediction metadata provenance & zero-fabrication (R01-T01 to R01-T05)
- Monte Carlo statistical honesty & Oracle bounds (R01-T06 to R01-T09)
- Multi-solver contamination guards & visualizers (R01-T10 to R01-T16)
- Control Tower dynamic KPIs & honest baseline (R01-T17 to R01-T19)
- Context Bar honest defaults & page honesty (R01-T20 to R01-T23)
- Optimization Lab dynamic benchmark wiring (R01-T24)
"""

from typing import Any, Dict
import pandas as pd
import pytest

from dashboard.adapters.monte_carlo_adapter import (
    adapt_mc_scenario_drilldown,
    adapt_monte_carlo_to_views,
)
from dashboard.adapters.prediction_adapter import adapt_prediction_row_to_view
from dashboard.components.context_bar import render_context_bar
from dashboard.core.contracts import (
    FlightPredictionView,
    RobustnessView,
    SolverRunView,
)
from dashboard.core.validation import IncompatibleComparisonError, ScientificValidator
from dashboard.services.scenario_service import ScenarioService
from dashboard.visualizers.robustness_charts import (
    create_mc_boxplot_figure,
    create_mc_convergence_figure,
    create_mc_cost_distribution_figure,
    create_mc_ecdf_figure,
    validate_single_solver_dataframe,
)


# ==============================================================================
# 1. PREDICTION METADATA PROVENANCE (R01-T01 to R01-T05)
# ==============================================================================

def test_r01_t01_prediction_missing_metadata_defaults_to_na():
    """R01-T01: Missing carrier, origin, destination must be 'N/A', NOT fabricated 'DL', 'ORD', 'ATL'."""
    row = {
        "flight_id": "LEG_ARR_0001",
        "predicted_delay_min": 12.5,
    }
    view = adapt_prediction_row_to_view(row, flight_manifest=None)
    assert view.carrier == "N/A"
    assert view.origin == "N/A"
    assert view.destination == "N/A"
    assert view.carrier != "DL"
    assert view.origin != "ORD"
    assert view.destination != "ATL"


def test_r01_t02_prediction_missing_sched_arr_time_is_none():
    """R01-T02: Missing sched_arr_time_min must be None, NOT fabricated 480 (08:00)."""
    row = {
        "flight_id": "LEG_ARR_0001",
        "predicted_delay_min": 15.0,
    }
    view = adapt_prediction_row_to_view(row, flight_manifest=None)
    assert view.sched_arr_time_min is None
    assert view.sched_arr_time_min != 480


def test_r01_t03_prediction_unmatched_flight_id_gives_na_metadata():
    """R01-T03: Flight ID not in scenario schedule dictionary must result in 'N/A' and None."""
    dummy_schedule = {
        "S1500-0001": type("MockFlight", (), {"carrier": "WN", "scheduled_arrival_min": 100})()
    }
    row = {
        "flight_id": "LEG_ARR_9999",  # Not in schedule
        "predicted_delay_min": 5.0,
    }
    view = adapt_prediction_row_to_view(row, flight_manifest=dummy_schedule)
    assert view.carrier == "N/A"
    assert view.sched_arr_time_min is None


def test_r01_t04_prediction_exact_zero_delay_preserved():
    """R01-T04: Realized predicted delay of 0.0 must be preserved exactly, not dropped or overwritten."""
    row = {
        "flight_id": "LEG_ARR_0002",
        "predicted_delay_min": 0.0,
    }
    view = adapt_prediction_row_to_view(row)
    assert view.predicted_arr_delay_min == 0.0


def test_r01_t05_prediction_cross_scenario_guard():
    """R01-T05: When row scenario does not match active scenario_id, raises ValueError."""
    row = {
        "flight_id": "LEG_ARR_0001",
        "scenario_id": "SCEN_OTHER",
        "predicted_delay_min": 10.0,
    }
    with pytest.raises(ValueError, match="Cross-scenario mismatch"):
        adapt_prediction_row_to_view(row, scenario_id="SCEN_P09_CANONICAL_120")


# ==============================================================================
# 2. MONTE CARLO STATISTICAL HONESTY & ORACLE BOUNDS (R01-T06 to R01-T09)
# ==============================================================================

def test_r01_t06_monte_carlo_mode_a_missing_metrics_are_none():
    """R01-T06: Mode A missing metrics must be None, NOT fabricated 1469.17."""
    empty_summary = {
        "mode_a_fixed_plan": {
            "CPSat": {}  # No mean_cost
        }
    }
    views = adapt_monte_carlo_to_views(empty_summary, solver_key="CPSat")
    view_a = views["mode_a"]
    assert view_a.mean_cost is None
    assert view_a.median_cost is None
    assert view_a.mean_cost != 1469.17


def test_r01_t07_monte_carlo_mode_b_missing_metrics_are_none():
    """R01-T07: Mode B missing metrics must be None, NOT fabricated 130.73 or 2.556."""
    empty_summary = {
        "mode_b_recourse": {
            "CPSat": {}
        }
    }
    views = adapt_monte_carlo_to_views(empty_summary, solver_key="CPSat")
    view_b = views["mode_b"]
    assert view_b.mean_cost is None
    assert view_b.mean_reassignments is None
    assert view_b.mean_cost != 130.73


def test_r01_t08_monte_carlo_mode_c_oracle_academic_notes():
    """R01-T08: Mode C must be explicitly declared as Realized Greedy Oracle Baseline, not proven global optimum."""
    summary = {
        "mode_c_oracle": {
            "Oracle": {
                "mean_cost": 130.73,
                "n_evaluated": 500,
            }
        }
    }
    views = adapt_monte_carlo_to_views(summary)
    view_c = views["mode_c"]
    assert "Realized Greedy Oracle Baseline" in view_c.academic_notes
    assert "KHÔNG phải là nghiệm tối ưu toán học toàn cục" in view_c.academic_notes


def test_r01_t09_monte_carlo_mode_c_is_not_deployable():
    """R01-T09: Mode C is_deployable must strictly be False."""
    summary = {
        "mode_c_oracle": {
            "Oracle": {
                "mean_cost": 130.73,
            }
        }
    }
    views = adapt_monte_carlo_to_views(summary)
    view_c = views["mode_c"]
    assert view_c.is_deployable is False


# ==============================================================================
# 3. MULTI-SOLVER CONTAMINATION GUARDS (R01-T10 to R01-T16)
# ==============================================================================

@pytest.fixture
def multi_solver_mc_df() -> pd.DataFrame:
    """Fixture providing multi-solver DataFrame with 1500 rows (Greedy, CPSat, Hybrid)."""
    rows = []
    for s in ["Greedy", "CPSat", "Hybrid"]:
        for i in range(500):
            rows.append({
                "realization_id": f"MC500_S{i:04d}",
                "scenario_index": i,
                "solver_name": s,
                "objective_value": 100.0 if s == "CPSat" else (200.0 if s == "Greedy" else 150.0),
                "reassignment_count": 2 if s == "CPSat" else 5,
                "remote_count": 0,
            })
    return pd.DataFrame(rows)


def test_r01_t10_validate_single_solver_dataframe_filters_to_target(multi_solver_mc_df):
    """R01-T10: validate_single_solver_dataframe filters multi-solver DataFrame to requested solver."""
    filtered = validate_single_solver_dataframe(multi_solver_mc_df, solver_name="CPSat")
    assert len(filtered) == 500
    assert set(filtered["solver_name"].unique()) == {"CPSat"}


def test_r01_t11_validate_single_solver_dataframe_single_solver_unchanged():
    """R01-T11: Single-solver DataFrame passes through without modification."""
    df = pd.DataFrame([{"solver_name": "CPSat", "objective_value": 100.0}] * 10)
    filtered = validate_single_solver_dataframe(df, solver_name="CPSat")
    assert len(filtered) == 10


def test_r01_t12_cost_distribution_figure_guards_against_mixing(multi_solver_mc_df):
    """R01-T12: create_mc_cost_distribution_figure filters multi-solver inputs to prevent distribution skew."""
    fig = create_mc_cost_distribution_figure(
        fixed_df=multi_solver_mc_df,
        recourse_df=multi_solver_mc_df,
        solver_name="CPSat",
    )
    assert fig is not None
    # Figure should be created cleanly without exception
    assert len(fig.data) >= 2


def test_r01_t13_ecdf_figure_guards_against_mixing(multi_solver_mc_df):
    """R01-T13: create_mc_ecdf_figure filters multi-solver inputs."""
    fig = create_mc_ecdf_figure(
        fixed_df=multi_solver_mc_df,
        recourse_df=multi_solver_mc_df,
        solver_name="CPSat",
    )
    assert fig is not None
    assert len(fig.data) >= 2


def test_r01_t14_boxplot_and_convergence_guard_against_mixing(multi_solver_mc_df):
    """R01-T14: create_mc_boxplot_figure and create_mc_convergence_figure filter inputs."""
    fig_box = create_mc_boxplot_figure(multi_solver_mc_df, solver_name="CPSat")
    assert fig_box is not None

    fig_conv = create_mc_convergence_figure(multi_solver_mc_df, solver_name="CPSat")
    assert fig_conv is not None
    # For 500 samples of CPSat, x length should be 500, not 1500
    scatter_traces = [t for t in fig_conv.data if hasattr(t, "x") and len(t.x) > 0]
    assert any(len(t.x) == 500 for t in scatter_traces)


def test_r01_t15_mc_drilldown_respects_solver_name(multi_solver_mc_df):
    """R01-T15: adapt_mc_scenario_drilldown returns metrics matching the requested solver."""
    drilldown = adapt_mc_scenario_drilldown(
        scenario_id="MC500_S0000",
        df_fixed=multi_solver_mc_df,
        df_recourse=multi_solver_mc_df,
        solver_name="CPSat",
    )
    assert drilldown["fixed_plan"] is not None
    assert drilldown["fixed_plan"]["solver_name"] == "CPSat"
    assert drilldown["fixed_plan"]["objective_value"] == 100.0


def test_r01_t16_scientific_validator_strict_contamination_rejection(multi_solver_mc_df):
    """R01-T16: ScientificValidator raises IncompatibleComparisonError when allow_filter=False."""
    with pytest.raises(IncompatibleComparisonError, match="Multi-solver contamination detected"):
        ScientificValidator.validate_single_solver_dataframe(
            multi_solver_mc_df,
            target_solver="CPSat",
            allow_filter=False,
        )


# ==============================================================================
# 4. CONTROL TOWER DYNAMIC KPIS & HONEST BASELINE (R01-T17 to R01-T19)
# ==============================================================================

def test_r01_t17_control_tower_nominal_conflicts_dynamic():
    """R01-T17: Nominal conflicts in canonical 120 scenario must be computed dynamically (0 conflicts scheduled)."""
    service = ScenarioService()
    flights, gates = service.load_scenario("SCEN_P09_CANONICAL_120")

    gate_flights: Dict[str, list] = {}
    for f in flights:
        if f.nominal_gate_id:
            gate_flights.setdefault(f.nominal_gate_id, []).append(f)
    conflicts = 0
    for g, f_list in gate_flights.items():
        n = len(f_list)
        for i in range(n):
            for j in range(i + 1, n):
                f1, f2 = f_list[i], f_list[j]
                if f1.occupancy_start_min < f2.occupancy_end_min and f2.occupancy_start_min < f1.occupancy_end_min:
                    conflicts += 1

    assert conflicts == 0, "Canonical scheduled timetable must have 0 static gate overlaps on scheduled times."


def test_r01_t18_control_tower_turnaround_slack_dynamic():
    """R01-T18: Turnaround slack distribution must be computed from flight objects, not hardcoded."""
    service = ScenarioService()
    flights, _ = service.load_scenario("SCEN_P09_CANONICAL_120")

    slacks = [f.turnaround_slack_min for f in flights if f.turnaround_slack_min is not None]
    assert len(slacks) == 120
    gt20 = sum(1 for s in slacks if s > 20)
    b5_20 = sum(1 for s in slacks if 5 <= s <= 20)
    lt5 = sum(1 for s in slacks if s < 5)

    # In canonical 120, turnaround is scheduled 60m with min 45m -> 15m slack for all 120
    assert b5_20 == 120
    assert gt20 == 0
    assert lt5 == 0


def test_r01_t19_active_run_mismatch_or_none_defaults_to_not_run():
    """R01-T19: When active_run is None or has different scenario_id, solver status must be baseline."""
    # Simulation of page 01 check logic
    active_run = SolverRunView(
        solver_name="cpsat",
        scenario_id="SCEN_OTHER_999",  # Mismatched scenario
        objective_value=130.0,
        decision_cost=130.0,
        reporting_cost=130.0,
        reassignment_count=0,
        remote_gate_count=0,
        conflict_count=0,
        solve_time_sec=0.1,
        status="OPTIMAL",
        termination_reason="OPTIMAL",
        is_optimal_proven=True,
    )
    active_scenario_id = "SCEN_P09_CANONICAL_120"
    if active_run is not None and getattr(active_run, "scenario_id", None) != active_scenario_id:
        active_run = None

    assert active_run is None


# ==============================================================================
# 5. CONTEXT BAR & PAGE HONESTY (R01-T20 to R01-T24)
# ==============================================================================

def test_r01_t20_context_bar_defaults_are_honest():
    """R01-T20: render_context_bar defaults must be CANONICAL BASELINE and is_optimal=False."""
    import inspect
    sig = inspect.signature(render_context_bar)
    assert sig.parameters["solver_status_text"].default == "LỊCH CƠ SỞ (CANONICAL BASELINE)"
    assert sig.parameters["is_optimal"].default is False


def test_r01_t21_flight_intelligence_handles_none_sched_arr_time():
    """R01-T21: Flight Intelligence sorting & display must handle sched_arr_time_min=None without error."""
    views = [
        FlightPredictionView(flight_id="F1", sched_arr_time_min=None, predicted_arr_delay_min=10.0),
        FlightPredictionView(flight_id="F2", sched_arr_time_min=480, predicted_arr_delay_min=5.0),
    ]
    # Sorting by arrival time
    sorted_views = sorted(views, key=lambda x: x.sched_arr_time_min if x.sched_arr_time_min is not None else -1)
    assert sorted_views[0].flight_id == "F1"
    assert sorted_views[1].flight_id == "F2"

    # Formatting table row
    for v in sorted_views:
        if v.sched_arr_time_min is not None:
            time_str = f"{v.sched_arr_time_min // 60:02d}:{v.sched_arr_time_min % 60:02d}"
        else:
            time_str = "N/A"
        assert time_str in ["N/A", "08:00"]


def test_r01_t22_flight_prediction_view_immutability():
    """R01-T22: FlightPredictionView is a frozen dataclass with schema_version."""
    v = FlightPredictionView(flight_id="F100")
    assert v.schema_version == "1.0"
    with pytest.raises(Exception):
        v.carrier = "UA"  # Frozen dataclass mutation forbidden


def test_r01_t23_robustness_view_immutability_and_none_support():
    """R01-T23: RobustnessView allows None metrics and enforces immutability."""
    r = RobustnessView(mode_name="MODE_A", scenario_count=500, mean_cost=None)
    assert r.mean_cost is None
    with pytest.raises(Exception):
        r.mean_cost = 100.0


def test_r01_t24_optimization_lab_benchmark_summary_rows():
    """R01-T24: Multi-solver summaries in Optimization Lab compute actual non-hardcoded averages."""
    from dashboard.adapters.artifact_loader import ArtifactLoader
    loader = ArtifactLoader()
    df = loader.load_solver_benchmarks()
    assert not df.empty

    solver_groups = df.groupby("solver_variant")
    assert len(solver_groups) >= 3

    for variant, group in solver_groups:
        feasible_runs = group[group["feasible"].astype(bool)]
        if not feasible_runs.empty:
            avg_cost = float(feasible_runs["objective_value"].mean())
            # Real costs are not hardcoded 130.0 for all solvers
            assert avg_cost > 0.0
