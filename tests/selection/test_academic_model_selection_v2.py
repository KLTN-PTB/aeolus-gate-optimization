"""Unit and integration tests for Model Selection Protocol V2.

Verifies:
1. Three distinct roles separation (Point Champion, Forecast Champion, Downstream Candidate)
2. Audit of pre-registered rules in configs/academic_model_selection.yaml (identifies gaps)
3. Ridge vs Ensemble tie handling and post-hoc parsimony provenance
4. P5 vs P4 role separation and capability-driven eligibility
5. Fail-closed joint system selection status (JOINT_SELECTION_STATUS = BLOCKED)
6. Zero unscientific claims enforcement ('scientifically proven best', 'globally optimal model')
7. Manifest V2 schema completeness and SHA-256 sidecar integrity
8. Zero 2024 holdout access
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import pytest

from src.data.access_guard import DataAccessDenied, assert_data_access_allowed
from src.evaluation.model_selection import (
    DEFAULT_OUTPUT_MANIFEST_V2,
    DEFAULT_SELECTION_POLICY_PATH,
    ModelRole,
    PreRegistrationStatus,
    SelectionPolicy,
    SelectionRule,
    assert_no_unscientific_claims,
    audit_pre_registered_policy,
    evaluate_joint_system_selection,
    evaluate_role_a_point_selection,
    evaluate_role_b_probabilistic_forecast_selection,
    evaluate_role_c_downstream_candidate_selection,
)


def test_three_distinct_roles_separation() -> None:
    """The three selection roles must be distinct and evaluated under their own criteria."""
    point_rule = SelectionRule("mae", "minimize", ("rmse",), 0.10)
    prob_rule = SelectionRule("crps", "minimize", ("nll",), 0.10)

    point_metrics = {
        "arrival_linear_baseline_v1": {"mae": 23.29, "rmse": 63.53},
        "arrival_weighted_ensemble_v1": {"mae": 23.29, "rmse": 63.53},
    }
    prob_metrics = {
        "P4_ngboost_student_t": {"crps": 17.79, "nll": 4.596, "cov_80": 0.767, "cov_90": 0.848},
        "P5_quantile_regression": {"crps": 16.85, "nll": "NOT_AVAILABLE", "cov_80": 0.759, "cov_90": 0.873},
    }

    role_a = evaluate_role_a_point_selection(point_metrics, point_rule)
    role_b = evaluate_role_b_probabilistic_forecast_selection(prob_metrics, prob_rule)
    role_c = evaluate_role_c_downstream_candidate_selection(prob_metrics)

    assert role_a["role"] == ModelRole.POINT_CHAMPION.value
    assert role_b["role"] == ModelRole.PROBABILISTIC_FORECAST_CHAMPION.value
    assert role_c["role"] == ModelRole.DOWNSTREAM_CANDIDATE.value

    # Models chosen are not forced to be identical
    assert role_a["selected_champion"] == "arrival_linear_baseline_v1"
    assert role_b["selected_champion"] == "P5_quantile_regression"
    assert role_c["selected_candidate"] == "P4_ngboost_student_t"


def test_pre_registered_rules_audit() -> None:
    """Historical config must be audited accurately without retroactively claiming unwritten rules."""
    audit = audit_pre_registered_policy(DEFAULT_SELECTION_POLICY_PATH)

    # Pre-registered elements
    assert audit["primary_metric"].is_pre_registered is True
    assert audit["primary_metric"].status == PreRegistrationStatus.PRE_REGISTERED.value
    assert audit["tolerance"].is_pre_registered is True
    assert audit["tie_break"].is_pre_registered is True

    # Missing / unwritten elements must be UNKNOWN / POST_HOC
    assert audit["complexity_rule"].is_pre_registered is False
    assert audit["complexity_rule"].status == PreRegistrationStatus.UNKNOWN.value

    assert audit["calibration_rule"].is_pre_registered is False
    assert audit["calibration_rule"].status == PreRegistrationStatus.UNKNOWN.value

    assert audit["distribution_capability_requirement"].is_pre_registered is False
    assert audit["distribution_capability_requirement"].status == PreRegistrationStatus.UNKNOWN.value

    assert audit["downstream_eligibility_rule"].is_pre_registered is False
    assert audit["downstream_eligibility_rule"].status == PreRegistrationStatus.UNKNOWN.value


def test_ridge_vs_ensemble_tie_and_parsimony_provenance() -> None:
    """When Ridge and Ensemble are within tolerance, outcome is a tie; Ridge selection is POST-HOC."""
    point_rule = SelectionRule("mae", "minimize", ("rmse",), 0.10)
    point_metrics = {
        "arrival_linear_baseline_v1": {"mae": 23.2936},
        "arrival_weighted_ensemble_v1": {"mae": 23.2936},
        "arrival_xgboost_baseline_v1": {"mae": 24.9467},
    }

    res = evaluate_role_a_point_selection(point_metrics, point_rule)

    # Pre-registered outcome is a tie
    assert res["pre_registered_outcome"]["tie_status"] == "TIED_WITHIN_EFFECT_SIZE_THRESHOLD"
    assert set(res["pre_registered_outcome"]["tied_candidates"]) == {
        "arrival_linear_baseline_v1",
        "arrival_weighted_ensemble_v1",
    }

    # Selected champion is Linear, but provenance MUST be marked as POST_HOC_PARSIMONY
    assert res["selected_champion"] == "arrival_linear_baseline_v1"
    assert res["decision_provenance"] == "POST_HOC_PARSIMONY"
    assert "post-hoc parsimony" in res["provenance_note"].lower()


def test_p5_vs_p4_role_separation() -> None:
    """P5 is forecast champion on CRPS; P4 is downstream candidate on continuous sampling."""
    prob_rule = SelectionRule("crps", "minimize", ("nll",), 0.10)
    prob_metrics = {
        "P1_empirical": {"crps": 17.00, "nll": "NOT_AVAILABLE"},
        "P4_ngboost_student_t": {"crps": 17.79, "nll": 4.596},
        "P5_quantile_regression": {"crps": 16.85, "nll": "NOT_AVAILABLE"},
    }

    res_b = evaluate_role_b_probabilistic_forecast_selection(prob_metrics, prob_rule)
    res_c = evaluate_role_c_downstream_candidate_selection(prob_metrics)

    # Role B: P5 is decisive leader in CRPS
    assert res_b["selected_champion"] == "P5_quantile_regression"
    assert res_b["pre_registered_outcome"]["tie_status"] == "DECISIVE_LEADER"

    # Role C: P5 is ineligible; P4 is selected
    assert res_c["eligibility_audit"]["P5_quantile_regression"]["eligible"] is False
    assert res_c["eligibility_audit"]["P4_ngboost_student_t"]["eligible"] is True
    assert res_c["selected_candidate"] == "P4_ngboost_student_t"


def test_joint_system_selection_blocked() -> None:
    """Joint system selection must fail closed (BLOCKED) when no pre-registered joint rule existed."""
    audit = audit_pre_registered_policy(DEFAULT_SELECTION_POLICY_PATH)
    joint_res = evaluate_joint_system_selection(audit)

    assert joint_res["pre_registered_joint_rule_exists"] is False
    assert joint_res["joint_selection_status"] == "BLOCKED"
    assert joint_res["decision_provenance"] == "POST_HOC_ARCHITECTURAL_DECISION"


def test_no_unscientific_claims_enforced() -> None:
    """The system must reject forbidden unscientific phrases."""
    # Test rejection of forbidden phrases
    with pytest.raises(ValueError, match="Forbidden unscientific phrase detected"):
        assert_no_unscientific_claims({"claim": "This is the scientifically proven best model."})

    with pytest.raises(ValueError, match="Forbidden unscientific phrase detected"):
        assert_no_unscientific_claims({"claim": "Our search identified the globally optimal model."})

    # Verify that the generated manifest V2 does NOT contain any forbidden phrases
    assert DEFAULT_OUTPUT_MANIFEST_V2.exists()
    with open(DEFAULT_OUTPUT_MANIFEST_V2, "r", encoding="utf-8") as f:
        manifest_data = json.load(f)
    assert_no_unscientific_claims(manifest_data)


def test_manifest_v2_structure_and_hashes() -> None:
    """Verify that academic_model_selection_v2.json is complete, valid, and matches SHA-256 sidecar."""
    manifest_path = Path("artifacts/manifests/academic_model_selection_v2.json")
    sha_path = Path("artifacts/manifests/academic_model_selection_v2.sha256")

    assert manifest_path.exists()
    assert sha_path.exists()

    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Check required top-level keys
    required_keys = {
        "manifest_version",
        "task",
        "temporal_governance",
        "candidate_set",
        "metrics_used",
        "pre_registration_audit",
        "selection_table",
        "three_distinct_roles",
        "joint_system_governance",
        "legacy_comparators",
        "paired_evidence_reference",
        "decision_trace",
        "audit_provenance",
    }
    assert required_keys.issubset(set(data.keys()))

    # Check three distinct roles
    roles = data["three_distinct_roles"]
    assert "role_a_point_champion" in roles
    assert "role_b_probabilistic_forecast_champion" in roles
    assert "role_c_downstream_candidate" in roles

    # Check SHA-256 sidecar
    hasher = hashlib.sha256()
    hasher.update(manifest_path.read_bytes())
    computed_sha = hasher.hexdigest()

    sidecar_content = sha_path.read_text(encoding="utf-8").strip()
    assert computed_sha in sidecar_content


def test_zero_2024_access_during_selection() -> None:
    """Attempting to access 2024 data during selection must strictly raise DataAccessDenied."""
    with pytest.raises(DataAccessDenied):
        assert_data_access_allowed(2024, "development")

    with pytest.raises(DataAccessDenied):
        assert_data_access_allowed(2024, "hpo")
