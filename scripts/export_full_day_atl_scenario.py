"""Export the complete, 100% full-day flight schedule for Atlanta (ATL) on 2024-01-01.

This script extracts all 1,500 real flights (745 Inbounds + 755 Outbounds) at ATL on 2024-01-01,
computes their ML delay predictions (p_delay, delay_est_min) using the Champion XGBoost/LightGBM
models, and enriches every flight with:
1. Scheduled flight times: CRS_DEP_TIME, CRS_ARR_TIME, CRS_ELAPSED_TIME, sched_dep_min, sched_arr_min.
2. ML Predicted times: predicted_dep_time, predicted_arr_time, predicted_dep_min, predicted_arr_min, p_delay, delay_est_min.
3. Actual ground-truth times: actual_dep_time, actual_arr_time, actual_elapsed_time_min, dep_delay_min, arr_delay_min, taxi_in_min, taxi_out_min.
4. Gate operations attributes: chain_group_id, aircraft_type, turnaround_time_min, dwell_time_min.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Final

import joblib
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

REPO_ROOT: Final = Path(__file__).resolve().parent.parent
MODELS_DIR: Final = REPO_ROOT / "src" / "artifacts" / "models"
SPLIT_DIR: Final = REPO_ROOT / "src" / "data" / "split"
PROCESSED_2024_DIR: Final = REPO_ROOT / "src" / "data" / "processed" / "tabular_by_year" / "year=2024"
SCENARIOS_DIR: Final = REPO_ROOT / "src" / "artifacts" / "scenarios"
GROUND_TRUTH_DIR: Final = SCENARIOS_DIR / "ground_truth"

ROW_GROUP_SIZE: Final = 1_048_576
CATEGORICAL_COLS: Final = ["OP_CARRIER_CODE", "ORIGIN_CODE", "DEST_CODE"]


def parse_minute_of_day(time_str_series: pd.Series) -> pd.Series:
    """Convert timestamp strings 'YYYY-MM-DD HH:MM:SS' to minute of day (0..1439)."""
    hh = time_str_series.str.slice(11, 13).astype(int)
    mm = time_str_series.str.slice(14, 16).astype(int)
    return (hh * 60 + mm).astype(np.int16)


def assign_aircraft_properties(flight_keys: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Deterministically assign aircraft_type, turnaround_time, and dwell_time based on flight_key hash."""
    types, turnarounds, dwells = [], [], []
    for k in flight_keys:
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


def extract_full_day_atl(target_date: str = "2024-01-01") -> tuple[pd.DataFrame, pd.DataFrame]:
    """Scan all 26 partitions of 2024 and collect metadata for target_date at ATL."""
    files = sorted(PROCESSED_2024_DIR.glob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"Không tìm thấy file 2024 tại {PROCESSED_2024_DIR}")

    logger.info("1. Đang quét 26 files dữ liệu gốc 2024 để tìm toàn bộ chuyến bay ATL ngày %s...", target_date)
    inbound_records = []
    outbound_records = []
    global_offset = 0

    cols = [
        "flight_key", "FL_DATE", "OP_CARRIER", "OP_CARRIER_FL_NUM", "ORIGIN", "DEST",
        "CRS_DEP_TIME", "DEP_TIME", "DEP_DELAY",
        "CRS_ARR_TIME", "ARR_TIME", "ARR_DELAY",
        "CRS_ELAPSED_TIME", "ACTUAL_ELAPSED_TIME", "TAXI_IN", "TAXI_OUT",
        "O_LATITUDE", "O_LONGITUDE", "D_LATITUDE", "D_LONGITUDE"
    ]

    for f in files:
        df = pd.read_parquet(f, columns=cols)
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
        c_clean = c[valid_mask].reset_index(drop=True)
        n_clean = len(c_clean)

        date_mask = c_clean["FL_DATE"].str.slice(0, 10) == target_date
        in_idx = np.where(date_mask & (c_clean["DEST"] == "ATL"))[0]
        out_idx = np.where(date_mask & (c_clean["ORIGIN"] == "ATL"))[0]

        for idx in in_idx:
            row = c_clean.iloc[idx].to_dict()
            row["global_idx"] = global_offset + idx
            row["direction"] = "ARR"
            inbound_records.append(row)

        for idx in out_idx:
            row = c_clean.iloc[idx].to_dict()
            row["global_idx"] = global_offset + idx
            row["direction"] = "DEP"
            outbound_records.append(row)

        global_offset += n_clean

    df_in = pd.DataFrame(inbound_records)
    df_out = pd.DataFrame(outbound_records)
    logger.info("-> Tìm thấy: %d chuyến đến (Inbound) và %d chuyến đi (Outbound) tại ATL (Tổng: %d chuyến)",
                len(df_in), len(df_out), len(df_in) + len(df_out))
    return df_in, df_out


def predict_inbounds(df_in: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Extract features and predict delay probabilities & minutes for Inbound flights."""
    logger.info("2. Dự báo ML cho %d chuyến đến (Arrival models)...", len(df_in))
    clf_path = MODELS_DIR / "champion_arrival_classifier.joblib"
    reg_path = MODELS_DIR / "champion_arrival_regressor.joblib"
    arr_clf = joblib.load(clf_path)
    arr_reg = joblib.load(reg_path)

    feat_path = SPLIT_DIR / "arrival_regression" / "test" / "X_part_2024.parquet"
    pf = pq.ParquetFile(feat_path)

    by_rg = defaultdict(list)
    for i, g_idx in enumerate(df_in["global_idx"]):
        rg = g_idx // ROW_GROUP_SIZE
        offset = g_idx % ROW_GROUP_SIZE
        by_rg[rg].append((i, offset))

    chunks = []
    for rg, items in by_rg.items():
        offsets = [offset for _, offset in items]
        row_indices = [idx for idx, _ in items]
        df_rg = pf.read_row_group(rg).to_pandas()
        sliced = df_rg.iloc[offsets].copy()
        sliced["_orig_order"] = row_indices
        chunks.append(sliced)

    X_in = pd.concat(chunks, ignore_index=True).sort_values(by="_orig_order").drop(columns=["_orig_order"]).reset_index(drop=True)
    for c in CATEGORICAL_COLS:
        if c in X_in.columns:
            X_in[c] = X_in[c].astype("int16").astype("category")

    p_delay = arr_clf.predict_proba(X_in)[:, 1]
    delay_est = arr_reg.predict(X_in)
    return np.round(p_delay, 4), np.round(delay_est, 2)


def predict_outbounds(df_out: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Extract features and predict delay probabilities & minutes for Outbound flights."""
    logger.info("3. Dự báo ML cho %d chuyến đi (Departure models)...", len(df_out))
    clf_path = MODELS_DIR / "champion_departure_classifier.joblib"
    reg_path = MODELS_DIR / "champion_departure_regressor.joblib"
    dep_clf = joblib.load(clf_path)
    dep_reg = joblib.load(reg_path)

    feat_path = SPLIT_DIR / "departure_regression" / "test" / "X_part_2024.parquet"
    pf = pq.ParquetFile(feat_path)

    by_rg = defaultdict(list)
    for i, g_idx in enumerate(df_out["global_idx"]):
        rg = g_idx // ROW_GROUP_SIZE
        offset = g_idx % ROW_GROUP_SIZE
        by_rg[rg].append((i, offset))

    chunks = []
    for rg, items in by_rg.items():
        offsets = [offset for _, offset in items]
        row_indices = [idx for idx, _ in items]
        df_rg = pf.read_row_group(rg).to_pandas()
        sliced = df_rg.iloc[offsets].copy()
        sliced["_orig_order"] = row_indices
        chunks.append(sliced)

    X_out = pd.concat(chunks, ignore_index=True).sort_values(by="_orig_order").drop(columns=["_orig_order"]).reset_index(drop=True)
    for c in CATEGORICAL_COLS:
        if c in X_out.columns:
            X_out[c] = X_out[c].astype("int16").astype("category")

    p_delay = dep_clf.predict_proba(X_out)[:, 1]
    delay_est = dep_reg.predict(X_out)
    return np.round(p_delay, 4), np.round(delay_est, 2)


def build_full_day_scenario(target_date: str = "2024-01-01") -> Path:
    """Build and save the full 1500 flights scenario for ATL with complete time attributes."""
    SCENARIOS_DIR.mkdir(parents=True, exist_ok=True)
    GROUND_TRUTH_DIR.mkdir(parents=True, exist_ok=True)

    t_start = time.time()
    df_in, df_out = extract_full_day_atl(target_date=target_date)

    # Inbound predictions
    p_arr_delay, delay_est_arr = predict_inbounds(df_in)
    df_in["p_delay"] = p_arr_delay
    df_in["delay_est_min"] = delay_est_arr

    # Outbound predictions
    p_dep_delay, delay_est_dep = predict_outbounds(df_out)
    df_out["p_delay"] = p_dep_delay
    df_out["delay_est_min"] = delay_est_dep

    # Combine all 1,500 flights
    df_all = pd.concat([df_in, df_out], ignore_index=True)

    # 1. Base Identifiers
    df_all["flight_key"] = df_all["flight_key"]
    df_all["airport"] = "ATL"
    df_all["fl_date"] = df_all["FL_DATE"].str.slice(0, 10)
    df_all["carrier"] = df_all["OP_CARRIER"]
    df_all["fl_num"] = df_all["OP_CARRIER_FL_NUM"].astype(int)
    df_all["origin"] = df_all["ORIGIN"]
    df_all["dest"] = df_all["DEST"]
    df_all["chain_group_id"] = (
        df_all["fl_date"] + "_" + df_all["carrier"].astype(str) + "_" + df_all["fl_num"].astype(str)
    )

    # 2. Scheduled Flight Times (CRS)
    df_all["crs_dep_time"] = df_all["CRS_DEP_TIME"]
    df_all["crs_arr_time"] = df_all["CRS_ARR_TIME"]
    df_all["sched_dep_min"] = parse_minute_of_day(df_all["CRS_DEP_TIME"])
    df_all["sched_arr_min"] = parse_minute_of_day(df_all["CRS_ARR_TIME"])
    df_all["crs_elapsed_time_min"] = df_all["CRS_ELAPSED_TIME"].astype(np.float32)

    # sched_time_min reflects the event at ATL (ARR time for inbound, DEP time for outbound)
    df_all["sched_time_min"] = np.where(df_all["direction"] == "ARR", df_all["sched_arr_min"], df_all["sched_dep_min"])

    # 3. ML Predicted Times (Using delay_est_min from champion models)
    # Predicted event time at ATL:
    pred_dep_dt = pd.to_datetime(df_all["CRS_DEP_TIME"]) + pd.to_timedelta(df_all["delay_est_min"], unit="m")
    pred_arr_dt = pd.to_datetime(df_all["CRS_ARR_TIME"]) + pd.to_timedelta(df_all["delay_est_min"], unit="m")

    df_all["predicted_dep_time"] = pred_dep_dt.dt.strftime("%Y-%m-%d %H:%M:%S")
    df_all["predicted_arr_time"] = pred_arr_dt.dt.strftime("%Y-%m-%d %H:%M:%S")
    df_all["predicted_dep_min"] = (pred_dep_dt.dt.hour * 60 + pred_dep_dt.dt.minute).astype(np.int16)
    df_all["predicted_arr_min"] = (pred_arr_dt.dt.hour * 60 + pred_arr_dt.dt.minute).astype(np.int16)
    df_all["predicted_time_min"] = np.where(df_all["direction"] == "ARR", df_all["predicted_arr_min"], df_all["predicted_dep_min"])

    # 4. Actual Times (Ground Truth BTS data)
    actual_dep_dt = pd.to_datetime(df_all["DEP_TIME"])
    actual_arr_dt = pd.to_datetime(df_all["ARR_TIME"])

    df_all["actual_dep_time"] = df_all["DEP_TIME"]
    df_all["actual_arr_time"] = df_all["ARR_TIME"]
    df_all["actual_dep_min"] = (actual_dep_dt.dt.hour * 60 + actual_dep_dt.dt.minute).astype(np.int16)
    df_all["actual_arr_min"] = (actual_arr_dt.dt.hour * 60 + actual_arr_dt.dt.minute).astype(np.int16)
    df_all["actual_time_min"] = np.where(df_all["direction"] == "ARR", df_all["actual_arr_min"], df_all["actual_dep_min"])

    df_all["actual_elapsed_time_min"] = df_all["ACTUAL_ELAPSED_TIME"].astype(np.float32)
    df_all["dep_delay_min"] = df_all["DEP_DELAY"].astype(np.float32)
    df_all["arr_delay_min"] = df_all["ARR_DELAY"].astype(np.float32)
    df_all["taxi_in_min"] = df_all["TAXI_IN"].fillna(0).astype(np.float32)
    df_all["taxi_out_min"] = df_all["TAXI_OUT"].fillna(0).astype(np.float32)

    # 5. Aircraft & Gate Operational Properties
    ac_types, turnarounds, dwells = assign_aircraft_properties(df_all["flight_key"])
    df_all["aircraft_type"] = ac_types
    df_all["turnaround_time_min"] = turnarounds
    df_all["dwell_time_min"] = dwells

    # Sort chronologically by scheduled ATL event time
    df_all = df_all.sort_values(by=["sched_time_min", "flight_key"]).reset_index(drop=True)

    # Complete master schema for CP-SAT and evaluation
    all_columns = [
        # Identifiers
        "flight_key", "airport", "direction", "fl_date", "carrier", "fl_num", "origin", "dest", "chain_group_id",
        # Scheduled (CRS) Times
        "crs_dep_time", "crs_arr_time", "sched_dep_min", "sched_arr_min", "sched_time_min", "crs_elapsed_time_min",
        # ML Predicted Times & Probabilities
        "p_delay", "delay_est_min", "predicted_dep_time", "predicted_arr_time", "predicted_dep_min", "predicted_arr_min", "predicted_time_min",
        # Actual Times & Ground Truth
        "actual_dep_time", "actual_arr_time", "actual_dep_min", "actual_arr_min", "actual_time_min",
        "actual_elapsed_time_min", "dep_delay_min", "arr_delay_min", "taxi_in_min", "taxi_out_min",
        # Aircraft & Gate Constraints
        "aircraft_type", "turnaround_time_min", "dwell_time_min"
    ]

    out_file = SCENARIOS_DIR / f"atl_{target_date.replace('-', '_')}_full_day_1500_flights.parquet"
    df_all[all_columns].to_parquet(out_file, index=False)
    logger.info("4. Đã lưu kịch bản TOÀN DIỆN 100%% (%d chuyến x %d cột) tại: %s", len(df_all), len(all_columns), out_file.name)

    # Also save Ground Truth separately (for strict Simulation Safety Guard if needed)
    gt_file = GROUND_TRUTH_DIR / f"atl_{target_date.replace('-', '_')}_full_day_1500_flights_ground_truth.parquet"
    gt_cols = ["flight_key", "direction", "fl_date", "actual_dep_time", "actual_arr_time", "actual_elapsed_time_min", "dep_delay_min", "arr_delay_min"]
    df_all[gt_cols].to_parquet(gt_file, index=False)
    logger.info("   Đã cập nhật đối soát mặt đất tại: %s", gt_file.name)

    elapsed = time.time() - t_start
    logger.info("======================================================================")
    logger.info("HOÀN TẤT XUẤT ĐẦY ĐỦ THỜI GIAN BAY DỰ KIẾN/THỰC TẾ TRONG %.2f GIÂY!", elapsed)
    logger.info("======================================================================")
    return out_file


if __name__ == "__main__":
    build_full_day_scenario("2024-01-01")
