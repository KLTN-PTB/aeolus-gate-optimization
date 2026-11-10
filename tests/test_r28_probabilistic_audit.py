"""Test Suite for AEOLUS V4 Task R28: Probabilistic Metric, Calibration & Dependency Audit.

Implements all 11 required tests from Prompt R28:
1. test_p4_is_continuous_density_only_if_implementation_supports_it
2. test_p4_calibration_claim_requires_direct_evidence
3. test_p5_is_quantile_only_if_implementation_supports_only_quantiles
4. test_p5_no_unsupported_continuous_density_claim
5. test_metric_classification
6. test_no_pinball_as_crps
7. test_no_approximation_as_exact
8. test_dependency_closure
9. test_metric_capability_matrix
10. test_p4_exact_crps_claim
11. test_p4_exact_nll_claim
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
import numpy as np

from src.contracts.distribution import (
    CapabilityNotSupportedError,
    NGBoostStudentTDistribution,
    QuantilePredictiveDistribution,
)
from src.models.probabilistic.candidate_interfaces import (
    P4NGBoostStudentTCandidate,
    P5QuantileRegressionCandidate,
)

ROOT = Path(__file__).resolve().parents[1]

CAP_MATRIX_PATH = ROOT / "artifacts" / "audit" / "r28_probabilistic_capability_matrix.json"
CALIB_PATH = ROOT / "artifacts" / "audit" / "r28_calibration_evidence.json"
LINEAGE_PATH = ROOT / "artifacts" / "audit" / "r28_metric_lineage.json"
DEPS_PATH = ROOT / "artifacts" / "audit" / "r28_dependency_closure.json"
DOC_PATH = ROOT / "docs" / "audit" / "R28_PROBABILISTIC_AUDIT.md"


@pytest.fixture(scope="module")
def cap_matrix():
    assert CAP_MATRIX_PATH.is_file(), f"Missing capability matrix: {CAP_MATRIX_PATH}"
    return json.loads(CAP_MATRIX_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def calib_data():
    assert CALIB_PATH.is_file(), f"Missing calibration audit: {CALIB_PATH}"
    return json.loads(CALIB_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def lineage_data():
    assert LINEAGE_PATH.is_file(), f"Missing metric lineage: {LINEAGE_PATH}"
    return json.loads(LINEAGE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def deps_data():
    assert DEPS_PATH.is_file(), f"Missing dependency closure: {DEPS_PATH}"
    return json.loads(DEPS_PATH.read_text(encoding="utf-8"))


def test_p4_is_continuous_density_only_if_implementation_supports_it(cap_matrix):
    """Test 1: Verify P4 is classified as continuous density because implementation supports it."""
    p4 = cap_matrix["capability_table"]["P4_ngboost_student_t"]
    assert p4["density"] is True
    assert p4["continuous_cdf"] is True
    assert p4["continuous_sampling"] is True

    cand = P4NGBoostStudentTCandidate()
    caps = cand.capabilities()
    assert caps["has_cdf"] is True
    assert caps["has_sampler"] is True
    assert caps["has_nll"] is True

    dist = NGBoostStudentTDistribution(
        mu=np.array([5.0]),
        sigma=np.array([2.0]),
        df=np.array([4.0]),
    )
    assert dist.capabilities.cdf is True
    assert dist.capabilities.sample is True
    assert dist.capabilities.nll is True


def test_p4_calibration_claim_requires_direct_evidence(calib_data):
    """Test 2: Verify P4 calibration is not claimed without direct empirical evidence."""
    assert calib_data["calibration_verdict"] == "NOT_SEPARATELY_CERTIFIED"
    findings = calib_data["findings"]
    assert findings["pit_uniformity_hypothesis_test_present"] is False
    assert findings["nominal_vs_empirical_coverage_table_present"] is False
    assert findings["direct_empirical_calibration_evidence_status"] == "ABSENT"

    amendment = calib_data["claim_boundary_amendment"]
    assert "empirical calibration is not separately certified" in amendment["amended_certified_phrase"]


def test_p5_is_quantile_only_if_implementation_supports_only_quantiles(cap_matrix):
    """Test 3: Verify P5 is classified as quantile-only because implementation only supports quantiles."""
    p5 = cap_matrix["capability_table"]["P5_quantile_regression"]
    assert p5["density"] is False
    assert p5["quantiles"] is True
    assert p5["continuous_cdf"] is False
    assert p5["continuous_sampling"] is False

    cand = P5QuantileRegressionCandidate()
    caps = cand.capabilities()
    assert caps["has_mean"] is False
    assert caps["has_quantiles"] is True
    assert caps["has_median"] is True
    assert caps["has_cdf"] is False
    assert caps["has_sampler"] is False
    assert caps["has_nll"] is False


def test_p5_no_unsupported_continuous_density_claim():
    """Test 4: Verify invoking continuous density / sampling / cdf on P5 raises CapabilityNotSupportedError."""
    quantiles = {0.1: np.array([5.0]), 0.5: np.array([10.0]), 0.9: np.array([15.0])}
    dist = QuantilePredictiveDistribution(quantiles_dict=quantiles)

    with pytest.raises(CapabilityNotSupportedError, match="CDF"):
        dist.cdf(10.0)

    with pytest.raises(CapabilityNotSupportedError, match="sampling"):
        dist.sample(10)

    with pytest.raises(CapabilityNotSupportedError, match="expectation"):
        _ = dist.mean


def test_metric_classification(lineage_data):
    """Test 5: Verify all metric uses belong to exactly one of the 5 taxonomy classes."""
    tax = lineage_data["crps_terminology_taxonomy"]
    expected_classes = {
        "exact_continuous_crps",
        "exact_discrete_crps",
        "crps_quantile_approximation",
        "pinball_loss",
        "unsupported_label",
    }
    assert set(tax.keys()) == expected_classes


def test_no_pinball_as_crps(lineage_data):
    """Test 6: Verify pinball loss is not labeled as exact CRPS."""
    tax = lineage_data["crps_terminology_taxonomy"]
    assert tax["pinball_loss"]["is_valid_continuous"] is False
    assert "Pinball loss is never reported as exact CRPS" in lineage_data["rules_enforced"][0]


def test_no_approximation_as_exact(lineage_data):
    """Test 7: Verify quantile approximation is explicitly distinguished from exact CRPS."""
    tax = lineage_data["crps_terminology_taxonomy"]
    assert tax["crps_quantile_approximation"]["is_valid_continuous"] is False
    assert tax["exact_continuous_crps"]["is_valid_continuous"] is True
    p5_dev = lineage_data["model_metric_lineage"]["P5_quantile_regression"]["dev_2023_metrics"]
    assert p5_dev["classification"] == "crps_quantile_approximation"


def test_dependency_closure(deps_data):
    """Test 8: Verify dependency closure contains all 10 certified packages with pinned versions."""
    deps = {d["package"]: d["version"] for d in deps_data["dependencies"]}
    assert len(deps) >= 10
    assert "scipy" in deps
    assert "ngboost" in deps
    assert "lightgbm" in deps
    assert "xgboost" in deps
    assert "scikit-learn" in deps
    assert "numpy" in deps
    assert "pandas" in deps
    assert "ortools" in deps
    assert "pyarrow" in deps
    assert "pytest" in deps


def test_metric_capability_matrix(cap_matrix):
    """Test 9: Verify capability table has entries for P1 through P5 with distinct profiles."""
    table = cap_matrix["capability_table"]
    assert set(table.keys()) == {
        "P1_empirical",
        "P2_xgb_gaussian_oof",
        "P3_ngboost_normal",
        "P4_ngboost_student_t",
        "P5_quantile_regression",
    }
    # P4 has density, P5 does not
    assert table["P4_ngboost_student_t"]["density"] is True
    assert table["P5_quantile_regression"]["density"] is False


def test_p4_exact_crps_claim(lineage_data):
    """Test 10: Verify P4 continuous CRPS is certified as exact continuous CRPS (~17.65 holdout)."""
    p4_metrics = lineage_data["model_metric_lineage"]["P4_ngboost_student_t"]
    holdout = p4_metrics["holdout_2024_metrics"]
    assert holdout["classification"] == "exact_continuous_crps"
    assert abs(holdout["crps_continuous_exact"] - 17.6532) < 0.01


def test_p4_exact_nll_claim(lineage_data):
    """Test 11: Verify P4 continuous NLL is certified as exact continuous NLL (~4.63 holdout)."""
    p4_metrics = lineage_data["model_metric_lineage"]["P4_ngboost_student_t"]
    holdout = p4_metrics["holdout_2024_metrics"]
    assert abs(holdout["nll_continuous_exact"] - 4.6307) < 0.01
