"""Stage 3 — Distribution Ablation: Separating Conditional Variance from Mixture Structure.

Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 6
Candidates:
- D1: K=1, fixed global sigma
- D2: K=1, heteroscedastic sigma(x)
- D3: K=3, Gaussian mixture
- D4 (Conditional K=5): Opened only if Stage 0 pre-registered opening criteria are satisfied.

Diagnostic Ablation:
- with calendar_year vs without calendar_year.

Likelihood:
- Discretized Gaussian mixture (Primary: log mass log[Phi(b) - Phi(a)])
- Continuous Gaussian mixture (Secondary comparison)

Architecture:
Input -> embeddings + engineered numeric features
-> Linear 128 -> GELU
-> Linear 64 -> GELU
-> Linear 32 -> GELU
-> distribution head
(No BatchNorm, No Dropout, No Multi-task, No Weather, No Chain)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import logging
from typing import Any, Final, Mapping, Sequence

import numpy as np
import pandas as pd
from scipy.special import logsumexp, ndtr
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, TensorDataset

from src.models.probabilistic.contracts import (
    DEFAULT_SIGMA_FLOOR,
    PROBABILISTIC_PREDICTOR_COLUMNS,
    ProbabilisticContractViolation,
)
from src.models.probabilistic.metrics import PRE_REGISTERED_QUANTILES
from src.models.probabilistic.likelihood import (
    continuous_mixture_log_prob,
    discrete_mixture_cdf,
    discrete_mixture_quantile,
    discretized_mixture_log_prob,
    log_ndtr_diff,
)
from src.models.probabilistic.representation import (
    DAYS_PER_WEEK,
    MINUTES_PER_DAY,
    MONTHS_PER_YEAR,
)

LOGGER = logging.getLogger(__name__)

DEFAULT_CARRIER_EMB_DIM: Final = 8
DEFAULT_ORIGIN_EMB_DIM: Final = 16
DEFAULT_FLIGHT_EMB_DIM: Final = 16


class DistributionLadderCandidate(str, Enum):
    """Core distribution ladder candidates."""

    D1_K1_FIXED_SIGMA = "D1_k1_fixed_sigma"
    D2_K1_HETEROSCEDASTIC = "D2_k1_heteroscedastic"
    D3_K3_MIXTURE = "D3_k3_mixture"
    D4_K5_MIXTURE = "D4_k5_mixture"


# =============================================================================
# PyTorch Log-Ndtr-Diff for Discretized Likelihood with Autograd
# =============================================================================

def log_ndtr_diff_torch(a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
    """Numerically stable log[Phi(b) - Phi(a)] in PyTorch.

    Prevents underflow/cancellation across deep left, right, and straddle regimes.
    """
    # 1. Direct difference where safe
    phi_b = torch.special.ndtr(b)
    phi_a = torch.special.ndtr(a)
    diff = phi_b - phi_a
    safe_diff = torch.clamp(diff, min=1e-35)
    log_diff = torch.log(safe_diff)

    # 2. Asymptotic right tail: a > 4.0
    # Phi(b) - Phi(a) = Phi(-a) - Phi(-b)
    # log[Phi(-a) - Phi(-b)] = log_ndtr(-a) + log(1 - exp(log_ndtr(-b) - log_ndtr(-a)))
    right_mask = a > 4.0
    if right_mask.any():
        ar = a[right_mask]
        br = b[right_mask]
        l_ma = torch.special.log_ndtr(-ar)
        l_mb = torch.special.log_ndtr(-br)
        delta = torch.clamp(l_ma - l_mb, min=1e-15)
        # log(1 - exp(-delta)) via log1p(-exp(-delta))
        log_diff[right_mask] = l_ma + torch.log1p(-torch.exp(-delta) + 1e-15)

    # 3. Asymptotic left tail: b < -4.0
    left_mask = b < -4.0
    if left_mask.any():
        al = a[left_mask]
        bl = b[left_mask]
        l_b = torch.special.log_ndtr(bl)
        l_a = torch.special.log_ndtr(al)
        delta = torch.clamp(l_b - l_a, min=1e-15)
        log_diff[left_mask] = l_b + torch.log1p(-torch.exp(-delta) + 1e-15)

    return log_diff


def discretized_mixture_nll_torch(
    y: torch.Tensor,  # (N,)
    pi: torch.Tensor,  # (N, K)
    mu: torch.Tensor,  # (N, K)
    sigma: torch.Tensor,  # (N, K)
) -> torch.Tensor:
    """Compute negative log-likelihood for discretized Gaussian mixture."""
    y_exp = y.unsqueeze(1)  # (N, 1)
    a = (y_exp - 0.5 - mu) / sigma  # (N, K)
    b = (y_exp + 0.5 - mu) / sigma  # (N, K)

    log_comp = log_ndtr_diff_torch(a, b)  # (N, K)
    log_pi = torch.log(torch.clamp(pi, min=1e-30))  # (N, K)

    # logsumexp over component dimension
    log_p = torch.logsumexp(log_pi + log_comp, dim=-1)  # (N,)
    return -torch.mean(log_p)


# =============================================================================
# Closed-Form Gaussian Mixture CRPS (Grimit et al., 2006)
# =============================================================================

def _a_function_np(mu: np.ndarray, s2: np.ndarray) -> np.ndarray:
    """A(mu, sigma^2) = 2*sigma*phi(mu/sigma) + mu*(2*Phi(mu/sigma) - 1)."""
    s = np.sqrt(np.maximum(s2, 1e-12))
    z = mu / s
    phi = (1.0 / np.sqrt(2.0 * np.pi)) * np.exp(-0.5 * z**2)
    Phi = ndtr(z)
    return 2.0 * s * phi + mu * (2.0 * Phi - 1.0)


def gaussian_mixture_crps(
    y: np.ndarray,  # (N,)
    pi: np.ndarray,  # (N, K)
    mu: np.ndarray,  # (N, K)
    sigma: np.ndarray,  # (N, K)
) -> np.ndarray:
    """Exact closed-form CRPS for Gaussian mixtures (Grimit et al., 2006).

    CRPS(F, y) = sum_k pi_k A(y - mu_k, sigma_k^2)
                 - 0.5 * sum_j sum_k pi_j pi_k A(mu_j - mu_k, sigma_j^2 + sigma_k^2)
    """
    y = np.asarray(y, dtype=np.float64)
    pi = np.asarray(pi, dtype=np.float64)
    mu = np.asarray(mu, dtype=np.float64)
    sigma = np.asarray(sigma, dtype=np.float64)
    s2 = sigma**2

    n, k = pi.shape

    # Term 1: sum_k pi_k A(y - mu_k, sigma_k^2)
    y_exp = y[:, None]
    term1_matrix = _a_function_np(y_exp - mu, s2)
    term1 = np.sum(pi * term1_matrix, axis=1)

    # Term 2: 0.5 * sum_j sum_k pi_j pi_k A(mu_j - mu_k, sigma_j^2 + sigma_k^2)
    # Broadcast across components: (N, K, 1) and (N, 1, K)
    mu_j = mu[:, :, None]
    mu_k = mu[:, None, :]
    s2_j = s2[:, :, None]
    s2_k = s2[:, None, :]
    pi_j = pi[:, :, None]
    pi_k = pi[:, None, :]

    mu_diff = mu_j - mu_k
    s2_sum = s2_j + s2_k
    a_pairwise = _a_function_np(mu_diff, s2_sum)

    term2 = 0.5 * np.sum(pi_j * pi_k * a_pairwise, axis=(1, 2))
    return term1 - term2


# =============================================================================
# Preprocessor for Stage 3 (With/Without calendar_year)
# =============================================================================

class Stage3DistributionPreprocessor:
    """Prepares continuous features and categorical embeddings with year ablation toggle."""

    def __init__(
        self,
        *,
        include_calendar_year: bool = True,
        sigma_floor: float = DEFAULT_SIGMA_FLOOR,
    ) -> None:
        self.include_calendar_year = include_calendar_year
        self.sigma_floor = sigma_floor
        self.is_fitted_ = False

        self.carrier_to_idx_: dict[str, int] = {}
        self.origin_to_idx_: dict[str, int] = {}
        self.flight_freq_map_: dict[str, float] = {}

        self.numeric_cols_: list[str] = (
            ["CRS_ELAPSED_TIME", "calendar_year", "calendar_day_of_month", "is_weekend"]
            if include_calendar_year
            else ["CRS_ELAPSED_TIME", "calendar_day_of_month", "is_weekend"]
        )
        self.numeric_medians_: dict[str, float] = {}
        self.scaler_means_: np.ndarray | None = None
        self.scaler_scales_: np.ndarray | None = None

    def fit(self, X: pd.DataFrame) -> "Stage3DistributionPreprocessor":
        missing = set(PROBABILISTIC_PREDICTOR_COLUMNS).difference(X.columns)
        if missing:
            raise ProbabilisticContractViolation(f"Missing columns: {sorted(missing)}")

        n_train = len(X)

        # 1. Numerics
        self.numeric_medians_ = {}
        mat = np.empty((n_train, len(self.numeric_cols_)), dtype=np.float64)
        for i, col in enumerate(self.numeric_cols_):
            v = pd.to_numeric(X[col], errors="coerce").to_numpy(dtype=np.float64)
            valid = np.isfinite(v)
            med = float(np.median(v[valid])) if np.any(valid) else 0.0
            self.numeric_medians_[col] = med
            mat[:, i] = np.where(valid, v, med)

        self.scaler_means_ = np.mean(mat, axis=0)
        scales = np.std(mat, axis=0)
        self.scaler_scales_ = np.where(scales > 1e-8, scales, 1.0)

        # 2. Vocabularies
        carriers = sorted(X["OP_CARRIER"].dropna().astype(str).str.strip().unique())
        self.carrier_to_idx_ = {c: i for i, c in enumerate(carriers)}

        origins = sorted(X["ORIGIN"].dropna().astype(str).str.strip().unique())
        self.origin_to_idx_ = {o: i for i, o in enumerate(origins)}

        # 3. Flight number frequency mapping (from Stage 2 result)
        fl_counts = X["OP_CARRIER_FL_NUM"].dropna().astype(str).str.strip().value_counts()
        self.flight_freq_map_ = {fl: cnt / float(n_train) for fl, cnt in fl_counts.items()}

        self.is_fitted_ = True
        return self

    def transform(self, X: pd.DataFrame) -> dict[str, np.ndarray]:
        if not self.is_fitted_ or self.scaler_means_ is None or self.scaler_scales_ is None:
            raise ProbabilisticContractViolation("Preprocessor not fitted")

        n = len(X)
        hour = pd.to_numeric(X["scheduled_departure_hour"], errors="coerce").to_numpy(dtype=np.float64)
        minute = pd.to_numeric(X["scheduled_departure_minute"], errors="coerce").to_numpy(dtype=np.float64)
        t = 60.0 * hour + minute
        sin_t = np.sin(2.0 * np.pi * t / MINUTES_PER_DAY)
        cos_t = np.cos(2.0 * np.pi * t / MINUTES_PER_DAY)

        month = pd.to_numeric(X["calendar_month"], errors="coerce").to_numpy(dtype=np.float64)
        sin_m = np.sin(2.0 * np.pi * (month - 1.0) / MONTHS_PER_YEAR)
        cos_m = np.cos(2.0 * np.pi * (month - 1.0) / MONTHS_PER_YEAR)

        dow = pd.to_numeric(X["calendar_day_of_week"], errors="coerce").to_numpy(dtype=np.float64)
        sin_d = np.sin(2.0 * np.pi * (dow - 1.0) / DAYS_PER_WEEK)
        cos_d = np.cos(2.0 * np.pi * (dow - 1.0) / DAYS_PER_WEEK)

        mat = np.empty((n, len(self.numeric_cols_)), dtype=np.float64)
        for i, col in enumerate(self.numeric_cols_):
            v = pd.to_numeric(X[col], errors="coerce").to_numpy(dtype=np.float64)
            valid = np.isfinite(v)
            mat[:, i] = np.where(valid, v, self.numeric_medians_[col])

        scaled_num = (mat - self.scaler_means_) / self.scaler_scales_
        continuous = np.column_stack([sin_t, cos_t, sin_m, cos_m, sin_d, cos_d, scaled_num]).astype(
            np.float32
        )

        c_raw = X["OP_CARRIER"].astype(object).fillna("").astype(str).str.strip()
        carrier_idx = np.array(
            [self.carrier_to_idx_.get(c, len(self.carrier_to_idx_)) for c in c_raw], dtype=np.int64
        )

        o_raw = X["ORIGIN"].astype(object).fillna("").astype(str).str.strip()
        origin_idx = np.array(
            [self.origin_to_idx_.get(o, len(self.origin_to_idx_)) for o in o_raw], dtype=np.int64
        )

        fl_raw = X["OP_CARRIER_FL_NUM"].astype(object).fillna("").astype(str).str.strip()
        flight_freq = np.array([self.flight_freq_map_.get(fl, 0.0) for fl in fl_raw], dtype=np.float32).reshape(
            -1, 1
        )

        return {
            "continuous": continuous,
            "carrier": carrier_idx,
            "origin": origin_idx,
            "flight_freq": flight_freq,
        }


# =============================================================================
# Stage 3 Neural Network Architecture (Minimal Embedding-MLP v1)
# =============================================================================

class Stage3DistributionModel(nn.Module):
    """Embedding-MLP Minimal V1 for Distribution Ablation.

    Architecture:
    Input -> embeddings + continuous features
    -> Linear 128 -> GELU
    -> Linear 64 -> GELU
    -> Linear 32 -> GELU
    -> distribution head
    """

    def __init__(
        self,
        candidate: DistributionLadderCandidate,
        num_continuous: int,
        num_carriers: int,
        num_origins: int,
        *,
        k_components: int = 1,
        sigma_floor: float = DEFAULT_SIGMA_FLOOR,
        carrier_emb_dim: int = DEFAULT_CARRIER_EMB_DIM,
        origin_emb_dim: int = DEFAULT_ORIGIN_EMB_DIM,
        flight_emb_dim: int = DEFAULT_FLIGHT_EMB_DIM,
    ) -> None:
        super().__init__()
        self.candidate = candidate
        self.k_components = k_components
        self.sigma_floor = sigma_floor

        self.carrier_emb = nn.Embedding(num_carriers, carrier_emb_dim)
        self.origin_emb = nn.Embedding(num_origins, origin_emb_dim)
        self.flight_proj = nn.Linear(1, flight_emb_dim)

        in_dim = num_continuous + carrier_emb_dim + origin_emb_dim + flight_emb_dim

        # Trunk: 128 -> GELU -> 64 -> GELU -> 32 -> GELU
        self.trunk = nn.Sequential(
            nn.Linear(in_dim, 128),
            nn.GELU(),
            nn.Linear(128, 64),
            nn.GELU(),
            nn.Linear(64, 32),
            nn.GELU(),
        )

        # Distribution Head
        if candidate == DistributionLadderCandidate.D1_K1_FIXED_SIGMA:
            self.mu_head = nn.Linear(32, 1)
            # Fixed global sigma parameter (softplus(3.5) + 1.0 ~ 34.0)
            self.raw_sigma = nn.Parameter(torch.tensor(3.5))
        elif candidate == DistributionLadderCandidate.D2_K1_HETEROSCEDASTIC:
            self.mu_head = nn.Linear(32, 1)
            self.sigma_head = nn.Linear(32, 1)
            self.sigma_head.bias.data.fill_(3.5)
        elif candidate in (
            DistributionLadderCandidate.D3_K3_MIXTURE,
            DistributionLadderCandidate.D4_K5_MIXTURE,
        ):
            k = self.k_components
            self.pi_head = nn.Linear(32, k)
            self.mu_head = nn.Linear(32, k)
            self.sigma_head = nn.Linear(32, k)

            # Initialization policy
            self.pi_head.bias.data.fill_(0.0)  # Uniform component weights
            self.sigma_head.bias.data.fill_(3.5)
            # Spread component means slightly around 0 to avoid symmetry trap
            spread = torch.linspace(-5.0, 15.0, k)
            self.mu_head.bias.data.copy_(spread)

    def forward(
        self,
        x_cont: torch.Tensor,
        x_carrier: torch.Tensor,
        x_origin: torch.Tensor,
        x_flight: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        c = self.carrier_emb(x_carrier)
        o = self.origin_emb(x_origin)
        fl = self.flight_proj(x_flight)

        fused = torch.cat([x_cont, c, o, fl], dim=1)
        features = self.trunk(fused)  # (N, 32)
        n = features.shape[0]

        if self.candidate == DistributionLadderCandidate.D1_K1_FIXED_SIGMA:
            mu = self.mu_head(features)  # (N, 1)
            sig_val = F.softplus(self.raw_sigma) + self.sigma_floor
            sigma = sig_val.expand_as(mu)  # (N, 1)
            pi = torch.ones((n, 1), device=features.device, dtype=features.dtype)

        elif self.candidate == DistributionLadderCandidate.D2_K1_HETEROSCEDASTIC:
            mu = self.mu_head(features)  # (N, 1)
            raw_s = self.sigma_head(features)
            sigma = F.softplus(raw_s) + self.sigma_floor  # (N, 1)
            pi = torch.ones((n, 1), device=features.device, dtype=features.dtype)

        else:
            raw_pi = self.pi_head(features)  # (N, K)
            pi = F.softmax(raw_pi, dim=-1)  # (N, K)
            mu = self.mu_head(features)  # (N, K)
            raw_s = self.sigma_head(features)
            sigma = F.softplus(raw_s) + self.sigma_floor  # (N, K)

        return pi, mu, sigma


# =============================================================================
# Training & Evaluation Procedure
# =============================================================================

def train_distribution_candidate(
    candidate: DistributionLadderCandidate,
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    inner_train_df: pd.DataFrame,
    inner_val_df: pd.DataFrame,
    *,
    include_calendar_year: bool = True,
    k_components: int = 1,
    seed: int = 202601,
    max_epochs: int = 20,
    batch_size: int = 256,
    lr: float = 1e-3,
    weight_decay: float = 1e-4,
    device: str = "cpu",
) -> dict[str, Any]:
    """Execute the locked 2-phase distribution training procedure."""
    torch.manual_seed(seed)
    np.random.seed(seed)

    # -------------------------------------------------------------------------
    # PHASE 1: Inner Early Stopping (Select best_epoch strictly on inner_val)
    # -------------------------------------------------------------------------
    inner_prep = Stage3DistributionPreprocessor(include_calendar_year=include_calendar_year)
    inner_prep.fit(inner_train_df)

    i_train_dict = inner_prep.transform(inner_train_df)
    i_val_dict = inner_prep.transform(inner_val_df)

    y_i_train = torch.tensor(inner_train_df["ARR_DELAY"].to_numpy(dtype=np.float32), dtype=torch.float32)
    y_i_val = torch.tensor(inner_val_df["ARR_DELAY"].to_numpy(dtype=np.float32), dtype=torch.float32)

    inner_model = Stage3DistributionModel(
        candidate=candidate,
        num_continuous=i_train_dict["continuous"].shape[1],
        num_carriers=len(inner_prep.carrier_to_idx_) + 1,
        num_origins=len(inner_prep.origin_to_idx_) + 1,
        k_components=k_components,
    ).to(device)

    inner_optimizer = torch.optim.AdamW(inner_model.parameters(), lr=lr, weight_decay=weight_decay)

    train_ds = TensorDataset(
        torch.from_numpy(i_train_dict["continuous"]),
        torch.from_numpy(i_train_dict["carrier"]),
        torch.from_numpy(i_train_dict["origin"]),
        torch.from_numpy(i_train_dict["flight_freq"]),
        y_i_train,
    )
    inner_train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)

    val_cont = torch.from_numpy(i_val_dict["continuous"]).to(device)
    val_carrier = torch.from_numpy(i_val_dict["carrier"]).to(device)
    val_origin = torch.from_numpy(i_val_dict["origin"]).to(device)
    val_fl = torch.from_numpy(i_val_dict["flight_freq"]).to(device)
    val_y_dev = y_i_val.to(device)

    best_epoch = 1
    best_inner_nll = float("inf")
    inner_nll_history: list[float] = []

    for epoch in range(1, max_epochs + 1):
        inner_model.train()
        for b_cont, b_c, b_o, b_fl, b_y in inner_train_loader:
            inner_optimizer.zero_grad()
            pi, mu, sigma = inner_model(b_cont.to(device), b_c.to(device), b_o.to(device), b_fl.to(device))
            loss = discretized_mixture_nll_torch(b_y.to(device), pi, mu, sigma)
            if not torch.isfinite(loss):
                continue
            loss.backward()
            torch.nn.utils.clip_grad_norm_(inner_model.parameters(), max_norm=1.0)
            inner_optimizer.step()

        inner_model.eval()
        with torch.no_grad():
            pi_val, mu_val, sigma_val = inner_model(val_cont, val_carrier, val_origin, val_fl)
            val_loss = float(discretized_mixture_nll_torch(val_y_dev, pi_val, mu_val, sigma_val).item())
            inner_nll_history.append(val_loss)
            if val_loss < best_inner_nll:
                best_inner_nll = val_loss
                best_epoch = epoch

    del inner_model, inner_optimizer, inner_prep
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    # -------------------------------------------------------------------------
    # PHASE 2: Outer Retraining (Refit fresh from scratch on full outer-train)
    # -------------------------------------------------------------------------
    outer_prep = Stage3DistributionPreprocessor(include_calendar_year=include_calendar_year)
    outer_prep.fit(train_df)

    o_train_dict = outer_prep.transform(train_df)
    o_val_dict = outer_prep.transform(val_df)

    y_train = torch.tensor(train_df["ARR_DELAY"].to_numpy(dtype=np.float32), dtype=torch.float32)
    y_val_np = val_df["ARR_DELAY"].to_numpy(dtype=np.float64)

    torch.manual_seed(seed + 100)
    np.random.seed(seed + 100)

    outer_model = Stage3DistributionModel(
        candidate=candidate,
        num_continuous=o_train_dict["continuous"].shape[1],
        num_carriers=len(outer_prep.carrier_to_idx_) + 1,
        num_origins=len(outer_prep.origin_to_idx_) + 1,
        k_components=k_components,
    ).to(device)

    outer_optimizer = torch.optim.AdamW(outer_model.parameters(), lr=lr, weight_decay=weight_decay)

    outer_train_ds = TensorDataset(
        torch.from_numpy(o_train_dict["continuous"]),
        torch.from_numpy(o_train_dict["carrier"]),
        torch.from_numpy(o_train_dict["origin"]),
        torch.from_numpy(o_train_dict["flight_freq"]),
        y_train,
    )
    outer_train_loader = DataLoader(outer_train_ds, batch_size=batch_size, shuffle=True)

    for _ in range(1, best_epoch + 1):
        outer_model.train()
        for b_cont, b_c, b_o, b_fl, b_y in outer_train_loader:
            outer_optimizer.zero_grad()
            pi, mu, sigma = outer_model(b_cont.to(device), b_c.to(device), b_o.to(device), b_fl.to(device))
            loss = discretized_mixture_nll_torch(b_y.to(device), pi, mu, sigma)
            if not torch.isfinite(loss):
                continue
            loss.backward()
            torch.nn.utils.clip_grad_norm_(outer_model.parameters(), max_norm=1.0)
            outer_optimizer.step()

    # Out-of-sample evaluation on outer validation
    outer_model.eval()
    with torch.no_grad():
        out_cont = torch.from_numpy(o_val_dict["continuous"]).to(device)
        out_carrier = torch.from_numpy(o_val_dict["carrier"]).to(device)
        out_origin = torch.from_numpy(o_val_dict["origin"]).to(device)
        out_fl = torch.from_numpy(o_val_dict["flight_freq"]).to(device)

        pi_t, mu_t, sigma_t = outer_model(out_cont, out_carrier, out_origin, out_fl)
        pi_val = pi_t.cpu().numpy().astype(np.float64)
        mu_val = mu_t.cpu().numpy().astype(np.float64)
        sigma_val = sigma_t.cpu().numpy().astype(np.float64)

    # 1. Negative Log-Likelihoods
    nll_discretized = float(-np.mean(discretized_mixture_log_prob(y_val_np, pi_val, mu_val, sigma_val)))
    nll_continuous = float(-np.mean(continuous_mixture_log_prob(y_val_np, pi_val, mu_val, sigma_val)))

    # 2. Exact Closed-Form Gaussian Mixture CRPS
    crps_vec = gaussian_mixture_crps(y_val_np, pi_val, mu_val, sigma_val)
    crps_mean = float(np.mean(crps_vec))

    # 3. Component statistics
    mean_weights = np.mean(pi_val, axis=0)  # (K,)
    entropy_per_row = -np.sum(pi_val * np.log(np.maximum(pi_val, 1e-30)), axis=1)
    mean_entropy = float(np.mean(entropy_per_row))
    n_eff_per_row = 1.0 / np.sum(pi_val**2, axis=1)
    mean_n_eff = float(np.mean(n_eff_per_row))

    # 4. Sigma quantiles
    sigma_flat = sigma_val.ravel()
    sigma_stats = {
        "mean": float(np.mean(sigma_flat)),
        "std": float(np.std(sigma_flat)),
        "q10": float(np.percentile(sigma_flat, 10)),
        "q50": float(np.percentile(sigma_flat, 50)),
        "q90": float(np.percentile(sigma_flat, 90)),
    }

    # 5. Point prediction (Mixture mean)
    y_pred_point = np.sum(pi_val * mu_val, axis=1)
    mae = float(np.mean(np.abs(y_val_np - y_pred_point)))

    return {
        "candidate": candidate.value,
        "include_calendar_year": include_calendar_year,
        "best_epoch": best_epoch,
        "best_inner_nll": best_inner_nll,
        "metrics": {
            "nll_discretized": nll_discretized,
            "nll_continuous": nll_continuous,
            "crps": crps_mean,
            "mae": mae,
        },
        "component_stats": {
            "k_components": k_components,
            "component_weights": [float(w) for w in mean_weights],
            "min_component_weight": float(np.min(mean_weights)),
            "component_entropy": mean_entropy,
            "effective_component_count": mean_n_eff,
        },
        "sigma_stats": sigma_stats,
        "predictions": {
            "pi": pi_val,
            "mu": mu_val,
            "sigma": sigma_val,
            "crps_vec": crps_vec,
            "y_pred_point": y_pred_point,
        },
    }


def vectorized_discrete_mixture_quantile(
    p: float,
    pi: np.ndarray,  # (N, K)
    mu: np.ndarray,  # (N, K)
    sigma: np.ndarray,  # (N, K)
    *,
    y_min: int = -300,
    y_max: int = 3000,
) -> np.ndarray:
    """Compute exact discrete integer quantile Q(p) = min{y in Z : F(y) >= p} vectorized over N samples."""
    n = pi.shape[0]
    low = np.full(n, y_min, dtype=np.int64)
    high = np.full(n, y_max, dtype=np.int64)
    ans = np.full(n, y_max, dtype=np.int64)

    # 12 iterations covers range 3300 (2^12 = 4096)
    while np.any(low <= high):
        mid = (low + high) // 2
        z = (mid[:, None] + 0.5 - mu) / sigma
        cdf_val = np.sum(ndtr(z) * pi, axis=-1)
        cond = cdf_val >= p
        ans[cond] = mid[cond]
        high[cond] = mid[cond] - 1
        low[~cond] = mid[~cond] + 1

    return ans.astype(np.float64)

