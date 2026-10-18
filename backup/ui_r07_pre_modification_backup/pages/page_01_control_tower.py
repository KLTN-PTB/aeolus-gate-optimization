"""Page 01: Control Tower (Tổng quan Điều hành).

Executive operational overview for Atlanta Hub (ATL) flight operations,
displaying incoming delay waves, concourse utilization, and CP-SAT optimization health.
Enforces authentic data provenance and eliminates fabricated defaults.
"""

from typing import Any, Dict, List, Optional
import pandas as pd
import streamlit as st

from dashboard.adapters.artifact_loader import ArtifactLoader
from dashboard.components.context_bar import render_context_bar
from dashboard.components.kpi_card import render_kpi_card
from dashboard.components.research_inspector import render_research_inspector
from dashboard.core.contracts import SolverRunView
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

    # 4. Scenario Launcher Banner
    st.markdown(
        f"""
        <div class="aeolus-card" style="padding: 12px 18px; margin-bottom: 16px; border-left: 4px solid #47C5C0;">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
                <div>
                    <span style="font-size: 16px; font-weight: 700; color: #F0F4F8;">
                        ✈️ CẢNG HÀNG KHÔNG QUỐC TẾ ATLANTA (ATL) — {scenario_context.scenario_id}
                    </span>
                    <div style="font-size: 12px; color: #94A3B8; margin-top: 3px;">
                        Quy mô: <b>{scenario_context.flight_count} Lượt bay</b> | Hạ tầng: <b>{scenario_context.gate_count} Cổng ống lồng + {scenario_context.remote_capacity} Bãi đỗ xa</b> | Ngày khai thác: <b>2023-07-15</b>
                    </div>
                </div>
                <div style="text-align: right;">
                    <span class="aeolus-badge aeolus-badge-info" style="font-size: 11px;">
                        NGUỒN DỮ LIỆU: {scenario_context.provenance.value}
                    </span>
                    <div style="font-size: 11px; color: #64748B; margin-top: 4px; font-family: 'JetBrains Mono', monospace;">
                        DIGEST: {scenario_context.scenario_hash[:16]}...
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 5. Authoritative Data Loading (Zero Shortcut, Zero Fabrication)
    turns = scenario_service.load_scenario_turns(active_scenario_id)
    turn_count_str = f"{len(turns)} Cặp quay vòng" if len(turns) > 0 else "N/A (Chưa ghép cặp)"
    inventory = scenario_service.get_scenario_gate_inventory(active_scenario_id)
    contact_count = inventory["contact_count"]
    remote_count = inventory["remote_count"]

    predictions = scenario_service.load_scenario_predictions(active_scenario_id)
    if predictions:
        pred_delays = [p.predicted_arr_delay_min for p in predictions]
        avg_delay = float(sum(pred_delays) / len(pred_delays))
        pct_ge_15 = float(sum(1 for d in pred_delays if d >= 15.0) / len(pred_delays) * 100)
    else:
        avg_delay = None
        pct_ge_15 = None

    # Compute Nominal Conflicts Dynamically
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

    # 6. Four Primary Executive KPI Cards
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        render_kpi_card(
            title="LƯỢT TÀU BAY & QUAY VÒNG",
            value=f"{len(flights)} Lượt bay",
            subtitle=turn_count_str,
            badge_text="[ATL ĐIỀU HÀNH]",
            badge_type="info",
            icon="✈️",
            help_tooltip="Tổng số lượt cất/hạ cánh và số cặp quay vòng xác thực.",
        )

    with col2:
        render_kpi_card(
            title="TÀI NGUYÊN CỔNG ĐỖ",
            value=f"{contact_count} Ống lồng + {remote_count} Đỗ xa",
            subtitle="Sức chứa đỗ xa: 1 tàu bay | Bãi tràn: Cho phép",
            badge_text=f"[TỔNG {len(gates)} VỊ TRÍ]",
            badge_type="info",
            icon="🏢",
            help_tooltip="Phân loại tài nguyên cổng: Cổng ống lồng cố định, bãi đỗ xa hữu hạn, bãi tràn không giới hạn.",
        )

    with col3:
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
            title="DỰ BÁO ĐỘ TRỄ ML",
            value=delay_val,
            subtitle=delay_sub,
            badge_text=badge_t,
            badge_type=badge_type,
            icon="⏱️",
            help_tooltip="Dự báo trễ trung bình có dấu từ mô hình Dual-Core ML.",
        )

    with col4:
        if active_run is not None:
            opt_val = f"{active_run.solver_name.upper()} ({active_run.status.upper()})"
            opt_sub = f"{active_run.conflict_count} Xung đột • {active_run.remote_gate_count} Cổng xa"
            opt_badge = "[🛡️ ĐÃ TỐI ƯU]" if active_run.conflict_count == 0 else "[⚠️ CÒN XUNG ĐỘT]"
            opt_badge_type = "success" if active_run.conflict_count == 0 else "error"
        else:
            opt_val = "CHƯA CHẠY [NOT_RUN]"
            opt_sub = "Chưa kích hoạt giải thuật"
            opt_badge = "[CHƯA GIẢI PHÁP]"
            opt_badge_type = "info"
        render_kpi_card(
            title="TRẠNG THÁI TỐI ƯU HÓA",
            value=opt_val,
            subtitle=opt_sub,
            badge_text=opt_badge,
            badge_type=opt_badge_type,
            icon="🛡️",
            help_tooltip="Trạng thái nghiệm tối ưu của kịch bản hiện hành.",
        )

    st.markdown("<div style='margin-top: 16px;'></div>", unsafe_allow_html=True)

    # 7. Charts Row: Timeline & Gate Concourse Utilization
    chart_col1, chart_col2 = st.columns([7, 5])

    with chart_col1:
        timeline_fig = create_activity_timeline_figure(flights)
        st.plotly_chart(timeline_fig, width="stretch")

    with chart_col2:
        concourse_fig = create_concourse_utilization_figure(
            gates=gates,
            assignments=active_run.assignments if active_run else None,
        )
        st.plotly_chart(concourse_fig, width="stretch")

    # 8. Operational Health & Quick Actions
    bot_col1, bot_col2 = st.columns([7, 5])

    with bot_col1:
        if turns:
            slacks = [t.remaining_slack_min for t in turns]
        else:
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
                f'<div><span class="aeolus-badge aeolus-badge-success">● An toàn (&gt;20m)</span>: <b>{gt20} lượt ({pct_gt20:.1f}%)</b></div>'
                f'<div><span class="aeolus-badge aeolus-badge-warning">● Rủi ro TB (5-20m)</span>: <b>{b5_20} lượt ({pct_b5_20:.1f}%)</b></div>'
                f'<div><span class="aeolus-badge aeolus-badge-error">● Nguy cơ cao (&lt;5m)</span>: <b>{lt5} lượt ({pct_lt5:.1f}%)</b></div>'
                f'</div>'
            )
        else:
            slack_html = '<div style="font-size: 13px; color: #94A3B8;">Kịch bản hiện tại chưa có dữ liệu đệm quay vòng (Unpaired Scenario).</div>'

        st.markdown(
            f"""
            <div class="aeolus-card">
                <div style="font-weight: 600; font-size: 14px; margin-bottom: 8px;">
                    🔄 PHÂN BỔ SLACK QUAY VÒNG TÀU BAY (TURNAROUND SLACK HEALTH)
                </div>
                <div style="font-size: 13px; color: #94A3B8; margin-bottom: 12px;">
                    Độ an toàn thời gian đệm quay vòng giữa chuyến hạ cánh và cất cánh liên tiếp:
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
            if st.button("🔬 Xem Flight Intelligence", width="stretch"):
                st.session_state[SessionStateKeys.CURRENT_PAGE] = PageKeys.FLIGHT_INTELLIGENCE.value
                st.rerun()
        with btn_c2:
            if st.button("🛫 Xem Gate Operations", width="stretch"):
                st.session_state[SessionStateKeys.CURRENT_PAGE] = PageKeys.GATE_OPERATIONS.value
                st.rerun()

    # 9. Research Inspector Drawer
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
            "nominal_conflicts": nominal_conflicts,
            "hash": scenario_context.scenario_hash,
        },
    )
