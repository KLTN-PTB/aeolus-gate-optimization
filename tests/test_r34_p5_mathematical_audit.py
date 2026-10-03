"""R34 Test Suite: P5 Quantile Configuration and CRPS Mathematical Audit.

Verifies:
1. test_final_quantile_count: PRE_REGISTERED_QUANTILES has length 9.
2. test_final_quantile_levels: Quantiles match (0.025, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.975).
3. test_prediction_shape_matches_quantile_count: Actual prediction parquet has 9 quantile columns.
4. test_metric_source_traceable: Traces 16.8477 and 16.7675 in raw manifests.
5. test_metric_classification: Reconciles taxonomy to CRPS_QUANTILE_APPROXIMATION.
6. test_no_pinball_as_crps: Confirms pinball loss is distinct from integrated CRPS approximation.
7. test_no_approximation_as_exact_crps: Asserts crps_exact is False, crps_approx is True.
8. test_no_unsupported_continuous_density: Confirms continuous CDF raises CapabilityNotSupportedError.
9. test_no_unsupported_continuous_nll: Confirms nll capability is False.
10. test_no_unsupported_pit: Confirms pit capability is False.
"""

from __future__ import annotations

import json
import os
import numpy as np
import pandas as pd
import pytest

from src.contracts.distribution import (
    CapabilityNotSupportedError,
    QuantilePredictiveDistribution,
)
from src.models.probabilistic.metrics import (
    PRE_REGISTERED_QUANTILES,
    compute_pinball_loss,
)
from src.models.probabilistic.unified_evaluation import (
    compute_quantile_crps_approximation,
)


def test_final_quantile_count() -> None:
    """Verify that P5 pre-registered quantile grid has exactly 9 levels."""
    assert len(PRE_REGISTERED_QUANTILES) == 9


def test_final_quantile_levels() -> None:
    """Verify exact pre-registered quantile levels."""
    expected = (0.025, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.975)
    assert tuple(PRE_REGISTERED_QUANTILES) == expected


def test_prediction_shape_matches_quantile_count() -> None:
    """Verify that raw OOF prediction parquet files contain exactly 9 quantile columns."""
    path = "artifacts/probabilistic_benchmark/core_probabilistic_benchmark_v2/core_probabilistic_benchmark_v2/oof/P5_quantile_regression_fold_1.parquet"
    assert os.path.exists(path), f"Missing {path}"

    df = pd.read_parquet(path)
    q_cols = [c for c in df.columns if c.startswith("q_")]
    assert len(q_cols) == 9
    expected_cols = [
        "q_0.025",
        "q_0.050",
        "q_0.100",
        "q_0.250",
        "q_0.500",
        "q_0.750",
        "q_0.900",
        "q_0.950",
        "q_0.975",
    ]
    assert q_cols == expected_cols


def test_metric_source_traceable() -> None:
    """Verify traceability of 16.85 (16.8477 in V1) and 16.7675 in 2024 holdout."""
    v1_path = "artifacts/manifests/academic_model_selection_v1.json"
    assert os.path.exists(v1_path)
    with open(v1_path, "r", encoding="utf-8") as f:
        v1_data = json.load(f)
    p5_v1 = v1_data["ranking_free_comparison_table"]["probabilistic_models"]["P5_quantile_regression"]
    assert abs(p5_v1["crps"] - 16.8477) < 1e-3

    holdout_path = "artifacts/post_holdout_v3/marginal_forecast_metrics_2024_v3.json"
    assert os.path.exists(holdout_path)
    with open(holdout_path, "r", encoding="utf-8") as f:
        holdout_data = json.load(f)
    p5_holdout = holdout_data["metrics"]["P5_quantile_regression"]
    assert abs(p5_holdout["crps"] - 16.7675) < 1e-4


def test_metric_classification() -> None:
    """Verify that R34 audit artifact classifies 16.85 as CRPS_QUANTILE_APPROXIMATION."""
    cap_path = "artifacts/audit/r34_p5_capability_forensics.json"
    assert os.path.exists(cap_path)
    with open(cap_path, "r", encoding="utf-8") as f:
        cap_data = json.load(f)
    assert cap_data["taxonomy_classification"] == "CRPS_QUANTILE_APPROXIMATION"
    assert cap_data["final_status_block"]["P5_16_85_METRIC"] == "CRPS_QUANTILE_APPROXIMATION"


def test_no_pinball_as_crps() -> None:
    """Verify that pinball loss is numerically distinct from integrated CRPS approximation."""
    y = np.array([20.0])
    q_dict = {a: np.array([15.0 + 10.0 * a]) for a in PRE_REGISTERED_QUANTILES}

    pinball_50 = float(compute_pinball_loss(y, q_dict[0.5], 0.5)[0])
    crps_approx = float(compute_quantile_crps_approximation(y, q_dict)[0])

    # Integrated CRPS over 9 quantiles is distinctly different from a single pinball loss
    assert abs(pinball_50 - crps_approx) > 0.1
    assert crps_approx > 0.0


def test_no_approximation_as_exact_crps() -> None:
    """Verify that QuantilePredictiveDistribution explicitly disclaims exact CRPS."""
    q_dict = {a: np.array([10.0]) for a in PRE_REGISTERED_QUANTILES}
    dist = QuantilePredictiveDistribution(quantiles_dict=q_dict)

    caps = dist.capabilities
    assert caps.crps_exact is False
    assert caps.crps_approx is True


def test_no_unsupported_continuous_density() -> None:
    """Verify that QuantilePredictiveDistribution rejects continuous CDF evaluation."""
    q_dict = {a: np.array([10.0]) for a in PRE_REGISTERED_QUANTILES}
    dist = QuantilePredictiveDistribution(quantiles_dict=q_dict)

    assert dist.capabilities.cdf is False
    with pytest.raises(CapabilityNotSupportedError, match="do not provide a continuous CDF"):
        dist.cdf(10.0)


def test_no_unsupported_continuous_nll() -> None:
    """Verify that QuantilePredictiveDistribution disclaims continuous likelihood."""
    q_dict = {a: np.array([10.0]) for a in PRE_REGISTERED_QUANTILES}
    dist = QuantilePredictiveDistribution(quantiles_dict=q_dict)

    assert dist.capabilities.nll is False


def test_no_unsupported_pit() -> None:
    """Verify that QuantilePredictiveDistribution disclaims continuous PIT calibration."""
    q_dict = {a: np.array([10.0]) for a in PRE_REGISTERED_QUANTILES}
    dist = QuantilePredictiveDistribution(quantiles_dict=q_dict)

    assert dist.capabilities.pit is False
