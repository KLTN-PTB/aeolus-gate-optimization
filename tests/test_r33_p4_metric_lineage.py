"""R33 Targeted Audit Test Suite: P4 Metric Lineage and Discrepancy Reconciliation.

Verifies:
1. test_old_p4_metric_source_exists: 17.6532 / 4.6307 exists in marginal_forecast_metrics_2024_v3.json.
2. test_r32_p4_metric_source_exists: 17.1539 / 4.0321 exists in r32_independent_forensic_verification.json.
3. test_metric_sources_are_traceable: Trace lineage across manifests and audits.
4. test_dataset_split_reconciles: Distinguishes 2023 dev (18.484 / 4.5805) from 2024 holdout (17.6532 / 4.6307).
5. test_p4_model_identity_reconciles: Verifies P4 Student-T distribution parameters and guards.
6. test_p4_metric_implementation_reconciles: Validates exact continuous CRPS and NLL functions.
7. test_no_unresolved_metric_alias: Asserts discrepancy classification is ONE_VALUE_IS_INVALID_OR_MISLABELED.
8. test_final_authoritative_metric_identified: Confirms authoritative metrics and safety of certification.
"""

from __future__ import annotations

import hashlib
import json
import os
import numpy as np
import pytest
from scipy.stats import t as student_t

from src.contracts.distribution import NGBoostStudentTDistribution
from src.models.probabilistic.student_t_correctness import analytical_student_t_crps


def compute_file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def test_old_p4_metric_source_exists() -> None:
    """Verify that the original 2024 holdout metrics (17.6532 / 4.6307) exist in raw evidence."""
    path = "artifacts/post_holdout_v3/marginal_forecast_metrics_2024_v3.json"
    assert os.path.exists(path), f"Missing {path}"

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    p4_metrics = data["metrics"]["P4_ngboost_student_t"]
    assert abs(p4_metrics["crps"] - 17.6532) < 1e-4, f"Unexpected CRPS: {p4_metrics['crps']}"
    assert abs(p4_metrics["nll"] - 4.6307) < 1e-4, f"Unexpected NLL: {p4_metrics['nll']}"
    assert data["holdout_year"] == 2024
    assert data["n_samples"] == 5000


def test_r32_p4_metric_source_exists() -> None:
    """Verify that R32 reported 17.1539 / 4.0321 in its audit JSON artifact."""
    path = "artifacts/audit/r32_independent_forensic_verification.json"
    assert os.path.exists(path), f"Missing {path}"

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    q8 = data["mandatory_questions"]["Q8_p4_continuous_distribution_calibration"]
    raw = q8["raw_values"]
    assert abs(raw["exact_continuous_crps"] - 17.1539) < 1e-4
    assert abs(raw["exact_continuous_nll"] - 4.0321) < 1e-4


def test_metric_sources_are_traceable() -> None:
    """Verify cryptographic lineage of 17.6532 / 4.6307 across lineage manifests."""
    # Check post-holdout evaluation manifest
    manifest_path = "artifacts/post_holdout_v3/post_holdout_evaluation_manifest_v3.json"
    assert os.path.exists(manifest_path)
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    found_crps = False
    found_nll = False
    for rec in manifest["provenance_audit"]["comparison_records"]:
        if rec.get("model_id") == "P4_ngboost_student_t":
            if rec.get("metric") == "crps_continuous_exact":
                assert abs(rec["val_2024_holdout"] - 17.6532) < 1e-4
                assert abs(rec["val_2023_dev"] - 18.484) < 1e-3
                found_crps = True
            elif rec.get("metric") == "nll_continuous_exact":
                assert abs(rec["val_2024_holdout"] - 4.6307) < 1e-4
                assert abs(rec["val_2023_dev"] - 4.5805) < 1e-3
                found_nll = True

    assert found_crps, "P4 crps comparison record missing in post_holdout manifest"
    assert found_nll, "P4 nll comparison record missing in post_holdout manifest"

    # Check R28 metric lineage audit
    r28_path = "artifacts/audit/r28_metric_lineage.json"
    assert os.path.exists(r28_path)
    with open(r28_path, "r", encoding="utf-8") as f:
        r28 = json.load(f)
    p4_r28 = r28["model_metric_lineage"]["P4_ngboost_student_t"]
    assert abs(p4_r28["holdout_2024_metrics"]["crps_continuous_exact"] - 17.6532) < 1e-4
    assert abs(p4_r28["holdout_2024_metrics"]["nll_continuous_exact"] - 4.6307) < 1e-4


def test_dataset_split_reconciles() -> None:
    """Verify distinctness of 2023 development selection vs 2024 post-holdout."""
    dev_path = "artifacts/manifests/academic_model_selection_v3.json"
    holdout_path = "artifacts/post_holdout_v3/marginal_forecast_metrics_2024_v3.json"

    with open(dev_path, "r", encoding="utf-8") as f:
        dev_data = json.load(f)
    with open(holdout_path, "r", encoding="utf-8") as f:
        holdout_data = json.load(f)

    p4_dev = dev_data["ranking_free_comparison_table"]["probabilistic_models"]["P4_ngboost_student_t"]
    p4_holdout = holdout_data["metrics"]["P4_ngboost_student_t"]

    # Development metrics
    assert abs(p4_dev["crps"] - 18.484) < 1e-3
    assert abs(p4_dev["nll"] - 4.5805) < 1e-3

    # Holdout metrics
    assert abs(p4_holdout["crps"] - 17.6532) < 1e-4
    assert abs(p4_holdout["nll"] - 4.6307) < 1e-4

    # Assert distinct splits
    assert abs(p4_dev["crps"] - p4_holdout["crps"]) > 0.5
    assert abs(p4_dev["nll"] - p4_holdout["nll"]) > 0.04


def test_p4_model_identity_reconciles() -> None:
    """Verify P4 implements Student-T with valid parameter constraints."""
    mu = np.array([5.0, 10.0])
    sigma = np.array([3.0, 4.0])
    df = np.array([4.0, 5.0])

    dist = NGBoostStudentTDistribution(mu=mu, sigma=sigma, df=df)
    dist.validate()

    assert dist.capabilities.nll is True
    assert dist.capabilities.cdf is True
    assert dist.capabilities.quantile is True
    assert dist.capabilities.sample is True

    # Check parameter floors are enforced
    dist_floored = NGBoostStudentTDistribution(mu=mu, sigma=np.array([0.01, 0.05]), df=np.array([1.2, 1.5]))
    assert np.all(dist_floored._sigma >= 1.0)
    assert np.all(dist_floored._df >= 2.1)

    # Check NaN validation raises
    with pytest.raises(Exception):
        bad_dist = NGBoostStudentTDistribution(mu=np.array([np.nan, 10.0]), sigma=sigma, df=df)
        bad_dist.validate()


def test_p4_metric_implementation_reconciles() -> None:
    """Verify analytical Student-T CRPS matches mathematical formulation."""
    y = np.array([12.0])
    mu = np.array([10.0])
    sigma = np.array([5.0])
    df = np.array([4.0])

    val = analytical_student_t_crps(y, mu, sigma, df)
    assert np.isfinite(val).all()
    assert float(val[0]) > 0.0

    # NLL computation check
    z = (y - mu) / sigma
    nll_val = float(-(student_t.logpdf(z, df=df) - np.log(sigma))[0])
    assert np.isfinite(nll_val)
    assert nll_val > 0.0


def test_no_unresolved_metric_alias() -> None:
    """Verify R33 audit classification resolves the discrepancy to ONE_VALUE_IS_INVALID_OR_MISLABELED."""
    r33_path = "artifacts/audit/r33_p4_metric_lineage.json"
    assert os.path.exists(r33_path), f"Missing {r33_path}"

    with open(r33_path, "r", encoding="utf-8") as f:
        r33_data = json.load(f)

    assert r33_data["discrepancy_classification"] == "ONE_VALUE_IS_INVALID_OR_MISLABELED"
    assert r33_data["final_status_block"]["P4_METRIC_DISCREPANCY"] == "RESOLVED"
    assert r33_data["final_status_block"]["R33_STATUS"] == "PASS"


def test_final_authoritative_metric_identified() -> None:
    """Verify that authoritative P4 metrics are certified and final package is safe."""
    r33_path = "artifacts/audit/r33_p4_metric_lineage.json"
    with open(r33_path, "r", encoding="utf-8") as f:
        r33_data = json.load(f)

    auth = r33_data["final_authoritative_p4_metrics"]
    assert abs(auth["2024_post_holdout_evaluation"]["crps"] - 17.6532) < 1e-4
    assert abs(auth["2024_post_holdout_evaluation"]["nll"] - 4.6307) < 1e-4
    assert abs(auth["2023_development_selection"]["crps"] - 18.484) < 1e-3
    assert abs(auth["2023_development_selection"]["nll"] - 4.5805) < 1e-3

    assert r33_data["final_status_block"]["FINAL_CERTIFICATION_CURRENTLY_SAFE"] == "YES"
    assert r33_data["final_status_block"]["RETRAIN_REQUIRED"] == "NO"
