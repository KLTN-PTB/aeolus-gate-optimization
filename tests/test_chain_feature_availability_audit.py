from __future__ import annotations

import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
AUDIT_VERSION = "reconstructed_chain_feature_availability_audit_v1"
AUDIT_MANIFEST_PATH = (
    ROOT / "artifacts" / "manifests" / f"{AUDIT_VERSION}.json"
)
POLICY_PATH = ROOT / "configs" / "reconstructed_chain_feature_policy.yaml"

REVIEW_REQUIRED_FEATURES = {
    "chain_position",
    "legs_before_target",
    "is_first_chain_leg",
    "minutes_from_chain_first_departure",
    "minutes_since_previous_scheduled_departure",
    "has_previous_chain_leg",
    "previous_leg_destination_matches_target_origin",
}
BLOCKED_FEATURES = {
    "is_single_leg_chain",
    "chain_length",
    "legs_after_target",
    "is_last_chain_leg",
    "chain_length_gt_6",
    "minutes_to_chain_last_departure",
    "minutes_to_next_scheduled_departure",
    "has_next_chain_leg",
    "next_leg_origin_matches_target_destination",
    "chain_schedule_span_minutes",
    "chain_position_fraction",
}
IDENTIFIER_ONLY_FIELDS = {
    "flight_key",
    "chain_id",
    "source_year",
    "source_row_number",
}
CANDIDATE_FEATURES = REVIEW_REQUIRED_FEATURES | BLOCKED_FEATURES


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_policy() -> dict:
    return yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))


def _policy_statuses(policy: dict) -> dict[str, str]:
    return {
        feature: group["status"]
        for group in policy["groups"].values()
        for feature in group["features"]
    }


def test_audit_manifest_records_completed_fail_closed_outcome() -> None:
    audit = _load_json(AUDIT_MANIFEST_PATH)

    assert audit["version"] == AUDIT_VERSION
    assert audit["protocol"] == "Research Protocol V4.0"
    assert audit["source_artifact"] == "schedule_chain_v1"
    assert audit["source_artifact_version"] == "schedule_chain_v1"
    assert audit["cutoff"] == "target CRS_DEP_TIME - 2 hours"
    assert audit["audit_status"] == "COMPLETED"
    assert audit["external_evidence_used"] is False
    assert audit["schedule_publication_snapshot_evidence_found"] is False
    assert audit["candidate_feature_count"] == 18
    assert audit["approved_keep_safe_features"] == []
    assert set(audit["review_required_features"]) == REVIEW_REQUIRED_FEATURES
    assert set(audit["blocked_features"]) == BLOCKED_FEATURES
    assert set(audit["identifier_only_fields"]) == IDENTIFIER_ONLY_FIELDS
    assert audit["ml_enablement"] is False
    assert audit["arr_b_enabled"] is False
    assert audit["diagnostic_materialization_allowed"] is True
    assert audit["ml_materialization_allowed"] is False
    assert audit["ml_branch_status"] == "BLOCKED_PENDING_NEW_EVIDENCE"
    assert audit["2024_accessed"] is False
    assert audit["2023_performance_used"] is False
    assert audit["model_result_used"] is False
    assert audit["feature_artifact_generated"] is False
    assert audit["reconstruction_modified"] is False


def test_every_candidate_has_explicit_evidence_result_and_valid_status() -> None:
    audit = _load_json(AUDIT_MANIFEST_PATH)
    feature_results = audit["feature_results"]

    assert set(feature_results) == CANDIDATE_FEATURES
    for feature, result in feature_results.items():
        assert result["final_status"] in {
            "KEEP_SAFE",
            "REVIEW_REQUIRED",
            "BLOCKED_UNTIL_PROVEN",
            "DROP",
            "IDENTIFIER_ONLY",
        }
        assert result["required_information"]
        assert result["member_direction"]
        assert result["required_fields"]
        assert result["only_scheduled_fields"] is True
        assert isinstance(result["requires_member_exists"], bool)
        assert isinstance(result["requires_member_does_not_exist"], bool)
        assert isinstance(result["requires_final_chain_length"], bool)
        assert isinstance(result["requires_future_schedule_membership"], bool)
        assert result["point_in_time_evidence_available"] is False
        assert result["c4_schedule_availability"] == "UNPROVEN"
        assert result["reason"]
        assert result["point_in_time_snapshot_reconstructable"] == (
            "CONDITIONAL_ON_UNAVAILABLE_VERSIONED_SNAPSHOT"
        )

    assert all(
        feature_results[name]["final_status"] == "REVIEW_REQUIRED"
        for name in REVIEW_REQUIRED_FEATURES
    )
    assert all(
        feature_results[name]["final_status"] == "BLOCKED_UNTIL_PROVEN"
        for name in BLOCKED_FEATURES
    )
    assert all(
        feature_results[name]["final_status"] != "KEEP_SAFE"
        for name in CANDIDATE_FEATURES
    )


def test_audit_manifest_matches_policy_exactly() -> None:
    audit = _load_json(AUDIT_MANIFEST_PATH)
    policy = _load_policy()
    policy_statuses = _policy_statuses(policy)
    manifest_statuses = {
        name: result["final_status"]
        for name, result in audit["feature_results"].items()
    }
    manifest_statuses.update(
        {name: "IDENTIFIER_ONLY" for name in audit["identifier_only_fields"]}
    )

    assert policy["current_status"] == "AUDIT_COMPLETE"
    assert policy["audit_result"] == "NO_KEEP_SAFE_FEATURES"
    assert policy["audit_result_version"] == audit["version"]
    assert policy["audit_result_path"] == (
        "artifacts/manifests/reconstructed_chain_feature_availability_audit_v1.json"
    )
    assert policy["keep_safe_feature_count"] == 0
    assert policy["ml_enabled"] is False
    assert policy["arr_b_enabled"] is False
    assert policy["diagnostic_materialization_allowed"] is True
    assert policy["diagnostic_materialization_executed"] is False
    assert policy["ml_materialization_allowed"] is False
    assert policy["ml_branch_status"] == "BLOCKED_PENDING_NEW_EVIDENCE"
    assert policy["closure_status"] == "COMPLETED_WITH_BLOCKED_ML_BRANCH"
    assert policy_statuses == manifest_statuses


def test_week3b_closure_records_skipped_optional_execution() -> None:
    policy = _load_policy()

    assert policy["substage_disposition"] == {
        "3B.0": "COMPLETED_PASS",
        "3B.1": "SKIPPED_NOT_REQUIRED_FOR_ML",
        "3B.2": "COMPLETED_THROUGH_E006",
        "3B.3": "SKIPPED_OPTIONAL_DIAGNOSTIC",
        "3B.4": "COMPLETED_PASS",
    }
    assert policy["materialization_decision"] == {
        "status": "SKIPPED_OPTIONAL_DIAGNOSTIC",
        "reason": "NO_KEEP_SAFE_FEATURES",
    }
    assert not (ROOT / "src" / "features" / "reconstructed_chain_features.py").exists()
    assert not (
        ROOT / "data" / "processed" / "reconstructed_chain_features_v1"
    ).exists()


def test_c1_c10_results_are_complete_and_fail_closed() -> None:
    gates = _load_json(AUDIT_MANIFEST_PATH)["c1_c10_gate_results"]

    assert set(gates) == {f"C{index}" for index in range(1, 11)}
    assert gates["C1"]["status"] == "PASS"
    assert gates["C2"]["status"] == "PASS"
    assert gates["C3"]["status"] == "PASS"
    assert gates["C4"]["status"] == "UNPROVEN"
    assert gates["C5"]["status"] == "PASS"
    assert gates["C6"]["status"] == "PASS"
    assert gates["C7"]["status"] == "PASS_FAIL_CLOSED"
    assert gates["C8"]["status"] == "PENDING_IMPLEMENTATION"
    assert gates["C9"]["status"] == "PASS"
    assert gates["C10"]["status"] == "PASS_POLICY_ONLY"


def test_registry_preserves_e005_and_adds_e006_without_changing_d026() -> None:
    registry = (ROOT / "docs" / "decisions" / "decision_registry.md").read_text(
        encoding="utf-8"
    )

    assert "| D026 | Reconstructed Chain Feature Availability Boundary |" in registry
    assert "| E005 | Reconstructed Schedule Flight Chain |" in registry
    assert (
        "| E006 | Reconstructed Chain Feature Point-in-Time Availability Audit |"
        in registry
    )
    assert "No candidate reconstructed Chain feature is currently approved" in registry


def test_audit_report_is_distinct_from_plan_and_records_zero_keep_safe() -> None:
    report_path = (
        ROOT
        / "docs"
        / "dataset_audit"
        / "reconstructed_chain_feature_availability_audit_v1.md"
    )
    report = report_path.read_text(encoding="utf-8")

    assert "# Reconstructed Chain Feature Availability Audit V1" in report
    assert "KEEP_SAFE_FEATURES = []" in report
    assert "EXTERNAL_EVIDENCE_USED = NO" in report
    assert "is_single_leg_chain" in report
    assert "BLOCKED_UNTIL_PROVEN" in report
    assert "ML_ADMISSIBLE=false" in report
