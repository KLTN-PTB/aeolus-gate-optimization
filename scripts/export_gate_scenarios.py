"""Export and standardize gate scheduling scenarios for CP-SAT and heuristic solvers.

This script implements the improvements outlined in docs/evaluations_and_improvements/prediction_artifact_improvements.md:
1. Recovers canonical flight keys and exact minute-level schedule times (CRS_DEP_TIME, CRS_ARR_TIME).
2. Generates turnaround chain groups and simulated aircraft types (Narrowbody / Widebody).
3. Produces standard CP-SAT scenario datasets for benchmark days (Typical, Peak, Disruption) at ATL.
4. Adheres to the Simulation Safety Guard: Excludes ground-truth delay labels from solver inputs,
   while storing ground truth separately for post-hoc robustness evaluation.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Final

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

REPO_ROOT: Final = Path(__file__).resolve().parent.parent
PREDICTIONS_DIR: Final = REPO_ROOT / "src" / "artifacts" / "predictions"
PROCESSED_2024_DIR: Final = REPO_ROOT / "src" / "data" / "processed" / "tabular_by_year" / "year=2024"
SCENARIOS_DIR: Final = REPO_ROOT / "src" / "artifacts" / "scenarios"
GROUND_TRUTH_DIR: Final = SCENARIOS_DIR / "ground_truth"


def parse_minute_of_day(time_str_series: pd.Series) -> pd.Series:
    """Convert timestamp strings like '2024-01-01 12:52:00' to minute of day (0..1439)."""
    # Extract HH:MM
    hh = time_str_series.str.slice(11, 13).astype(int)
    mm = time_str_series.str.slice(14, 16).astype(int)
    return (hh * 60 + mm).astype(np.int16)


def assign_aircraft_properties(flight_keys: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Deterministically assign aircraft_type, turnaround_time, and dwell_time based on flight_key hash.

    Distribution:
    - ~85% NARROWBODY (turnaround: 40 min, dwell: 45 min)
    - ~15% WIDEBODY   (turnaround: 75 min, dwell: 60 min)
    """
    types = []
    turnarounds = []
    dwells = []

    for k in flight_keys:
        # Use first 4 hex digits of md5 hash modulo 100
        val = int(hashlib.md5(k.encode("utf-8")).hexdigest()[:4], 16) % 100
        if val < 85:
            types.append("NARROWBODY")
            turnarounds.append(40)
            dwells.append(45)
        else:
            types.append("WIDEBODY")
            turnarounds.append(75)
            dwells.append(60)

    return (
        pd.Series(types, index=flight_keys.index, dtype="string"),
        pd.Series(turnarounds, index=flight_keys.index, dtype=np.int16),
        pd.Series(dwells, index=flight_keys.index, dtype=np.int16),
    )


def load_raw_2024_matching_sample(sample_size: int = 1_000_000) -> pd.DataFrame:
    """Load and clean raw 2024 tabular records to match the 1M row sample of predictions."""
    files = sorted(PROCESSED_2024_DIR.glob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"Không tìm thấy file 2024 parquet tại: {PROCESSED_2024_DIR}")

    logger.info("Đang đọc và làm sạch dữ liệu gốc 2024 từ %d files...", len(files))
    cols = [
        "flight_key", "FL_DATE", "OP_CARRIER", "OP_CARRIER_FL_NUM", "ORIGIN", "DEST",
        "CRS_DEP_TIME", "CRS_ARR_TIME", "CRS_ELAPSED_TIME", "DEP_DELAY", "ARR_DELAY",
        "MONTH", "DAY_OF_MONTH", "DAY_OF_WEEK",
        "O_LATITUDE", "O_LONGITUDE", "D_LATITUDE", "D_LONGITUDE"
    ]

    clean_chunks = []
    accumulated = 0

    for f in files:
        df = pd.read_parquet(f, columns=cols)
        # Apply standard Aeolus cleaning filter
        c = df.dropna(subset=["CRS_ELAPSED_TIME", "ARR_DELAY", "DEP_DELAY", "CRS_DEP_TIME", "CRS_ARR_TIME"])
        valid_mask = (
            (c["CRS_ELAPSED_TIME"] > 0) &
            (c["ARR_DELAY"] >= -300) & (c["ARR_DELAY"] <= 2000) &
            (c["DEP_DELAY"] >= -300) & (c["DEP_DELAY"] <= 2000) &
            (c["O_LATITUDE"] >= -90) & (c["O_LATITUDE"] <= 90) &
            (c["O_LONGITUDE"] >= -180) & (c["O_LONGITUDE"] <= 180) &
            (c["D_LATITUDE"] >= -90) & (c["D_LATITUDE"] <= 90) &
            (c["D_LONGITUDE"] >= -180) & (c["D_LONGITUDE"] <= 180)
        )
        chunk_clean = c[valid_mask]
        clean_chunks.append(chunk_clean)
        accumulated += len(chunk_clean)
        if accumulated >= sample_size:
            break

    df_clean = pd.concat(clean_chunks, ignore_index=True).iloc[:sample_size]
    logger.info("-> Đã khớp thành công %d dòng dữ liệu gốc 2024.", len(df_clean))
    return df_clean


def build_atl_scenarios() -> None:
    """Build enriched predictions and standardized scenario files for CP-SAT."""
    SCENARIOS_DIR.mkdir(parents=True, exist_ok=True)
    GROUND_TRUTH_DIR.mkdir(parents=True, exist_ok=True)

    pred_path = PREDICTIONS_DIR / "full_turn_unified_predictions_for_cpsat.parquet"
    if not pred_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file dự báo: {pred_path}")

    logger.info("1. Đang nạp tệp dự báo: %s", pred_path.name)
    df_pred = pd.read_parquet(pred_path)
    sample_size = len(df_pred)

    logger.info("2. Nạp và làm giàu dữ liệu định danh từ kho 2024...")
    df_raw = load_raw_2024_matching_sample(sample_size=sample_size)

    # Verification of 1:1 match
    assert (df_raw["MONTH"] == df_pred["MONTH"]).all(), "Month mismatch between predictions and raw sample!"
    assert (df_raw["DAY_OF_MONTH"] == df_pred["DAY"]).all(), "Day mismatch between predictions and raw sample!"
    logger.info("✓ Khớp dữ liệu 100% giữa dự báo ML và bảng gốc.")

    # 3. Filter for ATL flights (both Arrivals and Departures)
    atl_arr_mask = (df_raw["DEST"] == "ATL")
    atl_dep_mask = (df_raw["ORIGIN"] == "ATL")
    atl_mask = atl_arr_mask | atl_dep_mask

    logger.info("Tổng số chuyến bay liên quan đến ATL: %d", atl_mask.sum())

    # Build standardized Arrival records at ATL
    df_arr = pd.DataFrame({
        "flight_key": df_raw.loc[atl_arr_mask, "flight_key"].values,
        "airport": "ATL",
        "direction": "ARR",
        "fl_date": df_raw.loc[atl_arr_mask, "FL_DATE"].str.slice(0, 10).values,
        "carrier": df_raw.loc[atl_arr_mask, "OP_CARRIER"].values,
        "fl_num": df_raw.loc[atl_arr_mask, "OP_CARRIER_FL_NUM"].values,
        "origin": df_raw.loc[atl_arr_mask, "ORIGIN"].values,
        "dest": "ATL",
        "sched_time_min": parse_minute_of_day(df_raw.loc[atl_arr_mask, "CRS_ARR_TIME"]).values,
        "p_delay": df_pred.loc[atl_arr_mask, "p_arr_delay_15"].astype(np.float32).values,
        "delay_est_min": df_pred.loc[atl_arr_mask, "predicted_arr_delay_min"].astype(np.float32).values,
        "chain_group_id": (
            df_raw.loc[atl_arr_mask, "FL_DATE"].str.slice(0, 10) + "_" +
            df_raw.loc[atl_arr_mask, "OP_CARRIER"].astype(str) + "_" +
            df_raw.loc[atl_arr_mask, "OP_CARRIER_FL_NUM"].astype(str)
        ).values,
        # Ground truth kept for separate evaluation file
        "y_true_delay_min": df_pred.loc[atl_arr_mask, "y_true_arr_delay_min"].astype(np.float32).values,
    })

    # Build standardized Departure records at ATL
    df_dep = pd.DataFrame({
        "flight_key": df_raw.loc[atl_dep_mask, "flight_key"].values,
        "airport": "ATL",
        "direction": "DEP",
        "fl_date": df_raw.loc[atl_dep_mask, "FL_DATE"].str.slice(0, 10).values,
        "carrier": df_raw.loc[atl_dep_mask, "OP_CARRIER"].values,
        "fl_num": df_raw.loc[atl_dep_mask, "OP_CARRIER_FL_NUM"].values,
        "origin": "ATL",
        "dest": df_raw.loc[atl_dep_mask, "DEST"].values,
        "sched_time_min": parse_minute_of_day(df_raw.loc[atl_dep_mask, "CRS_DEP_TIME"]).values,
        "p_delay": df_pred.loc[atl_dep_mask, "p_dep_delay_15"].astype(np.float32).values,
        "delay_est_min": df_pred.loc[atl_dep_mask, "predicted_dep_delay_min"].astype(np.float32).values,
        "chain_group_id": (
            df_raw.loc[atl_dep_mask, "FL_DATE"].str.slice(0, 10) + "_" +
            df_raw.loc[atl_dep_mask, "OP_CARRIER"].astype(str) + "_" +
            df_raw.loc[atl_dep_mask, "OP_CARRIER_FL_NUM"].astype(str)
        ).values,
        # Ground truth kept for separate evaluation file
        "y_true_delay_min": df_pred.loc[atl_dep_mask, "y_true_dep_delay_min"].astype(np.float32).values,
    })

    # Combine into unified ATL dataset
    df_atl_all = pd.concat([df_arr, df_dep], ignore_index=True)
    df_atl_all = df_atl_all.sort_values(by=["fl_date", "sched_time_min"]).reset_index(drop=True)

    # Assign aircraft type and operational times
    ac_types, turnarounds, dwells = assign_aircraft_properties(df_atl_all["flight_key"])
    df_atl_all["aircraft_type"] = ac_types
    df_atl_all["turnaround_time_min"] = turnarounds
    df_atl_all["dwell_time_min"] = dwells

    logger.info("3. Tạo các tệp kịch bản chuẩn cho CP-SAT theo nguyên tắc an toàn (Simulation Safety Guard)...")

    # Define standard scenario benchmark dates
    scenarios_meta = [
        ("atl_2024_01_01_typical_day.parquet", "2024-01-01", "Kịch bản Ngày thường (Typical Day)"),
        ("atl_2024_01_15_winter_disruption.parquet", "2024-01-15", "Kịch bản Bão tuyết/Gián đoạn (Winter Disruption)"),
        ("atl_2024_07_04_peak_holiday.parquet", "2024-07-04", "Kịch bản Cao điểm Lễ Độc lập (Peak Summer Holiday)"),
    ]

    target_columns = [
        "flight_key", "airport", "direction", "fl_date", "carrier", "fl_num", "origin", "dest",
        "sched_time_min", "p_delay", "delay_est_min", "chain_group_id",
        "aircraft_type", "turnaround_time_min", "dwell_time_min"
    ]

    for fname, date_str, desc in scenarios_meta:
        sub = df_atl_all[df_atl_all["fl_date"] == date_str].copy().reset_index(drop=True)
        if sub.empty:
            logger.warning("Không có chuyến bay nào cho ngày %s!", date_str)
            continue

        # Safe CP-SAT input (NO y_true to prevent leakage)
        cpsat_input = sub[target_columns].copy()
        out_path = SCENARIOS_DIR / fname
        cpsat_input.to_parquet(out_path, index=False)

        # Ground truth evaluation file (for post-hoc verification)
        gt_path = GROUND_TRUTH_DIR / fname.replace(".parquet", "_ground_truth.parquet")
        sub[["flight_key", "direction", "fl_date", "sched_time_min", "y_true_delay_min"]].to_parquet(gt_path, index=False)

        logger.info("  ✓ Đã xuất %s (%d chuyến) -> %s", desc, len(cpsat_input), out_path.name)

    # Also export full ATL 2024 enriched dataset
    full_atl_out = SCENARIOS_DIR / "atl_gate_scheduling_full_2024_enriched.parquet"
    df_atl_all[target_columns].to_parquet(full_atl_out, index=False)
    logger.info("  ✓ Đã xuất toàn bộ dữ liệu ATL làm giàu: %s (%d chuyến)", full_atl_out.name, len(df_atl_all))

    # Also export the full 1M unified predictions with minutes and canonical keys
    logger.info("4. Xuất tệp full_turn_unified_predictions_minute_granularity.parquet...")
    df_full_enriched = df_pred.copy()
    df_full_enriched["flight_key"] = df_raw["flight_key"].values
    df_full_enriched["sched_dep_min"] = parse_minute_of_day(df_raw["CRS_DEP_TIME"]).values
    df_full_enriched["sched_arr_min"] = parse_minute_of_day(df_raw["CRS_ARR_TIME"]).values
    df_full_enriched["fl_date"] = df_raw["FL_DATE"].str.slice(0, 10).values
    df_full_enriched["carrier"] = df_raw["OP_CARRIER"].values
    df_full_enriched["fl_num"] = df_raw["OP_CARRIER_FL_NUM"].values

    enriched_full_path = PREDICTIONS_DIR / "full_turn_unified_predictions_minute_granularity.parquet"
    df_full_enriched.to_parquet(enriched_full_path, index=False)
    logger.info("  ✓ Đã xuất %s (%d dòng)", enriched_full_path.name, len(df_full_enriched))

    logger.info("======================================================================")
    logger.info("HOÀN TẤT CHUẨN HÓA DỮ LIỆU ĐẦU VÀO CHO BỘ GIẢI CP-SAT / SA!")
    logger.info("======================================================================")


if __name__ == "__main__":
    build_atl_scenarios()
