"""OOF Adapter: chuyển đổi file kết quả dự báo (OOF) từ bất kỳ mô hình ML nào sang CP-SAT.

Module này tự động:
1. Phát hiện format cột của file OOF (XGBoost, Random Forest, Linear, Hist Gradient Boosting, ...)
2. Nếu OOF thiếu cột lịch trình (CRS_DEP_TIME, CRS_ELAPSED_TIME) hoặc chain_id,
   tự động JOIN/enrich từ tabular_by_year và chain_members trong src/data/processed/
3. Chuyển đổi CRS_DEP_TIME (string dạng "0800") → phút kể từ 00:00
4. Trả về ProblemInstance sẵn sàng cho CP-SAT solver

Quy tắc bắt buộc:
- KHÔNG đưa nhãn thật (ARR_DELAY, DEP_DELAY) vào CP-SAT
- Chỉ sử dụng đầu ra dự báo (p_delay, delay_est_min) từ mô hình ML
"""

from __future__ import annotations

import logging
import sys
import warnings
from pathlib import Path
from typing import Any, Optional

# Ensure project root is in sys.path when executed directly as a script
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Ensure UTF-8 output encoding for Windows terminal
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import pandas as pd
import pyarrow.parquet as pq

from src.data.load_aeolus import resolve_project_root
from src.optimization.contracts import CostParams, Flight, Gate, ProblemInstance

logger = logging.getLogger(__name__)


# =====================================================================
# ÁNH XẠ CỘT LINH HOẠT (FLEXIBLE COLUMN MAPPING)
# =====================================================================
# Mỗi trường dữ liệu mà CP-SAT cần có danh sách tên cột ưu tiên.
# Adapter sẽ tìm theo thứ tự ưu tiên (trái → phải), dùng cột đầu tiên tìm thấy.

COLUMN_ALIASES: dict[str, list[str]] = {
    "flight_id": [
        "session_id", "flight_key", "flight_id", "FLIGHT_KEY", "FLIGHT_ID",
        "fl_key", "id", "flight_idx", "flight_index", "idx", "index",
    ],
    "p_delay": [
        "p_delay_max", "p_arr_delay_15", "p_dep_delay_15", "p_delay", "prob_delay", "xgb_prob",
        "pred_prob", "probability", "prob", "p_delay_15",
        "predicted_probability", "xgb_pred_prob",
    ],
    "delay_est_min": [
        "arr_delay_est_min", "dep_delay_est_min", "predicted_arr_delay_min", "predicted_dep_delay_min", "delay_est_min",
        "pred_arr_delay", "pred_dep_delay", "pred_delay", "pred_delay_min",
        "xgb_pred", "xgb_pred_delay", "predicted_delay", "predicted_delay_min",
        "regression_pred",
    ],
    "sched_time": [
        "sched_start_min", "sched_time_min", "pred_start_min", "CRS_DEP_TIME", "crs_dep_time",
        "CRS_ARR_TIME", "crs_arr_time", "scheduled_time",
        "departure_time", "arrival_time", "ARR_HOUR", "DEP_HOUR",
        "arr_hour", "dep_hour",
    ],
    "dwell_time": [
        "sched_duration_min", "pred_duration_min", "dwell_time_min", "CRS_ELAPSED_TIME", "crs_elapsed_time",
        "elapsed_time", "block_time",
    ],
    "chain_id": [
        "chain_group_id", "chain_id", "CHAIN_ID", "chain",
        "rotation_id", "turn_id",
    ],
    "direction": [
        "session_type", "direction", "DIRECTION", "dir", "flight_direction",
    ],
    "aircraft_type": [
        "aircraft_type", "AIRCRAFT_TYPE", "ac_type", "type",
    ],
    "current_gate": [
        "current_gate", "gate", "GATE", "assigned_gate",
    ],
    "turnaround_time": [
        "turnaround_time_min", "turnaround_time", "turnaround",
        "T_turnaround", "t_turnaround", "turn_time", "turn_time_min",
        "min_turnaround_time",
    ],
    "origin_airport": [
        "ORIGIN_AIRPORT", "origin_airport", "origin", "ORIGIN",
    ],
    "dest_airport": [
        "DEST_AIRPORT", "dest_airport", "destination", "DEST", "dest",
    ],
    "actual_delay": [
        "arr_true_delay_min", "dep_true_delay_min", "actual_delay_min",
        "y_true_arr_delay_min", "y_true_dep_delay_min", "ARR_DELAY", "DEP_DELAY",
    ],
    "month": [
        "MONTH", "month",
    ],
    "day": [
        "DAY", "day",
    ],
}


def _find_column(df: pd.DataFrame, field: str) -> Optional[str]:
    """Tìm tên cột thực tế trong DataFrame dựa trên danh sách alias."""
    aliases = COLUMN_ALIASES.get(field, [])
    for alias in aliases:
        if alias in df.columns:
            return alias
    return None


def _crs_time_str_to_minutes(time_val: object) -> int:
    """Chuyển CRS_DEP_TIME/CRS_ARR_TIME (dạng string "0800" hoặc số 800) → phút từ 00:00.

    Xử lý các format phổ biến trong dataset Aeolus:
    - String "0800" → 8*60 + 0 = 480
    - String "1430" → 14*60 + 30 = 870
    - String "2400" → 24*60 = 1440
    - Số nguyên 800 → 480
    - NaN/None → 0
    """
    if pd.isna(time_val):
        return 0
    try:
        time_str = str(time_val).strip()
        # Loại bỏ phần thập phân nếu có (VD: "800.0" → "800")
        if "." in time_str:
            time_str = time_str.split(".")[0]
        # Pad to 4 digits: "800" → "0800"
        time_str = time_str.zfill(4)
        hours = int(time_str[:2])
        minutes = int(time_str[2:])
        return hours * 60 + minutes
    except (ValueError, TypeError):
        return 0


def _parse_time_to_minutes(time_val: object, col_name: Optional[str] = None) -> int:
    """Chuyển đổi các định dạng thời gian lịch trình thành phút từ 00:00.

    Hỗ trợ:
    - ARR_HOUR / DEP_HOUR (số nguyên 0-23) → hour * 60
    - CRS_DEP_TIME / CRS_ARR_TIME (string "0800", int 800) → _crs_time_str_to_minutes
    - sched_time_min (phút từ 00:00) → int
    """
    if pd.isna(time_val):
        return 0
    if col_name and col_name.upper() in ("ARR_HOUR", "DEP_HOUR", "ARR_H", "DEP_H", "HOUR"):
        try:
            return int(float(time_val)) * 60
        except (ValueError, TypeError):
            return 0
    if col_name and "MIN" in col_name.upper() and not col_name.upper().startswith("CRS_"):
        try:
            return int(float(time_val))
        except (ValueError, TypeError):
            return 0
    return _crs_time_str_to_minutes(time_val)


# =====================================================================
# ENRICH: TỰ ĐỘNG JOIN TỪ DỮ LIỆU GỐC NẾU OOF THIẾU CỘT
# =====================================================================

def _load_tabular_columns(
    years: list[int],
    columns: list[str],
    project_root: Path,
) -> pd.DataFrame:
    """Đọc các cột cần thiết từ tabular_by_year (Hive-partitioned Parquet)."""
    base = project_root / "src" / "data" / "processed" / "tabular_by_year"
    frames = []
    for year in years:
        year_dir = base / f"year={year}"
        if not year_dir.exists():
            logger.warning("Không tìm thấy dữ liệu tabular cho năm %d", year)
            continue
        # Chỉ đọc các cột cần thiết để tiết kiệm bộ nhớ
        read_cols = ["flight_key"] + [c for c in columns if c != "flight_key"]
        try:
            df_year = pq.read_table(
                str(year_dir),
                columns=[c for c in read_cols if c in
                         pq.read_schema(str(year_dir / next(year_dir.iterdir()).name)).names],
            ).to_pandas()
            frames.append(df_year)
        except Exception as e:
            logger.warning("Lỗi khi đọc tabular năm %d: %s", year, e)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _load_chain_members(
    years: list[int],
    project_root: Path,
) -> pd.DataFrame:
    """Đọc chain_members từ flight_chain_reconstructed_v1."""
    base = project_root / "src" / "data" / "processed" / "flight_chain_reconstructed_v1" / "chain_members"
    frames = []
    for year in years:
        year_dir = base / f"year={year}"
        if not year_dir.exists():
            logger.warning("Không tìm thấy chain_members cho năm %d", year)
            continue
        try:
            df_year = pq.read_table(
                str(year_dir),
                columns=["flight_key", "chain_id"],
            ).to_pandas()
            frames.append(df_year)
        except Exception as e:
            logger.warning("Lỗi khi đọc chain_members năm %d: %s", year, e)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def enrich_oof_dataframe(
    df_oof: pd.DataFrame,
    project_root: Optional[Path] = None,
    enrich_schedule: bool = True,
    enrich_chain: bool = True,
) -> pd.DataFrame:
    """Bổ sung cột lịch trình và chain_id vào OOF DataFrame nếu thiếu.

    Parameters
    ----------
    df_oof : pd.DataFrame
        OOF DataFrame gốc từ XGBoost hoặc bất kỳ mô hình ML nào.
    project_root : Path, optional
        Đường dẫn gốc dự án. Nếu None, tự phát hiện.
    enrich_schedule : bool
        Có tự động JOIN lịch trình (CRS_DEP_TIME, CRS_ELAPSED_TIME) không.
    enrich_chain : bool
        Có tự động JOIN chain_id không.

    Returns
    -------
    pd.DataFrame
        DataFrame đã được bổ sung đầy đủ cột cho CP-SAT.
    """
    root = resolve_project_root(project_root)
    df = df_oof.copy()

    # Xác định flight_key column
    fk_col = _find_column(df, "flight_id")
    if fk_col is None:
        raise ValueError(
            f"OOF DataFrame không chứa cột flight_key/flight_id. "
            f"Các cột hiện có: {list(df.columns)}"
        )
    if fk_col != "flight_key":
        df = df.rename(columns={fk_col: "flight_key"})

    # Phát hiện năm từ flight_key hoặc validation_year/source_year
    years: list[int] = []
    if "validation_year" in df.columns:
        years = sorted(df["validation_year"].dropna().astype(int).unique().tolist())
    elif "source_year" in df.columns:
        years = sorted(df["source_year"].dropna().astype(int).unique().tolist())
    else:
        # Thử tất cả các năm development (2016-2023)
        years = list(range(2016, 2024))
        logger.info("Không phát hiện năm trong OOF, thử tất cả năm 2016-2023")

    # --- ENRICH SCHEDULE ---
    need_sched = enrich_schedule and _find_column(df, "sched_time") is None
    need_dwell = enrich_schedule and _find_column(df, "dwell_time") is None

    if need_sched or need_dwell:
        cols_to_load = []
        if need_sched:
            cols_to_load.append("CRS_DEP_TIME")
        if need_dwell:
            cols_to_load.append("CRS_ELAPSED_TIME")

        logger.info(
            "OOF thiếu cột %s — đang JOIN từ tabular_by_year...",
            cols_to_load,
        )
        df_tabular = _load_tabular_columns(years, cols_to_load, root)

        if not df_tabular.empty and "flight_key" in df_tabular.columns:
            # Loại bỏ trùng lặp flight_key (nếu có)
            df_tabular = df_tabular.drop_duplicates(subset=["flight_key"], keep="first")
            # Chỉ merge các cột chưa có
            merge_cols = ["flight_key"] + [c for c in cols_to_load if c in df_tabular.columns]
            df = df.merge(
                df_tabular[merge_cols],
                on="flight_key",
                how="left",
            )
            matched = df[cols_to_load[0]].notna().sum() if cols_to_load[0] in df.columns else 0
            logger.info(
                "JOIN thành công: %d/%d chuyến bay được bổ sung lịch trình",
                matched, len(df),
            )
        else:
            logger.warning("Không tìm thấy dữ liệu tabular_by_year để enrich")

    # --- ENRICH CHAIN ---
    if enrich_chain and _find_column(df, "chain_id") is None:
        logger.info("OOF thiếu cột chain_id — đang JOIN từ chain_members...")
        df_chain = _load_chain_members(years, root)

        if not df_chain.empty and "flight_key" in df_chain.columns:
            df_chain = df_chain.drop_duplicates(subset=["flight_key"], keep="first")
            df = df.merge(
                df_chain[["flight_key", "chain_id"]],
                on="flight_key",
                how="left",
            )
            matched = df["chain_id"].notna().sum()
            logger.info(
                "JOIN thành công: %d/%d chuyến bay được bổ sung chain_id",
                matched, len(df),
            )
        else:
            logger.warning("Không tìm thấy chain_members để enrich")

    return df


# =====================================================================
# CHUYỂN ĐỔI CHÍNH: OOF DataFrame → ProblemInstance
# =====================================================================

def oof_to_problem_instance(
    df_oof: pd.DataFrame,
    num_gates: int = 20,
    buffer_time_min: int = 15,
    default_dwell_time_min: int = 45,
    default_turnaround_time_min: int = 45,
    auto_enrich: bool = True,
    project_root: Optional[Path] = None,
    airport: Optional[str] = None,
    planning_date: Optional[str] = None,
    month: Optional[int] = None,
    day: Optional[int] = None,
    direction: Optional[str] = None,
    max_flights: Optional[int] = None,
    use_elapsed_as_dwell: bool = False,
) -> ProblemInstance:
    """Chuyển đổi OOF DataFrame từ bất kỳ mô hình ML nào sang ProblemInstance cho CP-SAT.

    Hỗ trợ tự động:
    - Phát hiện format cột (XGBoost, Random Forest, Linear, HGB, Unified Multi-Model, ...)
    - Tự động lọc theo Sân bay (airport) và Ngày (planning_date hoặc month/day)
    - Xử lý thông minh giờ lịch trình (ARR_HOUR / DEP_HOUR / CRS_DEP_TIME → phút từ 00:00)
    - JOIN từ dữ liệu gốc nếu thiếu cột lịch trình hoặc chain
    - Đảm bảo tính duy nhất của flight_id và tương thích 100% với CP-SAT

    Parameters
    ----------
    df_oof : pd.DataFrame
        OOF DataFrame từ bất kỳ mô hình ML nào.
    num_gates : int
        Số cổng đỗ trong sân bay mô phỏng.
    buffer_time_min : int
        Thời gian đệm an toàn giữa 2 chuyến (phút).
    default_dwell_time_min : int
        Thời gian đỗ mặc định nếu không có dữ liệu (hoặc khi CRS_ELAPSED_TIME là block flight time).
    default_turnaround_time_min : int
        Thời gian quay đầu mặc định (phút).
    auto_enrich : bool
        Tự động JOIN từ dữ liệu gốc nếu thiếu cột.
    project_root : Path, optional
        Đường dẫn gốc dự án.
    airport : Optional[str]
        Mã sân bay cần lập lịch (ví dụ "ATL"). Nếu dữ liệu chứa nhiều sân bay và > 500 dòng,
        adapter sẽ tự động lọc theo sân bay này (mặc định ATL nếu có).
    planning_date : Optional[str]
        Ngày lập lịch (dạng "YYYY-MM-DD" hoặc "2024-01-01").
    month : Optional[int]
        Tháng cần lọc (1-12).
    day : Optional[int]
        Ngày cần lọc (1-31).
    direction : Optional[str]
        Lọc chiều chuyến bay ("ARR" hoặc "DEP"). Nếu None, giữ cả hai.
    max_flights : Optional[int]
        Giới hạn số lượng chuyến bay tối đa đưa vào solver.
    use_elapsed_as_dwell : bool
        Nếu True, cho phép dùng CRS_ELAPSED_TIME làm dwell_time_min.
        Mặc định False (dùng default_dwell_time_min vì ELAPSED_TIME là thời gian bay trên không).

    Returns
    -------
    ProblemInstance
        Instance sẵn sàng cho CP-SAT solver.
    """
    df = df_oof.copy()

    # === BƯỚC 1: Validate cột dự báo bắt buộc ===
    p_col = _find_column(df, "p_delay")
    delay_col = _find_column(df, "delay_est_min")

    if p_col is None and delay_col is None:
        raise ValueError(
            f"OOF DataFrame phải chứa ít nhất 1 cột dự báo "
            f"(xác suất trễ hoặc số phút trễ ước tính). "
            f"Các cột hiện có: {list(df.columns)}. "
            f"Tên cột được hỗ trợ: {COLUMN_ALIASES['p_delay'] + COLUMN_ALIASES['delay_est_min']}"
        )

    # Cảnh báo nếu chỉ có 1 trong 2 cột dự báo
    if p_col is None:
        warnings.warn(
            "OOF thiếu cột xác suất trễ (p_delay / p_arr_delay_15 / p_dep_delay_15). "
            "CP-SAT sẽ dùng mặc định p_delay=0.5 cho tất cả chuyến bay.",
            UserWarning,
            stacklevel=2,
        )
    if delay_col is None:
        warnings.warn(
            "OOF thiếu cột số phút trễ ước tính (predicted_arr_delay_min / delay_est_min). "
            "CP-SAT sẽ dùng mặc định delay_est_min=0.0 cho tất cả chuyến bay.",
            UserWarning,
            stacklevel=2,
        )

    # === BƯỚC 2: Lọc theo Sân bay và Thời gian (Airport & Scenario Slicing) ===
    orig_col = _find_column(df, "origin_airport")
    dest_col = _find_column(df, "dest_airport")
    month_col = _find_column(df, "month")
    day_col = _find_column(df, "day")

    # Phân tích planning_date nếu có
    if planning_date:
        parts = planning_date.split("-")
        if len(parts) == 3:
            if month is None:
                try:
                    month = int(parts[1])
                except ValueError:
                    pass
            if day is None:
                try:
                    day = int(parts[2])
                except ValueError:
                    pass

    # Lọc theo Month và Day nếu có
    if month is not None and month_col is not None and month_col in df.columns:
        df = df[df[month_col] == month]
    if day is not None and day_col is not None and day_col in df.columns:
        df = df[df[day_col] == day]

    # Nếu DataFrame lớn (> 500 dòng) và chưa có bộ lọc airport/date:
    # Tự động chọn airport mục tiêu (ATL nếu có) và ngày đầu tiên để bảo đảm CP-SAT giải hiệu quả
    if len(df) > 500:
        if airport is None:
            if dest_col and (df[dest_col] == "ATL").any():
                airport = "ATL"
            elif orig_col and (df[orig_col] == "ATL").any():
                airport = "ATL"
            elif dest_col and not df[dest_col].empty:
                airport = str(df[dest_col].mode().iloc[0])
            if airport:
                logger.info("Tự động chọn airport='%s' cho tập dữ liệu lớn (%d chuyến bay)", airport, len(df))

        if month is None and month_col and month_col in df.columns and not df.empty:
            month = int(df[month_col].iloc[0])
            df = df[df[month_col] == month]
            logger.info("Tự động chọn month=%d", month)

        if day is None and day_col and day_col in df.columns and not df.empty:
            day = int(df[day_col].iloc[0])
            df = df[df[day_col] == day]
            logger.info("Tự động chọn day=%d", day)

    # Lọc theo Airport
    if airport is not None:
        airport_code = airport.upper()
        if dest_col and orig_col and dest_col in df.columns and orig_col in df.columns:
            if direction == "ARR":
                df = df[df[dest_col] == airport_code]
            elif direction == "DEP":
                df = df[df[orig_col] == airport_code]
            else:
                df = df[(df[dest_col] == airport_code) | (df[orig_col] == airport_code)]
        elif dest_col and dest_col in df.columns:
            df = df[df[dest_col] == airport_code]
        elif orig_col and orig_col in df.columns:
            df = df[df[orig_col] == airport_code]

    # Giới hạn max_flights nếu có
    if max_flights is not None and len(df) > max_flights:
        df = df.head(max_flights)

    if df.empty:
        raise ValueError(
            f"Không có chuyến bay nào phù hợp với bộ lọc: "
            f"airport={airport}, month={month}, day={day}, direction={direction}"
        )

    # === BƯỚC 3: Auto-enrich nếu thiếu cột lịch trình/chain ===
    if auto_enrich:
        df = enrich_oof_dataframe(df, project_root=project_root)

    # === BƯỚC 4: Phân giải cột và chuyển đổi giá trị ===
    fk_col = _find_column(df, "flight_id") or "flight_key"
    p_col = _find_column(df, "p_delay")
    delay_col = _find_column(df, "delay_est_min")
    sched_col = _find_column(df, "sched_time")
    dwell_col = _find_column(df, "dwell_time")
    chain_col = _find_column(df, "chain_id")
    dir_col = _find_column(df, "direction")
    gate_col = _find_column(df, "current_gate")
    turnaround_col = _find_column(df, "turnaround_time")

    mapping_report = {
        "flight_id": fk_col,
        "p_delay": p_col,
        "delay_est_min": delay_col,
        "sched_time": sched_col,
        "dwell_time": dwell_col,
        "chain_id": chain_col,
        "direction": dir_col,
        "current_gate": gate_col,
        "turnaround_time": turnaround_col,
        "filtered_rows": len(df),
    }
    logger.info("Column mapping: %s", mapping_report)

    # Tự động suy luận chiều chuyến bay từ chain nếu có
    chain_flight_dir: dict[Any, str] = {}
    if dir_col is None and chain_col is not None and sched_col is not None:
        chain_groups = df[df[chain_col].notna()].groupby(chain_col)
        for _, group in chain_groups:
            if len(group) == 2:
                sorted_indices = group.sort_values(sched_col).index.tolist()
                chain_flight_dir[sorted_indices[0]] = "ARR"
                chain_flight_dir[sorted_indices[1]] = "DEP"

    # === BƯỚC 5: Tạo Flight objects ===
    flights: list[Flight] = []
    seen_flight_ids: set[str] = set()

    for idx, row in df.iterrows():
        # Xác định chiều chuyến bay (direction)
        if "session_type" in row and pd.notna(row["session_type"]):
            st = str(row["session_type"])
            if st == "PAIRED_TURN":
                direction_i = "TURN"
            elif st == "UNMATCHED_ARR":
                direction_i = "ARR"
            elif st == "UNMATCHED_DEP":
                direction_i = "DEP"
            else:
                direction_i = "TURN"
        elif direction is not None:
            direction_i = direction
        elif dir_col is not None and pd.notna(row.get(dir_col)):
            direction_i = str(row.get(dir_col))
        elif dest_col and airport and row.get(dest_col) == airport.upper():
            direction_i = "ARR"
        elif orig_col and airport and row.get(orig_col) == airport.upper():
            direction_i = "DEP"
        elif idx in chain_flight_dir:
            direction_i = chain_flight_dir[idx]
        elif "ARR_HOUR" in row and "DEP_HOUR" not in row:
            direction_i = "ARR"
        elif "DEP_HOUR" in row and "ARR_HOUR" not in row:
            direction_i = "DEP"
        else:
            direction_i = "ARR"

        # Flight ID chuẩn hoá
        raw_fid = row.get(fk_col)
        if pd.isna(raw_fid):
            f_id = f"FL_{idx:04d}"
        elif isinstance(raw_fid, float) and raw_fid.is_integer():
            f_id = str(int(raw_fid))
        else:
            f_id = str(raw_fid)

        if f_id in seen_flight_ids:
            f_id = f"{f_id}_{direction_i}"
        if f_id in seen_flight_ids:
            f_id = f"{f_id}_{idx}"
        seen_flight_ids.add(f_id)

        # Xác suất trễ (ưu tiên đúng theo chiều ARR/DEP nếu có)
        if direction_i == "DEP" and "p_dep_delay_15" in row and pd.notna(row["p_dep_delay_15"]):
            raw_p = float(row["p_dep_delay_15"])
        elif direction_i == "ARR" and "p_arr_delay_15" in row and pd.notna(row["p_arr_delay_15"]):
            raw_p = float(row["p_arr_delay_15"])
        elif p_col is not None and pd.notna(row.get(p_col)):
            raw_p = float(row.get(p_col))
        else:
            raw_p = 0.5
        prob_delay = max(0.0, min(1.0, raw_p))

        # Số phút trễ ước tính (ưu tiên đúng theo chiều ARR/DEP nếu có)
        if direction_i == "DEP" and "predicted_dep_delay_min" in row and pd.notna(row["predicted_dep_delay_min"]):
            raw_delay = float(row["predicted_dep_delay_min"])
        elif direction_i == "ARR" and "predicted_arr_delay_min" in row and pd.notna(row["predicted_arr_delay_min"]):
            raw_delay = float(row["predicted_arr_delay_min"])
        elif delay_col is not None and pd.notna(row.get(delay_col)):
            raw_delay = float(row.get(delay_col))
        else:
            raw_delay = 0.0
        delay_est = raw_delay

        # Giờ lịch trình (phút từ 00:00)
        if direction_i == "ARR" and "ARR_HOUR" in row and pd.notna(row["ARR_HOUR"]):
            sched_time = int(float(row["ARR_HOUR"])) * 60
        elif direction_i == "DEP" and "DEP_HOUR" in row and pd.notna(row["DEP_HOUR"]):
            sched_time = int(float(row["DEP_HOUR"])) * 60
        elif sched_col is not None:
            raw_sched = row.get(sched_col)
            sched_time = _parse_time_to_minutes(raw_sched, sched_col)
        else:
            sched_time = 0

        # Thời gian đỗ tại cổng
        if dwell_col is not None:
            raw_dwell = row.get(dwell_col)
            if dwell_col in ("CRS_ELAPSED_TIME", "crs_elapsed_time", "elapsed_time", "block_time") and not use_elapsed_as_dwell:
                dwell_time = default_dwell_time_min
            else:
                dwell_time = int(float(raw_dwell)) if pd.notna(raw_dwell) and float(raw_dwell) > 0 else default_dwell_time_min
        else:
            dwell_time = default_dwell_time_min

        # Chain group
        if chain_col is not None:
            chain_val = row.get(chain_col)
            chain_group_id = str(chain_val) if pd.notna(chain_val) else None
        else:
            chain_group_id = None

        # Current gate
        if gate_col is not None:
            cur_gate = row.get(gate_col)
            current_gate = str(cur_gate) if pd.notna(cur_gate) else None
        else:
            current_gate = None

        # Turnaround time
        if turnaround_col is not None:
            raw_turn = row.get(turnaround_col)
            turnaround_time = int(float(raw_turn)) if pd.notna(raw_turn) and float(raw_turn) > 0 else None
        else:
            turnaround_time = None

        # Actual ground truth delay (chỉ phục vụ đánh giá hậu kiểm và đối chứng báo cáo)
        actual_delay = None
        if "arr_true_delay_min" in row and direction_i != "DEP" and pd.notna(row["arr_true_delay_min"]):
            actual_delay = float(row["arr_true_delay_min"])
        elif "dep_true_delay_min" in row and direction_i == "DEP" and pd.notna(row["dep_true_delay_min"]):
            actual_delay = float(row["dep_true_delay_min"])
        elif direction_i == "DEP" and "y_true_dep_delay_min" in row and pd.notna(row["y_true_dep_delay_min"]):
            actual_delay = float(row["y_true_dep_delay_min"])
        elif direction_i != "DEP" and "y_true_arr_delay_min" in row and pd.notna(row["y_true_arr_delay_min"]):
            actual_delay = float(row["y_true_arr_delay_min"])
        elif "DEP_DELAY" in row and direction_i == "DEP" and pd.notna(row["DEP_DELAY"]):
            actual_delay = float(row["DEP_DELAY"])
        elif "ARR_DELAY" in row and pd.notna(row["ARR_DELAY"]):
            actual_delay = float(row["ARR_DELAY"])

        ac_type = str(row.get("aircraft_type", row.get("AIRCRAFT_TYPE", "ALL"))) if pd.notna(row.get("aircraft_type", row.get("AIRCRAFT_TYPE"))) else "ALL"

        flight = Flight(
            flight_id=f_id,
            direction=direction_i,
            sched_time_min=sched_time,
            dwell_time_min=dwell_time,
            delay_est_min=delay_est,
            p_delay=prob_delay,
            aircraft_type=ac_type,
            current_gate=current_gate,
            chain_group_id=chain_group_id,
            turnaround_time_min=turnaround_time,
            actual_delay_min=actual_delay,
        )
        flights.append(flight)

    # === BƯỚC 6: Tạo Gates mô phỏng ===
    gates: list[Gate] = []
    for j in range(1, num_gates + 1):
        gates.append(Gate(
            gate_id=f"G{j:02d}",
            compatible_types=["ALL"],
            available_from_min=0,
            available_to_min=1440 * 2,  # 2 ngày (cho phép chuyến bay qua đêm)
        ))

    cost_params = CostParams(
        buffer_time_min=buffer_time_min,
        default_turnaround_time_min=default_turnaround_time_min,
    )

    actual_airport = airport or "ATL"
    actual_planning_date = planning_date or "2024-01-01"
    if month and day:
        actual_planning_date = f"2024-{month:02d}-{day:02d}"

    logger.info(
        "Chuyển đổi thành công: %d chuyến bay, %d cổng, airport=%s, date=%s",
        len(flights), len(gates), actual_airport, actual_planning_date,
    )

    return ProblemInstance(
        airport=actual_airport,
        planning_date=actual_planning_date,
        flights=flights,
        gates=gates,
        cost_params=cost_params,
    )


# =====================================================================
# TIỆN ÍCH: ĐỌC FILE VÀ GIẢI TRỰC TIẾP
# =====================================================================

def solve_from_oof_file(
    oof_path: str | Path,
    num_gates: int = 20,
    buffer_time_min: int = 15,
    mode: str = "expected",
    time_limit_sec: int = 60,
    auto_enrich: bool = True,
    project_root: Optional[Path] = None,
    use_turnaround: bool = False,
    default_turnaround_time_min: int = 45,
    return_schedule: bool = False,
    airport: Optional[str] = None,
    planning_date: Optional[str] = None,
    month: Optional[int] = None,
    day: Optional[int] = None,
    direction: Optional[str] = None,
    max_flights: Optional[int] = None,
    use_elapsed_as_dwell: bool = False,
) -> tuple[dict[str, str], str, float] | Any:
    """Đọc file OOF (Parquet/CSV) và giải bài toán gate assignment bằng CP-SAT.

    Đây là entry point đơn giản nhất — chỉ cần trỏ đến file OOF.

    Parameters
    ----------
    oof_path : str | Path
        Đường dẫn tới file OOF (.parquet hoặc .csv).
    num_gates : int
        Số cổng đỗ sân bay mô phỏng.
    buffer_time_min : int
        Thời gian đệm giữa 2 chuyến (phút).
    mode : str
        Chế độ tính occupancy: "expected", "worst_case".
    time_limit_sec : int
        Giới hạn thời gian giải CP-SAT (giây).
    auto_enrich : bool
        Tự động JOIN cột thiếu từ dữ liệu gốc.
    project_root : Path, optional
        Đường dẫn gốc dự án.
    use_turnaround : bool
        Kích hoạt tính toán thời gian quay đầu để tính thời gian cất cánh.
    default_turnaround_time_min : int
        Thời gian quay đầu mặc định (phút).
    return_schedule : bool
        Có trả về lịch chi tiết hay không.
    airport : Optional[str]
        Lọc theo sân bay đích/nguồn (ví dụ "ATL").
    planning_date : Optional[str]
        Ngày lập lịch (ví dụ "2024-01-01").
    month : Optional[int]
        Lọc theo tháng (1-12).
    day : Optional[int]
        Lọc theo ngày (1-31).
    direction : Optional[str]
        Lọc theo chiều ("ARR" hoặc "DEP").
    max_flights : Optional[int]
        Giới hạn số chuyến bay tối đa.
    use_elapsed_as_dwell : bool
        Có dùng CRS_ELAPSED_TIME làm dwell time không.

    Returns
    -------
    GateAssignmentResult hoặc tuple
        (assignment, solver_status, wall_time) hoặc (assignment, solver_status, wall_time, schedule_df)
    """
    from src.optimization.cp_sat_solver import solve_gate_assignment

    oof_path = Path(oof_path)
    logger.info("Đọc OOF file: %s", oof_path)

    if oof_path.suffix == ".parquet":
        df = pd.read_parquet(str(oof_path))
    elif oof_path.suffix in (".csv", ".tsv"):
        sep = "\t" if oof_path.suffix == ".tsv" else ","
        df = pd.read_csv(str(oof_path), sep=sep)
    else:
        raise ValueError(f"Định dạng file không được hỗ trợ: {oof_path.suffix}")

    logger.info("OOF shape: %s, columns: %s", df.shape, list(df.columns))

    instance = oof_to_problem_instance(
        df_oof=df,
        num_gates=num_gates,
        buffer_time_min=buffer_time_min,
        default_turnaround_time_min=default_turnaround_time_min,
        auto_enrich=auto_enrich,
        project_root=project_root,
        airport=airport,
        planning_date=planning_date,
        month=month,
        day=day,
        direction=direction,
        max_flights=max_flights,
        use_elapsed_as_dwell=use_elapsed_as_dwell,
    )

    return solve_gate_assignment(
        instance=instance,
        time_limit_sec=time_limit_sec,
        mode=mode,
        use_turnaround=use_turnaround,
        default_turnaround_time_min=default_turnaround_time_min,
        return_schedule=return_schedule,
    )


def diagnose_oof(df: pd.DataFrame) -> dict[str, object]:
    """Chẩn đoán nhanh OOF DataFrame — liệt kê cột nào tìm thấy, cột nào thiếu.

    Hữu ích để kiểm tra trước khi chạy CP-SAT.

    Returns
    -------
    dict
        Báo cáo chẩn đoán chi tiết.
    """
    report: dict[str, object] = {
        "shape": df.shape,
        "columns": list(df.columns),
        "column_mapping": {},
        "missing_fields": [],
        "ready_for_cpsat": True,
        "enrich_needed": False,
        "has_arrival_predictions": False,
        "has_departure_predictions": False,
        "has_schedule_info": False,
        "has_airport_dimension": False,
        "recommendation": "",
    }

    for field, aliases in COLUMN_ALIASES.items():
        found = _find_column(df, field)
        if found:
            report["column_mapping"][field] = found  # type: ignore[index]
        else:
            report["missing_fields"].append(field)  # type: ignore[union-attr]

    # Kiểm tra các chiều dự báo
    if "p_arr_delay_15" in df.columns or "predicted_arr_delay_min" in df.columns:
        report["has_arrival_predictions"] = True
    if "p_dep_delay_15" in df.columns or "predicted_dep_delay_min" in df.columns:
        report["has_departure_predictions"] = True
    if any(c in df.columns for c in ("sched_time_min", "CRS_DEP_TIME", "CRS_ARR_TIME", "ARR_HOUR", "DEP_HOUR")):
        report["has_schedule_info"] = True
    if "ORIGIN_AIRPORT" in df.columns or "DEST_AIRPORT" in df.columns:
        report["has_airport_dimension"] = True

    # Kiểm tra bắt buộc
    if "flight_id" in report["missing_fields"]:
        report["ready_for_cpsat"] = False

    p_missing = "p_delay" in report["missing_fields"]
    d_missing = "delay_est_min" in report["missing_fields"]
    if p_missing and d_missing:
        report["ready_for_cpsat"] = False

    # Kiểm tra cần enrich
    if "sched_time" in report["missing_fields"] or "chain_id" in report["missing_fields"]:
        report["enrich_needed"] = True

    # Tạo recommendation
    if not report["ready_for_cpsat"]:
        report["recommendation"] = "Tệp thiếu cột định danh chuyến bay hoặc toàn bộ cột dự báo ML."
    elif report["has_airport_dimension"] and df.shape[0] > 500:
        report["recommendation"] = "Sẵn sàng cho CP-SAT (khuyến nghị truyền tham số airport='ATL' và planning_date='YYYY-MM-DD')."
    elif report["enrich_needed"] and not report["has_schedule_info"]:
        report["recommendation"] = "Cần auto-enrich lịch trình từ dữ liệu gốc trước khi giải."
    else:
        report["recommendation"] = "Sẵn sàng giải trực tiếp với CP-SAT."

    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    print("=" * 75)
    print("      AEOLUS OOF ADAPTER - TEST CHẠY TRỰC TIẾP TỆP DỰ BÁO VỚI CP-SAT")
    print("=" * 75)

    test_file = PROJECT_ROOT / "src" / "artifacts" / "predictions" / "full_turn_unified_predictions_for_cpsat.parquet"
    if test_file.exists():
        print(f"-> Đang nạp và giải kịch bản từ: {test_file.name}")
        assignment, status, wall_time = solve_from_oof_file(
            test_file,
            airport="ATL",
            planning_date="2024-01-01",
            num_gates=25,
            time_limit_sec=10,
            auto_enrich=False,
        )
        print(f"-> Kết quả: Status = {status} | Thời gian giải = {wall_time:.2f}s | Đã xếp cổng = {len(assignment)} chuyến bay")
        print("=" * 75)
    else:
        print(f"Không tìm thấy file: {test_file}")
