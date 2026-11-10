"""CHART-02: Arrival Delay Distribution Visualizer.

Shows distribution of predicted arrival delays with threshold annotations.
"""

from typing import Sequence, Union
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from dashboard.visualizers.theme import (
    COLOR_ACCENT_PRIMARY,
    COLOR_STATUS_WARNING,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
    apply_aeolus_theme,
)


def create_delay_distribution_figure(
    predictions: Union[pd.DataFrame, Sequence[float]],
    threshold_min: float = 15.0,
) -> go.Figure:
    """Generate interactive arrival delay distribution histogram (CHART-02).

    Args:
        predictions: DataFrame containing 'predicted_delay_min'/'predicted_arr_delay_min'
                     or a sequence of delay float values.
        threshold_min: Delay alert threshold in minutes (default 15.0).

    Returns:
        go.Figure: Plotly figure conforming to CHART-02 contract.
    """
    fig = go.Figure()

    if isinstance(predictions, pd.DataFrame):
        col = None
        for candidate in ["predicted_delay_min", "predicted_arr_delay_min", "pred_delay"]:
            if candidate in predictions.columns:
                col = candidate
                break
        delays = predictions[col].dropna().tolist() if col else []
    else:
        delays = [d for d in predictions if d is not None and not np.isnan(d)]

    if not delays:
        fig.add_annotation(
            text="Chưa có dữ liệu dự báo độ trễ",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font={"size": 14, "color": COLOR_TEXT_MUTED},
        )
        fig.update_layout(
            title={"text": "Phân bố Độ trễ Dự báo (CHART-02)", "x": 0.05},
            xaxis_title="Độ trễ Dự báo (Phút)",
            yaxis_title="Số lượng Chuyến bay",
        )
        return apply_aeolus_theme(fig)

    delays_arr = np.array(delays)
    total_flights = len(delays_arr)
    mean_delay = float(np.mean(delays_arr))
    pct_delayed = float(np.mean(delays_arr >= threshold_min) * 100)

    # Histogram trace
    fig.add_trace(
        go.Histogram(
            x=delays_arr,
            nbinsx=20,
            name="Số chuyến bay",
            marker_color=COLOR_ACCENT_PRIMARY,
            marker_line_color="#101B2A",
            marker_line_width=1,
            hovertemplate=(
                "Khoảng trễ: %{x:.1f} phút<br>"
                "Số chuyến: %{y} chuyến<br>"
                f"Tổng số mẫu: {total_flights}"
                "<extra></extra>"
            ),
        )
    )

    # Add vertical dashed threshold line at +15 min
    fig.add_vline(
        x=threshold_min,
        line_dash="dash",
        line_color=COLOR_STATUS_WARNING,
        line_width=2,
        annotation_text=f"Ngưỡng FAA (+{int(threshold_min)}m): {pct_delayed:.1f}% trễ",
        annotation_position="top right",
        annotation_font={"size": 11, "color": COLOR_STATUS_WARNING},
    )

    fig.update_layout(
        title={
            "text": f"<b>PHÂN BỐ ĐỘ TRỄ DỰ BÁO (CHART-02)</b> — TB: {mean_delay:+.1f} min",
            "x": 0.02,
            "font": {"size": 14, "color": COLOR_TEXT_PRIMARY},
        },
        xaxis_title="Độ trễ Đến Dự báo (Phút)",
        yaxis_title="Số lượng Chuyến bay (Tần suất)",
        bargap=0.08,
        height=340,
        showlegend=False,
    )

    return apply_aeolus_theme(fig)
