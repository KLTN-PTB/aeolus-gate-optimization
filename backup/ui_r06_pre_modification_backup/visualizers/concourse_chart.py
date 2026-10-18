"""CHART-08: Gate Concourse Inventory & Utilization Visualizer.

Compares peak simultaneous gate occupancy against maximum available capacity
across concourses (Concourse T, Concourse A, Remote Apron).
"""

from typing import Any, Dict, List, Optional, Sequence
import plotly.graph_objects as go

from dashboard.core.contracts import GateTimelineView
from dashboard.visualizers.theme import (
    COLOR_ACCENT_PRIMARY,
    COLOR_BORDER_SUBTLE,
    COLOR_STATUS_ERROR,
    COLOR_STATUS_SUCCESS,
    COLOR_STATUS_WARNING,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
    apply_aeolus_theme,
)
from src.optimization.domain import Gate


def create_concourse_utilization_figure(
    concourse_stats: Optional[Dict[str, Dict[str, int]]] = None,
    gates: Optional[Sequence[Gate]] = None,
    assignments: Optional[Dict[str, Any]] = None,
) -> go.Figure:
    """Generate horizontal bar chart for concourse inventory & utilization (CHART-08).

    Args:
        concourse_stats: Dict mapping concourse name to dict with:
                         {"capacity": int, "occupied": int}
        gates: Optional collection of Gate domain objects to dynamically build stats.
        assignments: Optional active assignments dict to compute occupied count honestly.

    Returns:
        go.Figure: Plotly figure conforming to CHART-08 contract.
    """
    fig = go.Figure()

    if concourse_stats is None and gates is not None:
        stats: Dict[str, Dict[str, int]] = {}
        for g in gates:
            gid = str(g.gate_id)
            if getattr(g, "is_overflow", False):
                cname = "Bãi đỗ tràn"
            elif getattr(g.resource_type, "value", str(g.resource_type)) in ("REMOTE", "FINITE_REMOTE_STAND"):
                cname = "Remote Apron"
            elif gid.startswith("T") or (hasattr(g, "gate_index") and g.gate_index < 10):
                cname = "Concourse T"
            else:
                cname = "Concourse A"

            if cname not in stats:
                stats[cname] = {"capacity": 0, "occupied": 0}
            cap = int(g.capacity) if (g.capacity is not None and g.capacity < 1000) else 1
            stats[cname]["capacity"] += cap

        if assignments:
            for flight_id, assign in assignments.items():
                gid = getattr(assign, "gate_id", None) or (assign.get("gate_id") if isinstance(assign, dict) else None)
                if gid:
                    for g in gates:
                        if str(g.gate_id) == str(gid):
                            if getattr(g, "is_overflow", False):
                                cname = "Bãi đỗ tràn"
                            elif getattr(g.resource_type, "value", str(g.resource_type)) in ("REMOTE", "FINITE_REMOTE_STAND"):
                                cname = "Remote Apron"
                            elif str(gid).startswith("T") or (hasattr(g, "gate_index") and g.gate_index < 10):
                                cname = "Concourse T"
                            else:
                                cname = "Concourse A"
                            if cname in stats:
                                stats[cname]["occupied"] += 1
                            break

        concourse_stats = stats

    if not concourse_stats:
        concourse_stats = {
            "Concourse T": {"capacity": 10, "occupied": 0},
            "Concourse A": {"capacity": 15, "occupied": 0},
            "Remote Apron": {"capacity": 1, "occupied": 0},
        }

    concourses = list(concourse_stats.keys())
    capacities = [concourse_stats[c]["capacity"] for c in concourses]
    occupied = [concourse_stats[c]["occupied"] for c in concourses]

    utilizations = [
        (occ / cap * 100.0) if cap > 0 else 0.0
        for occ, cap in zip(occupied, capacities)
    ]

    # Assign bar colors based on thresholds (<80% green, 80-99% amber, 100% red)
    bar_colors = []
    for u in utilizations:
        if u >= 100.0:
            bar_colors.append(COLOR_STATUS_ERROR)
        elif u >= 80.0:
            bar_colors.append(COLOR_STATUS_WARNING)
        else:
            bar_colors.append(COLOR_STATUS_SUCCESS)

    # Hover templates
    hover_texts = [
        f"<b>{c}</b><br>"
        f"Cổng đang sử dụng: {occ}/{cap}<br>"
        f"Tỷ lệ chiếm dụng: {u:.1f}%<br>"
        f"Trạng thái: {'Áp lực chạm trần' if u >= 100 else ('Tải cao' if u >= 80 else 'Thông thoáng')}"
        for c, occ, cap, u in zip(concourses, occupied, capacities, utilizations)
    ]

    # Capacity background bars (subtle)
    fig.add_trace(
        go.Bar(
            y=concourses,
            x=capacities,
            name="Tổng Sức chứa Cổng",
            orientation="h",
            marker_color=COLOR_BORDER_SUBTLE,
            hoverinfo="skip",
        )
    )

    # Occupied bars
    fig.add_trace(
        go.Bar(
            y=concourses,
            x=occupied,
            name="Số Cổng Đang Dùng",
            orientation="h",
            marker_color=bar_colors,
            hovertext=hover_texts,
            hoverinfo="text",
            text=[f"{occ}/{cap} ({u:.0f}%)" for occ, cap, u in zip(occupied, capacities, utilizations)],
            textposition="inside",
            insidetextanchor="middle",
        )
    )

    fig.update_layout(
        barmode="overlay",
        title={
            "text": "<b>SỨC CHỨA CỔNG & KHU VỰC ĐỖ</b>",
            "x": 0.02,
            "font": {"size": 14, "color": COLOR_TEXT_PRIMARY},
        },
        xaxis_title="Số lượng Cổng đỗ (Vị trí)",
        yaxis_title="",
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
