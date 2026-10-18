"""Flight Inspector UI Component for Gate Operations.

Provides a deep operational audit of a selected flight or aircraft turn,
including physical times, gates, buffer integrity, slack, and constraint diagnostics.
"""

from typing import Dict, List, Optional, Sequence
import streamlit as st

from dashboard.core.contracts import GateTimelineView, RiskCategory
from dashboard.core.state import SessionStateKeys
from src.optimization.domain import Flight


def _format_time_clock(m: int) -> str:
    """Format minutes from midnight into HH:MM or +1d HH:MM if cross-midnight."""
    days = m // 1440
    rem = m % 1440
    hh = rem // 60
    mm = rem % 60
    d_str = f"+{days}d " if days > 0 else ""
    return f"{d_str}{hh:02d}:{mm:02d}"


def render_flight_inspector(
    selected_flight_id: Optional[str],
    all_flights: Sequence[Flight],
    assignments_map: Dict[str, GateTimelineView],
    solver_status: str = "TỐI ƯU TUYỆT ĐỐI (CP-SAT)",
) -> None:
    """Render the Flight Inspector card.

    Args:
        selected_flight_id: Currently active flight identifier.
        all_flights: List of all Flight objects in active scenario.
        assignments_map: Mapping of flight_id -> GateTimelineView.
        solver_status: Active solver status string.
    """
    flight_dict = {f.flight_id: f for f in all_flights}

    st.markdown(
        """
        <div style="font-weight: 600; font-size: 14px; margin-bottom: 8px; color: #47C5C0;">
            🔍 THÔNG TIN CHI TIẾT CHUYẾN BAY (FLIGHT INSPECTOR)
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Fallback selectbox selector ensuring synchronization even if chart click is unavailable
    flight_ids = sorted(list(flight_dict.keys()))
    if not flight_ids:
        st.info("Không có chuyến bay trong kịch bản hiện tại.")
        return

    default_idx = flight_ids.index(selected_flight_id) if selected_flight_id in flight_ids else 0
    chosen_id = st.selectbox(
        "Chọn chuyến bay để thanh tra chi tiết:",
        options=flight_ids,
        index=default_idx,
        key="inspector_flight_picker",
    )

    if chosen_id != selected_flight_id:
        st.session_state[SessionStateKeys.SELECTED_FLIGHT_ID] = chosen_id
        selected_flight_id = chosen_id

    fl = flight_dict.get(selected_flight_id)
    asn = assignments_map.get(selected_flight_id)

    if fl is None:
        st.markdown(
            """
            <div class="aeolus-card" style="padding: 16px; text-align: center; color: #94A3B8;">
                👆 Chọn một chuyến bay từ danh sách trên để xem phân tích chi tiết.
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    if asn is None:
        # Flight exists but unassigned
        sched_arr = _format_time_clock(fl.scheduled_arrival_min)
        sched_dep = _format_time_clock(fl.scheduled_departure_min)
        pred_arr = _format_time_clock(fl.predicted_arrival_min)
        st.markdown(
            f"""
            <div class="aeolus-card" style="padding: 16px; border-color: #E47777;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                    <div>
                        <span style="font-size: 18px; font-weight: 700; color: #F0F4F8;">{fl.flight_id}</span>
                        <span style="font-size: 13px; color: #94A3B8; margin-left: 8px;">({fl.carrier} {fl.flight_number}) • Tàu bay: {fl.aircraft_type or 'B738'}</span>
                    </div>
                    <div>
                        <span class="aeolus-badge aeolus-badge-error">⚠️ CHƯA ĐƯỢC PHÂN CỔNG (UNASSIGNED)</span>
                    </div>
                </div>
                <div style="font-size: 13px; color: #F0F4F8;">
                    Chuyến bay này chưa được gán vị trí đỗ trong kế hoạch hiện tại.
                </div>
                <div style="margin-top: 8px; font-size: 12px; color: #94A3B8;">
                    Lịch: {sched_arr} ➔ {sched_dep} | Dự kiến hạ cánh: {pred_arr} | Cổng danh định: {fl.nominal_gate_id or 'Chưa xác định'}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    # Extract operational attributes
    sched_arr = _format_time_clock(fl.scheduled_arrival_min)
    sched_dep = _format_time_clock(fl.scheduled_departure_min)
    pred_arr = _format_time_clock(fl.predicted_arrival_min)
    gate_out = _format_time_clock(asn.actual_gate_out_min)
    release = _format_time_clock(asn.actual_gate_release_min)

    delay_arr = fl.arrival_delay_min
    dwell_min = asn.actual_gate_out_min - asn.start_min
    slack_min = fl.turnaround_slack_min

    # Reassignment status
    is_reassigned = asn.is_reassigned
    reas_badge = (
        '<span class="aeolus-badge aeolus-badge-warning">⇄ ĐÃ TÁI PHÂN BỔ</span>'
        if is_reassigned
        else '<span class="aeolus-badge aeolus-badge-success">✓ ĐÚNG CỔNG GỐC</span>'
    )

    # Conflict status
    conflict_badge = (
        '<span class="aeolus-badge aeolus-badge-error">⚠️ CÓ XUNG ĐỘT</span>'
        if asn.has_conflict
        else '<span class="aeolus-badge aeolus-badge-success">🛡️ 0 XUNG ĐỘT</span>'
    )

    # Remote status
    remote_badge = (
        '<span class="aeolus-badge aeolus-badge-remote">🚌 BÃI ĐỖ TỪ XA</span>'
        if asn.is_remote
        else '<span class="aeolus-badge aeolus-badge-info">CỔNG TIẾP XÚC</span>'
    )

    card_html = f"""
    <div class="aeolus-card" style="padding: 16px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; border-bottom: 1px solid #263B5C; padding-bottom: 8px;">
            <div>
                <span style="font-size: 18px; font-weight: 700; color: #F0F4F8;">{fl.flight_id}</span>
                <span style="font-size: 13px; color: #94A3B8; margin-left: 8px;">({fl.carrier} {fl.flight_number}) • Tàu bay: {fl.aircraft_type or 'B738'}</span>
            </div>
            <div>
                {conflict_badge} {reas_badge} {remote_badge}
            </div>
        </div>

        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; font-size: 13px;">
            <div>
                <div style="color: #94A3B8; font-size: 11px;">CỔNG PHÂN BỔ (ASSIGNED)</div>
                <div style="font-weight: 700; color: #47C5C0; font-size: 15px;">{asn.gate_id}</div>
                <div style="color: #94A3B8; font-size: 11px;">Cổng gốc: <code>{fl.nominal_gate_id or asn.gate_id}</code></div>
            </div>
            <div>
                <div style="color: #94A3B8; font-size: 11px;">KHUNG THỜI GIAN THEO LỊCH</div>
                <div style="color: #F0F4F8;">Đến: <b>{sched_arr}</b> ➔ Đi: <b>{sched_dep}</b></div>
                <div style="color: #94A3B8; font-size: 11px;">Thời lượng lịch: {fl.scheduled_dwell_min} phút</div>
            </div>
            <div>
                <div style="color: #94A3B8; font-size: 11px;">DỰ BÁO TRỄ ĐẾN (ML PREDICTED)</div>
                <div style="color: {'#E5AD55' if delay_arr >= 15 else '#34C759'}; font-weight: 600;">{delay_arr:+.1f} phút</div>
                <div style="color: #94A3B8; font-size: 11px;">Hạ cánh dự kiến: <b>{pred_arr}</b></div>
            </div>
            <div>
                <div style="color: #94A3B8; font-size: 11px;">CỬA SỔ CHIẾM DỤNG CỔNG</div>
                <div style="color: #F0F4F8;">Vào: <b>{pred_arr}</b> ➔ Rời: <b>{gate_out}</b></div>
                <div style="color: #94A3B8; font-size: 11px;">Dwell thực tế: {dwell_min} phút</div>
            </div>
            <div>
                <div style="color: #94A3B8; font-size: 11px;">GIẢI PHÓNG CỔNG (RELEASE)</div>
                <div style="color: #00D2FF; font-weight: 600;">{release}</div>
                <div style="color: #94A3B8; font-size: 11px;">Đệm an toàn: +{asn.buffer_min} phút</div>
            </div>
            <div>
                <div style="color: #94A3B8; font-size: 11px;">ĐỆM SLACK QUAY VÒNG</div>
                <div style="color: {'#34C759' if slack_min >= 20 else ('#E5AD55' if slack_min >= 5 else '#E47777')}; font-weight: 600;">
                    {slack_min} phút {'(An toàn)' if slack_min >= 20 else ('(Rủi ro TB)' if slack_min >= 5 else '(Nguy cơ cao)')}
                </div>
                <div style="color: #94A3B8; font-size: 11px;">Tối thiểu: {fl.min_turnaround_min}m</div>
            </div>
        </div>

        <div style="margin-top: 12px; padding-top: 8px; border-top: 1px solid #263B5C; display: flex; justify-content: space-between; font-size: 12px; color: #94A3B8;">
            <div>Nguồn dữ liệu ML: <code>{asn.prediction_source}</code></div>
            <div>Loại tài nguyên: <code>{asn.resource_type}</code></div>
            <div>Trạng thái bộ giải: <b>{solver_status}</b></div>
        </div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)
