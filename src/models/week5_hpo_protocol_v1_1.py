"""Execution-amended Week-5 HPO protocol helpers.

The v1.1 protocol uses fresh study identities only.  It never opens, resumes,
imports, or mutates the blocked parent-v1 Optuna studies.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Final

import yaml

from src.models.week5_hpo_protocol import (
    EXPECTED_STUDY_IDS,
    Week5HPOProtocol,
    Week5ProtocolViolation,
    assert_hpo_year_allowed as _assert_hpo_year_allowed,
    canonical_protocol_hash,
    load_week5_hpo_protocol,
)
from src.data.load_aeolus import resolve_project_root


PROTOCOL_VERSION: Final = "week5_hpo_protocol_v1_1"
PARENT_PROTOCOL_VERSION: Final = "week5_hpo_protocol_v1"
PARENT_PROTOCOL_HASH: Final = (
    "b00ddf190776a12032b1e6b5b284beff8b48204017fe4c397140ac7a4da6844a"
)
EXPECTED_PROTOCOL_HASH: Final = (
    "b987c0489c5d18b02500f34c786c01359f45e50b2b32bdea3de4332a161556e5"
)
DEFAULT_CONFIG_PATH: Final = Path("configs/week5_hpo_v1_1.yaml")
DEFAULT_MANIFEST_PATH: Final = Path(
    "artifacts/manifests/week5_hpo_protocol_v1_1.json"
)
STORAGE_DIRECTORY: Final = Path("artifacts/optuna_studies")

_STATISTICAL_KEYS: Final = (
    "task_contract",
    "scope_guards",
    "dependencies",
    "folds",
    "data_contract",
    "budget",
    "randomness",
    "objectives",
    "forbidden_tuning_dimensions",
)


def load_week5_hpo_protocol_v1_1(
    *,
    project_root: Path | None = None,
    config_path: Path | None = None,
    manifest_path: Path | None = None,
) -> Week5HPOProtocol:
    """Load v1.1 and prove that it is an execution-only amendment."""

    root = resolve_project_root(project_root)
    parent = load_week5_hpo_protocol(project_root=root)
    config = _read_yaml(config_path or root / DEFAULT_CONFIG_PATH)
    manifest = _read_json(manifest_path or root / DEFAULT_MANIFEST_PATH)
    observed_hash = canonical_protocol_hash(config)

    if observed_hash != EXPECTED_PROTOCOL_HASH:
        raise Week5ProtocolViolation("Week-5 v1.1 frozen protocol hash mismatch")
    if manifest.get("protocol_sha256") != observed_hash:
        raise Week5ProtocolViolation("Week-5 v1.1 manifest protocol hash mismatch")
    _validate_parent_and_statistical_parity(config, parent)
    _validate_execution_amendment(config)
    _validate_manifest(manifest, config=config, protocol_hash=observed_hash)
    return Week5HPOProtocol(
        protocol_version=PROTOCOL_VERSION,
        protocol_hash=observed_hash,
        _config=deepcopy(config),
        _manifest=deepcopy(manifest),
    )


def assert_hpo_year_allowed(year: int) -> None:
    """Use the unchanged fail-closed HPO temporal guard."""

    _assert_hpo_year_allowed(year)


def deterministic_v1_1_study_name(study_id: str) -> str:
    """Return the only permitted v1.1 study name."""

    if study_id not in EXPECTED_STUDY_IDS:
        raise Week5ProtocolViolation(f"unknown Week-5 v1.1 study {study_id!r}")
    return f"{PROTOCOL_VERSION}__{study_id}"


def deterministic_v1_1_storage_path(project_root: Path, study_id: str) -> Path:
    """Return the fresh v1.1 SQLite path without creating it."""

    return Path(project_root) / STORAGE_DIRECTORY / (
        f"{deterministic_v1_1_study_name(study_id)}.sqlite3"
    )


def validate_fresh_v1_1_storage(
    *,
    project_root: Path,
    study_id: str,
    study_name: str,
    storage_path: Path,
) -> None:
    """Fail closed unless the requested v1.1 study storage is new and exact."""

    parent_name = f"{PARENT_PROTOCOL_VERSION}__{study_id}"
    parent_path = Path(project_root) / STORAGE_DIRECTORY / f"{parent_name}.sqlite3"
    if study_name == parent_name or Path(storage_path) == parent_path:
        raise Week5ProtocolViolation("v1 parent study/storage may not be resumed")

    expected_name = deterministic_v1_1_study_name(study_id)
    expected_path = deterministic_v1_1_storage_path(project_root, study_id)
    if study_name != expected_name or Path(storage_path) != expected_path:
        raise Week5ProtocolViolation("v1.1 study identity does not match frozen protocol")
    if expected_path.exists():
        raise Week5ProtocolViolation("fresh v1.1 storage collision")


def _validate_parent_and_statistical_parity(
    config: dict[str, Any], parent: Week5HPOProtocol
) -> None:
    if config.get("protocol_version") != PROTOCOL_VERSION:
        raise Week5ProtocolViolation("unexpected Week-5 v1.1 protocol version")
    if config.get("status") != "FROZEN_PRE_PRODUCTION":
        raise Week5ProtocolViolation("Week-5 v1.1 protocol is not frozen")
    if config.get("parent_protocol") != {
        "version": PARENT_PROTOCOL_VERSION,
        "hash": PARENT_PROTOCOL_HASH,
    }:
        raise Week5ProtocolViolation("Week-5 v1.1 parent protocol mismatch")
    if parent.protocol_hash != PARENT_PROTOCOL_HASH:
        raise Week5ProtocolViolation("validated parent protocol hash mismatch")

    parent_config = parent.config
    for key in _STATISTICAL_KEYS:
        if config.get(key) != parent_config.get(key):
            raise Week5ProtocolViolation(
                f"Week-5 v1.1 statistical protocol changed at {key}"
            )
    amended_studies = deepcopy(config.get("studies"))
    parent_studies = deepcopy(parent_config.get("studies"))
    if not isinstance(amended_studies, dict) or not isinstance(parent_studies, dict):
        raise Week5ProtocolViolation("Week-5 v1.1 studies are malformed")
    if set(amended_studies) != EXPECTED_STUDY_IDS:
        raise Week5ProtocolViolation("Week-5 v1.1 must define exactly six studies")
    for study_id in EXPECTED_STUDY_IDS:
        if amended_studies[study_id].pop("study_name", None) != (
            deterministic_v1_1_study_name(study_id)
        ):
            raise Week5ProtocolViolation("Week-5 v1.1 study identity mismatch")
        parent_studies[study_id].pop("study_name", None)
    if amended_studies != parent_studies:
        raise Week5ProtocolViolation("Week-5 v1.1 study definitions changed")


def _validate_execution_amendment(config: dict[str, Any]) -> None:
    if config.get("amendment") != {
        "id": "week5_hpo_execution_amendment_v1",
        "type": "EXECUTION_RELIABILITY_AMENDMENT",
        "reason": "ENVIRONMENTAL_WALL_CLOCK_INTERRUPTION",
        "statistical_protocol_changed": False,
        "execution_protocol_changed": True,
    }:
        raise Week5ProtocolViolation("Week-5 v1.1 amendment metadata changed")
    if config.get("resume_policy") != {
        "resumable_statuses": [],
        "completed_status": "COMPLETED",
        "protocol_hash_required": True,
        "mismatch_action": "FAIL_CLOSED",
    }:
        raise Week5ProtocolViolation("Week-5 v1.1 must forbid study resume")
    if config.get("execution") != {
        "production_platform": "windows",
        "prevent_system_sleep": True,
        "heartbeat_interval_seconds": 30,
        "suspend_gap_threshold_seconds": 120,
        "suspend_detection": {
            "enabled": True,
            "state_on_detection": "ENVIRONMENTAL_EXECUTION_INVALID",
            "primary_active_time_source": "QueryUnbiasedInterruptTime",
        },
        "fresh_study_required": True,
        "parent_protocol_resume_forbidden": True,
        "parent_trials_carry_forward_forbidden": True,
        "non_windows_production_behavior": "FAIL_CLOSED",
    }:
        raise Week5ProtocolViolation("Week-5 v1.1 execution policy changed")


def _validate_manifest(
    manifest: dict[str, Any], *, config: dict[str, Any], protocol_hash: str
) -> None:
    required = {
        "manifest_version": "week5_hpo_protocol_manifest_v1_1",
        "protocol_version": PROTOCOL_VERSION,
        "protocol_sha256": protocol_hash,
        "parent_protocol_version": PARENT_PROTOCOL_VERSION,
        "parent_protocol_hash": PARENT_PROTOCOL_HASH,
        "statistical_protocol_changed": False,
        "execution_protocol_changed": True,
        "production_hpo_started": False,
        "row_level_2023_accessed": False,
        "row_level_2024_accessed": False,
        "studies": config["studies"],
        "execution": config["execution"],
    }
    if any(manifest.get(key) != value for key, value in required.items()):
        raise Week5ProtocolViolation("Week-5 v1.1 manifest projection mismatch")


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise Week5ProtocolViolation("Week-5 v1.1 config is unreadable") from error
    if not isinstance(payload, dict):
        raise Week5ProtocolViolation("Week-5 v1.1 config must be a mapping")
    return payload


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise Week5ProtocolViolation("Week-5 v1.1 manifest is unreadable") from error
    if not isinstance(payload, dict):
        raise Week5ProtocolViolation("Week-5 v1.1 manifest must be a mapping")
    return payload
