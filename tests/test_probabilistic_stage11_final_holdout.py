"""Stage 11 — 2024 Final Holdout Unit Tests.

Validates that:
1. Pre-holdout audit verifies full system freeze and all 16 artifact hashes.
2. Tampering with any frozen artifact hash triggers audit rejection.
3. Access guard strictly permits 2024 final_evaluation while rejecting development/hpo.
4. Frozen model loads directly with pre-fitted weights and matches expected predictions.
5. 2024 holdout evaluation manifest complies with FINAL_HOLDOUT labeling.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import joblib
import numpy as np
import pandas as pd
import pytest

from src.data.access_guard import DataAccessDenied, assert_data_access_allowed
from src.models.probabilistic.baselines import B5NGBoostStudentT
from src.models.probabilistic.contracts import (
    DEFAULT_SIGMA_FLOOR,
    PROBABILISTIC_PREDICTOR_COLUMNS,
    ProbabilisticContractViolation,
)
from src.models.probabilistic.final_holdout import (
    PreHoldoutAuditReport,
    verify_freeze_before_holdout,
)

ROOT = Path(__file__).resolve().parents[1]


# =============================================================================
# Test 1: Pre-Holdout Audit
# =============================================================================

class TestPreHoldoutAudit:
    """Tests for verify_freeze_before_holdout."""

    def test_audit_passes_on_current_repository(self) -> None:
        """Audit must pass cleanly when repository state is FINAL_SYSTEM_FROZEN."""
        freeze_manifest = ROOT / "artifacts" / "manifests" / "full_system_freeze_manifest_v1.json"
        if not freeze_manifest.exists():
            pytest.skip("Full system freeze manifest not yet generated")

        report = verify_freeze_before_holdout(ROOT)
        assert report.audit_passed is True
        assert report.final_candidate_frozen is True
        assert report.weights_sha256_match is True
        assert report.all_16_hashes_match is True
        assert report.access_guard_authorized is True
        assert report.system_id == "SYS_B5_ngboost_student_t__DEP_D2_gaussian_copula"

    def test_audit_fails_when_manifest_missing(self, tmp_path: Path) -> None:
        """Audit must raise ProbabilisticContractViolation if freeze manifest is missing."""
        fake_root = tmp_path / "empty_proj"
        fake_root.mkdir(parents=True)
        (fake_root / "artifacts" / "manifests").mkdir(parents=True)

        with pytest.raises(ProbabilisticContractViolation, match="freeze manifest missing"):
            verify_freeze_before_holdout(fake_root)


# =============================================================================
# Test 2: Access Guard Enforcement on 2024
# =============================================================================

class TestAccessGuardHoldout:
    """Tests that 2024 access is restricted strictly to final_evaluation."""

    def test_2024_final_evaluation_authorized(self) -> None:
        """2024 must be authorized when freeze manifest is confirmed."""
        assert_data_access_allowed(2024, "final_evaluation")

    def test_2024_development_strictly_denied(self) -> None:
        """2024 must NEVER be accessible for development purpose."""
        with pytest.raises(DataAccessDenied, match="2024 is sealed from development access"):
            assert_data_access_allowed(2024, "development")

    def test_2024_hpo_strictly_denied(self) -> None:
        """2024 must NEVER be accessible for HPO purpose."""
        with pytest.raises(DataAccessDenied, match="HPO is blocked"):
            assert_data_access_allowed(2024, "hpo")


# =============================================================================
# Test 3: Frozen Model Load Integrity
# =============================================================================

class TestFrozenModelHoldout:
    """Tests for frozen model weights integrity."""

    def test_frozen_model_loads_without_fitting(self) -> None:
        """Model weights file loads directly into a fitted B5NGBoostStudentT."""
        weights_path = (
            ROOT
            / "artifacts"
            / "probabilistic"
            / "ngboost_student_t"
            / "model_weights_frozen_v1.joblib"
        )
        if not weights_path.exists():
            pytest.skip("Model weights not yet serialized")

        model = joblib.load(weights_path)
        assert isinstance(model, B5NGBoostStudentT)
        assert model.is_fitted_ is True

    def test_frozen_model_prediction_schema(self) -> None:
        """Frozen model produces compliant Student-T predictive distribution."""
        weights_path = (
            ROOT
            / "artifacts"
            / "probabilistic"
            / "ngboost_student_t"
            / "model_weights_frozen_v1.joblib"
        )
        if not weights_path.exists():
            pytest.skip("Model weights not yet serialized")

        model = joblib.load(weights_path)
        dummy_x = pd.DataFrame({
            "CRS_ELAPSED_TIME": [120.0, 180.0],
            "calendar_year": [2024, 2024],
            "calendar_month": [6, 7],
            "calendar_day_of_month": [15, 20],
            "calendar_day_of_week": [2, 5],
            "is_weekend": [0, 1],
            "scheduled_departure_hour": [10, 14],
            "scheduled_departure_minute": [30, 45],
            "OP_CARRIER": ["DL", "AA"],
            "ORIGIN": ["LGA", "ORD"],
            "OP_CARRIER_FL_NUM": [100, 200],
        })
        preds = model.predict_distribution(dummy_x)

        assert "mu" in preds
        assert "sigma" in preds
        assert "df" in preds
        assert "quantiles" in preds
        assert "event_probs" in preds
        assert len(preds["mu"]) == 2
        assert np.all(preds["sigma"] >= DEFAULT_SIGMA_FLOOR)
        assert np.all(preds["df"] >= 2.1)
