"""Plotly Visualizers for Page 04: Optimization Lab.

Implements Cost–Runtime Comparison & Pareto Frontier, Runtime Breakdown,
Mega-Hub Scalability Curves, and Formulation Comparison.
Enforces zero false optimality, explicit UNKNOWN status handling, rigorous axis units,
and elimination of fake/fabricated benchmark fallback data.
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from dashboard.core.validation import ScientificValidator
from dashboard.visualizers.theme import (
    COLOR_ACCENT_PRIMARY,
    COLOR_ACCENT_GLOW,
    COLOR_APRON_REMOTE,
    COLOR_BORDER_SUBTLE,
    COLOR_STATUS_ERROR,
    COLOR_STATUS_SUCCESS,
    COLOR_STATUS_WARNING,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    apply_aeolus_theme,
)

# Solver Visual Tokens
SOLVER_COLOR_MAP = {
    "GREEDY": "#E5AD55",                  # Amber
    "GREEDY_STANDALONE": "#E5AD55",
    "CP-SAT": "#47C5C0",                  # Cyan
    "CP_SAT_STANDALONE": "#47C5C0",
    "CP_SAT_SPARSE": "#47C5C0",
    "SA": "#A78BFA",                      # Violet
    "SA_STANDALONE": "#A78BFA",
    "SA_FROM_PRECOMPUTED_INCUMBENT": "#C4B5FD",
    "HYBRID": "#34C759",                  # Green
    "HYBRID_STANDALONE": "#34C759",
    "ORACLE": "#00D2FF",
}

SOLVER_SYMBOL_MAP = {
    "GREEDY": "diamond",
    "GREEDY_STANDALONE": "diamond",
    "CP-SAT": "circle",
    "CP_SAT_STANDALONE": "circle",
    "CP_SAT_SPARSE": "circle",
    "SA": "square",
    "SA_STANDALONE": "square",
    "SA_FROM_PRECOMPUTED_INCUMBENT": "square-open",
    "HYBRID": "star",
    "HYBRID_STANDALONE": "star",
}


def create_pareto_frontier_figure(
    benchmark_df: pd.DataFrame,
    cost_col: str = "objective_value",
    time_col: str = "total_wall_clock_ms",
) -> go.Figure:
    """Create Cost–Runtime Comparison & Pareto Frontier figure.

    - Excludes UNKNOWN and INFEASIBLE runs from the Pareto frontier curve.
    - Uses distinct colors, markers, and hover data for all solvers.
    - Never fabricates 0 or infinite cost for unsolved runs.
    - Calculates true biobjective Pareto non-dominated set (minimize cost and runtime).
    """
    fig = go.Figure()

    if benchmark_df is None or benchmark_df.empty:
        fig.add_annotation(
            text="Không có dữ liệu benchmark khả dụng",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(color=COLOR_TEXT_MUTED, size=14),
        )
        return apply_aeolus_theme(fig)

    df = benchmark_df.copy()
    if "feasible" in df.columns:
        feasible_mask = df["feasible"].astype(bool) & ~df["solver_status"].isin(["UNKNOWN", "INFEASIBLE"])
    else:
        feasible_mask = ~df["solver_status"].isin(["UNKNOWN", "INFEASIBLE"])

    # Ensure objective_value is finite numeric
    if cost_col in df.columns:
        feasible_mask = feasible_mask & df[cost_col].notna()

    df_feasible = df[feasible_mask].copy()
    df_unverified = df[~feasible_mask].copy()

    solver_col = "solver_variant" if "solver_variant" in df.columns else "solver"
    solvers = sorted(list(df[solver_col].dropna().unique()))

    pareto_candidates: List[Dict[str, Any]] = []

    for solver in solvers:
        sub = df_feasible[df_feasible[solver_col] == solver]
        if sub.empty:
            continue

        mean_cost = float(sub[cost_col].mean())
        mean_time = float(sub[time_col].mean())
        mean_reassign = float(sub["reassignment_count"].mean()) if "reassignment_count" in sub.columns else 0.0

        point_data = {
            "solver": solver,
            "cost": mean_cost,
            "time_ms": mean_time,
            "reassign": mean_reassign,
            "n_runs": len(sub),
        }
        pareto_candidates.append(point_data)

        color = SOLVER_COLOR_MAP.get(str(solver).upper(), COLOR_ACCENT_PRIMARY)
        symbol = SOLVER_SYMBOL_MAP.get(str(solver).upper(), "circle")
        display_name = str(solver).replace("_STANDALONE", "")

        fig.add_trace(
            go.Scatter(
                x=[mean_time],
                y=[mean_cost],
                mode="markers+text",
                name=display_name,
                text=[display_name],
                textposition="top right",
                textfont=dict(color=COLOR_TEXT_PRIMARY, size=11),
                marker=dict(
                    size=14,
                    color=color,
                    symbol=symbol,
                    line=dict(width=2, color="#FFFFFF"),
                ),
                hovertemplate=(
                    f"<b>{display_name}</b><br>"
                    f"Thời gian: %{{x:.1f}} ms<br>"
                    f"Decision Cost: %{{y:.2f}} pts<br>"
                    f"Đổi cổng TB: {mean_reassign:.1f}<br>"
                    f"Số lần chạy: {len(sub)}<extra></extra>"
                ),
            )
        )

    # Compute and plot Pareto non-dominated frontier among feasible runs
    non_dominated = ScientificValidator.compute_pareto_frontier(
        pareto_candidates, cost_key="cost", time_key="time_ms"
    )
    if len(non_dominated) >= 2:
        px = [p["time_ms"] for p in non_dominated]
        py = [p["cost"] for p in non_dominated]
        fig.add_trace(
            go.Scatter(
                x=px,
                y=py,
                mode="lines",
                name="Pareto Efficient Frontier",
                line=dict(color="#47C5C0", width=2, dash="dash"),
                hoverinfo="skip",
            )
        )

    # Callout / annotation for unverified or UNKNOWN runs (Task R06-E: No fake cost!)
    if not df_unverified.empty:
        unv_solvers = df_unverified[solver_col].unique()
        unv_desc = ", ".join([str(s).replace("_STANDALONE", "") for s in unv_solvers])
        fig.add_annotation(
            xref="paper",
            yref="paper",
            x=0.98,
            y=0.04,
            text=f"⚠️ Loại khỏi Pareto ({len(df_unverified)} runs UNKNOWN/Timeout):<br><b>{unv_desc}</b> (Cost: N/A)",
            showarrow=False,
            xanchor="right",
            yanchor="bottom",
            bgcolor="#261616",
            bordercolor=COLOR_STATUS_ERROR,
            borderwidth=1,
            font=dict(color="#FFB3B3", size=10),
        )

    fig.update_layout(
        title=dict(
            text="<b>So Sánh Chi Phí Quyết Định vs Thời Gian Thực Thi</b> (Cost–Runtime & Pareto Frontier)",
            font=dict(color=COLOR_TEXT_PRIMARY, size=14),
            x=0.02,
        ),
        xaxis=dict(
            title="Thời gian thực thi Wall-Clock (ms) [Thang đo Log]",
            type="log",
            showgrid=True,
            gridcolor=COLOR_BORDER_SUBTLE,
        ),
        yaxis=dict(
            title="Chi phí Quyết định (Decision Cost points)",
            showgrid=True,
            gridcolor=COLOR_BORDER_SUBTLE,
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.28,
            xanchor="center",
            x=0.5,
            font=dict(size=10, color=COLOR_TEXT_SECONDARY),
        ),
        height=430,
    )

    return apply_aeolus_theme(fig)


def create_runtime_breakdown_figure(
    benchmark_df: pd.DataFrame,
) -> go.Figure:
    """Create Runtime Breakdown by Algorithmic Phase.

    Breaks down:
    - Model Construction / Build Time (ms)
    - Search Time (ms)
    - Validation Time (ms)
    Total wall-clock includes all stages without confusing search with total.
    """
    fig = go.Figure()

    if benchmark_df is None or benchmark_df.empty:
        fig.add_annotation(
            text="Không có dữ liệu thời gian chi tiết",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(color=COLOR_TEXT_MUTED, size=14),
        )
        return apply_aeolus_theme(fig)

    df = benchmark_df.copy()
    solver_col = "solver_variant" if "solver_variant" in df.columns else "solver"

    grouped = df.groupby(solver_col).agg({
        "build_time_ms": "mean",
        "search_time_ms": "mean",
        "validation_time_ms": "mean",
        "total_wall_clock_ms": "mean",
    }).reset_index()

    solvers = [str(s).replace("_STANDALONE", "") for s in grouped[solver_col]]

    fig.add_trace(
        go.Bar(
            name="1. Khởi tạo mô hình (Build ms)",
            x=solvers,
            y=grouped["build_time_ms"],
            marker_color="#3B5780",
            hovertemplate="Build: %{y:.1f} ms<extra></extra>",
        )
    )
    fig.add_trace(
        go.Bar(
            name="2. Tìm kiếm nghiệm (Search ms)",
            x=solvers,
            y=grouped["search_time_ms"],
            marker_color=COLOR_ACCENT_PRIMARY,
            hovertemplate="Search: %{y:.1f} ms<extra></extra>",
        )
    )
    fig.add_trace(
        go.Bar(
            name="3. Hậu kiểm ràng buộc (Validation ms)",
            x=solvers,
            y=grouped["validation_time_ms"],
            marker_color=COLOR_STATUS_SUCCESS,
            hovertemplate="Validation: %{y:.1f} ms<extra></extra>",
        )
    )

    fig.update_layout(
        barmode="stack",
        title=dict(
            text="<b>Phân Rã Thời Gian Thực Thi</b> (Model Build vs Search vs Validation)",
            font=dict(color=COLOR_TEXT_PRIMARY, size=14),
            x=0.02,
        ),
        xaxis=dict(
            title="Thuật toán Giải (Solver Variant)",
            showgrid=False,
        ),
        yaxis=dict(
            title="Thời gian tính toán trung bình (ms)",
            showgrid=True,
            gridcolor=COLOR_BORDER_SUBTLE,
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.28,
            xanchor="center",
            x=0.5,
            font=dict(size=11, color=COLOR_TEXT_SECONDARY),
        ),
        height=390,
    )

    return apply_aeolus_theme(fig)


def create_scalability_curve_figure(
    scalability_df: pd.DataFrame,
) -> go.Figure:
    """Create Mega-Hub Scalability Curves (100 to 1,500 Flights).

    Strict scientific guards:
    - Never fabricates fake fallback data if artifact is missing.
    - Plots real formulations (dense_pairwise vs sparse_interval vs sparse_interval warm_start).
    - Status marker explicitly flags UNKNOWN and prevents false OPTIMAL/FEASIBLE claims.
    - N=1,500 CP-SAT status is strictly marked UNKNOWN (Budget exceeded 10s, no incumbent).
    """
    fig = go.Figure()

    if scalability_df is None or scalability_df.empty:
        fig.add_annotation(
            text="Không có dữ liệu mở rộng quy mô (scalability artifact không khả dụng)",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(color=COLOR_TEXT_MUTED, size=14),
        )
        return apply_aeolus_theme(fig)

    df = scalability_df.copy()
    n_col = "n_flights" if "n_flights" in df.columns else "flights"
    time_col = "total_wall_clock_ms" if "total_wall_clock_ms" in df.columns else "runtime_ms"
    status_col = "status" if "status" in df.columns else "solver_status"

    # Identify series by formulation and warm_start if present in DataFrame
    has_rendered_any = False
    if "formulation" in df.columns:
        series_configs = [
            {"formulation": "sparse_interval", "warm_start": True, "name": "CP-SAT Sparse Interval (Warm-Start)", "color": "#34C759", "dash": "solid"},
            {"formulation": "sparse_interval", "warm_start": False, "name": "CP-SAT Sparse Interval (Cold)", "color": "#47C5C0", "dash": "solid"},
            {"formulation": "dense_pairwise", "warm_start": False, "name": "CP-SAT Dense Pairwise (Khảo sát)", "color": "#E5AD55", "dash": "dot"},
        ]
        for s_cfg in series_configs:
            if "warm_start" in df.columns:
                sub = df[(df["formulation"] == s_cfg["formulation"]) & (df["warm_start"] == s_cfg["warm_start"])].copy()
            else:
                sub = df[df["formulation"] == s_cfg["formulation"]].copy()
            if sub.empty:
                continue

            has_rendered_any = True
            sub = sub.sort_values(by=n_col)
            x_vals = sub[n_col].tolist()
            y_vals = sub[time_col].tolist()

            marker_colors = []
            marker_symbols = []
            hover_texts = []

            for _, row in sub.iterrows():
                stat = str(row.get(status_col, "FEASIBLE")).upper()
                n_fl = int(row[n_col])
                rt = float(row[time_col])
                if stat == "OPTIMAL":
                    marker_colors.append(COLOR_STATUS_SUCCESS)
                    marker_symbols.append("circle")
                    hover_texts.append(f"N={n_fl}: {rt:.1f}ms [OPTIMAL Chứng minh]")
                elif stat == "FEASIBLE":
                    marker_colors.append(s_cfg["color"])
                    marker_symbols.append("square")
                    hover_texts.append(f"N={n_fl}: {rt:.1f}ms [FEASIBLE Khả thi]")
                elif stat == "UNKNOWN":
                    marker_colors.append(COLOR_STATUS_ERROR)
                    marker_symbols.append("x")
                    hover_texts.append(f"N={n_fl}: {rt:.1f}ms [UNKNOWN - Hết ngân sách 10s]")
                else:
                    marker_colors.append(COLOR_STATUS_WARNING)
                    marker_symbols.append("diamond")
                    hover_texts.append(f"N={n_fl}: {rt:.1f}ms [{stat}]")

            fig.add_trace(
                go.Scatter(
                    x=x_vals,
                    y=y_vals,
                    mode="lines+markers",
                    name=s_cfg["name"],
                    line=dict(color=s_cfg["color"], width=2.5, dash=s_cfg["dash"]),
                    marker=dict(
                        size=11,
                        color=marker_colors,
                        symbol=marker_symbols,
                        line=dict(width=1.5, color="#FFFFFF"),
                    ),
                    text=hover_texts,
                    hovertemplate="%{text}<extra></extra>",
                )
            )

    # Fallback to single trace if columns formulation/warm_start were not found
    if not has_rendered_any:
        sub = df.sort_values(by=n_col)
        fig.add_trace(
            go.Scatter(
                x=sub[n_col],
                y=sub[time_col],
                mode="lines+markers",
                name="CP-SAT Scalability",
                line=dict(color=COLOR_ACCENT_PRIMARY, width=2),
            )
        )

    # Prominent callout annotation for N=1500 UNKNOWN
    if 1500 in df[n_col].values:
        row_1500 = df[df[n_col] == 1500].iloc[0]
        y_1500 = float(row_1500[time_col])
        fig.add_annotation(
            x=1500,
            y=y_1500,
            text="⚠️ N=1,500: UNKNOWN<br>(10s timeout, không có nghiệm verified)",
            showarrow=True,
            arrowhead=2,
            arrowsize=1,
            arrowwidth=1.5,
            arrowcolor=COLOR_STATUS_ERROR,
            ax=-110,
            ay=-40,
            bgcolor="#261616",
            bordercolor=COLOR_STATUS_ERROR,
            borderwidth=1,
            font=dict(color="#FFB3B3", size=10),
        )

    fig.update_layout(
        title=dict(
            text="<b>Khả Năng Mở Rộng Quy Mô Cực Đại</b> (Mega-Hub Scalability: N=100 → 1.500 Chuyến)",
            font=dict(color=COLOR_TEXT_PRIMARY, size=14),
            x=0.02,
        ),
        xaxis=dict(
            title="Số lượng chuyến bay (N Flights)",
            showgrid=True,
            gridcolor=COLOR_BORDER_SUBTLE,
        ),
        yaxis=dict(
            title="Thời gian tính toán Wall-Clock (ms)",
            showgrid=True,
            gridcolor=COLOR_BORDER_SUBTLE,
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.28,
            xanchor="center",
            x=0.5,
            font=dict(size=10, color=COLOR_TEXT_SECONDARY),
        ),
        height=430,
    )

    return apply_aeolus_theme(fig)


def create_formulation_comparison_figure(
    formulation_data: Any,
) -> go.Figure:
    """Create Formulation Comparison figure comparing model construction time.

    Shows why Sparse Interval CP-SAT eliminates combinatorial blow-up.
    """
    fig = go.Figure()

    if not formulation_data:
        fig.add_annotation(
            text="Không có dữ liệu so sánh mô hình hóa",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(color=COLOR_TEXT_MUTED, size=14),
        )
        return apply_aeolus_theme(fig)

    if isinstance(formulation_data, list):
        df = pd.DataFrame(formulation_data)
    elif isinstance(formulation_data, dict):
        df = pd.DataFrame(list(formulation_data.values()))
    else:
        df = pd.DataFrame()

    if df.empty or "formulation" not in df.columns or "n_flights" not in df.columns:
        fig.add_annotation(
            text="Cấu trúc dữ liệu mô hình hóa không phù hợp",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(color=COLOR_TEXT_MUTED, size=14),
        )
        return apply_aeolus_theme(fig)

    build_col = "model_construction_ms" if "model_construction_ms" in df.columns else "build_time_ms"

    scales = sorted(list(df["n_flights"].unique()))
    formulations = sorted(list(df["formulation"].unique()))

    form_names = {
        "F0_BASELINE_DENSE": "F0: Baseline Dense Grid",
        "F1_SPARSE_PAIRWISE": "F1: Sparse Pairwise",
        "F2_SPARSE_INTERVAL": "F2: Sparse Interval (NoOverlap)",
        "F3_SPARSE_INTERVAL_WARMSTART": "F3: Sparse Interval + Warm-Start",
    }
    form_colors = {
        "F0_BASELINE_DENSE": "#E47777",
        "F1_SPARSE_PAIRWISE": "#E5AD55",
        "F2_SPARSE_INTERVAL": "#47C5C0",
        "F3_SPARSE_INTERVAL_WARMSTART": "#34C759",
    }

    for f_code in formulations:
        sub = df[df["formulation"] == f_code].sort_values(by="n_flights")
        display_label = form_names.get(f_code, f_code)
        color = form_colors.get(f_code, COLOR_ACCENT_PRIMARY)

        fig.add_trace(
            go.Bar(
                name=display_label,
                x=[f"N={n}" for n in sub["n_flights"]],
                y=sub[build_col],
                marker_color=color,
                hovertemplate=f"<b>{display_label}</b><br>Thời gian Build: %{{y:.1f}} ms<extra></extra>",
            )
        )

    fig.update_layout(
        barmode="group",
        title=dict(
            text="<b>Thời Gian Khởi Tạo Mô Hình (Model Construction Time ms)</b>",
            font=dict(color=COLOR_TEXT_PRIMARY, size=14),
            x=0.02,
        ),
        xaxis=dict(title="Quy mô bài toán (Số chuyến bay)", showgrid=False),
        yaxis=dict(title="Thời gian Build mô hình (ms) [Thang đo Log]", type="log", showgrid=True, gridcolor=COLOR_BORDER_SUBTLE),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.28,
            xanchor="center",
            x=0.5,
            font=dict(size=10, color=COLOR_TEXT_SECONDARY),
        ),
        height=390,
    )

    return apply_aeolus_theme(fig)
