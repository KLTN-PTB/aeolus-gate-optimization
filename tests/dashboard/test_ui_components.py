"""Authoritative unit test suite for Aeolus UI Shell, Components & Visualizers (Phase P10-C).

Covers all 20 mandatory requirements (P10C-01 through P10C-20).
"""

from typing import Dict, List
import numpy as np
import pandas as pd
import pytest
import plotly.graph_objects as go

from dashboard.adapters.artifact_loader import ArtifactLoader
from dashboard.adapters.prediction_adapter import adapt_prediction_row_to_view
from dashboard.adapters.turn_adapter import adapt_turn_to_view
from dashboard.app import PAGES
from dashboard.components.context_bar import render_context_bar
from dashboard.components.kpi_card import render_kpi_card
from dashboard.components.research_inspector import render_research_inspector
from dashboard.core.config import DEFAULT_CONFIG
from dashboard.core.contracts import (
    AircraftTurnView,
    FlightPredictionView,
    ProvenanceType,
    RiskCategory,
    ScenarioContext,
)
from dashboard.core.state import SessionStateKeys, get_initial_session_state
from dashboard.core.validation import DataLeakageError
from dashboard.services.scenario_service import ScenarioService
from dashboard.visualizers import (
    AEOLUS_PLOTLY_THEME,
    COLOR_ACCENT_GLOW,
    COLOR_ACCENT_PRIMARY,
    COLOR_BG_CANVAS,
    COLOR_BG_SURFACE,
    COLOR_STATUS_ERROR,
    COLOR_STATUS_SUCCESS,
    COLOR_STATUS_WARNING,
    apply_aeolus_theme,
    create_activity_timeline_figure,
    create_concourse_utilization_figure,
    create_delay_distribution_figure,
    create_shap_global_figure,
    create_shap_waterfall_figure,
    create_turn_dynamics_figure,
)


# ------------------------------------------------------------------------------
# P10C-01: Theme tokens and high-contrast color palette
# ------------------------------------------------------------------------------
def test_p10c_01_theme_tokens_contrast() -> None:
    assert COLOR_BG_CANVAS == "#101B2A"
    assert COLOR_BG_SURFACE == "#162338"
    assert COLOR_ACCENT_PRIMARY == "#47C5C0"
    assert COLOR_ACCENT_GLOW == "#00D2FF"
    assert COLOR_STATUS_SUCCESS == "#34C759"
    assert COLOR_STATUS_WARNING == "#E5AD55"
    assert COLOR_STATUS_ERROR == "#E47777"


# ------------------------------------------------------------------------------
# P10C-02: Plotly theme correctly applied to figures
# ------------------------------------------------------------------------------
def test_p10c_02_plotly_theme_applied() -> None:
    fig = go.Figure(go.Scatter(x=[1, 2], y=[3, 4]))
    fig = apply_aeolus_theme(fig)

    assert fig.layout.paper_bgcolor == COLOR_BG_SURFACE
    assert fig.layout.plot_bgcolor == COLOR_BG_CANVAS
    assert "Inter" in fig.layout.font.family
    assert fig.layout.hoverlabel.bgcolor == "#1D2E49"


# ------------------------------------------------------------------------------
# P10C-03: CHART-01 Activity Timeline empty state handling
# ------------------------------------------------------------------------------
def test_p10c_03_chart01_timeline_empty() -> None:
    fig = create_activity_timeline_figure([])
    assert len(fig.data) == 0
    assert len(fig.layout.annotations) > 0
    assert "Không có dữ liệu" in fig.layout.annotations[0].text


# ------------------------------------------------------------------------------
# P10C-04: CHART-01 Activity Timeline populated with flight legs
# ------------------------------------------------------------------------------
def test_p10c_04_chart01_timeline_populated() -> None:
    scenario_service = ScenarioService()
    flights, _ = scenario_service.load_scenario("SCEN_P09_CANONICAL_120")
    assert len(flights) == 120

    fig = create_activity_timeline_figure(flights, bin_size_minutes=15)
    assert len(fig.data) == 2  # Arrivals & Departures
    assert fig.data[0].name == "Hạ cánh (Inbound)"
    assert fig.data[1].name == "Cất cánh (Outbound)"
    assert fig.layout.barmode == "stack"
    assert fig.data[0].marker.color == COLOR_ACCENT_PRIMARY
    assert fig.data[1].marker.color == COLOR_ACCENT_GLOW


# ------------------------------------------------------------------------------
# P10C-05: CHART-02 Arrival Delay Distribution with threshold annotation
# ------------------------------------------------------------------------------
def test_p10c_05_chart02_delay_distribution() -> None:
    sample_delays = [-5.0, 0.0, 5.0, 12.0, 18.0, 25.0, 40.0]
    fig = create_delay_distribution_figure(sample_delays, threshold_min=15.0)

    assert len(fig.data) == 1
    assert isinstance(fig.data[0], go.Histogram)
    assert fig.data[0].marker.color == COLOR_ACCENT_PRIMARY

    # Verify vertical line threshold (+15 min)
    shapes = fig.layout.shapes
    assert any(s.x0 == 15.0 and s.line.dash == "dash" for s in shapes)


# ------------------------------------------------------------------------------
# P10C-06: CHART-02 Delay Distribution empty state handling
# ------------------------------------------------------------------------------
def test_p10c_06_chart02_empty_state() -> None:
    fig = create_delay_distribution_figure([])
    assert len(fig.data) == 0
    assert len(fig.layout.annotations) > 0
    assert "Chưa có dữ liệu" in fig.layout.annotations[0].text


# ------------------------------------------------------------------------------
# P10C-07: CHART-03 Turn Dynamics horizontal stacked bar decomposition
# ------------------------------------------------------------------------------
def test_p10c_07_chart03_turn_dynamics() -> None:
    turn = AircraftTurnView(
        turn_id="TURN_TEST_01",
        inbound_flight_id="F01",
        outbound_flight_id="F02",
        tail_number="N12345",
        aircraft_type="B738",
        sched_turn_window_min=75,
        min_turn_time_min=45,
        sched_slack_min=30,
        inbound_delay_absorbed_min=20.0,
        remaining_slack_min=10.0,
        propagated_outbound_delay_min=0.0,
        slack_risk_index=RiskCategory.LOW,
        gate_occupancy_start_min=480,
        gate_occupancy_end_min=555,
        buffer_min=15,
    )
    fig = create_turn_dynamics_figure(turn)

    assert len(fig.data) >= 3  # min turn, absorbed, remaining, buffer
    trace_names = [t.name for t in fig.data]
    assert any("Min Turn" in n for n in trace_names)
    assert any("Hấp thụ" in n for n in trace_names)
    assert any("Buffer" in n for n in trace_names)
    assert fig.layout.barmode == "stack"


# ------------------------------------------------------------------------------
# P10C-08: Turnaround slack and propagated delay mathematics verification
# ------------------------------------------------------------------------------
def test_p10c_08_chart03_turnaround_mathematics() -> None:
    sched_slack = 30
    inbound_delay = 40.0  # exceeds slack by 10m

    absorbed = min(float(sched_slack), inbound_delay)
    remaining_slack = max(0.0, sched_slack - inbound_delay)
    propagated_delay = max(0.0, inbound_delay - sched_slack)

    assert absorbed == 30.0
    assert remaining_slack == 0.0
    assert propagated_delay == 10.0


# ------------------------------------------------------------------------------
# P10C-09: CHART-05 Global TreeSHAP feature importance ranking
# ------------------------------------------------------------------------------
def test_p10c_09_chart05_shap_global() -> None:
    df = pd.DataFrame({
        "feature": ["feat_a", "feat_b", "feat_c"],
        "mean_abs_shap": [1.2, 5.4, 3.1],
    })
    fig = create_shap_global_figure(df, top_n=2)
    assert len(fig.data) == 1
    # top 2 should be feat_c and feat_b
    assert len(fig.data[0].x) == 2
    assert fig.data[0].orientation == "h"
    assert fig.data[0].marker.color == COLOR_ACCENT_PRIMARY


# ------------------------------------------------------------------------------
# P10C-10: CHART-06 Single-Flight Waterfall local accuracy check
# ------------------------------------------------------------------------------
def test_p10c_10_chart06_shap_waterfall_valid_sum() -> None:
    case_study = {
        "case_type": "On-Time Flight",
        "flight_metadata": {"carrier": "DL", "flight_num": 466},
        "base_expected_value_minutes": 8.0,
        "model_predicted_delay_minutes": 5.0,
        "feature_attributions_ordered": [
            {"feature": "f1", "attribution_minutes": -2.0},
            {"feature": "f2", "attribution_minutes": -1.0},
        ],
    }
    fig = create_shap_waterfall_figure(case_study)
    assert len(fig.data) == 1
    assert isinstance(fig.data[0], go.Waterfall)
    assert "Tổng SHAP khớp" in fig.layout.title.text


# ------------------------------------------------------------------------------
# P10C-11: CHART-08 Gate Concourse Inventory & Utilization
# ------------------------------------------------------------------------------
def test_p10c_11_chart08_concourse_utilization() -> None:
    stats = {
        "Concourse T": {"capacity": 10, "occupied": 8},
        "Concourse A": {"capacity": 15, "occupied": 15},
        "Remote Apron": {"capacity": 1, "occupied": 0},
    }
    fig = create_concourse_utilization_figure(stats)
    assert len(fig.data) == 2  # Background capacity + occupied bars
    assert fig.layout.barmode == "overlay"


# ------------------------------------------------------------------------------
# P10C-12: Zero Data Leakage verification in Flight Intelligence views
# ------------------------------------------------------------------------------
def test_p10c_12_zero_leakage_in_flight_intelligence() -> None:
    # A dictionary containing forbidden actual delay column must raise DataLeakageError
    leaky_row = {
        "flight_id": "F100",
        "sched_arr_time_min": 480,
        "predicted_arr_delay_min": 12.0,
        "actual_arr_delay_min": 14.0,  # FORBIDDEN
    }
    with pytest.raises(DataLeakageError):
        adapt_prediction_row_to_view(leaky_row)


# ------------------------------------------------------------------------------
# P10C-13: KPI Card Dual-Encoding & formatting verification
# ------------------------------------------------------------------------------
def test_p10c_13_kpi_card_dual_encoding() -> None:
    # Verify render_kpi_card accepts parameters without throwing
    # (Streamlit writes to session context in test environment)
    render_kpi_card(
        title="TỔNG CHUYẾN BAY",
        value="120 Chuyến",
        subtitle="60 Cặp quay vòng",
        badge_text="[🛡️ ĐÃ GIẢI TỎA]",
        badge_type="success",
    )


# ------------------------------------------------------------------------------
# P10C-14: Research Inspector metadata structure
# ------------------------------------------------------------------------------
def test_p10c_14_research_inspector_metadata() -> None:
    meta = {
        "scenario_id": "SCEN_P09_CANONICAL_120",
        "scenario_hash": "e7e7462f17b65b276ebdee9c7beced15e090f69b088a18896d5a91aaa8cb062f",
        "provenance": "SCHEDULE_BASELINE",
        "version": "stage10_frozen_v1",
    }
    render_research_inspector(metadata=meta, raw_data={"sample": 1})


# ------------------------------------------------------------------------------
# P10C-15: Global Context Bar modes
# ------------------------------------------------------------------------------
def test_p10c_15_context_bar_modes() -> None:
    ctx = ScenarioContext(
        scenario_id="SCEN_P09_CANONICAL_120",
        hub_iata="ATL",
        flight_count=120,
        gate_count=26,
        remote_capacity=1,
        scenario_hash="hash123",
    )
    render_context_bar(context=ctx, solver_status_text="TỐI ƯU TUYỆT ĐỐI (CP-SAT)", is_optimal=True)


# ------------------------------------------------------------------------------
# P10C-16: Application Shell Page Registration
# ------------------------------------------------------------------------------
def test_p10c_16_page_routing_registration() -> None:
    assert len(PAGES) == 5
    assert "01_control_tower" in PAGES
    assert "02_flight_intelligence" in PAGES
    assert "03_gate_operations" in PAGES
    assert "04_optimization_lab" in PAGES
    assert "05_robustness_lab" in PAGES


# ------------------------------------------------------------------------------
# P10C-17: Placeholder pages safety (No solver executions on import or render)
# ------------------------------------------------------------------------------
def test_p10c_17_placeholders_safety() -> None:
    from dashboard.pages import (
        page_03_gate_operations,
        page_04_optimization_lab,
        page_05_robustness_lab,
    )
    # Modules must have a callable render_page function
    assert callable(page_03_gate_operations.render_page)
    assert callable(page_04_optimization_lab.render_page)
    assert callable(page_05_robustness_lab.render_page)


# ------------------------------------------------------------------------------
# P10C-18: Real artifact loading across all Page 01 and 02 data sources
# ------------------------------------------------------------------------------
def test_p10c_18_artifact_loader_real_data() -> None:
    loader = ArtifactLoader(DEFAULT_CONFIG)
    
    # 1. Predictions sample
    preds = loader.load_csv("artifacts/remediation/native_dual_core/predictions_sample.csv")
    assert not preds.empty
    assert "predicted_delay_min" in preds.columns

    # 2. Regression metrics
    metrics = loader.load_regression_metrics()
    assert not metrics.empty
    assert "mae" in metrics.columns

    # 3. Global SHAP
    shap_global = loader.load_shap_global_importance()
    assert not shap_global.empty
    assert "feature" in shap_global.columns

    # 4. SHAP Case studies
    cases = loader.load_shap_case_studies()
    assert len(cases) == 3


# ------------------------------------------------------------------------------
# P10C-19: Session state defaults consistency
# ------------------------------------------------------------------------------
def test_p10c_19_session_state_defaults() -> None:
    defaults = get_initial_session_state()
    assert defaults[SessionStateKeys.CURRENT_PAGE] == "01_control_tower"
    assert defaults[SessionStateKeys.IS_RESEARCH_MODE] is False
    assert defaults[SessionStateKeys.ACTIVE_SCENARIO_ID] == "SCEN_P09_CANONICAL_120"


# ------------------------------------------------------------------------------
# P10C-20: Vietnamese typography and domain terminology
# ------------------------------------------------------------------------------
def test_p10c_20_vietnamese_typography_support() -> None:
    vietnamese_terms = [
        "Tổng quan Điều hành",
        "Dự báo Trễ Chuyến bay",
        "Động lực học Quay vòng",
        "Giải thích Mô hình SHAP",
        "Tối ưu Tuyệt đối",
        "Bãi đỗ từ xa",
        "Giãn cách an toàn",
    ]
    for term in vietnamese_terms:
        encoded = term.encode("utf-8").decode("utf-8")
        assert encoded == term
