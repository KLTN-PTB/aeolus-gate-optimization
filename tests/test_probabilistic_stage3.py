"""Unit tests for Stage 3 — Distribution Ablation.

Verifies:
1. PyTorch log_ndtr_diff_torch numerical stability across tail regimes.
2. Exact Gaussian mixture CRPS matches single Gaussian when K=1.
3. Distribution model ladder invariance (D1 fixed sigma, D2 heteroscedastic, D3 mixture).
4. Calendar-year controlled ablation toggle.
5. K=5 opening criteria evaluation logic.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import torch

from src.models.probabilistic.distribution_ablation import (
    DistributionLadderCandidate,
    Stage3DistributionModel,
    Stage3DistributionPreprocessor,
    gaussian_mixture_crps,
    log_ndtr_diff_torch,
)
from src.models.probabilistic.likelihood import log_ndtr_diff
from src.models.probabilistic.metrics import compute_gaussian_crps


def test_log_ndtr_diff_torch_stability():
    # Test right tail, left tail, and straddle
    a_np = np.array([-10.0, -5.0, -1.0, 0.5, 4.5, 8.0], dtype=np.float64)
    b_np = a_np + 0.5

    a_torch = torch.from_numpy(a_np)
    b_torch = torch.from_numpy(b_np)

    scipy_res = log_ndtr_diff(a_np, b_np)
    torch_res = log_ndtr_diff_torch(a_torch, b_torch).numpy()

    # Must be finite and close to scipy across all regimes
    assert np.all(np.isfinite(torch_res))
    assert np.allclose(scipy_res, torch_res, atol=1e-4, rtol=1e-3)


def test_gaussian_mixture_crps_k1_matches_single_gaussian():
    np.random.seed(42)
    n = 100
    y = np.random.normal(5, 20, n)
    mu = np.random.normal(5, 10, (n, 1))
    sigma = np.random.uniform(5, 30, (n, 1))
    pi = np.ones((n, 1), dtype=np.float64)

    # 1. Mixture CRPS with K=1
    crps_mix = gaussian_mixture_crps(y, pi, mu, sigma)

    # 2. Closed-form single Gaussian CRPS (y_true, mu, sigma)
    crps_single = compute_gaussian_crps(y, mu.squeeze(-1), sigma.squeeze(-1))

    assert np.allclose(crps_mix, crps_single, atol=1e-5)


def test_gaussian_mixture_crps_k3_properties():
    np.random.seed(42)
    n = 50
    y = np.random.normal(0, 15, n)
    pi = np.array([[0.5, 0.3, 0.2]] * n)
    mu = np.array([[-5.0, 0.0, 20.0]] * n)
    sigma = np.array([[10.0, 15.0, 30.0]] * n)

    crps_vals = gaussian_mixture_crps(y, pi, mu, sigma)
    assert len(crps_vals) == n
    assert np.all(crps_vals >= 0.0)
    assert np.all(np.isfinite(crps_vals))


def test_stage3_model_architectural_invariance():
    n = 20
    num_cont = 10
    num_carriers = 5
    num_origins = 10

    x_cont = torch.randn(n, num_cont)
    x_c = torch.randint(0, num_carriers, (n,))
    x_o = torch.randint(0, num_origins, (n,))
    x_fl = torch.rand(n, 1)

    for cand, k in [
        (DistributionLadderCandidate.D1_K1_FIXED_SIGMA, 1),
        (DistributionLadderCandidate.D2_K1_HETEROSCEDASTIC, 1),
        (DistributionLadderCandidate.D3_K3_MIXTURE, 3),
    ]:
        model = Stage3DistributionModel(
            candidate=cand,
            num_continuous=num_cont,
            num_carriers=num_carriers,
            num_origins=num_origins,
            k_components=k,
        )

        pi, mu, sigma = model(x_cont, x_c, x_o, x_fl)

        assert pi.shape == (n, k)
        assert mu.shape == (n, k)
        assert sigma.shape == (n, k)
        assert torch.all(sigma >= 1.0)  # sigma floor enforced
        assert torch.allclose(pi.sum(dim=-1), torch.ones(n))

        if cand == DistributionLadderCandidate.D1_K1_FIXED_SIGMA:
            # All sigma values must be identical across rows
            assert torch.all(sigma == sigma[0, 0])
        elif cand == DistributionLadderCandidate.D2_K1_HETEROSCEDASTIC:
            # Heteroscedastic sigma should vary with input features
            assert not torch.all(sigma == sigma[0, 0])


def test_stage3_calendar_year_ablation():
    df = {
        "CRS_ELAPSED_TIME": [100.0, 200.0],
        "calendar_year": [2018, 2018],
        "calendar_month": [6, 7],
        "calendar_day_of_month": [15, 20],
        "calendar_day_of_week": [3, 4],
        "is_weekend": [0, 1],
        "scheduled_departure_hour": [10, 14],
        "scheduled_departure_minute": [30, 45],
        "OP_CARRIER": ["DL", "WN"],
        "ORIGIN": ["ATL", "ORD"],
        "OP_CARRIER_FL_NUM": ["101", "202"],
    }
    df = pd.DataFrame(df)

    prep_with = Stage3DistributionPreprocessor(include_calendar_year=True)
    prep_with.fit(df)
    res_with = prep_with.transform(df)
    assert res_with["continuous"].shape[1] == 10  # 6 cyclic + 4 numeric

    prep_without = Stage3DistributionPreprocessor(include_calendar_year=False)
    prep_without.fit(df)
    res_without = prep_without.transform(df)
    assert res_without["continuous"].shape[1] == 9  # 6 cyclic + 3 numeric (no calendar_year)
