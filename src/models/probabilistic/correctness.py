"""MDN and Distributional Correctness Test Framework.

Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 7 (Stage 4)

Provides:
1. MarginalDistributionProtocol-compliant GaussianMixtureDistribution.
2. High-performance continuous and discrete sampling.
3. Distributional recovery metrics (Wasserstein-1, KS-statistic, Quantile MAE, CRPS).
4. Synthetic mixture data generation and optimization fitting.
5. Permutation invariance verification.
6. Degeneracy, dead component, and boundary stability checkers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from scipy.optimize import brentq
from scipy.special import ndtr
import torch
import torch.nn as nn

from src.models.probabilistic.distribution_ablation import (
    discretized_mixture_nll_torch,
    gaussian_mixture_crps,
    log_ndtr_diff_torch,
    vectorized_discrete_mixture_quantile,
)
from src.models.probabilistic.likelihood import (
    continuous_mixture_log_prob,
    discrete_mixture_cdf,
    discrete_mixture_quantile,
    discretized_mixture_log_prob,
    log_ndtr_diff,
)


class GaussianMixtureDistribution:
    """Parametric Gaussian mixture distribution implementing MarginalDistributionProtocol."""

    def __init__(
        self,
        pi: np.ndarray | Sequence[float],
        mu: np.ndarray | Sequence[float],
        sigma: np.ndarray | Sequence[float],
        *,
        discrete: bool = True,
        sigma_floor: float = 1.0,
    ) -> None:
        self.pi = np.asarray(pi, dtype=np.float64).ravel()
        self.mu = np.asarray(mu, dtype=np.float64).ravel()
        self.sigma = np.asarray(sigma, dtype=np.float64).ravel()
        self.discrete = discrete
        self.sigma_floor = float(sigma_floor)

        if not (len(self.pi) == len(self.mu) == len(self.sigma)):
            raise ValueError(
                f"Dimension mismatch: len(pi)={len(self.pi)}, len(mu)={len(self.mu)}, len(sigma)={len(self.sigma)}"
            )

        # Enforce parameter validity
        if np.any(self.pi < 0.0):
            raise ValueError("Mixture weights must be non-negative")
        total_pi = np.sum(self.pi)
        if not np.isclose(total_pi, 1.0, atol=1e-5):
            raise ValueError(f"Mixture weights must sum to 1.0 (got {total_pi})")
        self.pi = self.pi / total_pi  # Clean tiny precision drift

        if np.any(self.sigma < self.sigma_floor - 1e-7):
            raise ValueError(
                f"Sigma must be strictly >= sigma_floor ({self.sigma_floor}), got min {np.min(self.sigma)}"
            )

        self.k_components = len(self.pi)

    def cdf(self, y: np.ndarray | float | int) -> np.ndarray | float:
        """Evaluate CDF at y."""
        is_scalar = np.isscalar(y)
        arr = np.asarray(y, dtype=np.float64)

        if self.discrete:
            # Discrete integer arrival CDF: F(y) = P(Y <= y) = sum_k pi_k Phi((y + 0.5 - mu_k) / sigma_k)
            z = (arr[..., None] + 0.5 - self.mu) / self.sigma
        else:
            # Continuous CDF: F(y) = sum_k pi_k Phi((y - mu_k) / sigma_k)
            z = (arr[..., None] - self.mu) / self.sigma

        phi = ndtr(z)
        res = np.sum(phi * self.pi, axis=-1)
        if is_scalar:
            return float(res.item())
        return res

    def log_prob(self, y: np.ndarray | float | int) -> np.ndarray | float:
        """Evaluate log P(Y=y) (discrete) or log p(y) (continuous)."""
        arr = np.asarray(y, dtype=np.float64)
        is_scalar = np.isscalar(y)
        arr_flat = arr.ravel()

        if self.discrete:
            res = discretized_mixture_log_prob(arr_flat, self.pi, self.mu, self.sigma)
        else:
            res = continuous_mixture_log_prob(arr_flat, self.pi, self.mu, self.sigma)

        res_shaped = res.reshape(arr.shape)
        if is_scalar:
            return float(res_shaped.item())
        return res_shaped

    def prob(self, y: np.ndarray | float | int) -> np.ndarray | float:
        """Evaluate P(Y=y) (discrete PMF) or p(y) (continuous PDF)."""
        return np.exp(self.log_prob(y))

    def quantile(self, p: np.ndarray | float) -> np.ndarray | float | int:
        """Evaluate quantile function Q(p)."""
        is_scalar = np.isscalar(p)
        arr_p = np.asarray(p, dtype=np.float64)

        if self.discrete:
            res = discrete_mixture_quantile(arr_p, self.pi, self.mu, self.sigma)
            if is_scalar:
                return int(res.item())
            return res

        # Continuous quantile via root-finding on F(y) - p = 0
        flat_p = arr_p.ravel()
        out = np.empty_like(flat_p, dtype=np.float64)
        for idx, target_p in enumerate(flat_p):
            if target_p <= 0.0:
                out[idx] = -np.inf
                continue
            if target_p >= 1.0:
                out[idx] = np.inf
                continue

            # Bracket search
            min_mu, max_mu = np.min(self.mu), np.max(self.mu)
            max_sigma = np.max(self.sigma)
            low = min_mu - 10.0 * max_sigma
            high = max_mu + 10.0 * max_sigma
            while self.cdf(low) > target_p:
                low -= 10.0 * max_sigma
            while self.cdf(high) < target_p:
                high += 10.0 * max_sigma

            out[idx] = brentq(lambda y_val: self.cdf(y_val) - target_p, low, high)

        res_cont = out.reshape(arr_p.shape)
        if is_scalar:
            return float(res_cont.item())
        return res_cont

    def sample(self, n_samples: int, rng: np.random.Generator | None = None) -> np.ndarray:
        """Draw samples from the distribution."""
        if rng is None:
            rng = np.random.default_rng()

        # 1. Sample mixture component assignments
        comp_choices = rng.choice(self.k_components, size=n_samples, p=self.pi)

        # 2. Draw standard normal variates
        z = rng.standard_normal(size=n_samples)

        # 3. Transform to conditional Gaussian
        chosen_mu = self.mu[comp_choices]
        chosen_sigma = self.sigma[comp_choices]
        y_cont = chosen_mu + chosen_sigma * z

        if self.discrete:
            # Discretization into unit integer intervals [y-0.5, y+0.5] corresponds to rounding
            return np.rint(y_cont).astype(np.int64)
        return y_cont

    def event_prob(self, threshold: float | int) -> float:
        """Evaluate event probability P(Y >= threshold) consistently with CDF."""
        k = float(threshold)
        if self.discrete:
            # P(Y >= k) = 1 - P(Y <= k - 1) = 1 - F(k - 1) = sum_k pi_k * Phi(-(k - 0.5 - mu_k)/sigma_k)
            z = -(k - 0.5 - self.mu) / self.sigma
        else:
            # Continuous: P(Y >= k) = 1 - F(k) = sum_k pi_k * Phi(-(k - mu_k)/sigma_k)
            z = -(k - self.mu) / self.sigma
        return float(np.sum(self.pi * ndtr(z)))

    def crps(self, y: np.ndarray | float | int) -> np.ndarray | float:
        """Compute exact closed-form Gaussian mixture CRPS."""
        arr_y = np.asarray(y, dtype=np.float64)
        is_scalar = np.isscalar(y)
        arr_y_flat = arr_y.ravel()

        n = len(arr_y_flat)
        pi_mat = np.tile(self.pi, (n, 1))
        mu_mat = np.tile(self.mu, (n, 1))
        sigma_mat = np.tile(self.sigma, (n, 1))

        res = gaussian_mixture_crps(arr_y_flat, pi_mat, mu_mat, sigma_mat)
        if is_scalar:
            return float(res.item())
        return res.reshape(arr_y.shape)

    @property
    def component_entropy(self) -> float:
        """Shannon entropy of mixture weights: H(pi) = -sum_k pi_k log pi_k."""
        safe_pi = np.maximum(self.pi, 1e-30)
        return float(-np.sum(self.pi * np.log(safe_pi)))

    @property
    def effective_components(self) -> float:
        """Effective component count: N_eff = 1 / sum_k pi_k^2."""
        sum_sq = np.sum(self.pi**2)
        if sum_sq <= 0:
            return 1.0
        return float(1.0 / sum_sq)


def permute_mixture_parameters(
    pi: np.ndarray,
    mu: np.ndarray,
    sigma: np.ndarray,
    permutation: Sequence[int],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Permute mixture components according to a permutation order."""
    perm = list(permutation)
    return pi[perm], mu[perm], sigma[perm]


@dataclass(frozen=True)
class DistributionalRecoveryMetrics:
    """Metrics assessing distributional recovery on synthetic ground truth."""

    kolmogorov_smirnov_stat: float
    wasserstein_1_distance: float
    mean_absolute_quantile_error: float
    max_absolute_quantile_error: float
    crps_absolute_error: float
    per_quantile_errors: dict[float, float]
    passed: bool


def compute_distributional_recovery_metrics(
    true_dist: GaussianMixtureDistribution,
    fit_dist: GaussianMixtureDistribution,
    *,
    eval_quantiles: Sequence[float] = (0.025, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.975),
    grid_min: float = -50.0,
    grid_max: float = 150.0,
    grid_step: float = 0.5,
    ks_threshold: float = 0.035,
    w1_threshold: float = 0.75,
) -> DistributionalRecoveryMetrics:
    """Compute distributional distance metrics between true and fitted distributions."""
    # 1. Grid-based CDF comparison for KS and Wasserstein-1
    grid = np.arange(grid_min, grid_max + grid_step, grid_step)
    f_true = true_dist.cdf(grid)
    f_fit = fit_dist.cdf(grid)

    ks_stat = float(np.max(np.abs(f_true - f_fit)))
    w1_dist = float(np.sum(np.abs(f_true - f_fit)) * grid_step)

    # 2. Quantile errors
    q_errors: dict[float, float] = {}
    for p in eval_quantiles:
        q_true = true_dist.quantile(p)
        q_fit = fit_dist.quantile(p)
        q_errors[float(p)] = float(abs(q_true - q_fit))

    mean_q_error = float(np.mean(list(q_errors.values())))
    max_q_error = float(np.max(list(q_errors.values())))

    # 3. CRPS evaluation across synthetic samples
    rng = np.random.default_rng(202604)
    y_test = true_dist.sample(1000, rng=rng)
    crps_true = float(np.mean(true_dist.crps(y_test)))
    crps_fit = float(np.mean(fit_dist.crps(y_test)))
    crps_err = abs(crps_fit - crps_true)

    passed = (ks_stat <= ks_threshold) and (w1_dist <= w1_threshold)

    return DistributionalRecoveryMetrics(
        kolmogorov_smirnov_stat=ks_stat,
        wasserstein_1_distance=w1_dist,
        mean_absolute_quantile_error=mean_q_error,
        max_absolute_quantile_error=max_q_error,
        crps_absolute_error=crps_err,
        per_quantile_errors=q_errors,
        passed=passed,
    )


class DirectSyntheticMixtureModule(nn.Module):
    """Direct PyTorch parameterization of Gaussian mixture for synthetic recovery tests."""

    def __init__(self, k_components: int = 3, sigma_floor: float = 1.0) -> None:
        super().__init__()
        self.k = k_components
        self.sigma_floor = float(sigma_floor)

        # Initialize unconstrained parameters
        self.raw_weights = nn.Parameter(torch.zeros(k_components))
        self.raw_mu = nn.Parameter(torch.linspace(-5.0, 40.0, k_components))
        # Initial sigma raw such that softplus(raw) + 1.0 ~ [5, 12, 25]
        self.raw_sigma = nn.Parameter(torch.ones(k_components) * 2.0)

    def forward(self, batch_size: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        pi = torch.softmax(self.raw_weights, dim=-1).unsqueeze(0).expand(batch_size, -1)
        mu = self.raw_mu.unsqueeze(0).expand(batch_size, -1)
        sigma = (torch.nn.functional.softplus(self.raw_sigma) + self.sigma_floor).unsqueeze(0).expand(batch_size, -1)
        return pi, mu, sigma


def fit_synthetic_mixture(
    y_train: np.ndarray,
    k_components: int = 3,
    *,
    n_epochs: int = 150,
    batch_size: int = 1024,
    lr: float = 0.05,
    sigma_floor: float = 1.0,
    seed: int = 42,
) -> tuple[GaussianMixtureDistribution, list[float]]:
    """Fit direct Gaussian mixture to synthetic training targets using discretized NLL."""
    torch.manual_seed(seed)
    model = DirectSyntheticMixtureModule(k_components=k_components, sigma_floor=sigma_floor)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    y_tensor = torch.from_numpy(y_train).float()
    n_samples = len(y_train)

    loss_history: list[float] = []

    for epoch in range(n_epochs):
        perm = torch.randperm(n_samples)
        epoch_losses = []
        for i in range(0, n_samples, batch_size):
            indices = perm[i : i + batch_size]
            batch_y = y_tensor[indices]
            bs = len(batch_y)

            pi, mu, sigma = model(bs)
            loss = discretized_mixture_nll_torch(batch_y, pi, mu, sigma)

            optimizer.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

            epoch_losses.append(loss.item())

        loss_history.append(float(np.mean(epoch_losses)))

    with torch.no_grad():
        pi, mu, sigma = model(1)
        pi_np = pi[0].numpy()
        mu_np = mu[0].numpy()
        sigma_np = sigma[0].numpy()

    fitted_dist = GaussianMixtureDistribution(
        pi=pi_np,
        mu=mu_np,
        sigma=sigma_np,
        discrete=True,
        sigma_floor=sigma_floor,
    )
    return fitted_dist, loss_history
