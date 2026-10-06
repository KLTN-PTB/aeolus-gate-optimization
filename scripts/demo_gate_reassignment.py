"""Demo bài toán tái phân bổ cổng đỗ tàu bay (Gate Reassignment Problem - GRP).

Minh họa quy trình 2 giai đoạn:
1. Giai đoạn Tĩnh: Lập lịch cổng ban đầu (current_gate) theo giờ bay lịch trình (chưa biết trễ).
2. Giai đoạn Động: Khi mô hình ML dự báo trễ (p_delay, delay_est_min), CP-SAT giải bài toán
   tái phân bổ cổng đỗ sao cho:
   - 100% không bị xung đột thời gian (Hard constraint)
   - Tối thiểu hóa số chuyến bay phải đổi cổng (Objective: Minimize reassignment count)
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Ensure UTF-8 output encoding for Windows terminal
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import pandas as pd
from src.optimization.oof_adapter import oof_to_problem_instance
from src.optimization.cp_sat_solver import solve_gate_assignment


def run_gate_reassignment_demo(month: int = 10, day: int = 8, num_gates: int = 22) -> None:
    data_path = PROJECT_ROOT / "src" / "artifacts" / "predictions" / "full_turn_unified_predictions_for_cpsat.parquet"
    if not data_path.exists():
        print(f"Không tìm thấy tệp: {data_path}")
        return

    print("=" * 80)
    print(f"   MÔ PHỎNG TÁI PHÂN BỔ CỔNG ĐỖ TÀU BAY (GATE REASSIGNMENT) - SÂN BAY ATL")
    print(f"   Kịch bản ngày: Tháng {month}, Ngày {day} | Số cổng đỗ: {num_gates}")
    print("=" * 80)

    df = pd.read_parquet(data_path)

    # -------------------------------------------------------------
    # BƯỚC 1: Lập lịch ban đầu (Initial Plan / Scheduled Gate)
    # Giả định lúc lên lịch (Day - 1), chưa có trễ (p_delay=0, delay=0)
    # -------------------------------------------------------------
    print("\n[BƯỚC 1] Lập lịch cổng ban đầu theo giờ lịch trình (Chưa phát sinh trễ)...")
    inst_static = oof_to_problem_instance(
        df,
        airport="ATL",
        month=month,
        day=day,
        num_gates=num_gates,
        auto_enrich=False,
    )
    for f in inst_static.flights:
        f.p_delay = 0.0
        f.delay_est_min = 0.0

    initial_assignment, status_init, time_init = solve_gate_assignment(inst_static, time_limit_sec=15)
    print(f"-> Đã phân bổ cổng ban đầu (current_gate) cho {len(initial_assignment)} chuyến (Status: {status_init}, {time_init:.2f}s)")

    # -------------------------------------------------------------
    # BƯỚC 2: Mô hình ML đưa ra dự báo trễ chuyến bay
    # Gán current_gate vào flights và nạp p_delay + delay_est_min
    # -------------------------------------------------------------
    print("\n[BƯỚC 2] Nạp dự báo trễ từ mô hình Machine Learning & Tái phân bổ với CP-SAT...")
    inst_dynamic = oof_to_problem_instance(
        df,
        airport="ATL",
        month=month,
        day=day,
        num_gates=num_gates,
        auto_enrich=False,
    )
    for f in inst_dynamic.flights:
        f.current_gate = initial_assignment.get(f.flight_id)

    # Giải bài toán tái phân bổ cổng
    reassigned_map, status_dyn, time_dyn, schedule_df = solve_gate_assignment(
        inst_dynamic,
        mode="worst_case",
        time_limit_sec=15,
        return_schedule=True,
    )

    n_reassigned = schedule_df["is_reassigned"].sum()
    n_kept = len(schedule_df) - n_reassigned

    print(f"-> Kết quả tối ưu: Trạng thái = {status_dyn} | Thời gian giải = {time_dyn:.2f}s")
    print(f"-> Số chuyến GIỮ NGUYÊN cổng ban đầu: {n_kept}/{len(schedule_df)} ({n_kept/len(schedule_df)*100:.1f}%)")
    print(f"-> Số chuyến ĐỔI SANG CỔNG MỚI:       {n_reassigned}/{len(schedule_df)} ({n_reassigned/len(schedule_df)*100:.1f}%)")

    # -------------------------------------------------------------
    # BƯỚC 3: Hiển thị bảng so sánh Cổng ban đầu vs Cổng mới
    # -------------------------------------------------------------
    print("\n" + "=" * 80)
    print("BẢNG SO SÁNH: CỔNG BAN ĐẦU (current_gate) VS CỔNG MỚI (assigned_gate)")
    print("=" * 80)

    display_cols = [
        "flight_id", "direction", "current_gate", "assigned_gate",
        "is_reassigned", "delay_est_min", "occupancy_start_min", "occupancy_end_min"
    ]

    # In các chuyến bị đổi cổng trước (nếu có)
    reassigned_flights = schedule_df[schedule_df["is_reassigned"]]
    if not reassigned_flights.empty:
        print("\nCác chuyến bay phải đổi cổng do xung đột trễ:")
        print(reassigned_flights[display_cols].to_string(index=False))

    print("\nMẫu các chuyến bay giữ nguyên cổng ban đầu:")
    kept_flights = schedule_df[~schedule_df["is_reassigned"]]
    print(kept_flights[display_cols].head(10).to_string(index=False))
    print("=" * 80)


if __name__ == "__main__":
    run_gate_reassignment_demo(month=10, day=8, num_gates=22)
