"""Stage 2 — Representation Ablation: Flight Number Embedding vs Frequency Map.

Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 5
Primary objective:
Isolate whether flight-number embedding (R2) adds value beyond the current
frequency-map representation (R1), with low-card one-hot (R0) as control.

Experimental control invariants:
- same model architecture (MLP trunk: 128 -> LayerNorm -> Dropout(0.1) -> 64 -> 1);
- same hidden dimensions: [128, 64];
- same optimizer: AdamW(lr=1e-3, weight_decay=1e-4);
- same loss: SmoothL1Loss(beta=1.0);
- same batch policy: batch_size=256;
- same early-stopping protocol (2-phase inner/outer procedure);
- same seeds: 202601;
- same numeric continuous representation (10 cyclic + standardized features);
- same OP_CARRIER (dim 8) and ORIGIN (dim 16) embeddings;
- ONLY change the OP_CARRIER_FL_NUM representation being tested.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import logging
from typing import Any, Final, Mapping, Sequence

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, median_absolute_error, r2_score
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from src.models.probabilistic.contracts import (
    CATEGORICAL_EMBEDDING_COLUMNS,
    CYCLIC_SOURCE_COLUMNS,
    NUMERIC_SCALED_COLUMNS,
    PROBABILISTIC_PREDICTOR_COLUMNS,
    ProbabilisticContractViolation,
)
from src.models.probabilistic.representation import (
    CONTINUOUS_FEATURE_NAMES,
    DAYS_PER_WEEK,
    MINUTES_PER_DAY,
    MONTHS_PER_YEAR,
)

LOGGER = logging.getLogger(__name__)

DEFAULT_CARRIER_EMB_DIM: Final = 8
DEFAULT_ORIGIN_EMB_DIM: Final = 16
DEFAULT_FLIGHT_EMB_DIM: Final = 16
DEFAULT_TOP_FLIGHTS_ONE_HOT: Final = 50


class FlightNumberRepresentation(str, Enum):
    """Candidate representations for OP_CARRIER_FL_NUM."""

    R0_LOW_CARD_ONE_HOT = "R0_low_card_one_hot"
    R1_FREQUENCY_MAP = "R1_frequency_map"
    R2_EMBEDDING = "R2_embedding"


@dataclass(frozen=True)
class RepresentationProvenanceStats:
    """Detailed category counts and unknown index statistics for representation attribution."""

    train_flight_category_count: int
    val_flight_category_count: int
    unseen_flight_category_count: int
    unseen_flight_rate: float
    rare_count_le_1: int
    rare_count_le_5: int
    rare_count_le_10: int
    embedding_vocabulary_size: int
    unknown_index: int
    unknown_index_usage_count: int
    unknown_index_usage_rate: float


@dataclass(frozen=True)
class ProcessedAblationBatch:
    """Preprocessed tensors ready for neural net consumption."""

    continuous: np.ndarray  # (N, 10), float32
    carrier_indices: np.ndarray  # (N,), int64
    origin_indices: np.ndarray  # (N,), int64
    flight_feature: np.ndarray  # (N,) int64 for R2; (N, 1) float32 for R1; (N, M+1) float32 for R0
    provenance_stats: RepresentationProvenanceStats | None = None


class RepresentationAblationPreprocessor:
    """Fold-safe preprocessor managing candidate representations for OP_CARRIER_FL_NUM."""

    def __init__(
        self,
        rep_type: FlightNumberRepresentation,
        *,
        top_m_flights: int = DEFAULT_TOP_FLIGHTS_ONE_HOT,
    ) -> None:
        self.rep_type = rep_type
        self.top_m_flights = top_m_flights
        self.is_fitted_ = False

        # Numeric statistics
        self.numeric_medians_: dict[str, float] = {}
        self.scaler_means_: np.ndarray | None = None
        self.scaler_scales_: np.ndarray | None = None

        # Carrier & Origin vocabs
        self.carrier_to_idx_: dict[str, int] = {}
        self.origin_to_idx_: dict[str, int] = {}
        self.unknown_carrier_idx_: int = 0
        self.unknown_origin_idx_: int = 0

        # R2 Flight number vocab
        self.flight_to_idx_: dict[str, int] = {}
        self.unknown_flight_idx_: int = 0

        # R1 Frequency map
        self.flight_freq_map_: dict[str, float] = {}

        # R0 Top-M list
        self.top_m_flight_list_: list[str] = []
        self.top_m_to_idx_: dict[str, int] = {}

        # Train category statistics
        self.train_flight_counts_: dict[str, int] = {}

    def fit(self, X: pd.DataFrame) -> "RepresentationAblationPreprocessor":
        """Fit preprocessor statistics strictly on fold-training data."""
        missing = set(PROBABILISTIC_PREDICTOR_COLUMNS).difference(X.columns)
        if missing:
            raise ProbabilisticContractViolation(f"Missing approved predictors: {sorted(missing)}")

        n_train = len(X)
        if n_train == 0:
            raise ProbabilisticContractViolation("Cannot fit on empty training set")

        # 1. Numeric medians and scaling parameters
        self.numeric_medians_ = {}
        imputed_numerics = np.empty((n_train, len(NUMERIC_SCALED_COLUMNS)), dtype=np.float64)
        for i, col in enumerate(NUMERIC_SCALED_COLUMNS):
            vals = pd.to_numeric(X[col], errors="coerce").to_numpy(dtype=np.float64)
            valid = np.isfinite(vals)
            med = float(np.median(vals[valid])) if np.any(valid) else 0.0
            self.numeric_medians_[col] = med
            imputed_numerics[:, i] = np.where(valid, vals, med)

        self.scaler_means_ = np.mean(imputed_numerics, axis=0)
        scales = np.std(imputed_numerics, axis=0)
        self.scaler_scales_ = np.where(scales > 1e-8, scales, 1.0)

        # 2. OP_CARRIER vocabulary
        unique_carriers = sorted(X["OP_CARRIER"].dropna().astype(str).str.strip().unique())
        self.carrier_to_idx_ = {c: i for i, c in enumerate(unique_carriers)}
        self.unknown_carrier_idx_ = len(unique_carriers)

        # 3. ORIGIN vocabulary
        unique_origins = sorted(X["ORIGIN"].dropna().astype(str).str.strip().unique())
        self.origin_to_idx_ = {o: i for i, o in enumerate(unique_origins)}
        self.unknown_origin_idx_ = len(unique_origins)

        # 4. OP_CARRIER_FL_NUM representation-specific fitting
        raw_fl_series = X["OP_CARRIER_FL_NUM"].dropna().astype(str).str.strip()
        counts = raw_fl_series.value_counts(dropna=False, sort=True)
        self.train_flight_counts_ = {str(k): int(v) for k, v in counts.items()}

        unique_flights = sorted(self.train_flight_counts_.keys())
        self.flight_to_idx_ = {fl: i for i, fl in enumerate(unique_flights)}
        self.unknown_flight_idx_ = len(unique_flights)

        # Frequency map for R1
        self.flight_freq_map_ = {fl: cnt / float(n_train) for fl, cnt in self.train_flight_counts_.items()}

        # Top-M list for R0
        self.top_m_flight_list_ = list(counts.index[: self.top_m_flights])
        self.top_m_to_idx_ = {fl: i for i, fl in enumerate(self.top_m_flight_list_)}
        self.one_hot_dim_ = len(self.top_m_flight_list_) + 1

        self.is_fitted_ = True
        return self

    def transform(self, X: pd.DataFrame, *, compute_stats: bool = True) -> ProcessedAblationBatch:
        """Transform input features using strictly training-fitted parameters."""
        if not self.is_fitted_ or self.scaler_means_ is None or self.scaler_scales_ is None:
            raise ProbabilisticContractViolation("RepresentationAblationPreprocessor is not fitted")

        n_rows = len(X)

        # 1. Continuous cyclic & numeric features
        hour = pd.to_numeric(X["scheduled_departure_hour"], errors="coerce").to_numpy(dtype=np.float64)
        minute = pd.to_numeric(X["scheduled_departure_minute"], errors="coerce").to_numpy(dtype=np.float64)
        time_minutes = 60.0 * hour + minute
        sin_time = np.sin(2.0 * np.pi * time_minutes / MINUTES_PER_DAY)
        cos_time = np.cos(2.0 * np.pi * time_minutes / MINUTES_PER_DAY)

        month = pd.to_numeric(X["calendar_month"], errors="coerce").to_numpy(dtype=np.float64)
        sin_month = np.sin(2.0 * np.pi * (month - 1.0) / MONTHS_PER_YEAR)
        cos_month = np.cos(2.0 * np.pi * (month - 1.0) / MONTHS_PER_YEAR)

        dow = pd.to_numeric(X["calendar_day_of_week"], errors="coerce").to_numpy(dtype=np.float64)
        sin_dow = np.sin(2.0 * np.pi * (dow - 1.0) / DAYS_PER_WEEK)
        cos_dow = np.cos(2.0 * np.pi * (dow - 1.0) / DAYS_PER_WEEK)

        imputed_numerics = np.empty((n_rows, len(NUMERIC_SCALED_COLUMNS)), dtype=np.float64)
        for i, col in enumerate(NUMERIC_SCALED_COLUMNS):
            vals = pd.to_numeric(X[col], errors="coerce").to_numpy(dtype=np.float64)
            valid = np.isfinite(vals)
            med = self.numeric_medians_[col]
            imputed_numerics[:, i] = np.where(valid, vals, med)

        scaled_numerics = (imputed_numerics - self.scaler_means_) / self.scaler_scales_

        continuous = np.column_stack(
            [sin_time, cos_time, sin_month, cos_month, sin_dow, cos_dow, scaled_numerics]
        ).astype(np.float32)

        # 2. Categoricals: carrier & origin
        carrier_raw = X["OP_CARRIER"].astype(object).fillna("").astype(str).str.strip()
        carrier_idx = np.array(
            [self.carrier_to_idx_.get(c, self.unknown_carrier_idx_) for c in carrier_raw],
            dtype=np.int64,
        )

        origin_raw = X["ORIGIN"].astype(object).fillna("").astype(str).str.strip()
        origin_idx = np.array(
            [self.origin_to_idx_.get(o, self.unknown_origin_idx_) for o in origin_raw],
            dtype=np.int64,
        )

        # 3. Flight number representation
        fl_raw = X["OP_CARRIER_FL_NUM"].astype(object).fillna("").astype(str).str.strip()

        provenance: RepresentationProvenanceStats | None = None
        if compute_stats:
            val_counts = fl_raw.value_counts()
            val_cats = set(val_counts.index)
            train_cats = set(self.train_flight_counts_.keys())
            unseen_cats = val_cats.difference(train_cats)
            unseen_row_count = int(fl_raw.isin(unseen_cats).sum())

            # Rare category statistics in train
            cnt_arr = np.array(list(self.train_flight_counts_.values()))
            rare_1 = int((cnt_arr <= 1).sum())
            rare_5 = int((cnt_arr <= 5).sum())
            rare_10 = int((cnt_arr <= 10).sum())

            provenance = RepresentationProvenanceStats(
                train_flight_category_count=len(train_cats),
                val_flight_category_count=len(val_cats),
                unseen_flight_category_count=len(unseen_cats),
                unseen_flight_rate=float(unseen_row_count / n_rows) if n_rows > 0 else 0.0,
                rare_count_le_1=rare_1,
                rare_count_le_5=rare_5,
                rare_count_le_10=rare_10,
                embedding_vocabulary_size=len(train_cats) + 1,
                unknown_index=self.unknown_flight_idx_,
                unknown_index_usage_count=unseen_row_count,
                unknown_index_usage_rate=float(unseen_row_count / n_rows) if n_rows > 0 else 0.0,
            )

        if self.rep_type == FlightNumberRepresentation.R2_EMBEDDING:
            flight_feature = np.array(
                [self.flight_to_idx_.get(fl, self.unknown_flight_idx_) for fl in fl_raw],
                dtype=np.int64,
            )
        elif self.rep_type == FlightNumberRepresentation.R1_FREQUENCY_MAP:
            # Frequency mapped to continuous float32 (unknown -> 0.0)
            flight_feature = np.array(
                [self.flight_freq_map_.get(fl, 0.0) for fl in fl_raw],
                dtype=np.float32,
            ).reshape(-1, 1)
        elif self.rep_type == FlightNumberRepresentation.R0_LOW_CARD_ONE_HOT:
            # One-hot of top M + 1 bucket
            num_bins = len(self.top_m_flight_list_) + 1
            flight_feature = np.zeros((n_rows, num_bins), dtype=np.float32)
            other_idx = len(self.top_m_flight_list_)
            for row_i, fl in enumerate(fl_raw):
                idx = self.top_m_to_idx_.get(fl, other_idx)
                flight_feature[row_i, idx] = 1.0
        else:
            raise ProbabilisticContractViolation(f"Unsupported rep_type: {self.rep_type}")

        return ProcessedAblationBatch(
            continuous=continuous,
            carrier_indices=carrier_idx,
            origin_indices=origin_idx,
            flight_feature=flight_feature,
            provenance_stats=provenance,
        )


class PointNNModel(nn.Module):
    """Controlled Tabular Neural Network for Core Arrival Point Regression."""

    def __init__(
        self,
        rep_type: FlightNumberRepresentation,
        num_carriers: int,
        num_origins: int,
        *,
        num_continuous: int = 10,
        num_flight_categories: int | None = None,
        num_top_flights: int = DEFAULT_TOP_FLIGHTS_ONE_HOT,
        num_one_hot_bins: int | None = None,
        carrier_emb_dim: int = DEFAULT_CARRIER_EMB_DIM,
        origin_emb_dim: int = DEFAULT_ORIGIN_EMB_DIM,
        flight_emb_dim: int = DEFAULT_FLIGHT_EMB_DIM,
        hidden_dims: tuple[int, ...] = (128, 64),
        dropout_rate: float = 0.1,
    ) -> None:
        super().__init__()
        self.rep_type = rep_type
        self.carrier_emb = nn.Embedding(num_carriers, carrier_emb_dim)
        self.origin_emb = nn.Embedding(num_origins, origin_emb_dim)

        # Symmetric projection: all flight representations project to flight_emb_dim (16)
        if rep_type == FlightNumberRepresentation.R2_EMBEDDING:
            if num_flight_categories is None:
                raise ValueError("num_flight_categories required for R2_EMBEDDING")
            self.flight_proj = nn.Embedding(num_flight_categories, flight_emb_dim)
        elif rep_type == FlightNumberRepresentation.R1_FREQUENCY_MAP:
            self.flight_proj = nn.Linear(1, flight_emb_dim)
        elif rep_type == FlightNumberRepresentation.R0_LOW_CARD_ONE_HOT:
            in_bins = num_one_hot_bins if num_one_hot_bins is not None else (num_top_flights + 1)
            self.flight_proj = nn.Linear(in_bins, flight_emb_dim)

        # Total input dimension into MLP trunk is strictly identical across R0, R1, and R2:
        # continuous(10) + carrier(8) + origin(16) + flight(16) = 50 dimensions
        total_in_dim = num_continuous + carrier_emb_dim + origin_emb_dim + flight_emb_dim

        # Frozen MLP Trunk
        self.trunk = nn.Sequential(
            nn.Linear(total_in_dim, hidden_dims[0]),
            nn.ReLU(),
            nn.LayerNorm(hidden_dims[0]),
            nn.Dropout(dropout_rate),
            nn.Linear(hidden_dims[0], hidden_dims[1]),
            nn.ReLU(),
            nn.Linear(hidden_dims[1], 1),
        )

    def forward(
        self,
        x_cont: torch.Tensor,
        x_carrier: torch.Tensor,
        x_origin: torch.Tensor,
        x_flight: torch.Tensor,
    ) -> torch.Tensor:
        c_emb = self.carrier_emb(x_carrier)  # (N, 8)
        o_emb = self.origin_emb(x_origin)  # (N, 16)
        fl_rep = self.flight_proj(x_flight)  # (N, 16) for all R0, R1, R2

        fused = torch.cat([x_cont, c_emb, o_emb, fl_rep], dim=1)  # (N, 50)
        out = self.trunk(fused)  # (N, 1)
        return out.squeeze(-1)


def train_point_model_fold(
    rep_type: FlightNumberRepresentation,
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    inner_train_df: pd.DataFrame,
    inner_val_df: pd.DataFrame,
    *,
    seed: int = 202601,
    max_epochs: int = 20,
    batch_size: int = 256,
    lr: float = 1e-3,
    weight_decay: float = 1e-4,
    device: str = "cpu",
) -> dict[str, Any]:
    """Execute the locked 2-phase early-stopping protocol for representation ablation."""
    torch.manual_seed(seed)
    np.random.seed(seed)

    # -------------------------------------------------------------------------
    # PHASE 1: Inner Early Stopping (Select best_epoch strictly on inner_val)
    # -------------------------------------------------------------------------
    inner_prep = RepresentationAblationPreprocessor(rep_type)
    inner_prep.fit(inner_train_df)

    inner_train_batch = inner_prep.transform(inner_train_df, compute_stats=False)
    inner_val_batch = inner_prep.transform(inner_val_df, compute_stats=False)

    y_inner_train = torch.tensor(inner_train_df["ARR_DELAY"].to_numpy(dtype=np.float32), dtype=torch.float32)
    y_inner_val = inner_val_df["ARR_DELAY"].to_numpy(dtype=np.float64)

    inner_model = PointNNModel(
        rep_type=rep_type,
        num_carriers=len(inner_prep.carrier_to_idx_) + 1,
        num_origins=len(inner_prep.origin_to_idx_) + 1,
        num_flight_categories=len(inner_prep.flight_to_idx_) + 1,
        num_one_hot_bins=inner_prep.one_hot_dim_,
    ).to(device)

    inner_optimizer = torch.optim.AdamW(inner_model.parameters(), lr=lr, weight_decay=weight_decay)
    criterion = nn.SmoothL1Loss(beta=1.0)

    # Dataset & loader
    train_dataset = TensorDataset(
        torch.from_numpy(inner_train_batch.continuous),
        torch.from_numpy(inner_train_batch.carrier_indices),
        torch.from_numpy(inner_train_batch.origin_indices),
        torch.from_numpy(inner_train_batch.flight_feature),
        y_inner_train,
    )
    inner_train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)

    val_cont = torch.from_numpy(inner_val_batch.continuous).to(device)
    val_carrier = torch.from_numpy(inner_val_batch.carrier_indices).to(device)
    val_origin = torch.from_numpy(inner_val_batch.origin_indices).to(device)
    val_fl = torch.from_numpy(inner_val_batch.flight_feature).to(device)

    best_epoch = 1
    best_inner_mae = float("inf")
    inner_mae_history: list[float] = []

    for epoch in range(1, max_epochs + 1):
        inner_model.train()
        for b_cont, b_c, b_o, b_fl, b_y in inner_train_loader:
            inner_optimizer.zero_grad()
            pred = inner_model(b_cont.to(device), b_c.to(device), b_o.to(device), b_fl.to(device))
            loss = criterion(pred, b_y.to(device))
            loss.backward()
            inner_optimizer.step()

        inner_model.eval()
        with torch.no_grad():
            val_pred = inner_model(val_cont, val_carrier, val_origin, val_fl).cpu().numpy()
            epoch_mae = float(mean_absolute_error(y_inner_val, val_pred))
            inner_mae_history.append(epoch_mae)
            if epoch_mae < best_inner_mae:
                best_inner_mae = epoch_mae
                best_epoch = epoch

    # Completely discard inner model weights and memory
    del inner_model, inner_optimizer, inner_prep
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    # -------------------------------------------------------------------------
    # PHASE 2: Outer Retraining (Refit fresh from scratch on full outer-train)
    # -------------------------------------------------------------------------
    outer_prep = RepresentationAblationPreprocessor(rep_type)
    outer_prep.fit(train_df)

    outer_train_batch = outer_prep.transform(train_df, compute_stats=False)
    outer_val_batch = outer_prep.transform(val_df, compute_stats=True)

    y_train = torch.tensor(train_df["ARR_DELAY"].to_numpy(dtype=np.float32), dtype=torch.float32)
    y_val = val_df["ARR_DELAY"].to_numpy(dtype=np.float64)

    # Fresh seed for retraining consistency
    torch.manual_seed(seed + 100)
    np.random.seed(seed + 100)

    outer_model = PointNNModel(
        rep_type=rep_type,
        num_carriers=len(outer_prep.carrier_to_idx_) + 1,
        num_origins=len(outer_prep.origin_to_idx_) + 1,
        num_flight_categories=len(outer_prep.flight_to_idx_) + 1,
        num_one_hot_bins=outer_prep.one_hot_dim_,
    ).to(device)

    outer_optimizer = torch.optim.AdamW(outer_model.parameters(), lr=lr, weight_decay=weight_decay)

    outer_train_dataset = TensorDataset(
        torch.from_numpy(outer_train_batch.continuous),
        torch.from_numpy(outer_train_batch.carrier_indices),
        torch.from_numpy(outer_train_batch.origin_indices),
        torch.from_numpy(outer_train_batch.flight_feature),
        y_train,
    )
    outer_train_loader = DataLoader(outer_train_dataset, batch_size=batch_size, shuffle=True)

    # Train strictly for exactly best_epoch
    for _ in range(1, best_epoch + 1):
        outer_model.train()
        for b_cont, b_c, b_o, b_fl, b_y in outer_train_loader:
            outer_optimizer.zero_grad()
            pred = outer_model(b_cont.to(device), b_c.to(device), b_o.to(device), b_fl.to(device))
            loss = criterion(pred, b_y.to(device))
            loss.backward()
            outer_optimizer.step()

    # Out-of-sample evaluation on outer validation
    outer_model.eval()
    with torch.no_grad():
        out_cont = torch.from_numpy(outer_val_batch.continuous).to(device)
        out_carrier = torch.from_numpy(outer_val_batch.carrier_indices).to(device)
        out_origin = torch.from_numpy(outer_val_batch.origin_indices).to(device)
        out_fl = torch.from_numpy(outer_val_batch.flight_feature).to(device)
        y_pred = outer_model(out_cont, out_carrier, out_origin, out_fl).cpu().numpy().astype(np.float64)

    # Compute point metrics
    mae = float(mean_absolute_error(y_val, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_val, y_pred)))
    medae = float(median_absolute_error(y_val, y_pred))
    r2 = float(r2_score(y_val, y_pred))
    pearson_r = float(np.corrcoef(y_val, y_pred)[0, 1]) if np.std(y_pred) > 1e-8 else 0.0

    return {
        "candidate": rep_type.value,
        "best_epoch": best_epoch,
        "best_inner_mae": best_inner_mae,
        "inner_mae_history": inner_mae_history,
        "outer_metrics": {
            "mae": mae,
            "rmse": rmse,
            "medae": medae,
            "r2": r2,
            "pearson_r": pearson_r,
        },
        "y_pred": y_pred,
        "provenance_stats": outer_val_batch.provenance_stats,
    }
