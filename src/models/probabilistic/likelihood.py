"""Numerically stable discretized and continuous Gaussian mixture likelihoods.

Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 3.2
Specifications:
1. Discretized Gaussian mixture (Primary specification for quantized integer minutes):
   P(Y = y | X) = sum_k pi_k [ Phi((y + 0.5 - mu_k)/sigma_k) - Phi((y - 0.5 - mu_k)/sigma_k) ]
2. Continuous Gaussian mixture (Registered comparison specification):
   p(y | X) = sum_k pi_k N(y; mu_k, sigma_k^2)
3. Numerically stable log[Phi(b) - Phi(a)] avoiding underflow/cancellation in extreme tails.
4. Exact integer quantile: Q(p) = min{ y in Z : F(y) >= p }.
"""

from __future__ import annotations

import numpy as np
from scipy.special import log_ndtr, logsumexp, ndtr


def log1mexp(x: np.ndarray | float) -> np.ndarray | float:
    """Compute log(1 - exp(-x)) accurately for x > 0.

    Reference: Martin Maechler (2012), 'Accurately Computing log(1 - exp(-|a|))'.
    """
    is_scalar = np.isscalar(x)
    arr = np.asarray(x, dtype=np.float64)
    res = np.empty_like(arr)

    # When x <= 0, mathematically undefined; clip to tiny positive for safety
    safe_x = np.maximum(arr, 1e-16)

    # Threshold log(2) ~ 0.6931471805599453
    mask = safe_x <= 0.6931471805599453
    res[mask] = np.log(-np.expm1(-safe_x[mask]))
    res[~mask] = np.log1p(-np.exp(-safe_x[~mask]))

    if is_scalar:
        return float(res.item())
    return res


def log_ndtr_diff(
    a: np.ndarray | float, b: np.ndarray | float
) -> np.ndarray | float:
    """Accurately compute log[Phi(b) - Phi(a)] for a < b across all tail regimes.

    Prevents catastrophic cancellation when Phi(b) ~ Phi(a) in deep tails.
    """
    is_scalar = np.isscalar(a) and np.isscalar(b)
    arr_a = np.asarray(a, dtype=np.float64)
    arr_b = np.asarray(b, dtype=np.float64)

    if arr_a.shape != arr_b.shape:
        arr_a, arr_b = np.broadcast_arrays(arr_a, arr_b)

    res = np.empty_like(arr_a)

    # Handle degenerate a >= b
    equal_or_inverted = arr_a >= arr_b
    if np.any(equal_or_inverted):
        res[equal_or_inverted] = -np.inf

    valid = ~equal_or_inverted
    if not np.any(valid):
        return float(res.item()) if is_scalar else res

    # 1. Right tail: a >= 0 (both 0 <= a < b)
    # Using symmetry: Phi(b) - Phi(a) = Phi(-a) - Phi(-b) with -b < -a <= 0
    right = valid & (arr_a >= 0.0)
    if np.any(right):
        ar, br = arr_a[right], arr_b[right]
        l_ma = log_ndtr(-ar)
        l_mb = log_ndtr(-br)
        delta = np.maximum(l_ma - l_mb, 1e-15)
        res[right] = l_ma + log1mexp(delta)

    # 2. Left tail: b <= 0 (both a < b <= 0)
    left = valid & (arr_b <= 0.0)
    if np.any(left):
        al, bl = arr_a[left], arr_b[left]
        l_b = log_ndtr(bl)
        l_a = log_ndtr(al)
        delta = np.maximum(l_b - l_a, 1e-15)
        res[left] = l_b + log1mexp(delta)

    # 3. Straddle regime: a < 0 < b
    mid = valid & (arr_a < 0.0) & (arr_b > 0.0)
    if np.any(mid):
        am, bm = arr_a[mid], arr_b[mid]
        diff = ndtr(bm) - ndtr(am)
        # Direct difference is accurate when diff is substantial (> 1e-7)
        safe = diff > 1e-7
        mid_res = np.empty_like(am)
        if np.any(safe):
            mid_res[safe] = np.log(np.maximum(diff[safe], 1e-300))
        if np.any(~safe):
            l_b = log_ndtr(bm[~safe])
            l_a = log_ndtr(am[~safe])
            delta = np.maximum(l_b - l_a, 1e-15)
            mid_res[~safe] = l_b + log1mexp(delta)
        res[mid] = mid_res

    if is_scalar:
        return float(res.item())
    return res


def discretized_mixture_log_prob(
    y: np.ndarray,
    pi: np.ndarray,
    mu: np.ndarray,
    sigma: np.ndarray,
) -> np.ndarray:
    """Compute log P(Y = y | X) for discretized Gaussian mixture.

    Args:
        y: Target values (integer minutes), shape (N,)
        pi: Mixture weights, shape (N, K) or (K,) with sum(pi) == 1
        mu: Component means, shape (N, K) or (K,)
        sigma: Component scales > 0, shape (N, K) or (K,)

    Returns:
        log_prob: shape (N,)
    """
    y = np.asarray(y, dtype=np.float64)
    pi = np.asarray(pi, dtype=np.float64)
    mu = np.asarray(mu, dtype=np.float64)
    sigma = np.asarray(sigma, dtype=np.float64)

    # Ensure y has shape (N, 1) for broadcasting against (N, K)
    if y.ndim == 1:
        y_expanded = y[:, None]
    else:
        y_expanded = y

    a = (y_expanded - 0.5 - mu) / sigma
    b = (y_expanded + 0.5 - mu) / sigma

    log_comp_prob = log_ndtr_diff(a, b)
    log_pi = np.log(np.maximum(pi, 1e-30))

    # logsumexp over components axis (-1)
    return logsumexp(log_pi + log_comp_prob, axis=-1)


def continuous_mixture_log_prob(
    y: np.ndarray,
    pi: np.ndarray,
    mu: np.ndarray,
    sigma: np.ndarray,
) -> np.ndarray:
    """Compute log p(y | X) for continuous Gaussian mixture.

    Args:
        y: Target values, shape (N,)
        pi: Mixture weights, shape (N, K) or (K,)
        mu: Component means, shape (N, K) or (K,)
        sigma: Component scales > 0, shape (N, K) or (K,)

    Returns:
        log_prob: shape (N,)
    """
    y = np.asarray(y, dtype=np.float64)
    pi = np.asarray(pi, dtype=np.float64)
    mu = np.asarray(mu, dtype=np.float64)
    sigma = np.asarray(sigma, dtype=np.float64)

    if y.ndim == 1:
        y_expanded = y[:, None]
    else:
        y_expanded = y

    log_pi = np.log(np.maximum(pi, 1e-30))
    log_norm_const = -0.5 * np.log(2.0 * np.pi) - np.log(sigma)
    log_kernel = -0.5 * ((y_expanded - mu) / sigma) ** 2

    return logsumexp(log_pi + log_norm_const + log_kernel, axis=-1)


def discrete_mixture_cdf(
    y: np.ndarray | int | float,
    pi: np.ndarray,
    mu: np.ndarray,
    sigma: np.ndarray,
) -> np.ndarray:
    """Compute discrete CDF: F(y) = P(Y <= y) = sum_k pi_k Phi((y + 0.5 - mu_k) / sigma_k)."""
    y_arr = np.asarray(y, dtype=np.float64)
    is_scalar = y_arr.ndim == 0
    if is_scalar:
        y_arr = y_arr.reshape(1)

    z = (y_arr[..., None] + 0.5 - mu) / sigma
    phi = ndtr(z)
    res = np.sum(phi * pi, axis=-1)

    if is_scalar and res.size == 1:
        return float(res.item())
    return np.squeeze(res)


def discrete_mixture_quantile(
    p: np.ndarray | float,
    pi: np.ndarray,
    mu: np.ndarray,
    sigma: np.ndarray,
    *,
    y_min: int = -300,
    y_max: int = 3000,
) -> np.ndarray | int:
    """Compute exact integer quantile: Q(p) = min{ y in Z : F(y) >= p }.

    Uses exact integer bisection over [y_min, y_max].
    """
    is_scalar = np.isscalar(p)
    arr_p = np.asarray(p, dtype=np.float64)
    flat_p = arr_p.ravel()
    res = np.empty_like(flat_p, dtype=np.int64)

    for idx, target_p in enumerate(flat_p):
        if target_p <= 0.0:
            res[idx] = y_min
            continue
        if target_p >= 1.0:
            res[idx] = y_max
            continue

        low, high = y_min, y_max
        ans = high
        while low <= high:
            mid = (low + high) // 2
            cdf_val = discrete_mixture_cdf(mid, pi, mu, sigma)
            if cdf_val >= target_p:
                ans = mid
                high = mid - 1
            else:
                low = mid + 1
        res[idx] = ans

    out = res.reshape(arr_p.shape)
    if is_scalar:
        return int(out.item())
    return out
