"""Page 01: Control Tower (Tổng quan Điều hành).

Executive operational overview for Atlanta Hub (ATL) flight operations,
displaying incoming delay waves, concourse utilization, and CP-SAT optimization health.
"""

from typing import Any, Dict, List, Optional
import pandas as pd
import streamlit as st

from dashboard.adapters.artifact_loader import ArtifactLoader
from dashboard.components.context_bar import render_context_bar
from dashboard.components.kpi_card import render_kpi_card
from dashboard.components.research_inspector import render_research_inspector
from dashboard.core.state import PageKeys, SessionStateKeys
from dashboard.services.scenario_service import ScenarioService
from dashboard.visualizers.concourse_chart import create_concourse_utilization_figure
from dashboard.visualizers.timeline_chart import create_activity_timeline_figure


def render_page() -> None:
    """Render Page 01: Control Tower."""
    # 1. Active Scenario Context
    scenario_service = ScenarioService()
    active_scenario_id = st.session_state.get(
        SessionStateKeys.SELECTED_SCENARIO_ID, "SCEN_P09_CANONICAL_120"
    )

    try:
        scenario_context = scenario_service.get_scenario_context(active_scenario_id)
        flights, gates = scenario_service.load_scenario(active_scenario_id)
    except Exception as exc:
        st.error(f"Lỗi khi tải kịch bản {active_scenario_id}: {exc}")
        return

    # 2. Check Active Optimization Run in Session
    active_run: Optional[SolverRunView] = st.session_state.get(SessionStateKeys.ACTIVE_RESULT)
    if active_run is not None and getattr(active_run, "scenario_id", None) != active_scenario_id:
        active_run = None

    if active_run is not None:
        solver_status_text = f"{active_run.solver_name.upper()} ({active_run.status.upper()})"
        is_optimal = bool(active_run.is_optimal_proven)
    else:
        solver_status_text = "LỊCH DANH ĐỊNH GỐC (NOMINAL)"
        is_optimal = False

    # 3. Render Pinned Global Context Bar
    render_context_bar(
        context=scenario_context,
        solver_status_text=solver_status_text,
        is_optimal=is_optimal,
    )

    # 4. Load Predictions Summary for KPI Metrics (Without silent fake defaults)
    artifact_loader = ArtifactLoader()
    avg_delay = None
    pct_ge_15 = None
    try:
        pred_df = artifact_loader.load_csv("artifacts/remediation/native_dual_core/predictions_sample.csv")
        pred_delays = pred_df["predicted_delay_min"].dropna()
        if not pred_delays.empty:
            avg_delay = float(pred_delays.mean())
            pct_ge_15 = float((pred_delays >= 15.0).mean() * 100)
    except Exception:
        pass

    # 5. Compute Nominal Conflicts Dynamically
    gate_flights: Dict[str, list] = {}
    for f in flights:
        if f.nominal_gate_id:
            gate_flights.setdefault(f.nominal_gate_id, []).append(f)
    nominal_conflicts = 0
    for g, f_list in gate_flights.items():
        n_fl = len(f_list)
        for i in range(n_fl):
            for j in range(i + 1, n_fl):
                f1, f2 = f_list[i], f_list[j]
                if f1.occupancy_start_min < f2.occupancy_end_min and f2.occupancy_start_min < f1.occupancy_end_min:
                    nominal_conflicts += 1

    # 6. Five Executive KPI Cards
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        render_kpi_card(
            title="TỔNG CHUYẾN BAY",
            value=f"{len(flights)} Chuyến",
            subtitle=f"{len(flights) // 2} Cặp quay vòng",
            badge_text="[ATL ĐIỀU HÀNH]",
            badge_type="info",
            icon="✈️",
            help_tooltip="Tổng số lượt cất/hạ cánh trong kịch bản sóng sáng cao điểm.",
        )

    with col2:
        if avg_delay is not None:
            delay_val = f"{avg_delay:+.1f} min"
            delay_sub = f"{pct_ge_15:.1f}% trễ ≥ 15m"
            badge_t = "[⚠️ NGUY CƠ CAO]" if avg_delay > 15.0 else "[✓ BÌNH THƯỜNG]"
            badge_type = "warning" if avg_delay > 15.0 else "info"
        else:
            delay_val = "N/A"
            delay_sub = "Chưa có dự báo ML"
            badge_t = "[CHƯA CÓ DỮ LIỆU]"
            badge_type = "info"
        render_kpi_card(
            title="TRỄ ĐẾN DỰ BÁO",
            value=delay_val,
            subtitle=delay_sub,
            badge_text=badge_t,
            badge_type=badge_type,
            icon="⏱️",
            help_tooltip="Dự báo trễ trung bình từ mô hình NGBoost/XGBoost Dual-Core.",
        )

    with col3:
        render_kpi_card(
            title="XUNG ĐỘT TĨNH",
            value=f"{nominal_conflicts} Cặp xung đột",
            subtitle="Kế hoạch gốc chưa đổi cổng",
            badge_text="[⚠️ NGUY CƠ CAO]" if nominal_conflicts > 0 else "[✓ KHÔNG XUNG ĐỘT]",
            badge_type="error" if nominal_conflicts > 0 else "success",
            icon="⚡",
            help_tooltip="Số lượng va chạm thời gian cổng nếu duy trì lịch phân cổng tĩnh ban đầu.",
        )

    with col4:
        if active_run is not None:
            opt_val = f"{active_run.conflict_count} Xung đột"
            opt_sub = "100% Ràng buộc thỏa mãn" if active_run.conflict_count == 0 else f"{active_run.conflict_count} vi phạm"
            opt_badge = "[🛡️ ĐÃ GIẢI TỎA]" if active_run.conflict_count == 0 else "[⚠️ CÒN XUNG ĐỘT]"
            opt_badge_type = "success" if active_run.conflict_count == 0 else "error"
        else:
            opt_val = "CHƯA CHẠY [NOT_RUN]"
            opt_sub = "Chưa kích hoạt giải thuật"
            opt_badge = "[CHƯA CHẠY]"
            opt_badge_type = "info"
        render_kpi_card(
            title="TỐI ƯU HÓA",
            value=opt_val,
            subtitle=opt_sub,
            badge_text=opt_badge,
            badge_type=opt_badge_type,
            icon="🛡️",
            help_tooltip="Kết quả tối ưu phân cổng từ phiên làm việc hiện tại.",
        )

    with col5:
        if active_run is not None:
            remote_val = f"{active_run.remote_gate_count} Cổng"
            remote_sub = "100% Cổng ống lồng" if active_run.remote_gate_count == 0 else f"{active_run.remote_gate_count} chuyến đỗ xa"
            remote_badge = "[✓ TIỆN NGHI]" if active_run.remote_gate_count == 0 else "[🚌 BÃI ĐỖ XA]"
            remote_badge_type = "info" if active_run.remote_gate_count == 0 else "warning"
        else:
            remote_val = "CHƯA CHẠY [NOT_RUN]"
            remote_sub = "Theo dõi sau tối ưu"
            remote_badge = "[CHƯA CHẠY]"
            remote_badge_type = "info"
        render_kpi_card(
            title="CỔNG ĐỖ TỪ XA",
            value=remote_val,
            subtitle=remote_sub,
            badge_text=remote_badge,
            badge_type=remote_badge_type,
            icon="🚌",
            help_tooltip="Số chuyến phải đưa ra bãi đỗ xa (Remote Apron) sau khi tối ưu.",
        )

    st.markdown("<div style='margin-top: 16px;'></div>", unsafe_allow_html=True)

    # 7. Charts Row: CHART-01 (Timeline) & CHART-08 (Concourse Utilization)
    chart_col1, chart_col2 = st.columns([7, 5])

    with chart_col1:
        timeline_fig = create_activity_timeline_figure(flights)
        st.plotly_chart(timeline_fig, use_container_width=True)

    with chart_col2:
        concourse_fig = create_concourse_utilization_figure()
        st.plotly_chart(concourse_fig, use_container_width=True)

    # 8. Operational Health & Quick Actions
    bot_col1, bot_col2 = st.columns([7, 5])

    with bot_col1:
        slacks = [f.turnaround_slack_min for f in flights if f.turnaround_slack_min is not None]
        total_slacks = len(slacks)
        if total_slacks > 0:
            gt20 = sum(1 for s in slacks if s > 20)
            b5_20 = sum(1 for s in slacks if 5 <= s <= 20)
            lt5 = sum(1 for s in slacks if s < 5)
            pct_gt20 = (gt20 / total_slacks) * 100
            pct_b5_20 = (b5_20 / total_slacks) * 100
            pct_lt5 = (lt5 / total_slacks) * 100
            slack_html = (
                f'<div style="display: flex; gap: 16px; font-size: 13px;">'
                f'<div><span class="aeolus-badge aeolus-badge-success">● An toàn (&gt;20m)</span>: <b>{gt20} chuyến ({pct_gt20:.1f}%)</b></div>'
                f'<div><span class="aeolus-badge aeolus-badge-warning">● Rủi ro TB (5-20m)</span>: <b>{b5_20} chuyến ({pct_b5_20:.1f}%)</b></div>'
                f'<div><span class="aeolus-badge aeolus-badge-error">● Nguy cơ cao (&lt;5m)</span>: <b>{lt5} chuyến ({pct_lt5:.1f}%)</b></div>'
                f'</div>'
            )
        else:
            slack_html = '<div style="font-size: 13px; color: #94A3B8;">Không có dữ liệu slack quay vòng cho kịch bản này.</div>'

        st.markdown(
            f"""
            <div class="aeolus-card">
                <div style="font-weight: 600; font-size: 14px; margin-bottom: 8px;">
                    🔄 PHÂN BỔ SLACK QUAY VÒNG TÀU BAY (TURNAROUND SLACK HEALTH)
                </div>
                <div style="font-size: 13px; color: #94A3B8; margin-bottom: 12px;">
                    Phân loại rủi ro thời gian đệm quay vòng giữa chuyến hạ cánh và cất cánh liên tiếp:
                </div>
                {slack_html}
            </div>
            """,
            unsafe_allow_html=True,
        )

    with bot_col2:
        st.markdown(
            """
            <div class="aeolus-card">
                <div style="font-weight: 600; font-size: 14px; margin-bottom: 8px;">
                    ⚡ ĐIỀU HƯỚNG TÁC NGHIỆP NHANH
                </div>
                <div style="font-size: 13px; color: #94A3B8; margin-bottom: 12px;">
                    Chuyển nhanh đến các màn hình phân tích chuyên sâu:
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        btn_c1, btn_c2 = st.columns(2)
        with btn_c1:
            if st.button("🔬 Xem Flight Intelligence", use_container_width=True):
                st.session_state[SessionStateKeys.CURRENT_PAGE] = PageKeys.FLIGHT_INTELLIGENCE.value
                st.rerun()
        with btn_c2:
            if st.button("🛫 Xem Gate Operations", use_container_width=True):
                st.session_state[SessionStateKeys.CURRENT_PAGE] = PageKeys.GATE_OPERATIONS.value
                st.rerun()

    # 7. Research Inspector Drawer
    render_research_inspector(
        title="CONTROL TOWER AUDIT — THÔNG SỐ VẬN HÀNH & NGUỒN GỐC KỊCH BẢN",
        metadata={
            "scenario_id": active_scenario_id,
            "scenario_hash": scenario_context.scenario_hash,
            "provenance": scenario_context.provenance.value,
            "version": "stage10_frozen_v1",
        },
        raw_data={
            "scenario_id": active_scenario_id,
            "flight_count": len(flights),
            "gate_count": len(gates),
            "hub": "ATL",
            "hash": scenario_context.scenario_hash,
        },
    )
