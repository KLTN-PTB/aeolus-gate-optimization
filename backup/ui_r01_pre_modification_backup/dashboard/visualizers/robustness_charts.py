"""Plotly Visualizers for Page 05: Robustness Lab.

Implements CHART-12 (Cost Distribution Histogram), CHART-13 (Empirical CDF),
CHART-14 (Reassignment & Remote Stand Boxplots), and CHART-15 (Running Mean Convergence Trace).
Enforces distinct Mode A/B/C visual encoding and prominent Non-Deployable Oracle markings.
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
import plotly.graph_objects as go

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

# Robustness Mode Visual Tokens
MODE_COLORS = {
    "MODE_A": "#E47777",        # Alert Red / Coral for Rigid Fixed Plan
    "MODE_B": "#34C759",        # Clearance Green for Reactive Recourse
    "MODE_C": "#00D2FF",        # Runway Blue / Cyan for Non-deployable Oracle
}


def create_mc_cost_distribution_figure(
    fixed_df: pd.DataFrame,
    recourse_df: pd.DataFrame,
    oracle_df: Optional[pd.DataFrame] = None,
    cost_col: str = "objective_value",
) -> go.Figure:
    """Create CHART-12: Monte Carlo Cost Distribution Histogram across Modes.

    Distinguishes:
    - Mode A: Fixed Plan (includes conflict penalties)
    - Mode B: Reactive Recourse (tactical feasible dispatch)
    - Mode C: Oracle Benchmark (NON-DEPLOYABLE theoretical limit)
    """
    fig = go.Figure()

    # Mode A (Fixed Plan)
    if not fixed_df.empty and cost_col in fixed_df.columns:
        costs_a = fixed_df[cost_col].dropna().values
        fig.add_trace(
            go.Histogram(
                x=costs_a,
                name="Mode A: Kế hoạch Cố định (Fixed Plan)",
                marker_color=MODE_COLORS["MODE_A"],
                opacity=0.65,
                nbinsx=40,
                hovertemplate="Chi phí: %{x:.1f} pts<br>Số scenario: %{y}<extra>Mode A</extra>",
            )
        )

    # Mode B (Reactive Recourse)
    if not recourse_df.empty and cost_col in recourse_df.columns:
        costs_b = recourse_df[cost_col].dropna().values
        fig.add_trace(
            go.Histogram(
                x=costs_b,
                name="Mode B: Ứng phó Tức thời (Reactive Recourse)",
                marker_color=MODE_COLORS["MODE_B"],
                opacity=0.75,
                nbinsx=35,
                hovertemplate="Chi phí: %{x:.1f} pts<br>Số scenario: %{y}<extra>Mode B</extra>",
            )
        )

    # Mode C (Oracle) - Optional
    if oracle_df is not None and not oracle_df.empty and cost_col in oracle_df.columns:
        costs_c = oracle_df[cost_col].dropna().values
        fig.add_trace(
            go.Histogram(
                x=costs_c,
                name="Mode C: Tiên tri Lý thuyết [NON-DEPLOYABLE]",
                marker_color=MODE_COLORS["MODE_C"],
                opacity=0.5,
                nbinsx=35,
                hovertemplate="Chi phí: %{x:.1f} pts<br>Số scenario: %{y}<extra>Mode C (Oracle)</extra>",
            )
        )

    fig.update_layout(
        barmode="overlay",
        title=dict(
            text="CHART-12: Phân phối Chi phí Monte Carlo qua 500 Kịch bản Realization",
            font=dict(color=COLOR_TEXT_PRIMARY, size=14),
        ),
        xaxis=dict(
            title="Chi phí Mục tiêu Đánh giá (Cost Points)",
            showgrid=True,
            gridcolor=COLOR_BORDER_SUBTLE,
        ),
        yaxis=dict(
            title="Tần suất Kịch bản (Scenario Count)",
            showgrid=True,
            gridcolor=COLOR_BORDER_SUBTLE,
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.25,
            xanchor="center",
            x=0.5,
            font=dict(size=11, color=COLOR_TEXT_SECONDARY),
        ),
        height=400,
    )

    return apply_aeolus_theme(fig)


def create_mc_ecdf_figure(
    fixed_df: pd.DataFrame,
    recourse_df: pd.DataFrame,
    oracle_df: Optional[pd.DataFrame] = None,
    cost_col: str = "objective_value",
) -> go.Figure:
    """Create CHART-13: Empirical Cumulative Distribution Function (ECDF).

    Quantifies tail risk, showing cumulative probability P(Cost <= x).
    """
    fig = go.Figure()

    def _add_ecdf_trace(df: pd.DataFrame, name: str, color: str, dash: Optional[str] = None):
        if df.empty or cost_col not in df.columns:
            return
        vals = np.sort(df[cost_col].dropna().values)
        if len(vals) == 0:
            return
        probs = np.linspace(0, 1, len(vals))
        fig.add_trace(
            go.Scatter(
                x=vals,
                y=probs,
                mode="lines",
                name=name,
                line=dict(color=color, width=2.5, shape="hv", dash=dash),
                hovertemplate="Chi phí: %{x:.1f} pts<br>Xác suất tích lũy: %{y:.3f}<extra></extra>",
            )
        )

    _add_ecdf_trace(fixed_df, "Mode A: Fixed Plan", MODE_COLORS["MODE_A"], dash="dot")
    _add_ecdf_trace(recourse_df, "Mode B: Reactive Recourse", MODE_COLORS["MODE_B"], dash=None)
    if oracle_df is not None:
        _add_ecdf_trace(oracle_df, "Mode C: Oracle [NON-DEPLOYABLE]", MODE_COLORS["MODE_C"], dash="dash")

    # Reference p95 horizontal line
    fig.add_hline(
        y=0.95,
        line_dash="dash",
        line_color=COLOR_STATUS_WARNING,
        line_width=1,
        annotation_text="P95 Ngưỡng rủi ro đuôi (95%)",
        annotation_position="bottom right",
        annotation_font=dict(size=10, color=COLOR_STATUS_WARNING),
    )

    fig.update_layout(
        title=dict(
            text="CHART-13: Hàm Phân phối Tích lũy Thực nghiệm (ECDF & Tail Risk)",
            font=dict(color=COLOR_TEXT_PRIMARY, size=14),
        ),
        xaxis=dict(
            title="Chi phí Mục tiêu (Cost Points)",
            showgrid=True,
            gridcolor=COLOR_BORDER_SUBTLE,
        ),
        yaxis=dict(
            title="Xác suất Tích lũy P(Chi phí ≤ x)",
            range=[0, 1.05],
            showgrid=True,
            gridcolor=COLOR_BORDER_SUBTLE,
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.25,
            xanchor="center",
            x=0.5,
            font=dict(size=11, color=COLOR_TEXT_SECONDARY),
        ),
        height=400,
    )

    return apply_aeolus_theme(fig)


def create_mc_boxplot_figure(
    recourse_df: pd.DataFrame,
) -> go.Figure:
    """Create CHART-14: Recourse Reassignments and Remote Gate Usage Boxplot."""
    fig = go.Figure()

    if recourse_df.empty:
        fig.add_annotation(
            text="Không có dữ liệu Recourse",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(color=COLOR_TEXT_MUTED, size=14),
        )
        return apply_aeolus_theme(fig)

    if "reassignment_count" in recourse_df.columns:
        fig.add_trace(
            go.Box(
                y=recourse_df["reassignment_count"],
                name="Số lần Đổi cổng (Reassignments)",
                marker_color=COLOR_ACCENT_PRIMARY,
                boxmean="sd",
                hovertemplate="Số lần đổi: %{y}<extra></extra>",
            )
        )

    if "remote_count" in recourse_df.columns:
        fig.add_trace(
            go.Box(
                y=recourse_df["remote_count"],
                name="Sử dụng Bãi đỗ Từ xa (Remote Stands)",
                marker_color=COLOR_APRON_REMOTE,
                boxmean="sd",
                hovertemplate="Số chuyến đỗ xa: %{y}<extra></extra>",
            )
        )

    fig.update_layout(
        title=dict(
            text="CHART-14: Biến động Hành động Điều hành (Đổi Cổng & Sân đỗ Từ xa)",
            font=dict(color=COLOR_TEXT_PRIMARY, size=14),
        ),
        yaxis=dict(
            title="Số lượt chuyến / Chế độ",
            showgrid=True,
            gridcolor=COLOR_BORDER_SUBTLE,
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.2,
            xanchor="center",
            x=0.5,
            font=dict(size=11, color=COLOR_TEXT_SECONDARY),
        ),
        height=380,
    )

    return apply_aeolus_theme(fig)


def create_mc_convergence_figure(
    recourse_df: pd.DataFrame,
    cost_col: str = "objective_value",
) -> go.Figure:
    """Create CHART-15: Monte Carlo Running Mean Convergence Trace with Confidence Band.

    Demonstrates simulation stability:
    - Running mean: mu_n = (1/n) sum_{i=1}^n x_i
    - Standard error: se_n = s_n / sqrt(n)
    - 95% Confidence Band: mu_n +/- 1.96 * se_n
    """
    fig = go.Figure()

    if recourse_df.empty or cost_col not in recourse_df.columns:
        fig.add_annotation(
            text="Không có dữ liệu hội tụ",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(color=COLOR_TEXT_MUTED, size=14),
        )
        return apply_aeolus_theme(fig)

    costs = recourse_df[cost_col].dropna().values
    n_total = len(costs)
    if n_total < 2:
        return apply_aeolus_theme(fig)

    # Compute running statistics
    cum_sum = np.cumsum(costs)
    indices = np.arange(1, n_total + 1)
    running_mean = cum_sum / indices

    # Running sample variance
    # Var(X) = E[X^2] - (E[X])^2
    cum_sq = np.cumsum(costs**2)
    running_var = (cum_sq - (cum_sum**2) / indices) / np.maximum(indices - 1, 1)
    running_var[0] = 0.0
    running_se = np.sqrt(np.maximum(running_var, 0.0)) / np.sqrt(indices)

    ci_upper = running_mean + 1.96 * running_se
    ci_lower = running_mean - 1.96 * running_se

    # 1. Shaded CI band (Upper bound)
    fig.add_trace(
        go.Scatter(
            x=indices,
            y=ci_upper,
            mode="lines",
            line=dict(width=0),
            showlegend=False,
            hoverinfo="skip",
        )
    )

    # 2. Shaded CI band (Lower bound with fill)
    fig.add_trace(
        go.Scatter(
            x=indices,
            y=ci_lower,
            mode="lines",
            line=dict(width=0),
            fill="tonexty",
            fillcolor="rgba(71, 197, 192, 0.18)",
            name="Khoảng tin cậy 95% (±1.96 · MCSE)",
            hoverinfo="skip",
        )
    )

    # 3. Running mean trace
    fig.add_trace(
        go.Scatter(
            x=indices,
            y=running_mean,
            mode="lines",
            line=dict(color=COLOR_ACCENT_PRIMARY, width=2.5),
            name="Kỳ vọng Hội tụ (Running Mean)",
            hovertemplate="Cỡ mẫu n: %{x}<br>Trung bình chạy: %{y:.2f} pts<extra></extra>",
        )
    )

    # Final stabilized mean reference line
    final_mean = float(running_mean[-1])
    fig.add_hline(
        y=final_mean,
        line_dash="dot",
        line_color=COLOR_STATUS_SUCCESS,
        annotation_text=f"Ổn định: {final_mean:.2f} pts",
        annotation_position="bottom right",
        annotation_font=dict(size=10, color=COLOR_STATUS_SUCCESS),
    )

    fig.update_layout(
        title=dict(
            text="CHART-15: Vết Hội tụ Kỳ vọng Monte Carlo (Running Mean & Sai số Chuẩn)",
            font=dict(color=COLOR_TEXT_PRIMARY, size=14),
        ),
        xaxis=dict(
            title="Số lượng Kịch bản Mô phỏng Đã chạy (Sample Size n)",
            showgrid=True,
            gridcolor=COLOR_BORDER_SUBTLE,
        ),
        yaxis=dict(
            title="Kỳ vọng Chi phí Chạy (Running Cost Mean)",
            showgrid=True,
            gridcolor=COLOR_BORDER_SUBTLE,
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.25,
            xanchor="center",
            x=0.5,
            font=dict(size=11, color=COLOR_TEXT_SECONDARY),
        ),
        height=400,
    )

    return apply_aeolus_theme(fig)
