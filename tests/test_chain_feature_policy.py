from __future__ import annotations

import importlib
import importlib.util

import pytest


EXPECTED_FEATURE_STATUSES = {
    "chain_position": "REVIEW_REQUIRED",
    "legs_before_target": "REVIEW_REQUIRED",
    "is_first_chain_leg": "REVIEW_REQUIRED",
    "is_single_leg_chain": "BLOCKED_UNTIL_PROVEN",
    "minutes_from_chain_first_departure": "REVIEW_REQUIRED",
    "minutes_since_previous_scheduled_departure": "REVIEW_REQUIRED",
    "has_previous_chain_leg": "REVIEW_REQUIRED",
    "previous_leg_destination_matches_target_origin": "REVIEW_REQUIRED",
    "chain_length": "BLOCKED_UNTIL_PROVEN",
    "legs_after_target": "BLOCKED_UNTIL_PROVEN",
    "is_last_chain_leg": "BLOCKED_UNTIL_PROVEN",
    "chain_length_gt_6": "BLOCKED_UNTIL_PROVEN",
    "minutes_to_chain_last_departure": "BLOCKED_UNTIL_PROVEN",
    "minutes_to_next_scheduled_departure": "BLOCKED_UNTIL_PROVEN",
    "has_next_chain_leg": "BLOCKED_UNTIL_PROVEN",
    "next_leg_origin_matches_target_destination": "BLOCKED_UNTIL_PROVEN",
    "chain_schedule_span_minutes": "BLOCKED_UNTIL_PROVEN",
    "chain_position_fraction": "BLOCKED_UNTIL_PROVEN",
    "flight_key": "IDENTIFIER_ONLY",
    "chain_id": "IDENTIFIER_ONLY",
    "source_year": "IDENTIFIER_ONLY",
    "source_row_number": "IDENTIFIER_ONLY",
}


def load_policy_module():
    module_name = "src.features.chain_feature_policy"
    spec = importlib.util.find_spec(module_name)
    assert spec is not None, "chain feature availability policy module is missing"
    return importlib.import_module(module_name)


def test_policy_classifies_every_week3b_candidate_and_identifier() -> None:
    policy = load_policy_module()

    observed = {
        feature: policy.status_for_chain_feature(feature)
        for feature in EXPECTED_FEATURE_STATUSES
    }

    assert observed == EXPECTED_FEATURE_STATUSES
    assert set(policy.CHAIN_FEATURE_STATUSES) == set(EXPECTED_FEATURE_STATUSES)


@pytest.mark.parametrize(
    "feature",
    [
        "chain_position",
        "minutes_since_previous_scheduled_departure",
        "chain_length",
        "flight_key",
    ],
)
def test_non_keep_safe_status_cannot_enter_predictor_list(feature: str) -> None:
    policy = load_policy_module()

    with pytest.raises(
        policy.ChainFeatureAvailabilityViolation,
        match="not_ml_admissible",
    ):
        policy.assert_chain_features_ml_admissible([feature])


def test_unknown_chain_feature_fails_closed() -> None:
    policy = load_policy_module()

    with pytest.raises(
        policy.ChainFeatureAvailabilityViolation,
        match="not classified",
    ):
        policy.status_for_chain_feature("unknown_chain_feature")
    with pytest.raises(
        policy.ChainFeatureAvailabilityViolation,
        match="not classified",
    ):
        policy.assert_chain_features_ml_admissible(["unknown_chain_feature"])


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("KEEP_SAFE", True),
        ("REVIEW_REQUIRED", False),
        ("BLOCKED_UNTIL_PROVEN", False),
        ("DROP", False),
        ("IDENTIFIER_ONLY", False),
    ],
)
def test_only_keep_safe_status_is_potentially_ml_admissible(
    status: str, expected: bool
) -> None:
    policy = load_policy_module()

    assert policy.is_chain_feature_status_ml_admissible(status) is expected


def test_unknown_availability_status_fails_closed() -> None:
    policy = load_policy_module()

    with pytest.raises(
        policy.ChainFeatureAvailabilityViolation,
        match="Unknown chain feature availability status",
    ):
        policy.is_chain_feature_status_ml_admissible("UNREGISTERED_STATUS")
