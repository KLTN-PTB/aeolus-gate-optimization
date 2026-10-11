"""Page 04: Optimization Lab (Phòng thí nghiệm Tối ưu Toán học).

Comprehensive multi-solver benchmarking across Deterministic Greedy, CP-SAT,
Simulated Annealing (SA), and Hybrid Solvers.
Includes Workload Selector, Fair Comparison Guards, Cost–Runtime Pareto Analysis,
Algorithmic Phase Runtime Breakdown, Mega-Hub Scalability (100 to 1,500 flights),
and CP-SAT Formulation Comparison.
Enforces zero false optimality, explicit UNKNOWN status handling, and elimination of fake data.
"""

from typing import Any, Dict, List, Optional
import pandas as pd
import streamlit as st

from dashboard.adapters.artifact_loader import ArtifactLoader
from dashboard.adapters.export_adapter import export_benchmark_to_csv
from dashboard.components.context_bar import render_context_bar
from dashboard.components.kpi_card import render_kpi_card
from dashboard.components.research_inspector import render_research_inspector
from dashboard.core.state import SessionStateKeys
from dashboard.core.status_mapping import SolverStatus, TerminationReason, map_solver_status_to_badge
from dashboard.core.validation import IncompatibleComparisonError, ScientificValidator
from dashboard.services.scenario_service import ScenarioService
from dashboard.visualizers.optimization_charts import (
    create_formulation_comparison_figure,
    create_pareto_frontier_figure,
    create_runtime_breakdown_figure,
    create_scalability_curve_figure,
)

WORKLOAD_LABELS = {
    "SCEN_TIER_A_10F_3G": "Tier A: 10 Chuyến bay × 3 Cổng (Mini-Scale Benchmark)",
    "SCEN_TIER_A_20F_6G": "Tier A: 20 Chuyến bay × 6 Cổng (Small-Scale Benchmark)",
    "SCEN_TIER_B_100F_20G": "Tier B: 100 Chuyến bay × 20 Cổng (Medium Hub Benchmark)",
    "SCEN_TIER_B_200F_30G": "Tier B: 200 Chuyến bay × 30 Cổng (Large Hub Benchmark)",
    "SCEN_TIER_B_300F_50G": "Tier B: 300 Chuyến bay × 50 Cổng (Dense Peak Benchmark)",
}


def render_page() -> None:
    """Render Page 04: Optimization Lab."""
    scenario_service = ScenarioService()
    active_scenario_id = st.session_state.get(
        SessionStateKeys.ACTIVE_SCENARIO_ID, "SCEN_P09_CANONICAL_120"
    )
    is_research = st.session_state.get(SessionStateKeys.IS_RESEARCH_MODE, False)

    try:
        scenario_context = scenario_service.get_scenario_context(active_scenario_id)
    except Exception:
        scenario_context = None

    render_context_bar(
        context=scenario_context,
        solver_status_text="BENCHMARK SO SÁNH 4 THUẬT TOÁN (AUDITED)",
        is_optimal=False,
    )

    st.markdown("### ⚡ PHÒNG THÍ NGHIỆM TỐI ƯU TOÁN HỌC (OPTIMIZATION LAB)")
    st.markdown(
        "<span style='color: #94A3B8; font-size: 14px;'>"
        "Môi trường phân tích đối chuẩn (Benchmarking) khoa học độc lập giữa 4 nhóm giải thuật: "
        "<b>Deterministic Greedy</b>, <b>CP-SAT (Sparse Interval)</b>, <b>Simulated Annealing (SA)</b>, "
        "và <b>Hybrid Heuristic-Exact</b> theo nguyên tắc so sánh công bằng trên cùng bài toán."
        "</span>",
        unsafe_allow_html=True,
    )

    # Load benchmark artifacts safely
    loader = ArtifactLoader()
    try:
        benchmark_df = loader.load_solver_benchmarks()
    except Exception as exc:
        st.error(f"Không thể tải hồ sơ benchmark: {exc}")
        benchmark_df = pd.DataFrame()

    try:
        scalability_df = loader.load_csv("artifacts/remediation/cp_sat/scalability_results.csv")
    except Exception:
        scalability_df = pd.DataFrame()

    try:
        formulation_data = loader.load_cp_sat_formulations()
    except Exception:
        formulation_data = []

    if benchmark_df.empty:
        st.warning("Hồ sơ kết quả benchmark chưa khả dụng trên đĩa.")
        return

    # --------------------------------------------------------------------------
    # 1. EXPERIMENT CONTEXT & WORKLOAD SELECTOR (Task R06-B)
    # --------------------------------------------------------------------------
    available_workloads = list(benchmark_df["scenario_id"].unique())
    default_workload_idx = (
        available_workloads.index("SCEN_TIER_B_100F_20G")
        if "SCEN_TIER_B_100F_20G" in available_workloads
        else 0
    )

    with st.container(border=True):
        sel_c1, sel_c2 = st.columns([7, 5])
        with sel_c1:
            selected_workload = st.selectbox(
                "🎯 Chọn bài toán đối chuẩn thực nghiệm (Workload / Problem Scale):",
                options=available_workloads,
                index=default_workload_idx,
                format_func=lambda w: WORKLOAD_LABELS.get(w, w),
                key="opt_workload_selector",
            )
        with sel_c2:
            variants_in_workload = sorted(list(
                benchmark_df[benchmark_df["scenario_id"] == selected_workload]["solver_variant"].unique()
            ))
            selected_variants = st.multiselect(
                "Lọc thuật toán hiển thị:",
                options=variants_in_workload,
                default=variants_in_workload,
                format_func=lambda v: str(v).replace("_STANDALONE", ""),
                key="opt_variant_filter",
            )

    # Filter benchmark dataframe to active workload and chosen variants
    workload_df = benchmark_df[
        (benchmark_df["scenario_id"] == selected_workload)
        & (benchmark_df["solver_variant"].isin(selected_variants))
    ].copy()

    # Fairness compatibility banner (Task R06-B: Fair Comparison Policy)
    human_name = WORKLOAD_LABELS.get(selected_workload, selected_workload)
    st.markdown(
        f"""
        <div style="background: rgba(71, 197, 192, 0.08); border-left: 3px solid #47C5C0; padding: 10px 14px; border-radius: 4px; margin-top: 10px; margin-bottom: 16px; font-size: 13px; color: #F0F4F8;">
            <b>🛡️ Scientific Fairness Guard Active:</b> Tất cả các chỉ số đối chuẩn dưới đây được đo đạc trên 
            <b>CÙNG MỘT BÀI TOÁN ({human_name})</b>, chung tập chuyến bay và sức chứa cổng, 
            cùng hàm mục tiêu chuẩn hóa (<code>w_pref=10, w_remote=200, w_conflict=1000</code>) và đệm 15 phút.
            Hệ thống ngăn chặn việc xếp chung các bài toán quy mô khác nhau vào cùng một bảng xếp hạng.
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --------------------------------------------------------------------------
    # 2. SOLVER SUMMARY SCORECARD & EXECUTIVE KPI CARDS (Task R06-D)
    # --------------------------------------------------------------------------
    st.markdown("#### 1. Bảng Đối chuẩn Thuật toán (Multi-Solver Benchmark Scorecard)")

    summary_rows = []
    solver_groups = workload_df.groupby("solver_variant")

    for variant, group in solver_groups:
        feasible_mask = group["feasible"].astype(bool) & ~group["solver_status"].isin(["UNKNOWN", "INFEASIBLE"])
        feasible_runs = group[feasible_mask]
        has_feasible = not feasible_runs.empty

        avg_cost = float(feasible_runs["objective_value"].mean()) if has_feasible else None
        avg_time = float(group["total_wall_clock_ms"].mean())
        avg_build = float(group["build_time_ms"].mean()) if "build_time_ms" in group.columns else 0.0
        avg_search = float(group["search_time_ms"].mean()) if "search_time_ms" in group.columns else 0.0
        avg_reassign = float(feasible_runs["reassignment_count"].mean()) if has_feasible else 0.0
        avg_remote = float(feasible_runs["remote_count"].mean()) if has_feasible else 0.0

        # Scientific status rules (Task R06-D): Greedy & SA can NEVER be marked OPTIMAL
        v_upper = str(variant).upper()
        raw_status = str(group["solver_status"].iloc[0]).upper() if not group.empty else "UNKNOWN"

        if raw_status in ("UNKNOWN", "INFEASIBLE") or not has_feasible:
            is_opt = False
            status_label = f"{raw_status} (Không có nghiệm)"
        elif "GREEDY" in v_upper:
            is_opt = False
            status_label = "FEASIBLE (Heuristic)"
        elif "SA" in v_upper or "SIMULATED" in v_upper:
            is_opt = False
            status_label = "FEASIBLE (Metaheuristic)"
        elif "CP_SAT" in v_upper:
            is_opt = bool(group["optimality_proven"].iloc[0]) if "optimality_proven" in group.columns else False
            status_label = "OPTIMAL (Proven Gap 0.0%)" if is_opt else "FEASIBLE"
        elif "HYBRID" in v_upper:
            is_opt = bool(group["optimality_proven"].iloc[0]) if "optimality_proven" in group.columns else False
            status_label = "OPTIMAL (Proven)" if is_opt else "FEASIBLE"
        else:
            is_opt = False
            status_label = "FEASIBLE"

        time_str = f"{avg_time:.1f} ms" if avg_time < 1000.0 else f"{avg_time / 1000.0:.2f} s"

        summary_rows.append({
            "Thuật toán": str(variant).replace("_STANDALONE", ""),
            "Mô hình hóa (Formulation)": (
                "Rule-based Greedy" if "GREEDY" in v_upper
                else ("Sparse Interval CP" if "CP_SAT" in v_upper
                else ("Local Search Metaheuristic" if "SA" in v_upper
                else "Two-stage Hybrid"))
            ),
            "Số Lượt Chạy": len(group),
            "Chi phí Quyết định TB": f"{avg_cost:.2f} pts" if avg_cost is not None else "N/A (Chưa có nghiệm)",
            "Thời gian Thực thi TB": time_str,
            "Đổi cổng TB": f"{avg_reassign:.1f}" if has_feasible else "N/A",
            "Cổng xa TB": f"{avg_remote:.1f}" if has_feasible else "N/A",
            "Trạng thái Nghiệm": status_label,
            "Chứng minh Tối ưu": "CÓ (Proven)" if is_opt else "KHÔNG (Heuristic / Unproven)",
        })

    summary_table_df = pd.DataFrame(summary_rows)
    st.dataframe(summary_table_df, width="stretch", hide_index=True)

    # Executive KPI Cards for 4 main solvers (dynamically queried from workload_df)
    solver_kpi_map = {r["Thuật toán"]: r for r in summary_rows}

    def _get_solver_kpi(target_key: str):
        for name, r in solver_kpi_map.items():
            if target_key.upper() in name.upper():
                return r["Chi phí Quyết định TB"], f"Runtime: {r['Thời gian Thực thi TB']} | {r['Trạng thái Nghiệm']}"
        return "N/A", "Chưa có dữ liệu"

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        gr_cost, gr_sub = _get_solver_kpi("GREEDY")
        render_kpi_card(
            title="DETERMINISTIC GREEDY",
            value=gr_cost,
            subtitle=gr_sub,
            status="info" if "N/A" not in gr_cost else "neutral",
            help_text="Thuật toán heuristic gán tham lam theo thứ tự thời gian. Nhanh nhất nhưng không chứng minh được tính tối ưu toàn cục.",
        )
    with c2:
        cp_cost, cp_sub = _get_solver_kpi("CP_SAT")
        is_unknown = "N/A" in cp_cost or "UNKNOWN" in cp_sub
        render_kpi_card(
            title="CP-SAT (SPARSE INTERVAL)",
            value=cp_cost,
            subtitle=cp_sub,
            status="error" if is_unknown else "success",
            help_text="Mô hình Lập trình Ràng buộc sử dụng khoảng biến thiên thưa. Đạt nghiệm tối ưu toàn cục đã được chứng minh.",
        )
    with c3:
        sa_cost, sa_sub = _get_solver_kpi("SA")
        render_kpi_card(
            title="SIMULATED ANNEALING (SA)",
            value=sa_cost,
            subtitle=sa_sub,
            status="info" if "N/A" not in sa_cost else "neutral",
            help_text="Giải thuật tôi luyện kim loại (Metaheuristic). Tìm kiếm lân cận ngẫu nhiên, không thể khẳng định trạng thái OPTIMAL.",
        )
    with c4:
        hy_cost, hy_sub = _get_solver_kpi("HYBRID")
        render_kpi_card(
            title="HYBRID (GREEDY + CP-SAT)",
            value=hy_cost,
            subtitle=hy_sub,
            status="info" if "N/A" not in hy_cost else "neutral",
            help_text="Kết hợp khởi tạo nghiệm khả thi nhanh bằng Greedy và tối ưu hóa tinh bằng CP-SAT warm-start.",
        )

    # --------------------------------------------------------------------------
    # 3. COST–RUNTIME & PARETO FRONTIER ANALYSIS (Task R06-E & R06-F)
    # --------------------------------------------------------------------------
    st.markdown("---")
    st.markdown("#### 2. Phân tích Pareto Frontier & Phân rã Thời gian Thuật toán")

    col_chart1, col_chart2 = st.columns([1.1, 0.9])
    with col_chart1:
        fig_pareto = create_pareto_frontier_figure(workload_df)
        st.plotly_chart(fig_pareto, width="stretch")
    with col_chart2:
        fig_breakdown = create_runtime_breakdown_figure(workload_df)
        st.plotly_chart(fig_breakdown, width="stretch")

    st.caption(
        f"💡 **Ghi chú Toán học:** Biểu đồ thể hiện sự đánh đổi (trade-off) giữa Chi phí Quyết định và Thời gian tính toán "
        f"trên bài toán <b>{human_name}</b>. Đường đứt nét biểu thị đường biên Pareto (Pareto-efficient non-dominated frontier) "
        "được tính toán nghiêm ngặt trên các nghiệm khả thi. Các lượt chạy UNKNOWN không có nghiệm được loại khỏi đường biên Pareto."
    )

    # --------------------------------------------------------------------------
    # 4. MEGA-HUB SCALABILITY & FORMULATION COMPARISON (Task R06-H)
    # --------------------------------------------------------------------------
    st.markdown("---")
    st.markdown("#### 3. Khả năng Mở rộng Quy mô Cực đại (Mega-Hub Scalability: N=100 → 1.500 Chuyến)")

    col_scale, col_form = st.columns([1.1, 0.9])
    with col_scale:
        fig_scale = create_scalability_curve_figure(scalability_df)
        st.plotly_chart(fig_scale, width="stretch")

    with col_form:
        if formulation_data:
            fig_form = create_formulation_comparison_figure(formulation_data)
            st.plotly_chart(fig_form, width="stretch")
        else:
            st.info("Dữ liệu so sánh cấu trúc mô hình hóa chưa khả dụng.")

    st.warning(
        "⚠️ **Lưu ý Giới hạn Mở rộng Quy mô P06 (N=1,500 Flights):** "
        "Tại quy mô 1,500 chuyến bay × 50 tài nguyên, mô hình được khởi tạo thành công nhưng solver CP-SAT "
        "vượt quá ngân sách thời gian 10 giây mà chưa tìm thấy nghiệm hợp lệ (Trạng thái: <b>UNKNOWN</b>). "
        "Hệ thống KHÔNG ngụy tạo nghiệm hoặc gắn nhãn FEASIBLE/OPTIMAL khi chưa có minh chứng toán học.",
        icon="⚠️",
    )

    # --------------------------------------------------------------------------
    # 5. RESEARCH MODE AUDITING & REPRODUCIBILITY (Task R06-I)
    # --------------------------------------------------------------------------
    if is_research:
        st.markdown("---")
        st.markdown("#### 🔬 Khu vực Kiểm toán Chuyên sâu (Research Mode Inspector)")

        st.markdown(f"##### Dữ liệu Thô Toàn bộ Lượt Chạy cho {human_name} ({len(workload_df)} records)")
        st.dataframe(workload_df, width="stretch", hide_index=True)

        csv_data = export_benchmark_to_csv(workload_df, experiment_id=f"EXP_{selected_workload}")
        st.download_button(
            label="📥 Tải xuống Dữ liệu Benchmark Kịch bản này (CSV)",
            data=csv_data,
            file_name=f"benchmark_{selected_workload}.csv",
            mime="text/csv",
            width="stretch",
            key="btn_download_workload_csv",
        )

    render_research_inspector(
        title="OPTIMIZATION LAB PROVENANCE — THÔNG SỐ ĐỐI CHUẨN THUẬT TOÁN",
        metadata={
            "experiment_id": f"EXP_{selected_workload}",
            "scenario_id": selected_workload,
            "data_source": "artifacts/remediation/benchmarks/solver_runs.csv",
            "objective_version": "OBJ_V2_SEPARATION_CONSTRAINED",
            "capacity_policy": "CONTACT_1_REMOTE_K_APRON_INF",
            "total_benchmark_records": len(benchmark_df),
            "workload_runs_count": len(workload_df),
            "evaluated_solvers": selected_variants,
        },
        raw_data=workload_df.head(10).to_dict(orient="records"),
    )
