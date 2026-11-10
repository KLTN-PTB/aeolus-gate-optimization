"""Solver status and termination reason mapping to UI badges.

Decouples internal mathematical solver statuses from presentation tokens.
"""

from dataclasses import dataclass
from typing import Optional

from src.optimization.domain import SolverStatus, TerminationReason


@dataclass(frozen=True)
class StatusBadge:
    """Frontend visual representation of an optimization solver status."""

    label: str
    color_hex: str
    icon: str
    tooltip: str
    is_optimal: bool
    is_feasible: bool


def map_solver_status_to_badge(
    status: SolverStatus | str,
    termination_reason: Optional[TerminationReason | str] = None,
    gap: Optional[float] = None,
) -> StatusBadge:
    """Map domain solver status and termination reason to an authoritative UI badge.

    Enforces scientific semantics:
    - Only OPTIMAL_PROVEN gets marked is_optimal = True.
    - Heuristics (Greedy, SA) are NEVER certified as proven optimal, even with 0 cost.
    - INFEASIBLE and UNKNOWN are distinct.
    """
    # Normalize strings to enum names if needed
    status_str = status.name if isinstance(status, SolverStatus) else str(status).upper()
    term_str = (
        termination_reason.name
        if isinstance(termination_reason, TerminationReason)
        else (str(termination_reason).upper() if termination_reason else "")
    )

    if term_str == "OPTIMAL_PROVEN" or (status_str == "OPTIMAL" and not term_str):
        return StatusBadge(
            label="TỐI ƯU TUYỆT ĐỐI (OPTIMAL PROVEN)",
            color_hex="#34C759",  # Clearance Green
            icon="🏆",
            tooltip="Đã chứng minh nghiệm tối ưu toàn cục bằng CP-SAT (Optimality Gap = 0.0%).",
            is_optimal=True,
            is_feasible=True,
        )

    if term_str == "FEASIBLE_FOUND" or status_str == "FEASIBLE":
        gap_suffix = f" — Gap: {gap * 100:.2f}%" if gap is not None else ""
        return StatusBadge(
            label=f"KHẢ THI (FEASIBLE{gap_suffix})",
            color_hex="#00D2FF",  # Runway Cyan
            icon="✓",
            tooltip="Tìm thấy phương án phân cổng hợp lệ, thỏa mãn 100% ràng buộc cứng.",
            is_optimal=False,
            is_feasible=True,
        )

    if term_str == "HEURISTIC_STOP":
        return StatusBadge(
            label="HOÀN TẤT (HEURISTIC STOP)",
            color_hex="#E5AD55",  # Taxiway Amber
            icon="⚡",
            tooltip="Thuật toán tham lam/heuristic đã tìm thấy phương án hợp lệ khả thi.",
            is_optimal=False,
            is_feasible=True,
        )

    if term_str == "TIME_LIMIT":
        return StatusBadge(
            label="HẾT GIỜ TÌM KIẾM (TIME LIMIT)",
            color_hex="#E5AD55",  # Caution Amber
            icon="⏱️",
            tooltip="Bộ giải dừng do chạm giới hạn thời gian (Wall-clock budget).",
            is_optimal=False,
            is_feasible=(status_str == "FEASIBLE"),
        )

    if term_str == "PROVEN_INFEASIBLE" or status_str == "INFEASIBLE":
        return StatusBadge(
            label="KHÔNG KHẢ THI (INFEASIBLE)",
            color_hex="#E47777",  # Alert Red
            icon="⚠️",
            tooltip="Chứng minh toán học: Không tồn tại phương án phân cổng nào thỏa mãn đồng thời các ràng buộc cứng.",
            is_optimal=False,
            is_feasible=False,
        )

    if status_str == "TIMEOUT_NO_SOLUTION":
        return StatusBadge(
            label="QUÁ GIỜ — CHƯA CÓ NGHIỆM",
            color_hex="#E47777",  # Alert Red
            icon="⌛",
            tooltip="Hết thời gian tìm kiếm mà chưa kịp tìm thấy nghiệm khả thi đầu tiên.",
            is_optimal=False,
            is_feasible=False,
        )

    # UNKNOWN or MODEL_INVALID
    return StatusBadge(
        label=f"TRẠNG THÁI: {status_str}",
        color_hex="#94A3B8",  # Muted Gray
        icon="❓",
        tooltip="Trạng thái nghiệm chưa xác định hoặc mô hình chưa khởi tạo.",
        is_optimal=False,
        is_feasible=False,
    )
