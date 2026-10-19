"""Page 02: Flight Intelligence (Dự báo Trễ & ML).

Predictive core demonstrating machine learning dual-core arrival/departure delay forecasts,
aircraft turn dynamics and slack absorption, and global/local TreeSHAP explainability.
Enforces zero data leakage: ground-truth historical actual delay is strictly forbidden in planning mode.
"""

from typing import Any, Dict, List, Optional
import pandas as pd
import streamlit as st

from dashboard.adapters.artifact_loader import ArtifactLoader
from dashboard.components.common import render_empty_state, render_section_header
from dashboard.components.context_bar import render_context_bar
from dashboard.components.kpi_card import render_kpi_card
from dashboard.components.research_inspector import render_research_inspector
from dashboard.core.contracts import AircraftTurnView, RiskCategory
from dashboard.core.state import SessionStateKeys
from dashboard.services.scenario_service import ScenarioService
from dashboard.visualizers.delay_distribution_chart import create_delay_distribution_figure
from dashboard.visualizers.shap_charts import (
    create_shap_global_figure,
    create_shap_waterfall_figure,
)
from dashboard.visualizers.turn_dynamics_chart import create_turn_dynamics_figure


def render_page() -> None:
    """Render Page 02: Flight Intelligence."""
    scenario_service = ScenarioService()
    active_scenario_id = st.session_state.get(
        SessionStateKeys.SELECTED_SCENARIO_ID, "SCEN_P09_CANONICAL_120"
    )

    try:
        scenario_context = scenario_service.get_scenario_context(active_scenario_id)
        flights, _ = scenario_service.load_scenario(active_scenario_id)
    except Exception as exc:
        st.error(f"Lỗi khi tải kịch bản {active_scenario_id}: {exc}")
        return
    if scenario_context.time_basis == "HISTORICAL_REPLAY":
        render_context_bar(context=scenario_context, solver_status_text="TÁI HIỆN LỊCH SỬ", show_solver_status=True)
        st.info("Kịch bản này sử dụng thời gian thực tế BTS để tái hiện lịch sử, chưa có dự báo ML cho các chuyến năm 2026.")
        movements = scenario_service.load_scenario_movements(active_scenario_id)
        st.dataframe(pd.DataFrame(movements)[[
            "direction", "carrier", "flight_number", "origin", "destination", "tail_number",
            "scheduled_event_local", "actual_event_local", "actual_delay_min", "turn_id",
        ]], hide_index=True, width="stretch")
        st.download_button(
            "Tải 1.500 lượt đến–đi (CSV)", pd.DataFrame(movements).to_csv(index=False),
            file_name=f"movements_{active_scenario_id}.csv", mime="text/csv",
        )
        return

    # Render Context Bar
    render_context_bar(
        context=scenario_context,
        solver_status_text="DỰ BÁO HỌC MÁY (ML INFERENCE)",
        is_optimal=False,
    )

    artifact_loader = ArtifactLoader()

    # Load scenario predictions via authoritative ScenarioService (strictly zero-leakage)
    prediction_views = scenario_service.load_scenario_predictions(active_scenario_id)

    # Navigation Tabs
    tab_a, tab_b, tab_c = st.tabs([
        "📊 Tab A: Dự báo Trễ Chuyến bay (Dual-Core ML)",
        "🔄 Tab B: Động lực học Quay vòng (Turn Dynamics)",
        "🔬 Tab C: Giải thích Mô hình TreeSHAP",
    ])

    # --------------------------------------------------------------------------
    # TAB A: Dual-Core Flight Predictions
    # --------------------------------------------------------------------------
    with tab_a:
        render_section_header(
            title="DỰ BÁO ĐỘ TRỄ DUAL-CORE ML (INBOUND & OUTBOUND FORECASTS)",
            subtitle="Kiến trúc hai lõi: Core Inbound (NGBoost Student-t) & Core Outbound (Certified Gradient Boosting). Tuân thủ nghiêm ngặt chính sách Zero-Data Leakage.",
            badge_text="ZERO-LEAKAGE ENFORCED",
            badge_type="success",
        )

        # Filters row
        f_col1, f_col2, f_col3, f_col4 = st.columns([3, 2, 2, 2])
        with f_col1:
            search_query = st.text_input("🔍 Tìm mã chuyến / chặng bay:", placeholder="e.g. LEG_ARR_0001")
        with f_col2:
            direction_filter = st.selectbox(
                "Chiều bay (Direction):",
                ["Tất cả", "Hạ cánh (ARR)", "Cất cánh (DEP)"],
            )
        with f_col3:
            severity_filter = st.selectbox(
                "Mức độ trễ:",
                ["Tất cả", "Sớm/Đúng giờ (<0m)", "Trễ nhẹ (0-15m)", "Trễ vừa (15-30m)", "Trễ nặng (≥30m)"],
            )
        with f_col4:
            sort_order = st.selectbox(
                "Sắp xếp theo:",
                ["Trễ giảm dần", "Trễ tăng dần", "Mã chuyến bay", "Giờ dự kiến"],
            )

        # Filter predictions
        filtered_views = list(prediction_views)
        if search_query:
            filtered_views = [v for v in filtered_views if search_query.upper() in v.flight_id.upper()]

        if direction_filter == "Hạ cánh (ARR)":
            filtered_views = [v for v in filtered_views if v.flight_direction == "ARR"]
        elif direction_filter == "Cất cánh (DEP)":
            filtered_views = [v for v in filtered_views if v.flight_direction == "DEP"]

        if severity_filter == "Sớm/Đúng giờ (<0m)":
            filtered_views = [v for v in filtered_views if v.predicted_arr_delay_min < 0.0]
        elif severity_filter == "Trễ nhẹ (0-15m)":
            filtered_views = [v for v in filtered_views if 0.0 <= v.predicted_arr_delay_min < 15.0]
        elif severity_filter == "Trễ vừa (15-30m)":
            filtered_views = [v for v in filtered_views if 15.0 <= v.predicted_arr_delay_min < 30.0]
        elif severity_filter == "Trễ nặng (≥30m)":
            filtered_views = [v for v in filtered_views if v.predicted_arr_delay_min >= 30.0]

        if sort_order == "Trễ giảm dần":
            filtered_views.sort(key=lambda x: x.predicted_arr_delay_min, reverse=True)
        elif sort_order == "Trễ tăng dần":
            filtered_views.sort(key=lambda x: x.predicted_arr_delay_min)
        elif sort_order == "Mã chuyến bay":
            filtered_views.sort(key=lambda x: x.flight_id)
        elif sort_order == "Giờ dự kiến":
            filtered_views.sort(key=lambda x: x.effective_scheduled_time_min if x.effective_scheduled_time_min is not None else -1)

        t_col1, t_col2 = st.columns([7, 5])

        with t_col1:
            table_data = []
            for v in filtered_views[:60]:
                sched_m = v.effective_scheduled_time_min
                if sched_m is not None:
                    h = (sched_m // 60) % 24
                    m = sched_m % 60
                    day_prefix = "+1d " if sched_m >= 1440 else ""
                    time_str = f"{day_prefix}{h:02d}:{m:02d}"
                else:
                    time_str = "N/A"

                dir_badge = "🛬 ARR" if v.flight_direction == "ARR" else "🛫 DEP"

                prob_str = f"{v.probability_delay_15 * 100:.1f}%" if v.probability_delay_15 is not None else "N/A"
                model_name = v.prediction_model or ("NGBoost-StudentT" if v.flight_direction == "ARR" else "XGBoost-Point")

                table_data.append({
                    "Chuyến bay": v.flight_id,
                    "Chiều": dir_badge,
                    "Hãng": v.carrier,
                    "Giờ theo lịch": time_str,
                    "Trễ dự báo (min)": f"{v.predicted_arr_delay_min:+.2f}",
                    "P(Trễ ≥ 15m)": prob_str,
                    "Mô hình": model_name,
                })

            if table_data:
                st.dataframe(pd.DataFrame(table_data), width="stretch", height=350)
            else:
                st.info("Không tìm thấy chuyến bay phù hợp với bộ lọc hiện tại.")

        with t_col2:
            delays = [v.predicted_arr_delay_min for v in filtered_views] if filtered_views else []
            dist_fig = create_delay_distribution_figure(delays)
            st.plotly_chart(dist_fig, width="stretch")

    # --------------------------------------------------------------------------
    # TAB B: Aircraft Turn Dynamics & Slack Absorption
    # --------------------------------------------------------------------------
    with tab_b:
        render_section_header(
            title="ĐỘNG LỰC HỌC QUAY VÒNG & HẤP THỤ BUFFER (AIRCRAFT TURN DYNAMICS)",
            subtitle="Cơ chế lan truyền và triệt tiêu độ trễ giữa chuyến đến và đi trên cùng tàu bay. Thời gian chiếm dụng [A_pred, T_release) với giãn cách an toàn được cộng một lần duy nhất.",
            badge_text="DUAL-CORE TURNAROUND",
            badge_type="info",
        )

        st.markdown(
            """
            <div class="aeolus-card" style="padding: 12px 16px; margin-bottom: 14px;">
                <div style="font-weight: 600; font-size: 13px; color: #47C5C0;">
                    📐 QUY CHUẨN KHOA HỌC GHÉP CẶP QUAY VÒNG (TURNAROUND FORMULATION P07):
                </div>
                <div style="font-size: 13px; color: #F0F4F8; margin-top: 4px; line-height: 1.6;">
                    • Thời điểm tàu rời cổng: <code>D_gate_out = max(D_pred, A_pred + T_min)</code><br>
                    • Thời điểm giải phóng cổng an toàn: <code>T_release = D_gate_out + Buffer</code> (Buffer chỉ tính 1 lần)<br>
                    • Khoảng chiếm dụng cổng: <code>[A_pred, T_release)</code> | Đệm còn lại: <code>T_slack_remain = max(0, T_sched_slack - d_arr_pred)</code>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Load authoritative turns
        turns = scenario_service.load_scenario_turns(active_scenario_id)

        if not turns:
            render_empty_state(
                title="Kịch bản hiện tại chưa ghép cặp lượt bay (Unpaired Scenario)",
                message="Các chuyến bay trong kịch bản này là các lượt bay độc lập chưa gán số hiệu đuôi tàu bay (Tail Number). Để quan sát cơ chế quay vòng và hấp thụ độ trễ, vui lòng chọn kịch bản: Atlanta Dual-Core Turnaround (SCEN_P07_DUAL_CORE_30).",
                icon="🔄",
                action_label="Chọn kịch bản SCEN_P07_DUAL_CORE_30 trên thanh Context Bar hoặc Sidebar",
            )
        else:
            turn_options = {t.turn_id: t for t in turns}
            selected_turn_id = st.selectbox(
                "Chọn cặp quay vòng tàu bay xác thực:",
                options=list(turn_options.keys()),
                format_func=lambda x: f"{x} ({turn_options[x].inbound_flight_id} ➔ {turn_options[x].outbound_flight_id} • {turn_options[x].tail_number} • {turn_options[x].aircraft_type})",
            )
            current_turn = turn_options[selected_turn_id]

            turn_fig = create_turn_dynamics_figure(current_turn)
            st.plotly_chart(turn_fig, width="stretch")

            # Deconstructed Metrics
            kpi_c1, kpi_c2, kpi_c3, kpi_c4, kpi_c5 = st.columns(5)
            with kpi_c1:
                render_kpi_card(
                    title="CỬA SỔ QUAY VÒNG",
                    value=f"{current_turn.sched_turn_window_min} min",
                    subtitle=f"Tối thiểu T_min: {current_turn.min_turn_time_min}m",
                    badge_text="LỊCH GỐC",
                    badge_type="info",
                )
            with kpi_c2:
                render_kpi_card(
                    title="ĐỆM SLACK KHẢ DỤNG",
                    value=f"{current_turn.sched_slack_min} min",
                    subtitle="Đệm hấp thụ danh định",
                    badge_text="BAN ĐẦU",
                    badge_type="info",
                )
            with kpi_c3:
                render_kpi_card(
                    title="SLACK ĐÃ HẤP THỤ",
                    value=f"{current_turn.inbound_delay_absorbed_min:.1f} min",
                    subtitle=f"Từ trễ {current_turn.inbound_flight_id}",
                    badge_text="HẤP THỤ",
                    badge_type="warning" if current_turn.inbound_delay_absorbed_min > 0 else "info",
                )
            with kpi_c4:
                is_tight = current_turn.remaining_slack_min < 10.0
                render_kpi_card(
                    title="SLACK CÒN LẠI",
                    value=f"{current_turn.remaining_slack_min:.1f} min",
                    subtitle="Dự phòng phát sinh",
                    badge_text="[RỦI RO CAO]" if is_tight else "[AN TOÀN]",
                    badge_type="error" if is_tight else "success",
                )
            with kpi_c5:
                occ_duration = int(current_turn.gate_occupancy_end_min - current_turn.gate_occupancy_start_min)
                has_prop = current_turn.propagated_outbound_delay_min > 0
                render_kpi_card(
                    title="THỜI LƯỢNG CHIẾM CỔNG",
                    value=f"{occ_duration} min",
                    subtitle=f"Đã gồm {current_turn.buffer_min}m Buffer",
                    badge_text="[TRỄ DÂY CHUYỀN]" if has_prop else "[AN TOÀN GIẢI PHÓNG]",
                    badge_type="error" if has_prop else "success",
                )

    # --------------------------------------------------------------------------
    # TAB C: Model Explainability (TreeSHAP)
    # --------------------------------------------------------------------------
    with tab_c:
        render_section_header(
            title="GIẢI THÍCH MÔ HÌNH HỌC MÁY BẰNG TREESHAP (EXPLAINABLE ML)",
            subtitle="Áp dụng lý thuyết trò chơi hợp tác Shapley để bóc tách chính xác đóng góp của từng đặc trưng vào dự báo độ trễ. Đảm bảo tính cộng tính địa phương (Local Accuracy).",
            badge_text="SHAPLEY ADDITIVE EXPLANATIONS",
            badge_type="info",
        )

        shap_c1, shap_c2 = st.columns([6, 6])

        with shap_c1:
            try:
                importance_df = artifact_loader.load_shap_global_importance()
            except Exception:
                importance_df = pd.DataFrame()

            global_shap_fig = create_shap_global_figure(importance_df, top_n=8)
            st.plotly_chart(global_shap_fig, width="stretch")

        with shap_c2:
            try:
                case_studies = artifact_loader.load_shap_case_studies()
            except Exception:
                case_studies = []

            if case_studies:
                case_options = {
                    f"{c.get('flight_metadata', {}).get('carrier', '')}{c.get('flight_metadata', {}).get('flight_num', '')} ({c.get('case_type', '')})": c
                    for c in case_studies
                }
                selected_case_name = st.selectbox(
                    "Chọn chuyến bay đại diện để phân rã SHAP waterfall:",
                    options=list(case_options.keys()),
                )
                selected_case = case_options[selected_case_name]
                waterfall_fig = create_shap_waterfall_figure(selected_case)
                st.plotly_chart(waterfall_fig, width="stretch")
            else:
                st.info("Chưa tìm thấy dữ liệu case studies SHAP.")

        # Academic Metrics Table in Research Mode
        is_research = st.session_state.get(SessionStateKeys.IS_RESEARCH_MODE, False)
        if is_research:
            st.markdown("---")
            render_section_header(
                title="BẢNG ĐÁNH GIÁ ĐỘ CHÍNH XÁC NGOÀI MẪU (OOF VALIDATION METRICS)",
                subtitle="Đánh giá Out-Of-Fold qua 5-Fold Stratified Cross-Validation trên tập dữ liệu lịch sử BTS.",
                badge_text="RESEARCH MODE ONLY",
                badge_type="warning",
            )
            try:
                metrics_df = artifact_loader.load_regression_metrics()
                st.dataframe(metrics_df, width="stretch")
            except Exception as exc:
                st.warning(f"Không thể tải bảng metrics hồi quy: {exc}")

    # Research Inspector Drawer
    render_research_inspector(
        title="FLIGHT INTELLIGENCE AUDIT — THÔNG SỐ HUẤN LUYỆN & TREESHAP",
        metadata={
            "scenario_id": active_scenario_id,
            "scenario_hash": scenario_context.scenario_hash,
            "provenance": "PRECOMPUTED_PREDICTION",
            "model_family": "NGBoost Student-t + Certified Point XGBoost",
            "version": "stage10_frozen_v1",
        },
        raw_data={
            "scenario_id": active_scenario_id,
            "total_predictions": len(prediction_views),
            "shap_case_studies_count": len(case_studies) if 'case_studies' in locals() else 0,
            "leakage_audit_status": "CERTIFIED_ZERO_LEAKAGE",
        },
    )
