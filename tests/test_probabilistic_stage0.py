"""Comprehensive unit tests for Probabilistic Core Arrival Stage 0.

Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Stage 0
Test coverage:
- representation determinism
- time cyclic encoding
- calendar cyclic encoding
- unknown categorical embedding index
- inner/outer split safety
- no 2024 access guard
- no outer-val early stopping guard
- reproducibility of seed policy metadata
- target semantics audit invariants
- numerically stable likelihood and deep tail behavior
- discrete quantile monotonicity and integrity
- dependence interface and PSD policy
- candidate expansion and pruning rules
"""

from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.data.access_guard import DataAccessDenied, assert_data_access_allowed
from src.features.tabular_features import APPROVED_PREDICTOR_COLUMNS
from src.models.probabilistic.contracts import (
    CALIBRATION_80_BOUNDS,
    CALIBRATION_90_BOUNDS,
    CATEGORICAL_EMBEDDING_COLUMNS,
    CandidateExpansionRules,
    FINALIST_SEEDS,
    PREDETERMINED_DEPLOYMENT_SEED,
    PROBABILISTIC_PROTOCOL_VERSION,
    ProbabilisticContractViolation,
    ProbabilisticTemporalError,
    SCREENING_SEED,
    SEED_ENSEMBLE_CANDIDATE_ID,
    SEED_MANIFEST_VERSION,
    TARGET_SEMANTICS_DECISION,
)
from src.models.probabilistic.dependence_interface import (
    DayFlightBatch,
    DiscretePITPolicy,
    MarginalDistributionProtocol,
    PSDPolicy,
)
from src.models.probabilistic.likelihood import (
    continuous_mixture_log_prob,
    discrete_mixture_cdf,
    discrete_mixture_quantile,
    discretized_mixture_log_prob,
    log1mexp,
    log_ndtr_diff,
)
from src.models.probabilistic.representation import (
    CONTINUOUS_FEATURE_NAMES,
    ProbabilisticNNPreprocessor,
    ProcessedNNFeatures,
)
from src.models.probabilistic.splitting import (
    FROZEN_PROBABILISTIC_FOLDS,
    ProbabilisticInnerOuterFold,
    assert_early_stopping_safety,
    get_probabilistic_inner_outer_folds,
)


def _make_synthetic_arrival_df(n_rows: int = 50, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    hours = rng.integers(0, 24, size=n_rows)
    minutes = rng.integers(0, 60, size=n_rows)
    months = rng.integers(1, 13, size=n_rows)
    dows = rng.integers(1, 8, size=n_rows)
    days = rng.integers(1, 29, size=n_rows)
    years = rng.choice([2016, 2017, 2018], size=n_rows)
    elapsed = rng.uniform(45.0, 360.0, size=n_rows)
    is_weekend = np.isin(dows, [6, 7]).astype(int)

    carriers = rng.choice(["AA", "DL", "UA", "WN"], size=n_rows)
    origins = rng.choice(["BOS", "JFK", "LAX", "ORD", "MIA"], size=n_rows)
    flight_nums = rng.choice(["101", "202", "303", "404"], size=n_rows)

    df = pd.DataFrame(
        {
            "CRS_ELAPSED_TIME": elapsed,
            "calendar_year": years,
            "calendar_month": months,
            "calendar_day_of_month": days,
            "calendar_day_of_week": dows,
            "is_weekend": is_weekend,
            "scheduled_departure_hour": hours,
            "scheduled_departure_minute": minutes,
            "OP_CARRIER": carriers,
            "ORIGIN": origins,
            "OP_CARRIER_FL_NUM": flight_nums,
        }
    )
    return df[list(APPROVED_PREDICTOR_COLUMNS)]


# =========================================================================
# A. Representation Tests
# =========================================================================

def test_representation_determinism() -> None:
    df1 = _make_synthetic_arrival_df(n_rows=100, seed=123)
    df2 = _make_synthetic_arrival_df(n_rows=100, seed=123)

    prep1 = ProbabilisticNNPreprocessor()
    res1 = prep1.fit(df1).transform(df1)

    prep2 = ProbabilisticNNPreprocessor()
    res2 = prep2.fit(df2).transform(df2)

    np.testing.assert_array_equal(res1.continuous, res2.continuous)
    np.testing.assert_array_equal(res1.categorical, res2.categorical)
    assert prep1.numeric_medians_ == prep2.numeric_medians_
    assert prep1.vocabularies_ == prep2.vocabularies_
    assert prep1.unknown_indices_ == prep2.unknown_indices_


def test_time_cyclic_encoding() -> None:
    # Construct exact anchor departure times
    # 00:00 -> t=0
    # 06:00 -> t=360
    # 12:00 -> t=720
    # 18:00 -> t=1080
    test_df = pd.DataFrame(
        {
            "scheduled_departure_hour": [0, 6, 12, 18],
            "scheduled_departure_minute": [0, 0, 0, 0],
            "calendar_month": [1, 1, 1, 1],
            "calendar_day_of_month": [1, 1, 1, 1],
            "calendar_day_of_week": [1, 1, 1, 1],
            "is_weekend": [0, 0, 0, 0],
            "calendar_year": [2016, 2016, 2016, 2016],
            "CRS_ELAPSED_TIME": [120.0, 120.0, 120.0, 120.0],
            "OP_CARRIER": ["DL", "DL", "DL", "DL"],
            "ORIGIN": ["BOS", "BOS", "BOS", "BOS"],
            "OP_CARRIER_FL_NUM": ["100", "100", "100", "100"],
        }
    )[list(APPROVED_PREDICTOR_COLUMNS)]

    prep = ProbabilisticNNPreprocessor()
    res = prep.fit(test_df).transform(test_df)

    sin_time = res.continuous[:, 0]
    cos_time = res.continuous[:, 1]

    # t=0 (00:00): sin(0) = 0, cos(0) = 1
    assert np.isclose(sin_time[0], 0.0, atol=1e-7)
    assert np.isclose(cos_time[0], 1.0, atol=1e-7)

    # t=360 (06:00): sin(pi/2) = 1, cos(pi/2) = 0
    assert np.isclose(sin_time[1], 1.0, atol=1e-7)
    assert np.isclose(cos_time[1], 0.0, atol=1e-7)

    # t=720 (12:00): sin(pi) = 0, cos(pi) = -1
    assert np.isclose(sin_time[2], 0.0, atol=1e-7)
    assert np.isclose(cos_time[2], -1.0, atol=1e-7)

    # t=1080 (18:00): sin(3pi/2) = -1, cos(3pi/2) = 0
    assert np.isclose(sin_time[3], -1.0, atol=1e-7)
    assert np.isclose(cos_time[3], 0.0, atol=1e-7)

    # Verify unit circle norm
    np.testing.assert_allclose(sin_time**2 + cos_time**2, 1.0, atol=1e-7)


def test_calendar_cyclic_encoding() -> None:
    # Months 1, 4, 7, 10
    test_df = pd.DataFrame(
        {
            "scheduled_departure_hour": [12, 12, 12, 12],
            "scheduled_departure_minute": [0, 0, 0, 0],
            "calendar_month": [1, 4, 7, 10],
            "calendar_day_of_month": [1, 1, 1, 1],
            "calendar_day_of_week": [1, 1, 1, 1],
            "is_weekend": [0, 0, 0, 0],
            "calendar_year": [2016, 2016, 2016, 2016],
            "CRS_ELAPSED_TIME": [100.0, 100.0, 100.0, 100.0],
            "OP_CARRIER": ["DL", "DL", "DL", "DL"],
            "ORIGIN": ["BOS", "BOS", "BOS", "BOS"],
            "OP_CARRIER_FL_NUM": ["100", "100", "100", "100"],
        }
    )[list(APPROVED_PREDICTOR_COLUMNS)]

    prep = ProbabilisticNNPreprocessor()
    res = prep.fit(test_df).transform(test_df)

    sin_month = res.continuous[:, 2]
    cos_month = res.continuous[:, 3]

    # m=1 (Jan): (1-1)/12 = 0 -> sin=0, cos=1
    assert np.isclose(sin_month[0], 0.0, atol=1e-7)
    assert np.isclose(cos_month[0], 1.0, atol=1e-7)

    # m=4 (Apr): (4-1)/12 = 3/12 = 1/4 -> angle = pi/2 -> sin=1, cos=0
    assert np.isclose(sin_month[1], 1.0, atol=1e-7)
    assert np.isclose(cos_month[1], 0.0, atol=1e-7)

    # m=7 (Jul): (7-1)/12 = 6/12 = 1/2 -> angle = pi -> sin=0, cos=-1
    assert np.isclose(sin_month[2], 0.0, atol=1e-7)
    assert np.isclose(cos_month[2], -1.0, atol=1e-7)

    # m=10 (Oct): (10-1)/12 = 9/12 = 3/4 -> angle = 3pi/2 -> sin=-1, cos=0
    assert np.isclose(sin_month[3], -1.0, atol=1e-7)
    assert np.isclose(cos_month[3], 0.0, atol=1e-7)

    np.testing.assert_allclose(sin_month**2 + cos_month**2, 1.0, atol=1e-7)


def test_unknown_categorical_embedding_index() -> None:
    train_df = pd.DataFrame(
        {
            "scheduled_departure_hour": [10, 11],
            "scheduled_departure_minute": [0, 30],
            "calendar_month": [1, 2],
            "calendar_day_of_month": [5, 10],
            "calendar_day_of_week": [1, 2],
            "is_weekend": [0, 0],
            "calendar_year": [2016, 2017],
            "CRS_ELAPSED_TIME": [120.0, 150.0],
            "OP_CARRIER": ["AA", "DL"],
            "ORIGIN": ["BOS", "JFK"],
            "OP_CARRIER_FL_NUM": ["100", "200"],
        }
    )[list(APPROVED_PREDICTOR_COLUMNS)]

    prep = ProbabilisticNNPreprocessor()
    prep.fit(train_df)

    # Check fitted vocabularies
    # OP_CARRIER has 2 categories: "AA"=0, "DL"=1. Dedicated UNKNOWN index is 2.
    assert prep.vocabularies_["OP_CARRIER"] == {"AA": 0, "DL": 1}
    assert prep.unknown_indices_["OP_CARRIER"] == 2
    assert prep.vocabulary_sizes_["OP_CARRIER"] == 3

    # ORIGIN has 2 categories: "BOS"=0, "JFK"=1. UNKNOWN is 2.
    assert prep.vocabularies_["ORIGIN"] == {"BOS": 0, "JFK": 1}
    assert prep.unknown_indices_["ORIGIN"] == 2
    assert prep.vocabulary_sizes_["ORIGIN"] == 3

    # Transform with known and unknown categories
    val_df = pd.DataFrame(
        {
            "scheduled_departure_hour": [10, 11, 12],
            "scheduled_departure_minute": [0, 30, 45],
            "calendar_month": [1, 2, 3],
            "calendar_day_of_month": [5, 10, 15],
            "calendar_day_of_week": [1, 2, 3],
            "is_weekend": [0, 0, 0],
            "calendar_year": [2018, 2018, 2018],
            "CRS_ELAPSED_TIME": [120.0, 150.0, 180.0],
            "OP_CARRIER": ["DL", "UA", None],  # DL=1, UA=UNKNOWN(2), None=UNKNOWN(2)
            "ORIGIN": ["LAX", "BOS", ""],       # LAX=UNKNOWN(2), BOS=0, ""=UNKNOWN(2)
            "OP_CARRIER_FL_NUM": ["100", "999", "200"], # 100=0, 999=UNKNOWN(2), 200=1
        }
    )[list(APPROVED_PREDICTOR_COLUMNS)]

    val_res = prep.transform(val_df)
    cat = val_res.categorical

    # Check OP_CARRIER column (col 0)
    assert cat[0, 0] == 1  # DL
    assert cat[1, 0] == 2  # UA -> UNKNOWN
    assert cat[2, 0] == 2  # None -> UNKNOWN

    # Check ORIGIN column (col 1)
    assert cat[0, 1] == 2  # LAX -> UNKNOWN
    assert cat[1, 1] == 0  # BOS
    assert cat[2, 1] == 2  # "" -> UNKNOWN

    # Check OP_CARRIER_FL_NUM column (col 2)
    assert cat[0, 2] == 0  # 100
    assert cat[1, 2] == 2  # 999 -> UNKNOWN
    assert cat[2, 2] == 1  # 200

    # Strict invariant: no negative indices anywhere
    assert (cat >= 0).all()
    # Check max index strictly bounded by vocabulary_size - 1
    assert cat[:, 0].max() <= prep.vocabulary_sizes_["OP_CARRIER"] - 1


def test_reject_unauthorized_columns() -> None:
    df = _make_synthetic_arrival_df(n_rows=10)
    df["DEP_DELAY"] = 10.0  # Forbidden leakage column

    prep = ProbabilisticNNPreprocessor()
    with pytest.raises(ProbabilisticContractViolation, match="unauthorized extra columns"):
        prep.fit(df)


# =========================================================================
# B. Inner/Outer Split and Holdout Safety Tests
# =========================================================================

def test_inner_outer_split_safety() -> None:
    folds = get_probabilistic_inner_outer_folds()
    assert len(folds) == 4

    for f in folds:
        # 1. Outer validation year must strictly succeed outer train years
        assert f.outer_val_year > max(f.outer_train_years)
        assert f.outer_val_year not in f.outer_train_years

        # 2. Inner validation year must strictly succeed inner train years
        assert f.inner_val_year > max(f.inner_train_years)
        assert f.inner_val_year not in f.inner_train_years

        # 3. Inner split must partition outer_train exactly
        assert set(f.inner_train_years) | {f.inner_val_year} == set(f.outer_train_years)

        # 4. Outer validation must NEVER be in inner split
        assert f.outer_val_year not in f.inner_train_years
        assert f.outer_val_year != f.inner_val_year


def test_no_2024_access_guard() -> None:
    # Attempting to construct fold with 2024 must fail closed
    with pytest.raises(ProbabilisticTemporalError, match="2024 is sealed FINAL_HOLDOUT"):
        ProbabilisticInnerOuterFold(
            fold_id="invalid_2024",
            outer_train_years=(2016, 2017, 2018),
            outer_val_year=2024,
            inner_train_years=(2016, 2017),
            inner_val_year=2018,
        )

    # Access guard must reject 2024 for development
    with pytest.raises(DataAccessDenied):
        assert_data_access_allowed(2024, "development")


def test_no_2023_in_development_folds() -> None:
    # Attempting to include 2023 in rolling development fold must fail closed
    with pytest.raises(ProbabilisticTemporalError, match="2023 is DEVELOPMENT_MODEL_SELECTION"):
        ProbabilisticInnerOuterFold(
            fold_id="invalid_2023",
            outer_train_years=(2016, 2017, 2018, 2019, 2020, 2021, 2022),
            outer_val_year=2023,
            inner_train_years=(2016, 2017, 2018, 2019, 2020, 2021),
            inner_val_year=2022,
        )


def test_no_outer_val_early_stopping() -> None:
    fold1 = FROZEN_PROBABILISTIC_FOLDS[0]  # outer val 2019, inner val 2018

    # 1. Outer training cannot have early stopping enabled
    with pytest.raises(ProbabilisticTemporalError, match="cannot use early stopping"):
        assert_early_stopping_safety(
            fold1,
            monitored_val_year=2019,
            is_outer_training=True,
            early_stopping_enabled=True,
        )

    # 2. Outer training cannot monitor outer validation year
    with pytest.raises(ProbabilisticTemporalError, match="must not be monitored"):
        assert_early_stopping_safety(
            fold1,
            monitored_val_year=2019,
            is_outer_training=True,
            early_stopping_enabled=False,
        )

    # 3. Inner training cannot monitor outer validation year
    with pytest.raises(ProbabilisticTemporalError, match="must monitor inner_val_year"):
        assert_early_stopping_safety(
            fold1,
            monitored_val_year=2019,
            is_outer_training=False,
            early_stopping_enabled=True,
        )

    # 4. Valid inner training succeeds
    assert_early_stopping_safety(
        fold1,
        monitored_val_year=2018,
        is_outer_training=False,
        early_stopping_enabled=True,
    )

    # 5. Valid outer training (fixed epoch, no ES) succeeds
    assert_early_stopping_safety(
        fold1,
        monitored_val_year=0,  # no validation monitored
        is_outer_training=True,
        early_stopping_enabled=False,
    )


# =========================================================================
# C. Manifest and Seed Policy Metadata Tests
# =========================================================================

def test_reproducibility_of_seed_policy_metadata() -> None:
    manifest_path = Path("artifacts/manifests/seed_manifest_v1.json")
    assert manifest_path.exists(), "seed_manifest_v1.json must exist"

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["manifest_version"] == SEED_MANIFEST_VERSION
    assert payload["project_seed"] == SCREENING_SEED
    assert payload["screening_seed"] == SCREENING_SEED
    assert tuple(payload["finalist_seeds"]) == FINALIST_SEEDS
    assert payload["predetermined_deployment_seed"] == PREDETERMINED_DEPLOYMENT_SEED
    assert payload["registered_seed_ensemble_candidate"]["candidate_id"] == SEED_ENSEMBLE_CANDIDATE_ID


def test_probabilistic_protocol_manifest_invariants() -> None:
    manifest_path = Path("artifacts/manifests/probabilistic_protocol_v1.json")
    assert manifest_path.exists(), "probabilistic_protocol_v1.json must exist"

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["manifest_version"] == PROBABILISTIC_PROTOCOL_VERSION
    assert payload["task"] == "arrival_core"
    assert payload["hub"] == "ATL"
    assert payload["prediction_cutoff"] == "CRS_DEP_TIME - 2 hours"

    semantics = payload["target_semantics_audit"]
    assert semantics["status"] == "AUDITED_PASS"
    assert semantics["fractional_value_count"] == 0
    assert semantics["fractional_value_frequency"] == 0.0
    assert semantics["value_granularity_minutes"] == 1.0
    assert semantics["decision_record"] == TARGET_SEMANTICS_DECISION
    assert semantics["primary_likelihood_specification"] == "discretized_gaussian_mixture"
    assert semantics["secondary_likelihood_specification"] == "continuous_gaussian_mixture"


# =========================================================================
# D. Likelihood and Quantile Correctness Tests
# =========================================================================

def test_log1mexp_accuracy() -> None:
    # Near 0
    small_x = 1e-5
    expected_small = np.log(-np.expm1(-small_x))
    assert np.isclose(log1mexp(small_x), expected_small, rtol=1e-12)

    # Large x
    large_x = 25.0
    expected_large = np.log1p(-np.exp(-large_x))
    assert np.isclose(log1mexp(large_x), expected_large, rtol=1e-12)


def test_log_ndtr_diff_deep_tails() -> None:
    # 1. Central regime
    a_mid, b_mid = -0.5, 0.5
    expected_mid = np.log(0.691462461274013 - 0.3085375387259869)  # Phi(0.5) - Phi(-0.5)
    val_mid = log_ndtr_diff(a_mid, b_mid)
    assert np.isclose(val_mid, expected_mid, rtol=1e-6)

    # 2. Extreme right tail (a=19, b=20)
    # Direct ndtr would suffer underflow (1.0 - 1.0 = 0.0 -> log = -inf)
    val_right = log_ndtr_diff(19.0, 20.0)
    assert np.isfinite(val_right)
    assert val_right < -100.0

    # 3. Extreme left tail (a=-20, b=-19)
    val_left = log_ndtr_diff(-20.0, -19.0)
    assert np.isfinite(val_left)

    # Exact symmetry invariant: Phi(20) - Phi(19) == Phi(-19) - Phi(-20)
    assert np.isclose(val_right, val_left, rtol=1e-10)

    # 4. Degenerate a >= b returns -inf
    assert log_ndtr_diff(5.0, 5.0) == -np.inf
    assert log_ndtr_diff(5.0, 4.0) == -np.inf


def test_discrete_quantile_monotonicity() -> None:
    pi = np.array([0.4, 0.6])
    mu = np.array([0.0, 30.0])
    sigma = np.array([8.0, 20.0])

    p_grid = np.array([0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99])
    q_vals = discrete_mixture_quantile(p_grid, pi, mu, sigma)

    # Invariant 1: Quantiles are integers
    assert np.issubdtype(q_vals.dtype, np.integer)

    # Invariant 2: Strictly monotonic in p
    for i in range(len(q_vals) - 1):
        assert q_vals[i] <= q_vals[i + 1]

    # Invariant 3: Exact discrete quantile definition F(Q(p)) >= p > F(Q(p) - 1)
    for p_val, q_val in zip(p_grid, q_vals):
        f_q = discrete_mixture_cdf(q_val, pi, mu, sigma)
        f_prev = discrete_mixture_cdf(q_val - 1, pi, mu, sigma)
        assert f_q >= p_val
        assert f_prev < p_val


def test_discretized_mixture_log_prob_matches_discrete_cdf() -> None:
    pi = np.array([0.5, 0.5])
    mu = np.array([-5.0, 20.0])
    sigma = np.array([5.0, 10.0])

    # Check sum of probabilities over a wide integer range ~ 1.0
    y_range = np.arange(-50, 80)
    log_probs = discretized_mixture_log_prob(y_range, pi, mu, sigma)
    probs = np.exp(log_probs)

    assert (probs >= 0.0).all()
    # Total mass over [-50, 80] must be close to 1.0
    assert np.isclose(np.sum(probs), 1.0, atol=1e-4)


# =========================================================================
# E. Dependence Interface Tests
# =========================================================================

def test_day_flight_batch_variable_n() -> None:
    # Batch 1: 15 flights
    df_small = _make_synthetic_arrival_df(n_rows=15, seed=1)
    batch_small = DayFlightBatch(flight_date="2018-05-10", flight_features=df_small)
    assert batch_small.n_flights == 15

    # Batch 2: 240 flights
    df_large = _make_synthetic_arrival_df(n_rows=240, seed=2)
    batch_large = DayFlightBatch(flight_date="2018-05-11", flight_features=df_large)
    assert batch_large.n_flights == 240


def test_day_flight_batch_rejects_leakage() -> None:
    df = _make_synthetic_arrival_df(n_rows=20)
    df["ARR_TIME"] = "14:30"
    with pytest.raises(ProbabilisticContractViolation, match="realized post-cutoff columns"):
        DayFlightBatch(flight_date="2018-05-10", flight_features=df)


def test_psd_policy_projection() -> None:
    # Create non-PSD symmetric matrix
    non_psd = np.array([[1.0, 0.9, 0.9], [0.9, 1.0, 0.9], [0.9, 0.9, 0.1]])  # diagonal not 1, not PSD
    psd = PSDPolicy.ensure_psd(non_psd, min_eigenvalue=1e-5, is_correlation=True)

    # 1. Eigenvalues must all be >= min_eigenvalue
    eigvals = np.linalg.eigvalsh(psd)
    assert (eigvals >= 1e-6).all()

    # 2. Diagonal must be 1.0
    np.testing.assert_allclose(np.diag(psd), 1.0, atol=1e-6)

    # 3. Symmetry
    np.testing.assert_allclose(psd, psd.T, atol=1e-10)


def test_discrete_pit_policy() -> None:
    class MockMarginal:
        def cdf(self, y: float) -> float:
            # Simple discrete standard logistic-like CDF
            return float(1.0 / (1.0 + np.exp(-0.2 * y)))

        def quantile(self, p: float) -> float:
            return 0.0

        def sample(self, n_samples: int, rng: np.random.Generator) -> np.ndarray:
            return np.zeros(n_samples)

    marginals = [MockMarginal() for _ in range(5)]
    delays = np.array([-10.0, 0.0, 5.0, 15.0, 60.0])

    rng = np.random.default_rng(202601)
    u = DiscretePITPolicy.compute_randomized_pit(delays, marginals, rng)

    assert len(u) == 5
    assert (u > 0.0).all() and (u < 1.0).all()

    # Sensitivity across draws
    sens = DiscretePITPolicy.evaluate_pit_sensitivity(delays, marginals, n_draws=5, base_seed=202601)
    assert sens["n_draws"] == 5.0
    assert sens["sensitivity_stable"] == 1.0


# =========================================================================
# F. Candidate Expansion & Pruning Rules Tests
# =========================================================================

def test_candidate_expansion_rules() -> None:
    rules = CandidateExpansionRules()

    # K=5 Opening
    # All 3 met -> True
    assert rules.evaluate_k5_opening(
        effective_components=2.6, min_component_weight=0.08, crps_improvement_ci_lower=0.07
    )
    # Effective components < 2.50 -> False
    assert not rules.evaluate_k5_opening(
        effective_components=2.2, min_component_weight=0.08, crps_improvement_ci_lower=0.07
    )
    # Component weight < 0.05 -> False
    assert not rules.evaluate_k5_opening(
        effective_components=2.6, min_component_weight=0.03, crps_improvement_ci_lower=0.07
    )
    # CI lower <= 0.05 -> False
    assert not rules.evaluate_k5_opening(
        effective_components=2.6, min_component_weight=0.08, crps_improvement_ci_lower=0.04
    )

    # Pruning Stage 6.5
    # Passed candidate
    passed, reason = rules.evaluate_pruning(
        candidate_crps=19.10,
        best_crps=19.00,
        coverage_80=0.805,
        coverage_90=0.898,
        brier_60=0.0210,
        best_brier_60=0.0200,
    )
    assert passed
    assert reason == "PASS"

    # Failed on CRPS delta > 0.20
    passed, reason = rules.evaluate_pruning(
        candidate_crps=19.30,
        best_crps=19.00,
        coverage_80=0.805,
        coverage_90=0.898,
        brier_60=0.0210,
        best_brier_60=0.0200,
    )
    assert not passed
    assert "exceeds best" in reason

    # Failed on 80% calibration guard (< 0.75)
    passed, reason = rules.evaluate_pruning(
        candidate_crps=19.05,
        best_crps=19.00,
        coverage_80=0.720,
        coverage_90=0.898,
        brier_60=0.0210,
        best_brier_60=0.0200,
    )
    assert not passed
    assert "80% coverage" in reason
