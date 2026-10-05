"""Audit and test all prediction files in src/artifacts/predictions/ for CP-SAT compatibility."""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Ensure UTF-8 output encoding for Windows terminal
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from src.optimization.oof_adapter import diagnose_oof, solve_from_oof_file


def run_prediction_audit() -> None:
    predictions_dir = PROJECT_ROOT / "src" / "artifacts" / "predictions"
    if not predictions_dir.exists():
        print(f"Error: Directory not found: {predictions_dir}")
        return

    files = sorted(predictions_dir.glob("*.parquet"))
    print("=" * 80)
    print("BÁO CÁO QUÉT TOÀN BỘ FILE DỰ BÁO TRONG src/artifacts/predictions/")
    print(f"Tổng số file phát hiện: {len(files)}")
    print("=" * 80)

    summary_rows = []

    for file_path in files:
        print(f"\n📂 File: {file_path.name}")
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        df = pd.read_parquet(file_path)
        diag = diagnose_oof(df)

        print(f"   - Kích thước: {df.shape[0]:,} dòng × {df.shape[1]} cột ({file_size_mb:.2f} MB)")
        print(f"   - Các cột: {df.columns.tolist()[:10]}{'...' if len(df.columns) > 10 else ''}")
        print(f"   - Đã có dự báo Đến (ARR): {'Có' if diag['has_arrival_predictions'] else 'Không'}")
        print(f"   - Đã có dự báo Đi (DEP):  {'Có' if diag['has_departure_predictions'] else 'Không'}")
        print(f"   - Đã có mốc lịch trình:   {'Có' if diag['has_schedule_info'] else 'Không'}")
        print(f"   - Có chiều sân bay (ATL): {'Có' if diag['has_airport_dimension'] else 'Không'}")

        # Thử nghiệm giải với CP-SAT nếu có đủ thông tin
        cpsat_status = "N/A"
        solve_time_sec = 0.0
        num_assigned = 0

        if diag["ready_for_cpsat"] and diag["has_schedule_info"]:
            try:
                start_t = time.perf_counter()
                res, status, wall_time = solve_from_oof_file(
                    file_path,
                    airport="ATL",
                    planning_date="2024-01-01",
                    num_gates=25,
                    time_limit_sec=10,
                    auto_enrich=False,
                )
                solve_time_sec = wall_time
                cpsat_status = status
                num_assigned = len(res)
                print(f"   - Kiểm thử CP-SAT (ATL ngày 01/01): ✅ {status} ({wall_time:.2f}s, đã xếp {num_assigned} chuyến)")
            except Exception as e:
                cpsat_status = f"Lỗi: {e}"
                print(f"   - Kiểm thử CP-SAT: ❌ {e}")
        else:
            print(f"   - Kiểm thử CP-SAT: ⚠️ Chưa đủ thông tin độc lập ({diag['recommendation']})")

        summary_rows.append({
            "File": file_path.name,
            "Dòng": f"{df.shape[0]:,}",
            "Cột": df.shape[1],
            "ARR Pred": "✓" if diag["has_arrival_predictions"] else "-",
            "DEP Pred": "✓" if diag["has_departure_predictions"] else "-",
            "Schedule": "✓" if diag["has_schedule_info"] else "-",
            "Airport": "✓" if diag["has_airport_dimension"] else "-",
            "CP-SAT Status": cpsat_status,
            "Solve Time": f"{solve_time_sec:.2f}s" if solve_time_sec > 0 else "-",
            "Assigned": num_assigned if num_assigned > 0 else "-",
        })

    # In bảng tổng hợp
    df_summary = pd.DataFrame(summary_rows)
    print("\n" + "=" * 80)
    print("BẢNG TỔNG HỢP TRẠNG THÁI SẴN SÀNG CHO CP-SAT")
    print("=" * 80)
    print(df_summary.to_string(index=False))
    print("=" * 80)


if __name__ == "__main__":
    run_prediction_audit()
