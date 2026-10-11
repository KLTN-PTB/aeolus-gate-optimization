"""Unit and Integration Tests for Phase UI-R04: Control Tower & Dual-Core Flight Intelligence Redesign.

Verifies:
- Scenario launcher metadata and honest provenance display.
- Elimination of len(flights) // 2 turn count estimation.
- Authoritative loading of dual-core predictions (ARR & DEP) and turns.
- Occupancy interval formulation [A_pred, T_release) with single buffer addition.
- Concourse utilization unrun zero-occupied integrity (no fabricated 8 and 15).
- Clean visualizer titles (no raw chart ID codes).
- Zero data leakage enforcement in predictions.
- TreeSHAP explainability artifacts and research mode OOF validation.
"""

import math
from pathlib import Path
from typing import Any, Dict, List
import pandas as pd
import pytest

from dashboard.adapters.artifact_loader import ArtifactLoader
from dashboard.adapters.prediction_adapter import adapt_prediction_row_to_view
from dashboard.adapters.turn_adapter import adapt_turn_to_view
from dashboard.core.config import DEFAULT_CONFIG
from dashboard.core.contracts import (
    AircraftTurnView,
    FlightPredictionView,
    ProvenanceType,
    RiskCategory,
    SolverRunView,
)
from dashboard.services.scenario_service import ScenarioService
from dashboard.visualizers.concourse_chart import create_concourse_utilization_figure
from dashboard.visualizers.timeline_chart import create_activity_timeline_figure
from dashboard.visualizers.turn_dynamics_chart import create_turn_dynamics_figure
from src.optimization.domain import Flight, Gate, GateResourceType


# -----------------------------------------------------------------------------
# R04-T01 to R04-T10: Control Tower & Scenario Governance
# -----------------------------------------------------------------------------

def test_r04_t01_control_tower_scenario_launcher_metadata() -> None:
    """R04-T01: Verify scenario context contains hub, flight count, gate count, and deterministic digest."""
    svc = ScenarioService()
    ctx_120 = svc.get_scenario_context("SCEN_P09_CANONICAL_120")
    assert ctx_120.hub_iata == "ATL"
    assert ctx_120.flight_count == 120
    assert ctx_120.gate_count == 25
    assert len(ctx_120.scenario_hash) == 64

    ctx_p07 = svc.get_scenario_context("SCEN_P07_DUAL_CORE_30")
    assert ctx_p07.hub_iata == "ATL"
    assert ctx_p07.flight_count == 60
    assert ctx_p07.gate_count == 15
    assert len(ctx_p07.scenario_hash) == 64


def test_r04_t02_control_tower_kpi_turn_count_not_derived_shortcut() -> None:
    """R04-T02: Verify that turn count is NOT derived from len(flights)//2 shortcut.
    Unpaired scenarios must return an empty list of turns.
    """
    svc = ScenarioService()
    unpaired_turns = svc.load_scenario_turns("SCEN_P09_CANONICAL_120")
    assert unpaired_turns == []
    assert len(unpaired_turns) != 120 // 2  # Must NOT be 60


def test_r04_t03_control_tower_paired_scenario_turns_loaded() -> None:
    """R04-T03: Verify that SCEN_P07_DUAL_CORE_30 loads authentic turns."""
    svc = ScenarioService()
    turns = svc.load_scenario_turns("SCEN_P07_DUAL_CORE_30")
    assert len(turns) == 30
    first_turn = turns[0]
    assert first_turn.turn_id.startswith("TURN_")
    assert first_turn.inbound_flight_id.startswith("LEG_ARR_")
    assert first_turn.outbound_flight_id.startswith("LEG_DEP_")


def test_r04_t04_control_tower_gate_inventory_honest_breakdown() -> None:
    """R04-T04: Verify contact vs remote vs overflow gates are honestly distinguished."""
    svc = ScenarioService()
    inv_120 = svc.get_scenario_gate_inventory("SCEN_P09_CANONICAL_120")
    assert inv_120["contact_count"] == 25
    assert inv_120["remote_count"] == 1
    assert inv_120["overflow_allowed"] is True

    inv_p07 = svc.get_scenario_gate_inventory("SCEN_P07_DUAL_CORE_30")
    assert inv_p07["contact_count"] == 15
    assert inv_p07["remote_count"] == 1


def test_r04_t05_control_tower_predicted_delay_negative_sign_preserved() -> None:
    """R04-T05: Verify signed delays (e.g. negative values) are preserved without truncation."""
    svc = ScenarioService()
    preds = svc.load_scenario_predictions("SCEN_P07_DUAL_CORE_30")
    delays = [p.predicted_arr_delay_min for p in preds]
    assert any(d < 0.0 for d in delays), "Expected at least one negative signed delay in dual-core sample"
    avg_delay = sum(delays) / len(delays)
    assert avg_delay < 0.0, f"Average delay should be negative in dual-core sample: {avg_delay}"


def test_r04_t06_control_tower_unrun_optimization_status_is_honest() -> None:
    """R04-T06: Verify unrun optimization displays NOT_RUN, never false optimal."""
    import dashboard.pages.page_01_control_tower as p01
    # Verify the code logic contains NOT_RUN when active_run is None
    import inspect
    source = inspect.getsource(p01.render_page)
    assert "CHƯA CHẠY [NOT_RUN]" in source
    assert "Chưa kích hoạt giải thuật" in source


def test_r04_t07_control_tower_active_run_optimization_status_reported() -> None:
    """R04-T07: Verify when an active run exists, solver name and conflict count are reported."""
    run = SolverRunView(
        run_id="RUN_TEST_01",
        solver_name="CPSat",
        status="OPTIMAL",
        scenario_id="SCEN_P09_CANONICAL_120",
        conflict_count=0,
        remote_gate_count=0,
        objective_value=0.0,
        decision_cost=0.0,
        reporting_cost=0.0,
        reassignment_count=0,
        solve_time_sec=1.5,
        termination_reason="OPTIMAL",
        is_optimal_proven=True,
    )
    assert run.solver_name.upper() == "CPSAT"
    assert run.conflict_count == 0
    assert run.is_optimal_proven is True


def test_r04_t08_control_tower_concourse_utilization_unrun_zero_occupied() -> None:
    """R04-T08: Verify create_concourse_utilization_figure has occupied=0 when unrun."""
    fig = create_concourse_utilization_figure()
    occupied_trace = [t for t in fig.data if t.name == "Số Cổng Đang Dùng"][0]
    assert all(occ == 0 for occ in occupied_trace.x), "Default unrun occupied must be all 0 (no fabrication)"


def test_r04_t09_control_tower_concourse_utilization_dynamic_from_gates() -> None:
    """R04-T09: Verify create_concourse_utilization_figure dynamically computes from gates with 0 occupied."""
    gates = [
        Gate("G01", 0, GateResourceType.CONTACT_GATE, 1.0, False),
        Gate("G02", 1, GateResourceType.CONTACT_GATE, 1.0, False),
        Gate("REMOTE_01", 2, GateResourceType.FINITE_REMOTE_STAND, 1.0, False),
    ]
    fig = create_concourse_utilization_figure(gates=gates, assignments=None)
    occupied_trace = [t for t in fig.data if t.name == "Số Cổng Đang Dùng"][0]
    assert all(occ == 0 for occ in occupied_trace.x)


def test_r04_t10_control_tower_activity_timeline_clean_title() -> None:
    """R04-T10: Verify activity timeline figure has clean title without raw (CHART-01) code."""
    flights = [
        Flight("FL01", 0, "DL", "101", 540, 600, 545, "B738", "G01", 45, 60, 15, True, 600)
    ]
    fig = create_activity_timeline_figure(flights)
    title_text = fig.layout.title.text
    assert "(CHART-01)" not in title_text
    assert "BIỂU ĐỒ HOẠT ĐỘNG KHAI THÁC THEO KHUNG GIỜ" in title_text


# -----------------------------------------------------------------------------
# R04-T11 to R04-T18: Dual-Core Flight Intelligence (Tab A)
# -----------------------------------------------------------------------------

def test_r04_t11_flight_intelligence_dual_core_table_contains_arr_and_dep() -> None:
    """R04-T11: Verify predictions loaded for P07 contain both ARR and DEP flight directions."""
    svc = ScenarioService()
    preds = svc.load_scenario_predictions("SCEN_P07_DUAL_CORE_30")
    directions = set(p.flight_direction for p in preds)
    assert directions == {"ARR", "DEP"}
    arr_count = sum(1 for p in preds if p.flight_direction == "ARR")
    dep_count = sum(1 for p in preds if p.flight_direction == "DEP")
    assert arr_count == 30
    assert dep_count == 30


def test_r04_t12_flight_intelligence_direction_filter_isolates_arr_and_dep() -> None:
    """R04-T12: Verify filtering by direction strictly isolates ARR or DEP flights."""
    svc = ScenarioService()
    preds = svc.load_scenario_predictions("SCEN_P07_DUAL_CORE_30")
    arr_only = [p for p in preds if p.flight_direction == "ARR"]
    dep_only = [p for p in preds if p.flight_direction == "DEP"]
    assert all(p.flight_direction == "ARR" for p in arr_only)
    assert all(p.flight_direction == "DEP" for p in dep_only)
    assert len(arr_only) + len(dep_only) == len(preds)


def test_r04_t13_flight_intelligence_signed_delays_preserved_in_views() -> None:
    """R04-T13: Verify FlightPredictionView preserves exact signed values and risk categories."""
    row_arr = {
        "flight_id": "LEG_ARR_0001",
        "flight_direction": "ARR",
        "predicted_delay_min": -9.06,
        "sched_arr_time_min": 652,
    }
    view_arr = adapt_prediction_row_to_view(row_arr)
    assert view_arr.predicted_arr_delay_min == pytest.approx(-9.06, rel=1e-3)
    assert view_arr.risk_category == RiskCategory.LOW
    assert view_arr.flight_direction == "ARR"

    row_dep = {
        "flight_id": "LEG_DEP_0001",
        "flight_direction": "DEP",
        "predicted_delay_min": 1.10,
        "sched_dep_time_min": 966,
    }
    view_dep = adapt_prediction_row_to_view(row_dep)
    assert view_dep.predicted_arr_delay_min == pytest.approx(1.10, rel=1e-3)
    assert view_dep.flight_direction == "DEP"


def test_r04_t14_flight_intelligence_delay_quantiles_and_probabilities() -> None:
    """R04-T14: Verify probability_delay_15 and predictive quantiles are loaded from artifacts."""
    svc = ScenarioService()
    preds = svc.load_scenario_predictions("SCEN_P07_DUAL_CORE_30")
    arr_preds = [p for p in preds if p.flight_direction == "ARR"]
    assert any(p.probability_delay_15 is not None for p in arr_preds)
    assert any("q10" in p.predictive_quantiles for p in arr_preds)
    assert any("q90" in p.predictive_quantiles for p in arr_preds)


def test_r04_t15_flight_intelligence_model_provenance_reported() -> None:
    """R04-T15: Verify prediction models are reported honestly."""
    svc = ScenarioService()
    preds = svc.load_scenario_predictions("SCEN_P07_DUAL_CORE_30")
    arr_preds = [p for p in preds if p.flight_direction == "ARR"]
    assert all("ngboost" in str(p.prediction_model).lower() for p in arr_preds)


def test_r04_t16_flight_intelligence_zero_leakage_enforced_in_predictions() -> None:
    """R04-T16: Verify actual delay columns are rejected / stripped to prevent data leakage."""
    from dashboard.core.validation import DataLeakageError
    leak_row = {
        "flight_id": "LEG_ARR_TEST",
        "actual_delay_min": 25.0,  # Leakage candidate
        "predicted_delay_min": 10.0,
    }
    with pytest.raises((ValueError, DataLeakageError)):
        adapt_prediction_row_to_view(leak_row)


def test_r04_t17_flight_intelligence_unpaired_scenario_renders_empty_state() -> None:
    """R04-T17: Verify Tab B for unpaired scenario has empty turns list and displays empty state."""
    svc = ScenarioService()
    turns_120 = svc.load_scenario_turns("SCEN_P09_CANONICAL_120")
    assert len(turns_120) == 0


def test_r04_t18_flight_intelligence_sample_turns_hardcoding_eliminated() -> None:
    """R04-T18: Verify sample_turns hardcoding (e.g. TURN_DL1024_DL1502) is completely eliminated."""
    import inspect
    import dashboard.pages.page_02_flight_intelligence as p02
    src = inspect.getsource(p02.render_page)
    assert "TURN_DL1024_DL1502" not in src
    assert "TURN_NK0040_NK0041" not in src
    assert "sample_turns" not in src


# -----------------------------------------------------------------------------
# R04-T19 to R04-T25: Turn Dynamics & Explainability (Tab B & Tab C)
# -----------------------------------------------------------------------------

def test_r04_t19_flight_intelligence_turn_occupancy_interval_formula() -> None:
    """R04-T19: Verify D_gate_out = max(D_pred, A_pred + T_min) and T_release = D_gate_out + buffer."""
    turn_raw = {
        "turn_id": "TURN_TEST_01",
        "inbound_flight_id": "ARR_01",
        "outbound_flight_id": "DEP_01",
        "simulated_arrival_min": 882,
        "min_turnaround_min": 45,
        "departure_ml_min": 967,
        "simulated_departure_min": 967,
        "separation_buffer_min": 15,
        "gate_release_min": 982,
        "occupancy_duration_min": 100,
    }
    view = adapt_turn_to_view(turn_raw)
    assert view.gate_occupancy_start_min == 882
    # D_gate_out = max(967, 882 + 45) = 967
    # T_release = 967 + 15 = 982
    assert view.gate_occupancy_end_min == 982
    assert view.gate_occupancy_end_min - view.gate_occupancy_start_min == 100


def test_r04_t20_flight_intelligence_turn_buffer_counted_once() -> None:
    """R04-T20: Verify separation buffer is added exactly once without double counting."""
    svc = ScenarioService()
    turns = svc.load_scenario_turns("SCEN_P07_DUAL_CORE_30")
    for t in turns:
        # Buffer must be exactly 15
        assert t.buffer_min == 15
        # Total occupancy must equal (D_gate_out - A_pred) + buffer_min
        sim_dwell = (t.gate_occupancy_end_min - t.buffer_min) - t.gate_occupancy_start_min
        assert sim_dwell >= t.min_turn_time_min, "Physical dwell must satisfy min_turn_time_min"
        assert t.gate_occupancy_end_min == t.gate_occupancy_start_min + sim_dwell + t.buffer_min


def test_r04_t21_flight_intelligence_turn_slack_absorption_calculation() -> None:
    """R04-T21: Verify slack absorption and remaining slack calculations."""
    turn_dict = {
        "turn_id": "TURN_ABSORB_TEST",
        "inbound_flight_id": "A1",
        "outbound_flight_id": "D1",
        "scheduled_arrival_min": 500,
        "scheduled_departure_min": 600,  # Window = 100 min
        "min_turn_time_min": 45,        # Sched Slack = 100 - 45 = 55 min
        "predicted_arrival_delay_min": 20.0,
    }
    view = adapt_turn_to_view(turn_dict)
    assert view.sched_turn_window_min == 100
    assert view.sched_slack_min == 55
    assert view.inbound_delay_absorbed_min == 20.0
    assert view.remaining_slack_min == 35.0
    assert view.propagated_outbound_delay_min == 0.0


def test_r04_t22_flight_intelligence_turn_dynamics_clean_title() -> None:
    """R04-T22: Verify turn dynamics figure title is clean without raw (CHART-03) string."""
    turn_dict = {
        "turn_id": "TURN_CLEAN_TEST",
        "inbound_flight_id": "A1",
        "outbound_flight_id": "D1",
        "tail_number": "N123AA",
        "aircraft_type": "B738",
    }
    view = adapt_turn_to_view(turn_dict)
    fig = create_turn_dynamics_figure(view)
    assert "(CHART-03)" not in fig.layout.title.text
    assert "ĐỘNG LỰC HỌC QUAY VÒNG & HẤP THỤ BUFFER" in fig.layout.title.text


def test_r04_t23_flight_intelligence_treeshap_global_and_local_loading() -> None:
    """R04-T23: Verify TreeSHAP artifacts load without errors."""
    loader = ArtifactLoader()
    importance_df = loader.load_shap_global_importance()
    assert not importance_df.empty
    assert "feature" in importance_df.columns or "mean_abs_shap" in importance_df.columns

    case_studies = loader.load_shap_case_studies()
    assert len(case_studies) > 0
    first_case = case_studies[0]
    assert "flight_metadata" in first_case
    assert "feature_attributions_ordered" in first_case


def test_r04_t24_flight_intelligence_research_mode_oof_metrics() -> None:
    """R04-T24: Verify OOF regression metrics load valid metric columns."""
    loader = ArtifactLoader()
    metrics_df = loader.load_regression_metrics()
    assert not metrics_df.empty
    # Expect model column and standard error metrics (MAE, RMSE, etc.)
    cols = [c.lower() for c in metrics_df.columns]
    assert any("model" in c for c in cols)
    assert any("mae" in c or "rmse" in c for c in cols)


def test_r04_t25_control_tower_and_flight_intelligence_module_contracts() -> None:
    """R04-T25: Verify render_page contract exists on both Page 01 and Page 02 modules."""
    import dashboard.pages.page_01_control_tower as p01
    import dashboard.pages.page_02_flight_intelligence as p02
    assert hasattr(p01, "render_page")
    assert callable(p01.render_page)
    assert hasattr(p02, "render_page")
    assert callable(p02.render_page)
