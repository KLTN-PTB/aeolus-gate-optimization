"""CHART-07: Master Interactive Gate Gantt Chart Visualizer.

Implements continuous-time horizontal scheduling canvas with separation buffers,
concourse grouping, reassignment flags, conflict detection, and cross-midnight handling.
"""

from typing import Dict, List, Optional, Sequence, Tuple
import plotly.graph_objects as go

from dashboard.adapters.assignment_adapter import filter_assignments
from dashboard.core.contracts import GateTimelineView
from dashboard.visualizers.theme import (
    COLOR_ACCENT_GLOW,
    COLOR_ACCENT_PRIMARY,
    COLOR_APRON_REMOTE,
    COLOR_BORDER_ACTIVE,
    COLOR_BORDER_SUBTLE,
    COLOR_STATUS_ERROR,
    COLOR_STATUS_WARNING,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
    apply_aeolus_theme,
)
from src.optimization.domain import Gate


def _format_minute_to_clock(minute: int) -> str:
    """Format minutes from midnight into 24h clock string with day offset."""
    if minute < 0:
        return f"-{abs(minute)//60:02d}:{abs(minute)%60:02d}"
    day_offset = minute // 1440
    rem_min = minute % 1440
    h = rem_min // 60
    m = rem_min % 60
    if day_offset > 0:
        return f"(+{day_offset}d) {h:02d}:{m:02d}"
    return f"{h:02d}:{m:02d}"


def create_gate_gantt_figure(
    assignments: Sequence[GateTimelineView],
    gates: Optional[Sequence[Gate]] = None,
    time_zoom: Optional[Tuple[int, int]] = None,
    selected_flight_id: Optional[str] = None,
    concourse_filter: Optional[Sequence[str]] = None,
    carrier_filter: Optional[str] = None,
    resource_type_filter: Optional[str] = None,
    search_query: Optional[str] = None,
    is_nominal_view: bool = False,
    time_window_filter: Optional[Tuple[int, int]] = None,
) -> go.Figure:
    """Generate the Master Interactive Gate Gantt chart (CHART-07).

    Args:
        assignments: GateTimelineView collection.
        gates: Gate domain entities to display all gate rows.
        time_zoom: Optional (min_minute, max_minute) window.
        selected_flight_id: Optional flight ID to highlight.
        concourse_filter: Concourse codes to include (e.g. ['T', 'A', 'REMOTE', 'OVERFLOW']).
        carrier_filter: Carrier filter ('ALL' or specific carrier).
        resource_type_filter: Resource type filter.
        search_query: Search text for flight_id.
        is_nominal_view: Whether rendering nominal or optimized plan.
        time_window_filter: Optional (w_start, w_end) filter intersecting [start, release).

    Returns:
        go.Figure: High-density Gantt figure conforming to CHART-07 contract.
    """
    fig = go.Figure()

    # 1. Filter assignments (Task R05-B)
    filtered_asn: List[GateTimelineView] = filter_assignments(
        assignments=assignments,
        concourse_filter=concourse_filter,
        carrier_filter=carrier_filter,
        resource_type_filter=resource_type_filter,
        search_query=search_query,
        time_window=time_window_filter,
    )

    # 2. Determine gate list
    if gates:
        gate_ids = [g.gate_id for g in gates]
    else:
        gate_ids = sorted(list({a.gate_id for a in filtered_asn}))

    if not gate_ids and concourse_filter is None:
        gate_ids = ["G_01", "G_02", "REMOTE_APRON_01"]

    # Apply concourse filter to gate rows (Task R05-A / Task R05-B)
    if concourse_filter is not None:
        c_set = set(concourse_filter)
        filtered_gates = []
        for gid in gate_ids:
            upper = gid.upper().strip()
            clean = upper.replace("GATE_", "")
            if clean.startswith("REMOTE") or clean.startswith("STAND"):
                c = "REMOTE"
            elif clean.startswith("APRON") or clean.startswith("OVERFLOW") or clean.startswith("OVF") or "APRON" in upper:
                c = "OVERFLOW"
            elif clean.startswith("T"):
                c = "T"
            elif clean.startswith("A"):
                c = "A"
            elif clean[:1] in ("B", "C", "D", "E", "F"):
                c = clean[0]
            elif clean.startswith("G_") or clean.startswith("G"):
                digits = "".join([ch for ch in clean if ch.isdigit()])
                if digits:
                    try:
                        num = int(digits)
                        c = "T" if num <= 10 else "A"
                    except ValueError:
                        c = "T"
                else:
                    c = "UNKNOWN_GROUP"
            else:
                c = "UNKNOWN_GROUP"

            if c in c_set:
                filtered_gates.append(gid)
        gate_ids = filtered_gates

    # Reverse gate order so first gate appears at the top of Y-axis
    y_categories = list(reversed(gate_ids))

    if not filtered_asn and not gates:
        fig.add_annotation(
            text="Không có dữ liệu phân cổng phù hợp với bộ lọc hiện tại",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font={"size": 14, "color": COLOR_TEXT_MUTED},
        )
        fig.update_layout(title={"text": "Biểu đồ Master Gantt Phân Bổ Cổng", "x": 0.02})
        return apply_aeolus_theme(fig)

    # 3. Categorize bar segments
    # Traces:
    # 1. Nominal Contact (Cyan)
    # 2. Reassigned Contact (Amber)
    # 3. Remote Stand (Violet)
    # 4. Gate Conflict (Red)
    # 5. Separation Buffer (Patterned / Hatched)
    nom_y, nom_bases, nom_widths, nom_texts, nom_hovers = [], [], [], [], []
    reas_y, reas_bases, reas_widths, reas_texts, reas_hovers = [], [], [], [], []
    rem_y, rem_bases, rem_widths, rem_texts, rem_hovers = [], [], [], [], []
    conf_y, conf_bases, conf_widths, conf_texts, conf_hovers = [], [], [], [], []
    buf_y, buf_bases, buf_widths, buf_hovers = [], [], [], []

    for a in filtered_asn:
        if a.gate_id not in gate_ids:
            continue

        gate_y = a.gate_id
        start_m = a.start_min
        gate_out_m = a.actual_gate_out_min
        dwell_duration = max(1, gate_out_m - start_m)
        buffer_duration = a.buffer_min
        release_m = a.actual_gate_release_min

        status_text = "HỢP LỆ — ĐÚNG CỔNG DANH ĐỊNH"
        prefix = ""
        if a.has_conflict:
            status_text = "⚠️ XUNG ĐỘT — VA CHẠM THỜI GIAN"
            prefix = "⚠️ "
        elif a.is_remote:
            status_text = "🚌 BÃI ĐỖ TỪ XA (REMOTE STAND)"
            prefix = "🚌 "
        elif a.is_reassigned:
            status_text = "⇄ ĐÃ TÁI PHÂN BỔ (REASSIGNED)"
            prefix = "⇄ "

        bar_label = f"{prefix}{a.flight_id}"
        is_highlighted = (selected_flight_id and a.flight_id == selected_flight_id)
        if is_highlighted:
            bar_label = f"★ {bar_label}"

        hover_info = (
            f"<b>Chuyến bay: {a.flight_id}</b> ({a.carrier} {a.flight_number})<br>"
            f"Cổng phân bổ: <b>{a.gate_id}</b> (Gốc: {a.nominal_gate_id or a.gate_id})<br>"
            f"Khu vực: Concourse {a.concourse} ({a.resource_type})<br>"
            f"Giờ vào cổng (Gate-In): {_format_minute_to_clock(start_m)}<br>"
            f"Giờ rời cổng (Gate-Out): {_format_minute_to_clock(gate_out_m)}<br>"
            f"Giờ giải phóng cổng (Release): {_format_minute_to_clock(release_m)}<br>"
            f"Đệm giãn cách an toàn: {buffer_duration} phút<br>"
            f"Trạng thái: <b>{status_text}</b>"
            "<extra></extra>"
        )

        buffer_hover = (
            f"<b>Đệm Giãn cách An toàn (15 min)</b><br>"
            f"Cổng: {a.gate_id} | Chuyến: {a.flight_id}<br>"
            f"Khung giãn cách: {_format_minute_to_clock(gate_out_m)} ➔ {_format_minute_to_clock(release_m)}<br>"
            "Mục đích: Khử xung đột và phục vụ kéo đẩy tàu bay"
            "<extra></extra>"
        )

        # Buffer trace
        buf_y.append(gate_y)
        buf_bases.append(gate_out_m)
        buf_widths.append(buffer_duration)
        buf_hovers.append(buffer_hover)

        # Occupancy block categorization
        if a.has_conflict:
            conf_y.append(gate_y)
            conf_bases.append(start_m)
            conf_widths.append(dwell_duration)
            conf_texts.append(bar_label)
            conf_hovers.append(hover_info)
        elif a.is_remote:
            rem_y.append(gate_y)
            rem_bases.append(start_m)
            rem_widths.append(dwell_duration)
            rem_texts.append(bar_label)
            rem_hovers.append(hover_info)
        elif a.is_reassigned:
            reas_y.append(gate_y)
            reas_bases.append(start_m)
            reas_widths.append(dwell_duration)
            reas_texts.append(bar_label)
            reas_hovers.append(hover_info)
        else:
            nom_y.append(gate_y)
            nom_bases.append(start_m)
            nom_widths.append(dwell_duration)
            nom_texts.append(bar_label)
            nom_hovers.append(hover_info)

    # 4. Add traces to figure
    # Trace 1: Nominal Contact (Aerodrome Cyan)
    if nom_y:
        fig.add_trace(
            go.Bar(
                name="Cổng Tiếp xúc Danh định",
                y=nom_y,
                x=nom_widths,
                base=nom_bases,
                orientation="h",
                marker_color=COLOR_ACCENT_PRIMARY,
                marker_line_color="#101B2A",
                marker_line_width=1,
                text=nom_texts,
                textposition="inside",
                insidetextanchor="middle",
                textfont={"size": 10, "color": "#101B2A"},
                hovertext=nom_hovers,
                hoverinfo="text",
            )
        )

    # Trace 2: Reassigned Contact (Taxiway Amber)
    if reas_y:
        fig.add_trace(
            go.Bar(
                name="Cổng Tiếp xúc Đổi (Reassigned)",
                y=reas_y,
                x=reas_widths,
                base=reas_bases,
                orientation="h",
                marker_color=COLOR_STATUS_WARNING,
                marker_line_color="#101B2A",
                marker_line_width=1,
                text=reas_texts,
                textposition="inside",
                insidetextanchor="middle",
                textfont={"size": 10, "color": "#101B2A"},
                hovertext=reas_hovers,
                hoverinfo="text",
            )
        )

    # Trace 3: Remote Stand (Apron Violet)
    if rem_y:
        fig.add_trace(
            go.Bar(
                name="Bãi đỗ Từ xa (Remote Stand)",
                y=rem_y,
                x=rem_widths,
                base=rem_bases,
                orientation="h",
                marker_color=COLOR_APRON_REMOTE,
                marker_line_color="#101B2A",
                marker_line_width=1,
                text=rem_texts,
                textposition="inside",
                insidetextanchor="middle",
                textfont={"size": 10, "color": "#101B2A"},
                hovertext=rem_hovers,
                hoverinfo="text",
            )
        )

    # Trace 4: Conflict (Alert Red)
    if conf_y:
        fig.add_trace(
            go.Bar(
                name="⚠️ Xung đột Va chạm Lịch",
                y=conf_y,
                x=conf_widths,
                base=conf_bases,
                orientation="h",
                marker_color=COLOR_STATUS_ERROR,
                marker_line_color="#FFFFFF",
                marker_line_width=2,
                text=conf_texts,
                textposition="inside",
                insidetextanchor="middle",
                textfont={"size": 10, "color": "#FFFFFF"},
                hovertext=conf_hovers,
                hoverinfo="text",
            )
        )

    # Trace 5: Separation Buffer (Patterned hatched / subtle)
    if buf_y:
        fig.add_trace(
            go.Bar(
                name="Đệm Giãn cách (15m Buffer)",
                y=buf_y,
                x=buf_widths,
                base=buf_bases,
                orientation="h",
                marker_color="#263B5C",
                marker_pattern_shape="/",
                marker_pattern_fgcolor="#47C5C0",
                marker_pattern_fillmode="replace",
                marker_line_color="#3B5780",
                marker_line_width=1,
                opacity=0.6,
                hovertext=buf_hovers,
                hoverinfo="text",
            )
        )

    # 5. Configure Axes & Layout
    # Determine X-axis range
    all_starts = [a.start_min for a in filtered_asn] or [360]
    all_releases = [a.actual_gate_release_min for a in filtered_asn] or [720]

    min_x = min(all_starts) - 15
    max_x = max(all_releases) + 30

    if time_zoom:
        min_x = max(min_x, time_zoom[0])
        max_x = min(max_x, time_zoom[1])

    # Round to hour boundaries
    tick_start = int(min_x // 60 * 60)
    tick_end = int((max_x // 60 + 1) * 60)
    tick_vals = list(range(tick_start, tick_end + 60, 60))
    tick_texts = [_format_minute_to_clock(v) for v in tick_vals]

    plan_type_str = "KẾ HOẠCH TỐI ƯU HÓA" if not is_nominal_view else "KẾ HOẠCH DANH ĐỊNH GỐC (NOMINAL)"

    fig.update_layout(
        barmode="overlay",
        title={
            "text": f"<b>BIỂU ĐỒ GANTT TƯƠNG TÁC PHÂN BỔ CỔNG</b> — {plan_type_str}",
            "x": 0.02,
            "font": {"size": 14, "color": COLOR_TEXT_PRIMARY},
        },
        xaxis={
            "title": "Thời gian Vận hành (Giờ địa phương HH:MM)",
            "range": [min_x, max_x],
            "tickvals": tick_vals,
            "ticktext": tick_texts,
        },
        yaxis={
            "categoryorder": "array",
            "categoryarray": y_categories,
            "dtick": 1,
            "title": "Cổng đỗ & Vị trí đỗ",
        },
        height=max(540, len(gate_ids) * 22 + 100),
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.01,
            "xanchor": "left",
            "x": 0.0,
            "bgcolor": "rgba(0,0,0,0)",
        },
    )

    return apply_aeolus_theme(fig)
