"""CHART-03: Aircraft Turn & Slack Dynamics Visualizer.

Deconstructs an individual aircraft turnaround into minimum turn service time,
slack absorption, remaining slack buffer, propagated outbound delay, and safety separation.
"""

from typing import Any, Dict, Optional, Union
import plotly.graph_objects as go

from dashboard.core.contracts import AircraftTurnView
from dashboard.visualizers.theme import (
    COLOR_ACCENT_PRIMARY,
    COLOR_APRON_REMOTE,
    COLOR_STATUS_ERROR,
    COLOR_STATUS_SUCCESS,
    COLOR_STATUS_WARNING,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
    apply_aeolus_theme,
)


def create_turn_dynamics_figure(
    turn: Union[AircraftTurnView, Dict[str, Any], None],
) -> go.Figure:
    """Generate horizontal stacked turnaround dynamics chart (CHART-03).

    Args:
        turn: AircraftTurnView instance or equivalent dictionary.

    Returns:
        go.Figure: Plotly figure conforming to CHART-03 contract.
    """
    fig = go.Figure()

    if turn is None:
        fig.add_annotation(
            text="Chọn một cặp chuyến bay quay vòng để xem phân tích động lực học",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font={"size": 14, "color": COLOR_TEXT_MUTED},
        )
        fig.update_layout(
            title={"text": "Sơ đồ Động lực học Quay vòng & Hấp thụ Buffer (CHART-03)", "x": 0.05},
        )
        return apply_aeolus_theme(fig)

    if isinstance(turn, AircraftTurnView):
        d = turn.to_dict()
    else:
        d = turn

    turn_id = d.get("turn_id", "TURN_UNKNOWN")
    inbound_id = d.get("inbound_flight_id", "ARR")
    outbound_id = d.get("outbound_flight_id", "DEP")
    tail_num = d.get("tail_number", "N/A")
    ac_type = d.get("aircraft_type", "B738")

    min_turn = float(d.get("min_turn_time_min", 45))
    absorbed_delay = float(d.get("inbound_delay_absorbed_min", 0.0))
    remaining_slack = float(d.get("remaining_slack_min", 0.0))
    propagated_delay = float(d.get("propagated_outbound_delay_min", 0.0))
    buffer_min = float(d.get("buffer_min", 15))

    # Base category row
    category = [f"{turn_id}<br>({tail_num} • {ac_type})"]

    # 1. Min Turn Required (Cyan)
    fig.add_trace(
        go.Bar(
            y=category,
            x=[min_turn],
            name="1. DV Tối thiểu (Min Turn)",
            orientation="h",
            marker_color=COLOR_ACCENT_PRIMARY,
            hovertemplate=f"Dịch vụ tối thiểu yêu cầu: {min_turn:.0f} phút<extra></extra>",
        )
    )

    # 2. Absorbed Delay (Amber)
    if absorbed_delay > 0:
        fig.add_trace(
            go.Bar(
                y=category,
                x=[absorbed_delay],
                name="2. Trễ Đến Đã Hấp thụ",
                orientation="h",
                marker_color=COLOR_STATUS_WARNING,
                hovertemplate=f"Trễ đến đã hấp thụ vào slack: {absorbed_delay:.1f} phút<extra></extra>",
            )
        )

    # 3. Remaining Slack (Green)
    if remaining_slack > 0:
        fig.add_trace(
            go.Bar(
                y=category,
                x=[remaining_slack],
                name="3. Đệm Slack Còn lại",
                orientation="h",
                marker_color=COLOR_STATUS_SUCCESS,
                hovertemplate=f"Đệm thời gian còn lại: {remaining_slack:.1f} phút<extra></extra>",
            )
        )

    # 4. Propagated Outbound Delay (Red, if delay exceeded scheduled slack)
    if propagated_delay > 0:
        fig.add_trace(
            go.Bar(
                y=category,
                x=[propagated_delay],
                name="4. Trễ Lan truyền Cất cánh",
                orientation="h",
                marker_color=COLOR_STATUS_ERROR,
                hovertemplate=f"Trễ lan truyền sang chuyến cất cánh: {propagated_delay:.1f} phút<extra></extra>",
            )
        )

    # 5. Gate Separation Buffer (Violet)
    fig.add_trace(
        go.Bar(
            y=category,
            x=[buffer_min],
            name="5. Giãn cách An toàn Cổng (Buffer)",
            orientation="h",
            marker_color=COLOR_APRON_REMOTE,
            hovertemplate=f"Giãn cách giải phóng cổng: {buffer_min:.0f} phút<extra></extra>",
        )
    )

    total_window = min_turn + absorbed_delay + remaining_slack + propagated_delay + buffer_min

    fig.update_layout(
        barmode="stack",
        title={
            "text": f"<b>ĐỘNG LỰC HỌC QUAY VÒNG & HẤP THỤ BUFFER</b> — {inbound_id} ➔ {outbound_id}",
            "x": 0.02,
            "font": {"size": 14, "color": COLOR_TEXT_PRIMARY},
        },
        xaxis_title="Thời lượng Quá trình (Phút)",
        yaxis_title="",
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.05,
            "xanchor": "left",
            "x": 0.0,
            "bgcolor": "rgba(0,0,0,0)",
        },
        height=260,
    )

    return apply_aeolus_theme(fig)
