"""CHART-01: Operational Activity Timeline Visualizer.

Binned flight arrival and departure movements across 15-minute intervals.
"""

from typing import List, Sequence
import numpy as np
import plotly.graph_objects as go

from dashboard.visualizers.theme import (
    COLOR_ACCENT_GLOW,
    COLOR_ACCENT_PRIMARY,
    COLOR_TEXT_MUTED,
    apply_aeolus_theme,
)
from src.optimization.domain import Flight


def create_activity_timeline_figure(
    flights: Sequence[Flight],
    bin_size_minutes: int = 15,
) -> go.Figure:
    """Generate interactive 15-minute binned activity timeline figure (CHART-01).

    Args:
        flights: Collection of Flight domain objects.
        bin_size_minutes: Interval duration in minutes (default 15).

    Returns:
        go.Figure: Configured Plotly figure conforming to CHART-01 contract.
    """
    fig = go.Figure()

    if not flights:
        fig.add_annotation(
            text="Không có dữ liệu chuyến bay cho kịch bản đã chọn",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font={"size": 14, "color": COLOR_TEXT_MUTED},
        )
        fig.update_layout(
            title={"text": "Biểu đồ Hoạt động Khai thác theo Khung giờ", "x": 0.05},
            xaxis_title="Thời gian Địa phương (HH:MM)",
            yaxis_title="Số lượt Tàu bay",
        )
        return apply_aeolus_theme(fig)

    arr_times = [
        f.scheduled_arrival_min
        for f in flights
        if f.scheduled_arrival_min is not None and f.scheduled_arrival_min >= 0
    ]
    dep_times = [
        f.scheduled_departure_min
        for f in flights
        if f.scheduled_departure_min is not None and f.scheduled_departure_min >= 0
    ]

    all_times = arr_times + dep_times
    if not all_times:
        min_time = 360  # 06:00
        max_time = 720  # 12:00
    else:
        min_time = int(min(all_times) // bin_size_minutes * bin_size_minutes)
        max_time = int((max(all_times) // bin_size_minutes + 1) * bin_size_minutes)

    # Generate bin edges
    bins = list(range(min_time, max_time + bin_size_minutes, bin_size_minutes))
    bin_labels = [
        f"+1d {(b // 60) % 24:02d}:{b % 60:02d}" if b >= 1440 else f"{b // 60:02d}:{b % 60:02d}"
        for b in bins[:-1]
    ]

    arr_counts, _ = np.histogram(arr_times, bins=bins) if arr_times else ([0] * len(bin_labels), None)
    dep_counts, _ = np.histogram(dep_times, bins=bins) if dep_times else ([0] * len(bin_labels), None)

    # Hover templates
    arr_hover = [
        f"Khung giờ: {bin_labels[i]} - {bins[i+1]//60:02d}:{bins[i+1]%60:02d}<br>"
        f"Hạ cánh dự kiến: {arr_counts[i]} chuyến<br>"
        f"Cất cánh dự kiến: {dep_counts[i]} chuyến<br>"
        f"Tổng lưu lượng: {arr_counts[i] + dep_counts[i]} lượt tàu bay"
        for i in range(len(bin_labels))
    ]

    dep_hover = arr_hover

    # Inbound bar (Aerodrome Cyan)
    fig.add_trace(
        go.Bar(
            y=arr_counts,
            x=bin_labels,
            name="Hạ cánh (Inbound)",
            marker_color=COLOR_ACCENT_PRIMARY,
            hovertext=arr_hover,
            hoverinfo="text",
        )
    )

    # Outbound bar (Runway Blue)
    fig.add_trace(
        go.Bar(
            y=dep_counts,
            x=bin_labels,
            name="Cất cánh (Outbound)",
            marker_color=COLOR_ACCENT_GLOW,
            hovertext=dep_hover,
            hoverinfo="text",
        )
    )

    fig.update_layout(
        barmode="stack",
        title={
            "text": "<b>BIỂU ĐỒ HOẠT ĐỘNG KHAI THÁC THEO KHUNG GIỜ</b>",
            "x": 0.02,
            "font": {"size": 14},
        },
        xaxis_title="Thời gian Địa phương (HH:MM)",
        yaxis_title="Lượt Tàu bay / 15 phút",
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1.0,
            "bgcolor": "rgba(0,0,0,0)",
        },
        height=340,
    )

    return apply_aeolus_theme(fig)
