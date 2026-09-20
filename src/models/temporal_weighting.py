"""Temporal sample weighting module for Aeolus Gate Optimization.

Addresses Covariate Shift and COVID-19 pandemic distortion:
1. Penalizes lockdown year 2020 with weight = 0.5 to mitigate abnormal flight patterns.
2. Applies progressive decay for older pre-pandemic years (2016-2019).
3. Gives full weight (1.0) to the most recent training year (target_val_year - 1).
"""

from __future__ import annotations

from typing import Sequence
import numpy as np
import pandas as pd


def compute_temporal_sample_weights(
    years: pd.Series | np.ndarray | Sequence[int],
    target_val_year: int = 2022,
    *,
    covid_year: int = 2020,
    covid_weight: float = 0.5,
    annual_decay_rate: float = 0.04,
    min_weight: float = 0.75,
    max_weight: float = 1.0,
) -> np.ndarray:
    """Compute sample weights based on temporal proximity and pandemic shock.

    Args:
        years: Sequence or 1D array-like containing calendar year of each observation.
        target_val_year: The validation year being evaluated (default: 2022).
        covid_year: The year of peak pandemic anomaly (default: 2020).
        covid_weight: Penalty weight assigned to the COVID-19 year (default: 0.5).
        annual_decay_rate: Linear decay per year prior to the anchor year (default: 0.04).
        min_weight: Minimum floor for decayed sample weights (default: 0.75).
        max_weight: Maximum ceiling for sample weights (default: 1.0).

    Returns:
        np.ndarray of shape (N,) and dtype np.float32.
    """
    if isinstance(years, pd.Series):
        year_arr = years.to_numpy(dtype=np.int32)
    else:
        year_arr = np.asarray(years, dtype=np.int32).reshape(-1)

    if len(year_arr) == 0:
        return np.empty(0, dtype=np.float32)

    anchor_year = target_val_year - 1
    diff = anchor_year - year_arr

    # Linear decay clipped within [min_weight, max_weight]
    weights = np.clip(1.0 - annual_decay_rate * diff, min_weight, max_weight).astype(np.float32)

    # Penalize COVID-19 lockdown year
    weights[year_arr == covid_year] = np.float32(covid_weight)

    return weights
