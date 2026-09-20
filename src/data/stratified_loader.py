"""Stratified Sampling by Month Data Loader for Aeolus Gate Optimization.

Solves the truncated loading flaw:
- Scans all batches across the entire calendar year (12 months).
- Samples uniformly across all 12 calendar months (FL_DATE.dt.month).
- Ensures balanced temporal coverage without summer/storm season omission.
"""

from __future__ import annotations

import gc
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

from src.data.access_guard import assert_data_access_allowed
from src.data.load_aeolus import resolve_project_root
from src.data.preprocessing import iter_arrival_development_batches
from src.features.refactored_features import (
    PreparedArrivalFeaturesV2,
    prepare_arrival_features_v2,
)


def load_stratified_year_data(
    year: int,
    target_samples: int,
    *,
    project_root: Path | None = None,
    random_state: int = 42,
    batch_size: int = 16384,
) -> pd.DataFrame:
    """Load stratified samples uniformly distributed across 12 calendar months.

    Args:
        year: Year to load (2016-2022).
        target_samples: Desired total rows to sample for the year.
        project_root: Optional root directory of the project.
        random_state: Seed for reproducible sampling.
        batch_size: Batch size for scanning parquet partitions.

    Returns:
        pd.DataFrame containing target_samples stratified across all 12 months.
    """
    assert_data_access_allowed(year, "development")
    root = resolve_project_root(project_root)

    print(f"[*] Scanning all inbound batches for year {year} across 12 months...")
    raw_batches: list[pd.DataFrame] = []
    for batch in iter_arrival_development_batches(year, project_root=root, batch_size=batch_size):
        raw_batches.append(batch)

    if not raw_batches:
        raise ValueError(f"No arrival development batches found for year {year}")

    year_raw = pd.concat(raw_batches, ignore_index=True)
    del raw_batches
    gc.collect()

    # Determine month column
    if "MONTH" in year_raw.columns:
        month_series = year_raw["MONTH"].astype(int)
    else:
        month_series = pd.to_datetime(year_raw["FL_DATE"]).dt.month.astype(int)

    year_raw["_STRATA_MONTH"] = month_series

    # Compute target sample allocation per month
    unique_months = sorted(year_raw["_STRATA_MONTH"].unique())
    n_months = len(unique_months)
    base_quota = target_samples // n_months
    remainder = target_samples % n_months

    sampled_month_dfs: list[pd.DataFrame] = []
    rng = np.random.default_rng(random_state)

    for idx, m in enumerate(unique_months):
        quota = base_quota + (1 if idx < remainder else 0)
        m_df = year_raw.loc[year_raw["_STRATA_MONTH"] == m]
        if len(m_df) <= quota:
            sampled_month_dfs.append(m_df.copy())
        else:
            sampled_idx = rng.choice(m_df.index, size=quota, replace=False)
            sampled_month_dfs.append(m_df.loc[sampled_idx].copy())

    sampled_df = pd.concat(sampled_month_dfs, ignore_index=True)
    sampled_df = sampled_df.drop(columns=["_STRATA_MONTH"])

    # Shuffle the final stratified dataset
    shuffled_idx = rng.permutation(len(sampled_df))
    sampled_df = sampled_df.iloc[shuffled_idx].reset_index(drop=True)

    del year_raw
    gc.collect()

    return sampled_df


def get_month_distribution_report(df: pd.DataFrame, name: str = "Dataset") -> pd.DataFrame:
    """Compute percentage distribution across all 12 calendar months."""
    if "MONTH" in df.columns:
        months = df["MONTH"].astype(int)
    elif "FL_DATE" in df.columns:
        months = pd.to_datetime(df["FL_DATE"]).dt.month.astype(int)
    elif "calendar_month" in df.columns:
        months = df["calendar_month"].astype(int)
    else:
        raise ValueError("Cannot locate month column in dataframe")

    counts = months.value_counts().sort_index()
    pcts = (counts / len(df)) * 100.0
    report = pd.DataFrame({
        "Month": counts.index,
        "Count": counts.values,
        "Percentage": np.round(pcts.values, 2),
    })
    return report


def load_stratified_fold_data(
    train_years: Sequence[int],
    val_year: int,
    *,
    sample_train_per_year: int = 35000,
    sample_val: int = 40000,
    project_root: Path | None = None,
    random_state: int = 42,
) -> tuple[pd.DataFrame, pd.Series, pd.Series, np.ndarray, pd.DataFrame, pd.Series, pd.Series, pd.Series]:
    """Load and prepare features with monthly stratified sampling.

    Returns:
        (X_train, y_train_cls, y_train_reg, train_years_vec,
         X_val, y_val_cls, y_val_reg, val_flight_keys)
    """
    root = resolve_project_root(project_root)

    train_x_list: list[pd.DataFrame] = []
    train_cls_list: list[pd.Series] = []
    train_reg_list: list[pd.Series] = []
    train_year_list: list[np.ndarray] = []

    print(f"[*] Loading monthly-stratified Train data for years {list(train_years)} ({sample_train_per_year}/yr)...")
    for yr in train_years:
        raw_yr = load_stratified_year_data(
            yr,
            target_samples=sample_train_per_year,
            project_root=root,
            random_state=random_state + yr,
        )
        prep = prepare_arrival_features_v2(raw_yr)
        train_x_list.append(prep.X)
        train_cls_list.append(prep.y_arr_cls)
        train_reg_list.append(prep.y_arr_reg)
        train_year_list.append(np.full(len(prep.X), yr, dtype=np.int32))
        del raw_yr, prep
        gc.collect()

    X_train = pd.concat(train_x_list, ignore_index=True)
    y_train_cls = pd.concat(train_cls_list, ignore_index=True)
    y_train_reg = pd.concat(train_reg_list, ignore_index=True)
    train_years_vec = np.concatenate(train_year_list)

    print(f"[*] Loading monthly-stratified Validation data for year {val_year} ({sample_val} samples)...")
    raw_val = load_stratified_year_data(
        val_year,
        target_samples=sample_val,
        project_root=root,
        random_state=random_state + val_year,
    )
    val_prep = prepare_arrival_features_v2(raw_val)
    X_val = val_prep.X
    y_val_cls = val_prep.y_arr_cls
    y_val_reg = val_prep.y_arr_reg
    val_flight_keys = val_prep.identifiers["flight_key"]

    return (
        X_train,
        y_train_cls,
        y_train_reg,
        train_years_vec,
        X_val,
        y_val_cls,
        y_val_reg,
        val_flight_keys,
    )
