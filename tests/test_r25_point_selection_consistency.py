"""Test Suite for R25 Point Model Selection Numerical & Claim Consistency Audit.

Verifies:
1. test_2023_tie_rule: 2023 MAE difference <= 0.10 min indifference band (TIED).
2. test_2024_not_tie_rule: 2024 MAE difference > 0.10 min indifference band (NOT TIED).
3. test_selection_slice_is_2023: selection slice is strictly 2023 development.
4. test_holdout_is_2024_post_holdout: 2024 evaluation is strictly POST_HOLDOUT.
5. test_no_2024_selection_signal: 2024 had zero influence on model selection or tuning.
6. test_no_single_overall_champion_claim: joint overall champion is blocked; no single champion claimed.
7. test_audit_artifacts_integrity: audit manifests exist, parse, and verify hashes.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SEL_MANIFEST_PATH = ROOT / "artifacts" / "manifests" / "academic_model_selection_v3.json"
SEL_CONFIG_PATH = ROOT / "configs" / "model_selection_protocol_v2.yaml"
POST_HOLDOUT_METRICS_PATH = ROOT / "artifacts" / "post_holdout_v3" / "marginal_forecast_metrics_2024_v3.json"
POST_HOLDOUT_MANIFEST_PATH = ROOT / "artifacts" / "post_holdout_v3" / "post_holdout_evaluation_manifest_v3.json"
CERT_MANIFEST_PATH = ROOT / "artifacts" / "manifests" / "final_evidence_certification_v3.json"
CLAIM_AUDIT_PATH = ROOT / "artifacts" / "audit" / "final_claim_boundary_audit_v3.json"
R25_CONSISTENCY_PATH = ROOT / "artifacts" / "audit" / "r25_point_selection_consistency.json"
R25_RECONCILIATION_PATH = ROOT / "artifacts" / "audit" / "r25_claim_numeric_reconciliation.json"


def compute_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_2023_tie_rule() -> None:
    """Verify that on 2023 selection slice, Ridge and Ensemble tie under 0.10 min band."""
    assert SEL_MANIFEST_PATH.is_file()
    assert SEL_CONFIG_PATH.is_file()

    with open(SEL_CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    indifference_band = float(cfg["roles_definition"]["role_a_point_champion"]["regression"]["effect_size_delta"])
    assert indifference_band == 0.10

    data = json.loads(SEL_MANIFEST_PATH.read_text(encoding="utf-8"))
    point_models = data["ranking_free_comparison_table"]["point_models"]
    mae_ridge = float(point_models["arrival_linear_baseline_v1"]["mae"])
    mae_ensemble = float(point_models["arrival_weighted_ensemble_v1"]["mae"])
    diff = abs(mae_ridge - mae_ensemble)

    # Actual numerical verification
    assert diff <= indifference_band, f"Expected 2023 diff <= {indifference_band}, got {diff}"
    assert diff < 0.001, f"Expected difference < 0.001 min, got {diff}"

    # Verify selection outcome recorded in manifest
    outcome = data["selection_outcomes"]["point_regression"]
    assert outcome["tie_status"] == "TIED_WITHIN_EFFECT_SIZE_THRESHOLD"
    assert "arrival_linear_baseline_v1" in outcome["selected_candidates"]
    assert "arrival_weighted_ensemble_v1" in outcome["selected_candidates"]


def test_2024_not_tie_rule() -> None:
    """Verify that on 2024 post-holdout, Ridge and Ensemble do NOT tie under 0.10 min band."""
    assert POST_HOLDOUT_METRICS_PATH.is_file()

    with open(SEL_CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    indifference_band = float(cfg["roles_definition"]["role_a_point_champion"]["regression"]["effect_size_delta"])

    data = json.loads(POST_HOLDOUT_METRICS_PATH.read_text(encoding="utf-8"))
    metrics = data["metrics"]
    mae_ridge = float(metrics["arrival_linear_baseline_v1"]["point_mae"])
    mae_ensemble = float(metrics["arrival_weighted_ensemble_v1"]["point_mae"])
    diff = abs(mae_ridge - mae_ensemble)

    # Actual numerical verification
    assert diff > indifference_band, f"Expected 2024 diff > {indifference_band}, got {diff}"
    assert 0.40 <= diff <= 0.41, f"Expected diff approx 0.405 min, got {diff}"


def test_selection_slice_is_2023() -> None:
    """Verify that model selection slice is strictly 2023 and training is 2016-2022."""
    data = json.loads(SEL_MANIFEST_PATH.read_text(encoding="utf-8"))
    gov = data["temporal_governance"]

    assert gov["evaluation_year"] == 2023
    assert gov["evaluation_role"] == "development_model_selection"
    assert gov["training_window"] == [2016, 2017, 2018, 2019, 2020, 2021, 2022]
    assert gov["holdout_year"] == 2024
    assert gov["holdout_status"] == "SEALED_AND_PROTECTED"


def test_holdout_is_2024_post_holdout() -> None:
    """Verify that 2024 evaluation is strictly POST_HOLDOUT."""
    data = json.loads(POST_HOLDOUT_MANIFEST_PATH.read_text(encoding="utf-8"))
    assert data["evaluation_role"] == "POST_HOLDOUT"
    assert data["holdout_year"] == 2024
    assert data["protocol_name"].startswith("AEOLUS_V4_POST_HOLDOUT_REEVALUATION_PROTOCOL")


def test_no_2024_selection_signal() -> None:
    """Verify zero 2024 influence on training, tuning, selection, or thresholding."""
    consistency = json.loads(R25_CONSISTENCY_PATH.read_text(encoding="utf-8"))
    gov = consistency["temporal_governance_verification"]

    assert gov["zero_2024_retraining"] is True
    assert gov["zero_2024_selection_influence"] is True
    assert gov["zero_2024_hpo"] is True
    assert gov["zero_2024_threshold_tuning"] is True
    assert gov["zero_2024_ensemble_weight_tuning"] is True
    assert gov["zero_2024_calibration"] is True
    assert gov["zero_2024_feature_engineering"] is True


def test_no_single_overall_champion_claim() -> None:
    """Verify that single overall point champion is blocked across all manifests."""
    cert = json.loads(CERT_MANIFEST_PATH.read_text(encoding="utf-8"))
    roles = cert["decoupled_model_champions"]

    # Blocked joint champion
    assert roles["joint_overall_champion"] == "BLOCKED_FAIL_CLOSED"

    # Separate status per evaluation dataset
    pt = roles["point_prediction_role"]
    assert pt["status_2023_dev"] == "TIED_WITHIN_0.10_MIN_INDIFFERENCE_BAND"
    assert pt["status_2024_holdout"] == "NOT_TIED_DIFFERENCE_EXCEEDS_0.10_MIN"
    assert pt["overall_status"] == "NO_SINGLE_OVERALL_CHAMPION_ASSERTED"

    # Verify claim boundary audit prohibits universal champion claim
    claim_audit = json.loads(CLAIM_AUDIT_PATH.read_text(encoding="utf-8"))
    claim_map = {c["claim_id"]: c for c in claim_audit["claims"]}

    c2 = claim_map["CLAIM_02_POINT_CHAMPION_SELECTION"]
    assert "Both models tied overall across all years" in c2["prohibited_wording"]
    assert "Single overall point champion" in c2["prohibited_wording"]

    c5 = claim_map["CLAIM_05_SINGLE_OVERALL_CHAMPION"]
    assert c5["certification_status"] == "BLOCKED"
    assert "Universal champion" in c5["prohibited_wording"]


def test_audit_artifacts_integrity() -> None:
    """Verify R25 audit artifacts exist and hash-reconcile against underlying files."""
    assert R25_CONSISTENCY_PATH.is_file()
    assert R25_RECONCILIATION_PATH.is_file()

    consistency = json.loads(R25_CONSISTENCY_PATH.read_text(encoding="utf-8"))
    assert consistency["audit_verdict"] == "PASS"

    sources = consistency["source_artifacts"]
    for key, item in sources.items():
        p = ROOT / item["path"]
        assert p.is_file()
        assert compute_sha256(p) == item["sha256"], f"SHA mismatch for {item['path']}"
