"""Stage 2 Runner — Representation Ablation: Flight Number Embedding vs Frequency Map.

Executes expanding-window folds 1-4 for R0, R1, and R2 under identical experimental controls.
Saves fold prediction parquets and outputs the summary JSON manifest.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import time
from typing import Any

import numpy as np
import pandas as pd

from src.data.stratified_loader import load_stratified_fold_data
from src.models.probabilistic.representation_ablation import (
    FlightNumberRepresentation,
    train_point_model_fold,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
LOGGER = logging.getLogger(__name__)

FOLDS = [
    {
        "fold_id": "fold_1",
        "outer_train_years": [2016, 2017, 2018],
        "outer_val_year": 2019,
        "inner_train_years": [2016, 2017],
        "inner_val_years": [2018],
    },
    {
        "fold_id": "fold_2",
        "outer_train_years": [2016, 2017, 2018, 2019],
        "outer_val_year": 2020,
        "inner_train_years": [2016, 2017, 2018],
        "inner_val_years": [2019],
    },
    {
        "fold_id": "fold_3",
        "outer_train_years": [2016, 2017, 2018, 2019, 2020],
        "outer_val_year": 2021,
        "inner_train_years": [2016, 2017, 2018, 2019],
        "inner_val_years": [2020],
    },
    {
        "fold_id": "fold_4",
        "outer_train_years": [2016, 2017, 2018, 2019, 2020, 2021],
        "outer_val_year": 2022,
        "inner_train_years": [2016, 2017, 2018, 2019, 2020],
        "inner_val_years": [2021],
    },
]

CANDIDATES = [
    FlightNumberRepresentation.R0_LOW_CARD_ONE_HOT,
    FlightNumberRepresentation.R1_FREQUENCY_MAP,
    FlightNumberRepresentation.R2_EMBEDDING,
]


def run_stage2_representation_ablation(
    *,
    train_sample_per_year: int = 5000,
    val_sample: int = 5000,
    seed: int = 202601,
    max_epochs: int = 20,
    batch_size: int = 256,
    output_dir: str | Path = "artifacts/probabilistic/representation_ablation",
    manifest_path: str | Path = "artifacts/manifests/probabilistic_stage2_representation_ablation_v1.json",
) -> dict[str, Any]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    manifest_file = Path(manifest_path)
    manifest_file.parent.mkdir(parents=True, exist_ok=True)

    start_time = time.time()
    LOGGER.info("=================================================================")
    LOGGER.info("STARTING STAGE 2 REPRESENTATION ABLATION EXECUTION")
    LOGGER.info(
        f"Screening seed: {seed}, Sample: {train_sample_per_year}/yr train, {val_sample} val"
    )
    LOGGER.info("=================================================================")

    per_fold_results: dict[str, dict[str, Any]] = {}
    pooled_preds: dict[str, list[np.ndarray]] = {c.value: [] for c in CANDIDATES}
    pooled_true: list[np.ndarray] = []

    for fold in FOLDS:
        fold_id = fold["fold_id"]
        train_years = fold["outer_train_years"]
        val_year = fold["outer_val_year"]
        inner_train_years = fold["inner_train_years"]
        inner_val_years = fold["inner_val_years"]

        LOGGER.info(f"\n--- Processing {fold_id} (Train {train_years}, Val {val_year}) ---")

        # Load stratified fold data
        LOGGER.info(f"Loading monthly-stratified data for Train {train_years} and Val {val_year}...")
        root = Path(__file__).resolve().parents[1]
        (
            X_train,
            _,
            y_train_reg,
            _,
            X_val,
            _,
            y_val_reg,
            val_flight_keys,
        ) = load_stratified_fold_data(
            train_years=train_years,
            val_year=val_year,
            sample_train_per_year=train_sample_per_year,
            sample_val=val_sample,
            project_root=root,
            random_state=seed,
            feature_set="v1",
        )

        train_df = X_train.copy()
        train_df["ARR_DELAY"] = y_train_reg.to_numpy(dtype=np.float64)

        val_df = X_val.copy()
        val_df["ARR_DELAY"] = y_val_reg.to_numpy(dtype=np.float64)

        # Build flight_date and flight_key deterministically
        for df in (train_df, val_df):
            if "flight_date" not in df.columns:
                df["flight_date"] = (
                    df["calendar_year"].astype(int).astype(str)
                    + "-"
                    + df["calendar_month"].astype(int).astype(str).str.zfill(2)
                    + "-"
                    + df["calendar_day_of_month"].astype(int).astype(str).str.zfill(2)
                )
            if "flight_key" not in df.columns:
                df["flight_key"] = [
                    f"{d}_{c}_{fl}_{i}"
                    for i, (d, c, fl) in enumerate(
                        zip(df["flight_date"], df["OP_CARRIER"], df["OP_CARRIER_FL_NUM"])
                    )
                ]

        # Temporal inner splits
        inner_train_df = train_df[train_df["calendar_year"].isin(inner_train_years)].copy()
        inner_val_df = train_df[train_df["calendar_year"].isin(inner_val_years)].copy()

        y_val_true = val_df["ARR_DELAY"].to_numpy(dtype=np.float64)
        pooled_true.append(y_val_true)

        per_fold_results[fold_id] = {}

        for cand in CANDIDATES:
            LOGGER.info(f"  -> Training candidate: {cand.value}...")
            t0 = time.time()
            res = train_point_model_fold(
                rep_type=cand,
                train_df=train_df,
                val_df=val_df,
                inner_train_df=inner_train_df,
                inner_val_df=inner_val_df,
                seed=seed,
                max_epochs=max_epochs,
                batch_size=batch_size,
            )
            elapsed = time.time() - t0

            y_pred = res["y_pred"]
            pooled_preds[cand.value].append(y_pred)

            # Save prediction parquet
            pred_df = pd.DataFrame(
                {
                    "flight_key": val_df["flight_key"].to_numpy(),
                    "flight_date": val_df["flight_date"].to_numpy(),
                    "y_true": y_val_true,
                    "y_pred": y_pred,
                    "error": y_val_true - y_pred,
                    "abs_error": np.abs(y_val_true - y_pred),
                }
            )
            parquet_path = output_path / f"{cand.value}_predictions_{fold_id}.parquet"
            pred_df.to_parquet(parquet_path, index=False)

            stats = res["provenance_stats"]
            stats_dict = (
                {
                    "train_flight_category_count": stats.train_flight_category_count,
                    "val_flight_category_count": stats.val_flight_category_count,
                    "unseen_flight_category_count": stats.unseen_flight_category_count,
                    "unseen_flight_rate": stats.unseen_flight_rate,
                    "rare_count_le_1": stats.rare_count_le_1,
                    "rare_count_le_5": stats.rare_count_le_5,
                    "rare_count_le_10": stats.rare_count_le_10,
                    "embedding_vocabulary_size": stats.embedding_vocabulary_size,
                    "unknown_index": stats.unknown_index,
                    "unknown_index_usage_count": stats.unknown_index_usage_count,
                    "unknown_index_usage_rate": stats.unknown_index_usage_rate,
                }
                if stats is not None
                else {}
            )

            per_fold_results[fold_id][cand.value] = {
                "best_epoch": res["best_epoch"],
                "best_inner_mae": res["best_inner_mae"],
                "outer_metrics": res["outer_metrics"],
                "train_time_sec": elapsed,
                "provenance_stats": stats_dict,
                "predictions_artifact": str(parquet_path.resolve().relative_to(Path.cwd().resolve())).replace("\\", "/"),
            }

    # -------------------------------------------------------------------------
    # Pooled Development Metrics
    # -------------------------------------------------------------------------
    LOGGER.info("\n--- Computing Pooled Development Metrics ---")
    all_y_true = np.concatenate(pooled_true)
    pooled_metrics: dict[str, dict[str, Any]] = {}

    for cand in CANDIDATES:
        c_val = cand.value
        all_y_pred = np.concatenate(pooled_preds[c_val])
        mae = float(np.mean(np.abs(all_y_true - all_y_pred)))
        rmse = float(np.sqrt(np.mean((all_y_true - all_y_pred) ** 2)))
        medae = float(np.median(np.abs(all_y_true - all_y_pred)))
        r2 = float(
            1.0 - (np.sum((all_y_true - all_y_pred) ** 2) / np.sum((all_y_true - np.mean(all_y_true)) ** 2))
        )
        pearson_r = (
            float(np.corrcoef(all_y_true, all_y_pred)[0, 1]) if np.std(all_y_pred) > 1e-8 else 0.0
        )

        pooled_metrics[c_val] = {
            "pooled_mae": mae,
            "pooled_rmse": rmse,
            "pooled_medae": medae,
            "pooled_r2": r2,
            "pooled_pearson_r": pearson_r,
        }

    # Relative attribution comparisons against R1 (frequency map)
    r1_mae = pooled_metrics[FlightNumberRepresentation.R1_FREQUENCY_MAP.value]["pooled_mae"]
    r2_mae = pooled_metrics[FlightNumberRepresentation.R2_EMBEDDING.value]["pooled_mae"]
    r0_mae = pooled_metrics[FlightNumberRepresentation.R0_LOW_CARD_ONE_HOT.value]["pooled_mae"]

    attribution_comparison = {
        "baseline_representation": FlightNumberRepresentation.R1_FREQUENCY_MAP.value,
        "r1_frequency_map_mae": r1_mae,
        "r2_embedding_mae": r2_mae,
        "r2_minus_r1_mae_delta": float(r2_mae - r1_mae),
        "r2_relative_improvement_pct": float((r1_mae - r2_mae) / r1_mae * 100.0),
        "r0_low_card_one_hot_mae": r0_mae,
        "r0_minus_r1_mae_delta": float(r0_mae - r1_mae),
        "attribution_conclusion": (
            "R2 (embedding) improves point MAE over R1 (frequency-map)"
            if r2_mae < r1_mae
            else "R1 (frequency-map) matches or outperforms R2 (embedding)"
        ),
    }

    wall_clock = time.time() - start_time
    LOGGER.info(f"\n=================================================================")
    LOGGER.info(f"STAGE 2 REPRESENTATION ABLATION COMPLETED in {wall_clock:.2f} seconds")
    LOGGER.info(f"R1 (Frequency-Map) MAE: {r1_mae:.4f}")
    LOGGER.info(f"R2 (Embedding)     MAE: {r2_mae:.4f}")
    LOGGER.info(f"R0 (Top-50 OneHot) MAE: {r0_mae:.4f}")
    LOGGER.info(f"Attribution Delta (R2 - R1): {attribution_comparison['r2_minus_r1_mae_delta']:.4f} min")
    LOGGER.info("=================================================================")

    summary_manifest = {
        "manifest_version": "probabilistic_stage2_representation_ablation_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_manifest": "artifacts/manifests/probabilistic_protocol_v1.json",
        "seed": seed,
        "sample_train_per_year": train_sample_per_year,
        "sample_val": val_sample,
        "total_wall_seconds": wall_clock,
        "candidates_evaluated": [c.value for c in CANDIDATES],
        "folds": [f["fold_id"] for f in FOLDS],
        "validation_years": [f["outer_val_year"] for f in FOLDS],
        "per_fold_results": per_fold_results,
        "pooled_development_metrics": pooled_metrics,
        "attribution_comparison": attribution_comparison,
        "experimental_control": {
            "model_architecture": "MLP (50 -> 128 -> LayerNorm -> Dropout(0.1) -> 64 -> 1)",
            "hidden_dims": [128, 64],
            "optimizer": "AdamW(lr=0.001, weight_decay=0.0001)",
            "loss": "SmoothL1Loss(beta=1.0)",
            "batch_size": batch_size,
            "early_stopping_procedure": "Two-phase inner/outer (best_epoch from inner_val, retrained fresh on outer_train)",
            "numeric_representation": "10 cyclic and standardized continuous features",
            "carrier_origin_representation": "OP_CARRIER(dim 8) + ORIGIN(dim 16) embeddings",
        },
        "holdout_guards": {
            "2023_accessed": False,
            "2024_accessed": False,
        },
    }

    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(summary_manifest, f, indent=2)

    LOGGER.info(f"Summary manifest written to: {manifest_file}")
    return summary_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Stage 2 Representation Ablation")
    parser.add_argument("--train-sample", type=int, default=5000, help="Train samples per year")
    parser.add_argument("--val-sample", type=int, default=5000, help="Validation samples per year")
    parser.add_argument("--seed", type=int, default=202601, help="Screening seed")
    parser.add_argument("--epochs", type=int, default=20, help="Max inner epochs")
    parser.add_argument("--batch-size", type=int, default=256, help="Batch size")
    args = parser.parse_args()

    run_stage2_representation_ablation(
        train_sample_per_year=args.train_sample,
        val_sample=args.val_sample,
        seed=args.seed,
        max_epochs=args.epochs,
        batch_size=args.batch_size,
    )


if __name__ == "__main__":
    main()
