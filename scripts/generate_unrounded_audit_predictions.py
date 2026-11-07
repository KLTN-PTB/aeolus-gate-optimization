"""Generator of Exact Unrounded Flight-Level Predictions (float64) for M1-M4, 5M, and Local ATL.

Extracts:
- Canonical flight_key and flight date (FL_DATE)
- Ground-truth binary delay label (y_true_cls) & delay minutes (y_true_delay_min)
- Exact unrounded probabilities (float64) for ARR and DEP across:
  * M1 (Schedule-Only: 24 features)
  * M2 (Schedule + Network: 38 features)
  * M3 (Static Weather T-2h: 55 features)
  * M4 (Proposed Full Dynamics: 61 features)
  * XGBoost 5M Scale-up
  * Local ATL Benchmark
- Exact predicted delay minutes (regression) for ARR and DEP
- Verifies exact Brier scores, ROC-AUC, F1 without rounding discrepancies.

Outputs:
- Parquet: artifacts/audit_predictions/unrounded_flight_level_predictions_2024.parquet
- Markdown: artifacts/audit_predictions/AUDIT_UNROUNDED_METRICS_REPORT.md
"""

from __future__ import annotations

import gc
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Ensure UTF-8 output encoding for Windows terminal
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    roc_auc_score,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("audit_predictions")

OUTPUT_SPLIT_DIR = PROJECT_ROOT / "src" / "data" / "split_ablation"
if not OUTPUT_SPLIT_DIR.exists():
    OUTPUT_SPLIT_DIR = PROJECT_ROOT / "data" / "split_ablation"

MODELS_DIR = PROJECT_ROOT / "artifacts" / "models"
AUDIT_DIR = PROJECT_ROOT / "artifacts" / "audit_predictions"
AUDIT_DIR.mkdir(parents=True, exist_ok=True)


def extract_model_and_threshold(path: Path):
    if not path.exists():
        return None, 0.5
    d = joblib.load(path)
    if isinstance(d, dict):
        model = d.get("model", d)
        th = d.get("optimal_threshold", d.get("threshold", 0.5))
        return model, float(th) if th is not None else 0.5
    return d, 0.5


def get_feature_sets(direction: str) -> dict[str, list[str]]:
    delay_sfx = "ARR" if direction == "arrival" else "DEP"
    m1_schedule = [
        "DISTANCE_KM", "CRS_ELAPSED_TIME", "DEP_HOUR", "ARR_HOUR",
        "MONTH", "DAY", "DOW", "QUARTER", "IS_WEEKEND", "PEAK_HOUR",
        "SEASON_CODE", "TIME_OF_DAY_CODE", "DISTANCE_GROUP_CODE", "LONG_HAUL",
        "IS_COVID_PERIOD", "OP_CARRIER_CODE", "ORIGIN_CODE", "DEST_CODE",
        "MONTH_SIN", "MONTH_COS", "HOUR_SIN", "HOUR_COS", "DOW_SIN", "DOW_COS",
    ]
    m2_network = [
        "ORIGIN_CONGESTION_SAME_HOUR", "DEST_CONGESTION_SAME_HOUR",
        "ORIGIN_DAILY_FLIGHTS", "DEST_DAILY_FLIGHTS",
        "CARRIER_DELAY_RATE", "ORIGIN_DELAY_RATE", "ROUTE_DELAY_RATE", "DEST_DELAY_RATE",
        f"ROUTE_AVG_{delay_sfx}_DELAY_PAST", f"AIRLINE_AVG_{delay_sfx}_DELAY_PAST", f"ORIGIN_AVG_{delay_sfx}_DELAY_PAST",
        f"ROUTE_AVG_{delay_sfx}_DELAY_ROLLING", f"AIRLINE_AVG_{delay_sfx}_DELAY_ROLLING", f"ORIGIN_AVG_{delay_sfx}_DELAY_ROLLING",
    ]
    m3_weather_static = [
        "O_TEMP", "O_PRCP", "O_WSPD", "D_TEMP", "D_PRCP", "D_WSPD",
        "IS_ORIGIN_RAINY", "IS_DEST_RAINY", "IS_ORIGIN_WINDY", "IS_DEST_WINDY",
        "IS_ORIGIN_COLD", "IS_DEST_COLD", "TEMP_DIFF", "WSPD_DIFF",
        "WEATHER_SEVERITY_ORIGIN", "WEATHER_SEVERITY_DEST", "WEATHER_SEVERITY_TOTAL",
    ]
    m4_weather_dynamics = [
        "O_DELTA_TEMP_1H", "D_DELTA_TEMP_1H", "O_DELTA_WSPD_1H", "D_DELTA_WSPD_1H",
        "O_DELTA_TEMP_3H", "D_DELTA_TEMP_3H",
    ]
    return {
        "M1": m1_schedule,
        "M2": m1_schedule + m2_network,
        "M3": m1_schedule + m2_network + m3_weather_static,
        "M4": m1_schedule + m2_network + m3_weather_static + m4_weather_dynamics,
    }


def load_split_with_keys(task_name: str, max_train: int = 1_000_000, max_eval: int = 300_000):
    task_dir = OUTPUT_SPLIT_DIR / task_name
    if not task_dir.exists():
        raise FileNotFoundError(f"Partition directory not found: {task_dir}")

    def load_fold(fold_name: str, cap: int):
        fdir = task_dir / fold_name
        x_files = sorted(fdir.glob("X_*.parquet"))
        y_files = sorted(fdir.glob("y_*.parquet"))
        x_chunks, y_chunks = [], []
        for xf, yf in zip(x_files, y_files):
            x_chunks.append(pd.read_parquet(xf))
            y_chunks.append(pd.read_parquet(yf)["target"])
        X = pd.concat(x_chunks, ignore_index=True)
        y = pd.concat(y_chunks, ignore_index=True)
        if cap and len(X) > cap:
            X = X.iloc[:cap]
            y = y.iloc[:cap]
        return X, y

    logger.info("Loading %s folds...", task_name)
    X_tr, y_tr = load_fold("train", max_train)
    X_va, y_va = load_fold("valid", max_eval)
    X_te, y_te = load_fold("test", max_eval)

    return X_tr, y_tr, X_va, y_va, X_te, y_te


def main() -> None:
    t_start = time.time()
    logger.info("=" * 80)
    logger.info("STARTING UNROUNDED AUDIT PREDICTIONS EXTRACTION PIPELINE")
    logger.info("=" * 80)

    # 1. ARRIVAL SUITE
    X_tr_arr, y_tr_cls_arr, X_va_arr, y_va_cls_arr, X_te_arr, y_te_cls_arr = load_split_with_keys("arrival_classification")
    _, y_tr_reg_arr, _, y_va_reg_arr, _, y_te_reg_arr = load_split_with_keys("arrival_regression")

    # Construct canonical keys
    flight_keys = X_te_arr["flight_key"].astype(str).values
    fl_dates = (
        X_te_arr["source_year"].astype(str) + "-" +
        X_te_arr["MONTH"].astype(str).str.zfill(2) + "-" +
        X_te_arr["DAY"].astype(str).str.zfill(2)
    ).values

    out_df = pd.DataFrame({
        "flight_key": flight_keys,
        "fl_date": fl_dates,
        "arr_y_true_cls": y_te_cls_arr.values.astype("int8"),
        "arr_y_true_delay_min": y_te_reg_arr.values.astype("float32"),
    })

    audit_metrics = []
    configs_arr = get_feature_sets("arrival")

    for m_label, feat_cols in configs_arr.items():
        valid_cols = [c for c in feat_cols if c in X_tr_arr.columns]
        logger.info("[ARR %s] Training Classifier on %d features...", m_label, len(valid_cols))

        clf = lgb.LGBMClassifier(
            n_estimators=300, learning_rate=0.05, num_leaves=63,
            random_state=42, n_jobs=-1, verbose=-1,
        )
        clf.fit(
            X_tr_arr[valid_cols], y_tr_cls_arr,
            eval_set=[(X_va_arr[valid_cols], y_va_cls_arr)],
            callbacks=[lgb.early_stopping(25, verbose=False)],
        )
        p_val = clf.predict_proba(X_va_arr[valid_cols])[:, 1]
        p_test_unrounded = clf.predict_proba(X_te_arr[valid_cols])[:, 1]  # Exact float64!

        # Threshold optimization on validation
        thresholds = np.linspace(0.15, 0.55, 41)
        best_t, best_f1 = 0.5, 0.0
        for th in thresholds:
            f = f1_score(y_va_cls_arr, (p_val >= th).astype(int))
            if f > best_f1:
                best_f1, best_t = f, th

        # Regressor
        logger.info("[ARR %s] Training Regressor on %d features...", m_label, len(valid_cols))
        reg = lgb.LGBMRegressor(
            n_estimators=300, learning_rate=0.05, num_leaves=63,
            random_state=42, n_jobs=-1, verbose=-1,
        )
        reg.fit(
            X_tr_arr[valid_cols], y_tr_reg_arr,
            eval_set=[(X_va_arr[valid_cols], y_va_reg_arr)],
            callbacks=[lgb.early_stopping(25, verbose=False)],
        )
        pred_delay_unrounded = reg.predict(X_te_arr[valid_cols]).astype("float32")

        # Save to output DataFrame
        out_df[f"arr_prob_{m_label.lower()}"] = p_test_unrounded
        out_df[f"arr_pred_delay_min_{m_label.lower()}"] = pred_delay_unrounded

        roc_auc = roc_auc_score(y_te_cls_arr, p_test_unrounded)
        pr_auc = average_precision_score(y_te_cls_arr, p_test_unrounded)
        brier = brier_score_loss(y_te_cls_arr, p_test_unrounded)
        f1 = f1_score(y_te_cls_arr, (p_test_unrounded >= best_t).astype(int))
        mae = mean_absolute_error(y_te_reg_arr, pred_delay_unrounded)
        rmse = np.sqrt(mean_squared_error(y_te_reg_arr, pred_delay_unrounded))

        audit_metrics.append({
            "Direction": "Arrival (ARR)",
            "Model_Group": m_label,
            "Features": len(valid_cols),
            "ROC_AUC": round(float(roc_auc), 6),
            "PR_AUC": round(float(pr_auc), 6),
            "Brier_Score_Unrounded": round(float(brier), 6),
            "Opt_Threshold_T": round(float(best_t), 3),
            "F1_Score": round(float(f1), 6),
            "MAE_min": round(float(mae), 4),
            "RMSE_min": round(float(rmse), 4),
        })

    # XGBoost 5M Arrival Champion
    m5m_cls_path = MODELS_DIR / "champion_xgboost_optuna_5m_classifier.joblib"
    m5m_reg_path = MODELS_DIR / "champion_xgboost_optuna_5m_regressor.joblib"
    if m5m_cls_path.exists():
        logger.info("[ARR 5M] Loading champion 5M XGBoost model for exact unrounded inference...")
        xgb_5m_cls, t_5m = extract_model_and_threshold(m5m_cls_path)
        valid_5m = [c for c in getattr(xgb_5m_cls, "feature_names_in_", []) if c in X_te_arr.columns]
        if valid_5m:
            p_5m = xgb_5m_cls.predict_proba(X_te_arr[valid_5m])[:, 1]
            out_df["arr_prob_xgb_5m"] = p_5m
            brier_5m = brier_score_loss(y_te_cls_arr, p_5m)
            roc_5m = roc_auc_score(y_te_cls_arr, p_5m)
            audit_metrics.append({
                "Direction": "Arrival (ARR)",
                "Model_Group": "XGBoost_5M",
                "Features": len(valid_5m),
                "ROC_AUC": round(float(roc_5m), 6),
                "PR_AUC": round(float(average_precision_score(y_te_cls_arr, p_5m)), 6),
                "Brier_Score_Unrounded": round(float(brier_5m), 6),
                "Opt_Threshold_T": round(float(t_5m), 3),
                "F1_Score": round(float(f1_score(y_te_cls_arr, (p_5m >= t_5m).astype(int))), 6),
                "MAE_min": np.nan,
                "RMSE_min": np.nan,
            })

    # Local ATL Arrival Champion
    atl_arr_path = MODELS_DIR / "champion_atl_arrival_classifier.joblib"
    if atl_arr_path.exists():
        logger.info("[ARR Local ATL] Loading local ATL arrival classifier...")
        atl_cls, t_atl = extract_model_and_threshold(atl_arr_path)
        valid_atl = [c for c in getattr(atl_cls, "feature_names_in_", []) if c in X_te_arr.columns]
        if valid_atl:
            p_atl = atl_cls.predict_proba(X_te_arr[valid_atl])[:, 1]
            out_df["arr_prob_local_atl"] = p_atl
            audit_metrics.append({
                "Direction": "Arrival (ARR)",
                "Model_Group": "Local_ATL",
                "Features": len(valid_atl),
                "ROC_AUC": round(float(roc_auc_score(y_te_cls_arr, p_atl)), 6),
                "PR_AUC": round(float(average_precision_score(y_te_cls_arr, p_atl)), 6),
                "Brier_Score_Unrounded": round(float(brier_score_loss(y_te_cls_arr, p_atl)), 6),
                "Opt_Threshold_T": round(float(t_atl), 3),
                "F1_Score": round(float(f1_score(y_te_cls_arr, (p_atl >= t_atl).astype(int))), 6),
                "MAE_min": np.nan,
                "RMSE_min": np.nan,
            })

    del X_tr_arr, y_tr_cls_arr, X_va_arr, y_va_cls_arr, X_te_arr, y_te_cls_arr
    gc.collect()

    # 2. DEPARTURE SUITE
    X_tr_dep, y_tr_cls_dep, X_va_dep, y_va_cls_dep, X_te_dep, y_te_cls_dep = load_split_with_keys("departure_classification")
    _, y_tr_reg_dep, _, y_va_reg_dep, _, y_te_reg_dep = load_split_with_keys("departure_regression")

    out_df["dep_y_true_cls"] = y_te_cls_dep.values.astype("int8")
    out_df["dep_y_true_delay_min"] = y_te_reg_dep.values.astype("float32")

    configs_dep = get_feature_sets("departure")

    for m_label, feat_cols in configs_dep.items():
        valid_cols = [c for c in feat_cols if c in X_tr_dep.columns]
        logger.info("[DEP %s] Training Classifier on %d features...", m_label, len(valid_cols))

        clf = lgb.LGBMClassifier(
            n_estimators=300, learning_rate=0.05, num_leaves=63,
            random_state=42, n_jobs=-1, verbose=-1,
        )
        clf.fit(
            X_tr_dep[valid_cols], y_tr_cls_dep,
            eval_set=[(X_va_dep[valid_cols], y_va_cls_dep)],
            callbacks=[lgb.early_stopping(25, verbose=False)],
        )
        p_val = clf.predict_proba(X_va_dep[valid_cols])[:, 1]
        p_test_unrounded = clf.predict_proba(X_te_dep[valid_cols])[:, 1]

        thresholds = np.linspace(0.15, 0.55, 41)
        best_t, best_f1 = 0.5, 0.0
        for th in thresholds:
            f = f1_score(y_va_cls_dep, (p_val >= th).astype(int))
            if f > best_f1:
                best_f1, best_t = f, th

        logger.info("[DEP %s] Training Regressor on %d features...", m_label, len(valid_cols))
        reg = lgb.LGBMRegressor(
            n_estimators=300, learning_rate=0.05, num_leaves=63,
            random_state=42, n_jobs=-1, verbose=-1,
        )
        reg.fit(
            X_tr_dep[valid_cols], y_tr_reg_dep,
            eval_set=[(X_va_dep[valid_cols], y_va_reg_dep)],
            callbacks=[lgb.early_stopping(25, verbose=False)],
        )
        pred_delay_unrounded = reg.predict(X_te_dep[valid_cols]).astype("float32")

        out_df[f"dep_prob_{m_label.lower()}"] = p_test_unrounded
        out_df[f"dep_pred_delay_min_{m_label.lower()}"] = pred_delay_unrounded

        roc_auc = roc_auc_score(y_te_cls_dep, p_test_unrounded)
        pr_auc = average_precision_score(y_te_cls_dep, p_test_unrounded)
        brier = brier_score_loss(y_te_cls_dep, p_test_unrounded)
        f1 = f1_score(y_te_cls_dep, (p_test_unrounded >= best_t).astype(int))
        mae = mean_absolute_error(y_te_reg_dep, pred_delay_unrounded)
        rmse = np.sqrt(mean_squared_error(y_te_reg_dep, pred_delay_unrounded))

        audit_metrics.append({
            "Direction": "Departure (DEP)",
            "Model_Group": m_label,
            "Features": len(valid_cols),
            "ROC_AUC": round(float(roc_auc), 6),
            "PR_AUC": round(float(pr_auc), 6),
            "Brier_Score_Unrounded": round(float(brier), 6),
            "Opt_Threshold_T": round(float(best_t), 3),
            "F1_Score": round(float(f1), 6),
            "MAE_min": round(float(mae), 4),
            "RMSE_min": round(float(rmse), 4),
        })

    # XGBoost 5M Departure Champion
    m5m_dep_path = MODELS_DIR / "champion_xgboost_optuna_5m_departure_classifier.joblib"
    if m5m_dep_path.exists():
        logger.info("[DEP 5M] Loading champion 5M XGBoost departure model...")
        xgb_5m_dep_cls, t_5m_dep = extract_model_and_threshold(m5m_dep_path)
        valid_5m_dep = [c for c in getattr(xgb_5m_dep_cls, "feature_names_in_", []) if c in X_te_dep.columns]
        if valid_5m_dep:
            p_5m_dep = xgb_5m_dep_cls.predict_proba(X_te_dep[valid_5m_dep])[:, 1]
            out_df["dep_prob_xgb_5m"] = p_5m_dep
            audit_metrics.append({
                "Direction": "Departure (DEP)",
                "Model_Group": "XGBoost_5M",
                "Features": len(valid_5m_dep),
                "ROC_AUC": round(float(roc_auc_score(y_te_cls_dep, p_5m_dep)), 6),
                "PR_AUC": round(float(average_precision_score(y_te_cls_dep, p_5m_dep)), 6),
                "Brier_Score_Unrounded": round(float(brier_score_loss(y_te_cls_dep, p_5m_dep)), 6),
                "Opt_Threshold_T": round(float(t_5m_dep), 3),
                "F1_Score": round(float(f1_score(y_te_cls_dep, (p_5m_dep >= t_5m_dep).astype(int))), 6),
                "MAE_min": np.nan,
                "RMSE_min": np.nan,
            })

    # Local ATL Departure Champion
    atl_dep_path = MODELS_DIR / "champion_atl_departure_classifier.joblib"
    if atl_dep_path.exists():
        logger.info("[DEP Local ATL] Loading local ATL departure classifier...")
        atl_dep_cls, t_atl_dep = extract_model_and_threshold(atl_dep_path)
        valid_atl_dep = [c for c in getattr(atl_dep_cls, "feature_names_in_", []) if c in X_te_dep.columns]
        if valid_atl_dep:
            p_atl_dep = atl_dep_cls.predict_proba(X_te_dep[valid_atl_dep])[:, 1]
            out_df["dep_prob_local_atl"] = p_atl_dep
            audit_metrics.append({
                "Direction": "Departure (DEP)",
                "Model_Group": "Local_ATL",
                "Features": len(valid_atl_dep),
                "ROC_AUC": round(float(roc_auc_score(y_te_cls_dep, p_atl_dep)), 6),
                "PR_AUC": round(float(average_precision_score(y_te_cls_dep, p_atl_dep)), 6),
                "Brier_Score_Unrounded": round(float(brier_score_loss(y_te_cls_dep, p_atl_dep)), 6),
                "Opt_Threshold_T": round(float(t_atl_dep), 3),
                "F1_Score": round(float(f1_score(y_te_cls_dep, (p_atl_dep >= t_atl_dep).astype(int))), 6),
                "MAE_min": np.nan,
                "RMSE_min": np.nan,
            })

    # Save output parquet
    out_parquet_path = AUDIT_DIR / "unrounded_flight_level_predictions_2024.parquet"
    out_df.to_parquet(out_parquet_path, index=False)
    logger.info("✓ Saved Unrounded Flight-Level Predictions: %s (%d rows, %d cols)", out_parquet_path.name, len(out_df), len(out_df.columns))

    # Save Markdown Audit Summary Report
    metrics_df = pd.DataFrame(audit_metrics)
    report_path = AUDIT_DIR / "AUDIT_UNROUNDED_METRICS_REPORT.md"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    md_content = [
        "# BÁO CÁO ĐỐI SOÁT CHỈ SỐ MÔ HÌNH VỚI DỰ ĐOÁN THÔ CHƯA LÀM TRÒN (FLOAT64)",
        f"**Thời điểm tạo:** {now_str}  ",
        f"**Quy mô tập Test Holdout 2024:** {len(out_df):,} chuyến bay  ",
        f"**Tệp dữ liệu Parquet lưu trữ:** `{out_parquet_path.name}`  ",
        "",
        "## 1. Bảng Chỉ Số Chi Tiết Không Bị Sai Số Làm Tròn",
        "",
        metrics_df.to_markdown(index=False),
        "",
        "## 2. Ý Nghĩa Kỹ Thuật",
        "1. **Brier Score chính xác:** Loại bỏ hoàn toàn sự cố các ô trùng số do làm tròn 4 chữ số thập phân (`np.round(p, 4)`).",
        "2. **Ghép nối Chuyến bay & Bootstrap:** Cung cấp đầy đủ khóa `flight_key` chuẩn hóa và ngày bay `fl_date`, cho phép kiểm chứng chéo và lấy mẫu ngẫu nhiên (bootstrap) chính xác theo từng ngày.",
        "3. **Tương thích CP-SAT:** Cung cấp đồng thời cả xác suất trễ (`prob`) và số phút trễ dự báo (`pred_delay_min`) cho cả chiều đến (ARR) và chiều đi (DEP).",
    ]
    with open(report_path, "w", encoding="utf-8") as f_out:
        f_out.write("\n".join(md_content))

    duration = round(time.time() - t_start, 1)
    logger.info("🎉 UNROUNDED AUDIT EXTRACTION COMPLETED IN %.1f SECONDS!", duration)


if __name__ == "__main__":
    main()
