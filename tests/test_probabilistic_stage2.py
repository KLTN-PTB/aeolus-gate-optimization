"""Unit tests for Stage 2 — Representation Ablation.

Verifies:
1. Preprocessing fit strictly on train folds.
2. Unseen category handling (unknown index for R2, 0.0 for R1, other bucket for R0).
3. Symmetry and architectural invariance across R0, R1, R2.
4. Two-phase early-stopping protocol (inner validation determines best_epoch, outer retrains fresh).
5. Category statistics and provenance tracking.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import torch

from src.models.probabilistic.representation_ablation import (
    FlightNumberRepresentation,
    PointNNModel,
    RepresentationAblationPreprocessor,
    train_point_model_fold,
)


@pytest.fixture
def sample_train_val_dfs():
    np.random.seed(42)
    n_train = 200
    n_val = 50

    carriers = ["DL", "WN", "AA"]
    origins = ["ATL", "ORD", "DFW", "LAX"]
    flights = [f"FL_{i}" for i in range(1, 21)]

    def make_df(n: int, include_unseen: bool = False) -> pd.DataFrame:
        fl_pool = flights + ["FL_NEW_1", "FL_NEW_2"] if include_unseen else flights
        return pd.DataFrame(
            {
                "CRS_ELAPSED_TIME": np.random.uniform(60, 300, n),
                "calendar_year": np.full(n, 2018),
                "calendar_month": np.random.randint(1, 13, n),
                "calendar_day_of_month": np.random.randint(1, 29, n),
                "calendar_day_of_week": np.random.randint(1, 8, n),
                "is_weekend": np.random.choice([0, 1], n),
                "scheduled_departure_hour": np.random.randint(5, 23, n),
                "scheduled_departure_minute": np.random.randint(0, 60, n),
                "OP_CARRIER": np.random.choice(carriers, n),
                "ORIGIN": np.random.choice(origins, n),
                "OP_CARRIER_FL_NUM": np.random.choice(fl_pool, n),
                "ARR_DELAY": np.random.normal(5, 25, n),
            }
        )

    train_df = make_df(n_train, include_unseen=False)
    val_df = make_df(n_val, include_unseen=True)
    return train_df, val_df


def test_ablation_preprocessor_r2_embedding(sample_train_val_dfs):
    train_df, val_df = sample_train_val_dfs
    prep = RepresentationAblationPreprocessor(FlightNumberRepresentation.R2_EMBEDDING)
    prep.fit(train_df)

    assert prep.is_fitted_
    assert len(prep.flight_to_idx_) == 20
    assert prep.unknown_flight_idx_ == 20  # index 20 is dedicated UNKNOWN

    batch_val = prep.transform(val_df, compute_stats=True)
    assert batch_val.continuous.shape == (50, 10)
    assert batch_val.flight_feature.ndim == 1
    assert batch_val.flight_feature.dtype == np.int64

    # Check unknown index usage on unseen categories
    stats = batch_val.provenance_stats
    assert stats is not None
    assert stats.train_flight_category_count == 20
    assert stats.unseen_flight_category_count > 0
    assert stats.unknown_index_usage_count > 0
    assert (batch_val.flight_feature == 20).sum() == stats.unknown_index_usage_count


def test_ablation_preprocessor_r1_frequency(sample_train_val_dfs):
    train_df, val_df = sample_train_val_dfs
    prep = RepresentationAblationPreprocessor(FlightNumberRepresentation.R1_FREQUENCY_MAP)
    prep.fit(train_df)

    batch_val = prep.transform(val_df, compute_stats=True)
    assert batch_val.flight_feature.shape == (50, 1)
    assert batch_val.flight_feature.dtype == np.float32

    # Unseen flight numbers must have 0.0 frequency
    unseen_mask = val_df["OP_CARRIER_FL_NUM"].isin(["FL_NEW_1", "FL_NEW_2"])
    if unseen_mask.any():
        assert np.all(batch_val.flight_feature[unseen_mask.to_numpy()] == 0.0)


def test_ablation_preprocessor_r0_one_hot(sample_train_val_dfs):
    train_df, val_df = sample_train_val_dfs
    top_m = 5
    prep = RepresentationAblationPreprocessor(
        FlightNumberRepresentation.R0_LOW_CARD_ONE_HOT, top_m_flights=top_m
    )
    prep.fit(train_df)

    batch_val = prep.transform(val_df, compute_stats=True)
    assert batch_val.flight_feature.shape == (50, top_m + 1)
    # Each row must be a valid one-hot vector (sum to 1)
    assert np.allclose(batch_val.flight_feature.sum(axis=1), 1.0)


def test_point_nn_model_architectural_symmetry(sample_train_val_dfs):
    train_df, val_df = sample_train_val_dfs

    for rep in [
        FlightNumberRepresentation.R0_LOW_CARD_ONE_HOT,
        FlightNumberRepresentation.R1_FREQUENCY_MAP,
        FlightNumberRepresentation.R2_EMBEDDING,
    ]:
        prep = RepresentationAblationPreprocessor(rep)
        prep.fit(train_df)
        batch = prep.transform(val_df)

        model = PointNNModel(
            rep_type=rep,
            num_carriers=len(prep.carrier_to_idx_) + 1,
            num_origins=len(prep.origin_to_idx_) + 1,
            num_flight_categories=len(prep.flight_to_idx_) + 1,
            num_top_flights=prep.top_m_flights,
            num_one_hot_bins=prep.one_hot_dim_,
        )

        # Trunk must have identical layer shapes
        trunk_layers = list(model.trunk.children())
        assert isinstance(trunk_layers[0], torch.nn.Linear)
        assert trunk_layers[0].in_features == 50  # 10 cont + 8 carrier + 16 origin + 16 flight
        assert trunk_layers[0].out_features == 128
        assert trunk_layers[4].in_features == 128
        assert trunk_layers[4].out_features == 64
        assert trunk_layers[6].in_features == 64
        assert trunk_layers[6].out_features == 1

        out = model(
            torch.from_numpy(batch.continuous),
            torch.from_numpy(batch.carrier_indices),
            torch.from_numpy(batch.origin_indices),
            torch.from_numpy(batch.flight_feature),
        )
        assert out.shape == (50,)
        assert not torch.isnan(out).any()


def test_train_point_model_two_phase_protocol(sample_train_val_dfs):
    train_df, val_df = sample_train_val_dfs
    inner_train_df = train_df.iloc[:140].copy()
    inner_val_df = train_df.iloc[140:].copy()

    result = train_point_model_fold(
        rep_type=FlightNumberRepresentation.R1_FREQUENCY_MAP,
        train_df=train_df,
        val_df=val_df,
        inner_train_df=inner_train_df,
        inner_val_df=inner_val_df,
        seed=202601,
        max_epochs=4,
        batch_size=64,
    )

    assert "best_epoch" in result
    assert 1 <= result["best_epoch"] <= 4
    assert len(result["inner_mae_history"]) == 4
    assert "outer_metrics" in result
    assert result["outer_metrics"]["mae"] > 0
    assert result["outer_metrics"]["rmse"] > 0
    assert result["y_pred"].shape == (50,)
    assert result["provenance_stats"] is not None
