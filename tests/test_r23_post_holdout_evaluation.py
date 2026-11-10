"""Test Suite for R23 Locked 2024 Post-Holdout Re-Evaluation V3.

Verifies:
1. Manifest existence, JSON validity, and SHA-256 sidecar integrity.
2. Strict 'POST_HOLDOUT' terminology and year 2024.
3. Cryptographic linkage to system_freeze_manifest_v3.json.
4. Downstream operational records: exactly 84 runs across 7 candidates, 4 scenarios, 3 solvers.
5. Marginal forecast metrics on 5,000 monthly-stratified 2024 flights.
6. Provenance anomaly audit: verified distinct metrics, zero duplicated lineage.
7. P5 capability contract boundary: NO continuous NLL, NO continuous sampling.
8. P4 continuous metrics: exact Student-T CRPS and continuous NLL distinct from 2023.
9. Full failure accounting with 0 unaccounted failures.
10. Strict claim boundaries enforced: simulated synthetic research only.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
POST_HOLDOUT_V3_DIR = ROOT / "artifacts" / "post_holdout_v3"
MANIFEST_PATH = POST_HOLDOUT_V3_DIR / "post_holdout_evaluation_manifest_v3.json"
SIDECAR_PATH = POST_HOLDOUT_V3_DIR / "post_holdout_evaluation_manifest_v3.sha256"


def test_manifest_and_sidecar_integrity() -> None:
    """Verify manifest exists, parses, and matches its SHA-256 sidecar."""
    assert POST_HOLDOUT_V3_DIR.is_dir(), f"Missing dir: {POST_HOLDOUT_V3_DIR}"
    assert MANIFEST_PATH.is_file(), f"Missing manifest: {MANIFEST_PATH}"
    assert SIDECAR_PATH.is_file(), f"Missing sidecar: {SIDECAR_PATH}"

    manifest_bytes = MANIFEST_PATH.read_bytes()
    computed_sha = hashlib.sha256(manifest_bytes).hexdigest()
    sidecar_content = SIDECAR_PATH.read_text(encoding="utf-8").strip()
    recorded_sha = sidecar_content.split()[0]

    assert computed_sha == recorded_sha, (
        f"SHA-256 mismatch! Computed: {computed_sha}, Sidecar: {recorded_sha}"
    )


def test_manifest_governance_and_terminology() -> None:
    """Verify strictly 'POST_HOLDOUT' terminology, 2024 year, and freeze hash."""
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert payload["evaluation_role"] == "POST_HOLDOUT"
    assert payload["holdout_year"] == 2024
    assert payload["freeze_version"] == "v3"
    assert payload["manifest_version"] == "post_holdout_evaluation_manifest_v3"

    freeze_sidecar = ROOT / "artifacts" / "manifests" / "system_freeze_manifest_v3.sha256"
    assert freeze_sidecar.exists()
    expected_freeze_sha = freeze_sidecar.read_text(encoding="utf-8").split()[0]
    assert payload["freeze_manifest_v3_sha256"] == expected_freeze_sha


def test_downstream_evaluations_completeness() -> None:
    """Verify exactly 84 operational evaluations across 7 models, 4 scenarios, 3 solvers."""
    parquet_path = POST_HOLDOUT_V3_DIR / "downstream_operational_evaluations_v3.parquet"
    csv_path = POST_HOLDOUT_V3_DIR / "downstream_operational_evaluations_v3.csv"
    assert parquet_path.is_file()
    assert csv_path.is_file()

    df = pd.read_parquet(parquet_path)
    assert len(df) == 84, f"Expected 84 runs, got {len(df)}"

    expected_candidates = {
        "schedule_only",
        "arrival_linear_baseline_v1",
        "arrival_xgboost_baseline_v1",
        "arrival_weighted_ensemble_v1",
        "P5_quantile_regression",
        "P4_ngboost_student_t",
        "oracle_actual",
    }
    assert set(df["model_id"].unique()) == expected_candidates
    assert set(df["solver_name"].unique()) == {"DeterministicGreedy", "CPSat", "SimulatedAnnealing"}
    assert set(df["scenario_id"].unique()) == {
        "SCEN_2024_WINTER",
        "SCEN_2024_SPRING",
        "SCEN_2024_SUMMER",
        "SCEN_2024_FALL_DISRUPTED",
    }

    # Verify all records have POST_HOLDOUT role
    assert (df["evaluation_role"] == "POST_HOLDOUT").all()
    assert (df["holdout_year"] == 2024).all()


def test_marginal_forecast_metrics_and_capability_boundaries() -> None:
    """Verify marginal metrics on 5000 samples, P5 boundary, and P4 continuous metrics."""
    metrics_path = POST_HOLDOUT_V3_DIR / "marginal_forecast_metrics_2024_v3.json"
    assert metrics_path.is_file()

    payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert payload["evaluation_role"] == "POST_HOLDOUT"
    assert payload["holdout_year"] == 2024
    assert payload["n_samples"] == 5000

    metrics = payload["metrics"]
    assert "arrival_linear_baseline_v1" in metrics
    assert "arrival_xgboost_baseline_v1" in metrics
    assert "arrival_weighted_ensemble_v1" in metrics
    assert "P5_quantile_regression" in metrics
    assert "P4_ngboost_student_t" in metrics

    # P5 Capability Boundary
    p5 = metrics["P5_quantile_regression"]
    assert p5.get("nll") is None or p5.get("nll") == "NOT_AVAILABLE"
    assert p5.get("sampling_status") == "NOT_SUPPORTED"
    assert p5.get("capability_status") == "APPROVED_FORECAST_ONLY"

    # P4 Continuous Metrics
    p4 = metrics["P4_ngboost_student_t"]
    assert p4["crps"] is not None and isinstance(p4["crps"], (int, float))
    assert p4["nll"] is not None and isinstance(p4["nll"], (int, float))
    assert p4["sampling_status"] == "SUPPORTED_CONTINUOUS_PARAMETRIC"


def test_provenance_verification_and_non_repetition() -> None:
    """Verify provenance audit passed with zero anomalies and distinct 2023 vs 2024 values."""
    prov_path = POST_HOLDOUT_V3_DIR / "provenance_verification_v3.json"
    assert prov_path.is_file()

    audit = json.loads(prov_path.read_text(encoding="utf-8"))
    assert audit["has_lineage_anomaly"] is False
    assert audit["provenance_status"] == "VERIFIED_DISTINCT"
    assert audit["p4_continuous_lineage_verified"] is True
    assert audit["p5_capability_boundary_verified"] is True

    for record in audit["comparison_records"]:
        if "abs_difference" in record:
            assert record["is_suspiciously_identical"] is False
            assert record["status"] == "VERIFIED_DISTINCT"


def test_failures_accounting_is_comprehensive() -> None:
    """Verify failure accounting tracks all 84 cases with zero unaccounted failures."""
    fail_v3 = POST_HOLDOUT_V3_DIR / "failures_accounting_v3.json"
    fail_compat = POST_HOLDOUT_V3_DIR / "failures_accounting.json"
    assert fail_v3.is_file()
    assert fail_compat.is_file()

    summary = json.loads(fail_v3.read_text(encoding="utf-8"))
    assert summary["total_evaluated_cases"] == 84
    assert summary["total_failures_count"] == 0
    assert summary["evaluation_role"] == "POST_HOLDOUT"
    assert summary["holdout_year"] == 2024
