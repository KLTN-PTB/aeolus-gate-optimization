"""Comprehensive Probabilistic Evaluation Engine for Core Arrival.

Protocol: Phase 4 Common Distribution Contract
Scope:
- Delegates evaluation to common src.evaluation.forecast_metrics.evaluate_predictive_distribution
- Eliminates duplicate evaluation logic across repository
- Preserves backwards-compatible function signature
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.contracts.distribution import PredictiveDistribution
from src.evaluation.forecast_metrics import evaluate_predictive_distribution


def evaluate_probabilistic_prediction(
    prediction: PredictiveDistribution,
    y_true: np.ndarray | pd.Series,
) -> dict[str, Any]:
    """Compute comprehensive proper scores and calibration diagnostics.

    Delegates directly to common evaluation engine to ensure consistency and eliminate duplication.
    """
    return evaluate_predictive_distribution(prediction, y_true)
