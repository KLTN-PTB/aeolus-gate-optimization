"""Tests for Unified Probabilistic Evaluation Engine.

Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Sections 8, 9, 10
Verifies:
1. Unified evaluation for Student-T predictive models (discrete & continuous).
2. Unified evaluation for Gaussian Mixture predictive models.
3. Quantile inputs evaluation with crossing detection and monotonic rearrangement.
4. Interval coverage and width at nominal levels (0.50, 0.80, 0.90, 0.95).
5. Event metrics at thresholds Y >= 15, 60, 120 (Brier, LogScore, ECE).
6. Discrete randomized PIT (rPIT) uniformity test.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.models.probabilistic.contracts import ProbabilisticContractViolation
from src.models.probabilistic.correctness import GaussianMixtureDistribution
from src.models.probabilistic.student_t_correctness import StudentTDistribution
from src.models.probabilistic.unified_evaluation import (
    compute_expected_calibration_error,
    compute_quantile_crps_approximation,
    evaluate_probabilistic_predictions,
    rearrange_quantiles_monotonically,
)


def test_unified_evaluation_student_t_discrete() -> None:
    """Verify unified evaluation runs and produces all metrics for Student-t discrete model."""
    rng = np.random.default_rng(202601)
    n = 200
    mu = rng.normal(5.0, 3.0, size=n)
    sigma = rng.uniform(2.0, 5.0, size=n)
    df = np.full(n, 3.5)

    # True integer observations
    y_true = np.rint(mu + sigma * rng.standard_t(df=3.5, size=n)).astype(np.int64)

    res = evaluate_probabilistic_predictions(
        y_true,
        student_t_params=(mu, sigma, df),
        discrete=True,
        seed=202601,
    )

    assert res.sample_count == n
    assert res.discrete is True
    assert res.crps_mean is not None and res.crps_mean > 0.0
    assert res.nll_mean is not None and np.isfinite(res.nll_mean)

    # Intervals check
    for nom in (0.50, 0.80, 0.90, 0.95):
        assert nom in res.intervals
        interval = res.intervals[nom]
        assert 0.0 <= interval.coverage <= 1.0
        assert interval.mean_width > 0.0

    # Event metrics check
    for thr in (15, 60, 120):
        assert thr in res.event_metrics
        ev = res.event_metrics[thr]
        assert 0.0 <= ev.brier_score <= 1.0
        assert 0.0 <= ev.expected_calibration_error <= 1.0
        assert np.isfinite(ev.log_score)

    # Pinball losses check
    for alpha in (0.025, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.975):
        assert alpha in res.pinball_losses
        assert res.pinball_losses[alpha] > 0.0

    # rPIT check
    assert res.rpit_result is not None
    assert 0.0 <= res.rpit_result.ks_statistic <= 1.0
    assert len(res.rpit_result.histogram_10bins) == 10

    # Serialization check
    d = res.to_dict()
    assert d["sample_count"] == n
    assert "0.80" in d["intervals"]
    assert "15" in d["event_metrics"]


def test_unified_evaluation_gaussian_mixture_discrete() -> None:
    """Verify unified evaluation runs for Gaussian Mixture models."""
    n = 150
    k = 3
    pi = np.tile([0.6, 0.3, 0.1], (n, 1))
    mu = np.tile([0.0, 15.0, 45.0], (n, 1))
    sigma = np.tile([5.0, 10.0, 20.0], (n, 1))

    rng = np.random.default_rng(202602)
    y_true = rng.integers(-10, 80, size=n)

    res = evaluate_probabilistic_predictions(
        y_true,
        gaussian_mixture_params=(pi, mu, sigma),
        discrete=True,
    )

    assert res.sample_count == n
    assert res.crps_mean is not None and res.crps_mean > 0.0
    assert res.nll_mean is not None and np.isfinite(res.nll_mean)
    assert len(res.intervals) == 4
    assert len(res.event_metrics) == 3


def test_unified_evaluation_distribution_sequence() -> None:
    """Verify evaluation accepts a list of MarginalDistributionProtocol objects."""
    n = 50
    dist_list = [
        StudentTDistribution(mu=float(i), sigma=3.0, df=4.0, discrete=True)
        for i in range(n)
    ]
    y_true = np.array([i + 1 for i in range(n)], dtype=np.int64)

    res = evaluate_probabilistic_predictions(
        y_true,
        distribution=dist_list,
        discrete=True,
    )

    assert res.sample_count == n
    assert res.crps_mean is not None
    assert res.nll_mean is not None


def test_unified_evaluation_quantiles_and_rearrangement() -> None:
    """Verify quantile inputs, quantile crossing detection, and monotonic rearrangement."""
    n = 100
    y_true = np.linspace(-10, 50, n)

    # Synthesize quantiles with an intentional crossing inversion at index 0
    q_dict = {
        0.10: np.linspace(0, 40, n),
        0.50: np.linspace(5, 45, n),
        0.90: np.linspace(10, 50, n),
    }
    # Create inversion: q_0.10 > q_0.50 at sample 0
    q_dict[0.10][0] = 50.0

    res_raw = evaluate_probabilistic_predictions(
        y_true,
        quantiles=q_dict,
        rearrange_quantiles=False,
    )
    assert res_raw.quantile_crossing_inversions > 0
    assert res_raw.quantile_crossing_rate > 0.0

    res_fixed = evaluate_probabilistic_predictions(
        y_true,
        quantiles=q_dict,
        rearrange_quantiles=True,
    )
    assert res_fixed.quantile_crossing_inversions == 0
    assert res_fixed.quantile_crossing_rate == 0.0


def test_unified_evaluation_empty_error() -> None:
    """Verify empty input raises contract violation."""
    with pytest.raises(ProbabilisticContractViolation):
        evaluate_probabilistic_predictions(np.array([]), quantiles={0.5: np.array([])})
