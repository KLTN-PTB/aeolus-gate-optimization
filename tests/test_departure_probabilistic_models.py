"""Unit tests for Core Departure Probabilistic Models, Predictive Distributions, and Sampling Safety.

Protocol: Aeolus Dual Core Architecture Protocol V2
Phase: P5 Verification Suite
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import pytest

from src.contracts.distribution import (
    CapabilityNotSupportedError,
    DistributionCapabilities,
    DistributionValidationError,
    PredictiveDistribution,
)
from src.features.departure_features import (
    prepare_departure_inference,
    prepare_departure_training,
)
from src.models.interfaces import ModelCategory, ModelTask
from src.models.probabilistic.contracts import DEFAULT_SIGMA_FLOOR
from src.models.probabilistic.departure_distributions import (
    DepartureEmpiricalBaseline,
    DepartureGaussianResidualModel,
    DepartureNGBoostNormalModel,
    DepartureNGBoostStudentTModel,
    DepartureQuantileModel,
)
from src.models.registry import get_model_spec, list_models


ROOT = Path(__file__).resolve().parents[1]
DUAL_CORE_DIR = ROOT / "artifacts" / "dual_core"
MODELS_DIR = DUAL_CORE_DIR / "models"
PRED_DIR = DUAL_CORE_DIR / "predictions"
BENCH_DIR = DUAL_CORE_DIR / "benchmarks"


@pytest.fixture
def synthetic_training_batch() -> tuple[pd.DataFrame, np.ndarray]:
    """Generates synthetic outbound flight batch with signed delays."""
    np.random.seed(202601)
    n = 200
    df = pd.DataFrame(
        {
            "flight_key": [f"fl_{i}" for i in range(n)],
            "source_year": [2022] * n,
            "source_row_number": list(range(n)),
            "ORIGIN": ["ATL"] * n,
            "DEST": np.random.choice(["LGA", "ORD", "MCO", "DFW", "LAX"], size=n),
            "OP_CARRIER": np.random.choice(["DL", "9E", "WN", "AA"], size=n),
            "OP_CARRIER_FL_NUM": np.random.choice([101.0, 202.0, 303.0], size=n),
            "FL_DATE": ["2022-06-15 00:00:00"] * n,
            "CRS_DEP_TIME": ["2022-06-15 09:30:00"] * n,
            "CRS_ELAPSED_TIME": np.random.uniform(60.0, 300.0, size=n),
            "MONTH": [6] * n,
            "DAY_OF_MONTH": [15] * n,
            "DAY_OF_WEEK": [3] * n,
            # Realistic signed delay distribution: early clustered around -5, positive tail
            "DEP_DELAY": np.random.choice([-8.0, -5.0, -2.0, 0.0, 10.0, 45.0, 90.0], size=n),
        }
    )
    prep = prepare_departure_training(df)
    return prep.X, prep.y_dep_reg.values


class TestCapabilityContracts:
    """Verifies explicit capability declarations and fail-closed errors."""

    def test_empirical_baseline_capabilities(self, synthetic_training_batch):
        X, y = synthetic_training_batch
        model = DepartureEmpiricalBaseline()
        caps = model.capabilities()
        assert caps.supports("mean") is True
        assert caps.supports("median") is True
        assert caps.supports("sample") is True
        assert caps.supports("quantile") is True
        assert caps.supports("nll") is False  # Step CDF cannot evaluate continuous likelihood

        model.fit(X, y)
        dist = model.predict_distribution(X[:10])
        assert len(dist.mean) == 10
        assert dist.sample(5, seed=42).shape == (5, 10)

    def test_gaussian_residual_capabilities(self, synthetic_training_batch):
        X, y = synthetic_training_batch
        model = DepartureGaussianResidualModel()
        caps = model.capabilities()
        assert caps.supports("mean") is True
        assert caps.supports("nll") is True
        assert caps.supports("crps_exact") is True
        assert caps.supports("sample") is True

        model.fit(X, y)
        dist = model.predict_distribution(X[:10])
        assert len(dist.mean) == 10
        assert dist.sample(3, seed=42).shape == (3, 10)

    def test_student_t_capabilities(self, synthetic_training_batch):
        X, y = synthetic_training_batch
        model = DepartureNGBoostStudentTModel(n_estimators=5, learning_rate=0.01)
        caps = model.capabilities()
        assert caps.supports("mean") is True
        assert caps.supports("sample") is True
        assert caps.supports("nll") is True
        assert caps.supports("pit") is True

        model.fit(X, y)
        dist = model.predict_distribution(X[:10])
        assert len(dist.mean) == 10
        # Check degrees of freedom safety floor
        df_vals = dist.metadata["dist_params"]["df"]
        assert np.all(df_vals >= 2.1)

    def test_quantile_model_fails_closed_on_unsupported_sampling(self, synthetic_training_batch):
        X, y = synthetic_training_batch
        model = DepartureQuantileModel(n_estimators=5)
        caps = model.capabilities()
        assert caps.supports("quantile") is True
        assert caps.supports("sample") is False
        assert caps.supports("cdf") is False

        model.fit(X, y)
        dist = model.predict_distribution(X[:10])
        assert dist.capabilities.supports("sample") is False

        with pytest.raises(CapabilityNotSupportedError):
            dist.sample(10)

        with pytest.raises(CapabilityNotSupportedError):
            dist.cdf(15.0)


class TestSamplingSafetyAndReproducibility:
    """Verifies that generative draws are deterministic, non-clipped, and finite."""

    def test_student_t_sampling_reproducibility(self, synthetic_training_batch):
        X, y = synthetic_training_batch
        model = DepartureNGBoostStudentTModel(n_estimators=5, learning_rate=0.01)
        model.fit(X, y)

        sample1 = model.sample(X[:20], n_samples=50, seed=202601)
        sample2 = model.sample(X[:20], n_samples=50, seed=202601)

        # Exact bitwise parity given identical seed
        assert np.allclose(sample1, sample2, atol=1e-12)
        assert sample1.shape == (50, 20)
        assert np.all(np.isfinite(sample1))

    def test_gaussian_residual_sampling_reproducibility(self, synthetic_training_batch):
        X, y = synthetic_training_batch
        model = DepartureGaussianResidualModel()
        model.fit(X, y)

        sample1 = model.sample(X[:20], n_samples=50, seed=202601)
        sample2 = model.sample(X[:20], n_samples=50, seed=202601)

        assert np.allclose(sample1, sample2, atol=1e-12)
        assert sample1.shape == (50, 20)
        assert np.all(np.isfinite(sample1))

    def test_signed_support_preserved_no_negative_clipping(self, synthetic_training_batch):
        """Signed departure delays must include negative draws (early departures)."""
        X, y = synthetic_training_batch
        model = DepartureGaussianResidualModel()
        model.fit(X, y)

        draws = model.sample(X[:30], n_samples=100, seed=42)
        # Verify negative values exist and are not artificially clipped at 0
        assert np.any(draws < -1.0), "Predictive distribution must not artificially clip negative delays"


class TestMonotonicityAndParameterDomains:
    """Verifies mathematical consistency of CDF, quantiles, and parameters."""

    def test_cdf_and_quantile_monotonicity(self, synthetic_training_batch):
        X, y = synthetic_training_batch
        model = DepartureGaussianResidualModel()
        model.fit(X, y)
        dist = model.predict_distribution(X[:15])

        # Test quantile monotonicity
        q10 = dist.quantile(0.10)
        q50 = dist.quantile(0.50)
        q90 = dist.quantile(0.90)

        assert np.all(q10 <= q50)
        assert np.all(q50 <= q90)

        # Test CDF monotonicity
        cdf_neg10 = dist.cdf(-10.0)
        cdf_0 = dist.cdf(0.0)
        cdf_30 = dist.cdf(30.0)

        assert np.all(cdf_neg10 <= cdf_0)
        assert np.all(cdf_0 <= cdf_30)
        assert np.all(cdf_neg10 >= 0.0)
        assert np.all(cdf_30 <= 1.0)

    def test_validation_rejects_invalid_parameters(self):
        from src.contracts.distribution import GaussianResidualDistribution
        # Test validation error when sigma <= 0
        invalid_dist = GaussianResidualDistribution(
            mu=np.array([10.0, 5.0]),
            sigma=np.array([5.0, -1.0]),  # Invalid negative sigma
        )
        with pytest.raises(DistributionValidationError):
            invalid_dist.validate()


class TestRegistryAndDownstreamGuards:
    """Verifies that all Core Departure probabilistic models are registered and downstream-disabled."""

    def test_probabilistic_models_registered(self):
        expected_ids = [
            "departure_empirical_residual_v1",
            "departure_gaussian_residual_v1",
            "departure_ngboost_normal_v1",
            "departure_ngboost_student_t_v1",
            "departure_quantile_baseline_v1",
            "departure_distribution_v1",
        ]
        for mid in expected_ids:
            spec = get_model_spec(mid)
            assert spec is not None
            assert spec.task == ModelTask.CORE_DEPARTURE.value
            assert spec.category == ModelCategory.CORE_DEPARTURE.value
            assert spec.probabilistic is True
            assert spec.downstream_eligible is False, f"Model {mid} must be downstream ineligible!"


class TestArtifactIntegrity:
    """Verifies generated joblib models, prediction parquets, and readiness manifests."""

    @pytest.mark.skipif(
        not (MODELS_DIR / "departure_distribution_v1.joblib").exists(),
        reason="Champion distribution model not yet serialized",
    )
    def test_champion_distribution_reload_and_label_free_inference(self):
        champion = joblib.load(MODELS_DIR / "departure_distribution_v1.joblib")

        # Label-free raw input DataFrame strictly without DEP_DELAY or ARR_DELAY
        raw_test = pd.DataFrame(
            {
                "flight_key": ["t_1", "t_2"],
                "source_year": [2023, 2023],
                "source_row_number": [1, 2],
                "ORIGIN": ["ATL", "ATL"],
                "FL_DATE": ["2023-05-01 00:00:00", "2023-05-01 00:00:00"],
                "CRS_DEP_TIME": ["2023-05-01 08:30:00", "2023-05-01 17:45:00"],
                "CRS_ELAPSED_TIME": [120.0, 240.0],
                "MONTH": [5, 5],
                "DAY_OF_MONTH": [1, 1],
                "DAY_OF_WEEK": [1, 1],
                "OP_CARRIER": ["DL", "UA"],
                "OP_CARRIER_FL_NUM": [123.0, 456.0],
                "DEST": ["LGA", "ORD"],
            }
        )

        assert "DEP_DELAY" not in raw_test.columns
        assert "ARR_DELAY" not in raw_test.columns

        features = prepare_departure_inference(raw_test)
        dist = champion.predict_distribution(features.X)

        assert len(dist.mean) == 2
        assert np.all(np.isfinite(dist.mean))
        assert np.all(np.isfinite(dist.quantile(0.50)))
        assert dist.sample(10, seed=123).shape == (10, 2)

    @pytest.mark.skipif(
        not (BENCH_DIR / "departure_probabilistic_readiness_v1.json").exists(),
        reason="Readiness manifest not yet generated",
    )
    def test_readiness_manifest_status(self):
        with open(BENCH_DIR / "departure_probabilistic_readiness_v1.json", "r", encoding="utf-8") as f:
            manifest = json.load(f)

        assert manifest["overall_status"] in ("READY_FOR_DUAL_SIMULATION", "DEFERRED_POINT_ONLY")
        assert manifest["downstream_eligible"] is False
        assert len(manifest["readiness_gates"]) == 6
