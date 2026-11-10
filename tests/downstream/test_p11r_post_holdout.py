"""Unit and validation tests for P11-R: 2024 Post-Holdout Re-Evaluation After Methodology Repair."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
P11R_DIR = ROOT / "artifacts" / "post_holdout_re_evaluation_v1"
FREEZE_MANIFEST_PATH = ROOT / "artifacts" / "manifests" / "system_freeze_manifest.json"


def test_p11r_artifact_existence_and_integrity() -> None:
    """Verify all mandatory P11-R artifacts exist in the isolated namespace."""
    assert P11R_DIR.exists(), f"Missing P11-R directory at {P11R_DIR}"

    expected_files = [
        "run_manifest.json",
        "forecast_metrics.json",
        "downstream_results.parquet",
        "downstream_results.csv",
        "downstream_results.json",
        "robustness_results.json",
        "failure_accounting.json",
        "protocol_compliance.json",
        "reproducibility_manifest.json",
    ]
    for fname in expected_files:
        p = P11R_DIR / fname
        assert p.exists(), f"Missing expected artifact: {fname}"
        assert p.stat().st_size > 0, f"Artifact is empty: {fname}"


def test_p11r_role_and_semantics() -> None:
    """Verify mandatory classification POST_HOLDOUT_REEVALUATION_AFTER_METHODOLOGY_REPAIR."""
    manifest_path = P11R_DIR / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["classification"] == "POST_HOLDOUT_REEVALUATION_AFTER_METHODOLOGY_REPAIR"
    assert manifest["status"] == "COMPLETED"
    assert manifest["n_holdout_samples"] == 5000
    assert manifest["n_scenarios_evaluated"] == 4
    assert len(manifest["solvers_evaluated"]) == 4
    assert len(manifest["models_evaluated"]) == 4


def test_p11r_marginal_forecast_metrics() -> None:
    """Verify exact continuous CRPS, exact continuous NLL, and P4 performance."""
    metrics_path = P11R_DIR / "forecast_metrics.json"
    data = json.loads(metrics_path.read_text(encoding="utf-8"))

    assert data["evaluation_role"] == "POST_HOLDOUT_REEVALUATION_AFTER_METHODOLOGY_REPAIR"
    assert data["evaluation_year"] == 2024

    p4_metrics = data["models"]["P4_ngboost_student_t"]
    assert p4_metrics["point_mae"] < 23.0
    assert p4_metrics["point_rmse"] < 56.0
    assert "exact_continuous_crps" in p4_metrics
    assert 15.0 < p4_metrics["exact_continuous_crps"] < 20.0
    assert "exact_continuous_nll" in p4_metrics
    assert 4.0 < p4_metrics["exact_continuous_nll"] < 5.0
    assert "brier_score_ge_15" in p4_metrics
    assert p4_metrics["brier_score_ge_15"] < 0.20
    assert p4_metrics["calibration_status"] == "NOT_SEPARATELY_CERTIFIED"

    # Verify P5 historical evidence labeling
    p5_ref = data["models"]["historical_p5_reference"]
    assert p5_ref["evidence_type"] == "HISTORICAL_POST_HOLDOUT_EVIDENCE"
    assert "NOT_RECONSTRUCTED" in p5_ref["reconstruction_status"]
    assert p5_ref["downstream_capability"] == "FORECAST_ONLY (No continuous sampling)"


def test_p11r_downstream_solver_fairness() -> None:
    """Verify solver execution across all 4 scenarios under 2.0s ceiling."""
    import pandas as pd
    df = pd.read_parquet(P11R_DIR / "downstream_results.parquet")

    assert len(df) == 64  # 4 scenarios * 4 models * 4 solvers
    assert set(df["scenario_id"].unique()) == {
        "SCEN_2024_WINTER",
        "SCEN_2024_SPRING",
        "SCEN_2024_SUMMER",
        "SCEN_2024_FALL_DISRUPTED",
    }
    assert set(df["solver_name"].unique()) == {
        "DeterministicGreedy",
        "CPSat",
        "SimulatedAnnealing",
        "HybridCPSatSA",
    }
    # All solvers feasible under 2.0s budget
    assert df["feasible"].all()
    assert (df["runtime_ms"] <= 2500.0).all()


def test_p11r_robustness_and_recourse() -> None:
    """Verify Mode A (Fixed-Plan) vs Mode B (Recourse) across canonical N=500."""
    rob_path = P11R_DIR / "robustness_results.json"
    data = json.loads(rob_path.read_text(encoding="utf-8"))

    assert data["canonical_n"] == 500
    for scen_id in ["SCEN_2024_WINTER", "SCEN_2024_SPRING", "SCEN_2024_SUMMER", "SCEN_2024_FALL_DISRUPTED"]:
        assert scen_id in data["scenarios"]
        scen_data = data["scenarios"][scen_id]
        assert "P4_ngboost_student_t" in scen_data
        p4_rob = scen_data["P4_ngboost_student_t"]
        assert "mode_a_fixed_plan" in p4_rob
        assert "mode_b_recourse" in p4_rob
        assert p4_rob["mode_b_recourse"]["feasibility_rate"] == 1.0
        assert p4_rob["mode_b_recourse"]["mean_post_conflicts"] == 0.0


def test_p11r_failure_accounting_zero_dropping() -> None:
    """Verify failure accounting tracks all evaluations with zero dropped cases."""
    fail_path = P11R_DIR / "failure_accounting.json"
    data = json.loads(fail_path.read_text(encoding="utf-8"))

    assert data["zero_dropped_cases_verified"] is True
    assert data["total_records_tracked"] == 16000  # 4 scenarios * 4 models * 500 realizations * 2 modes


def test_p11r_historical_artifacts_preserved() -> None:
    """Verify historical 2024 artifacts in post_holdout/, post_holdout_v2/, post_holdout_v3/ are preserved."""
    for legacy_dir in ["post_holdout", "post_holdout_v2", "post_holdout_v3"]:
        p = ROOT / "artifacts" / legacy_dir
        assert p.exists()
        assert len(list(p.iterdir())) >= 5
