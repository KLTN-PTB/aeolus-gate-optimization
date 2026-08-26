"""Fail-closed ML availability policy for reconstructed Chain features.

This module validates policy metadata only.  It does not read reconstructed
data, derive features, join targets, or make a feature pass the normal Arrival
leakage contract.  A future Chain predictor must pass both gates independently.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from types import MappingProxyType
from typing import Final

import yaml


KEEP_SAFE: Final = "KEEP_SAFE"
REVIEW_REQUIRED: Final = "REVIEW_REQUIRED"
BLOCKED_UNTIL_PROVEN: Final = "BLOCKED_UNTIL_PROVEN"
DROP: Final = "DROP"
IDENTIFIER_ONLY: Final = "IDENTIFIER_ONLY"

ROOT: Final = Path(__file__).resolve().parents[2]
POLICY_PATH: Final = ROOT / "configs" / "reconstructed_chain_feature_policy.yaml"


class ChainFeatureAvailabilityViolation(ValueError):
    """Raised when a Chain feature has not passed the T-2h availability gate."""


def _load_policy() -> dict:
    payload = yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ChainFeatureAvailabilityViolation(
            f"Chain feature policy must be a mapping: {POLICY_PATH}"
        )
    return payload


_POLICY: Final = _load_policy()
VALID_AVAILABILITY_STATUSES: Final = frozenset(_POLICY["status_vocabulary"])

_feature_statuses: dict[str, str] = {}
for _group_name, _group in _POLICY["groups"].items():
    _status = _group["status"]
    if _status not in VALID_AVAILABILITY_STATUSES:
        raise ChainFeatureAvailabilityViolation(
            f"Unknown status {_status!r} in policy group {_group_name!r}"
        )
    for _feature in _group["features"]:
        if _feature in _feature_statuses:
            raise ChainFeatureAvailabilityViolation(
                f"Chain feature classified more than once: {_feature}"
            )
        _feature_statuses[_feature] = _status

CHAIN_FEATURE_STATUSES: Final = MappingProxyType(_feature_statuses)


def status_for_chain_feature(name: str) -> str:
    """Return the audited feature status; unknown names fail closed."""
    try:
        return CHAIN_FEATURE_STATUSES[name]
    except KeyError as error:
        raise ChainFeatureAvailabilityViolation(
            f"Chain feature is not classified: {name}"
        ) from error


def is_chain_feature_status_ml_admissible(status: str) -> bool:
    """Return whether a recognized availability status may proceed to leakage review."""
    if status not in VALID_AVAILABILITY_STATUSES:
        raise ChainFeatureAvailabilityViolation(
            f"Unknown chain feature availability status: {status}"
        )
    return status == KEEP_SAFE


def assert_chain_features_ml_admissible(names: Iterable[str]) -> None:
    """Reject every feature whose availability status is not ``KEEP_SAFE``.

    Passing this function is necessary but not sufficient: the normal Arrival
    leakage contract must also approve the feature before it can enter X.
    """
    rejected: dict[str, str] = {}
    for name in names:
        status = status_for_chain_feature(name)
        if not is_chain_feature_status_ml_admissible(status):
            rejected[name] = status
    if rejected:
        details = ", ".join(
            f"{name}={status}" for name, status in sorted(rejected.items())
        )
        raise ChainFeatureAvailabilityViolation(
            f"Chain features are not_ml_admissible: {details}"
        )
