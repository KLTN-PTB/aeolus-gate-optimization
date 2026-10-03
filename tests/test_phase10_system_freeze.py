"""Unit tests for Phase 10 Full System Freeze and Manifest Validation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import pytest

from src.data.access_guard import (
    DataAccessDenied,
    assert_data_access_allowed,
    is_system_freeze_confirmed,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "artifacts" / "manifests" / "system_freeze_manifest.json"
CHECKSUM_PATH = ROOT / "artifacts" / "manifests" / "system_freeze_manifest.sha256"


def test_system_freeze_manifest_exists_and_checksum_matches() -> None:
    """Freeze manifest must exist, be valid JSON, and match its SHA256 checksum."""
    assert MANIFEST_PATH.exists(), f"Missing freeze manifest at {MANIFEST_PATH}"
    assert CHECKSUM_PATH.exists(), f"Missing checksum at {CHECKSUM_PATH}"

    raw_bytes = MANIFEST_PATH.read_bytes()
    computed_hash = hashlib.sha256(raw_bytes).hexdigest()

    checksum_content = CHECKSUM_PATH.read_text(encoding="utf-8").strip()
    recorded_hash = checksum_content.split()[0]
    assert computed_hash == recorded_hash, f"Checksum mismatch: {computed_hash} != {recorded_hash}"


def test_access_guard_recognizes_system_freeze() -> None:
    """access_guard.is_system_freeze_confirmed must return True for the freeze manifest."""
    assert is_system_freeze_confirmed(MANIFEST_PATH) is True


def test_system_freeze_manifest_structure_and_governance() -> None:
    """Validate all required fields in the freeze manifest."""
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    # Core status
    assert payload["freeze_status"] == "FROZEN"
    assert payload["final_holdout_year"] == 2024
    assert payload["stage"] == "PHASE_10_FULL_SYSTEM_FREEZE"
    assert bool(payload["frozen_at"])

    # Git and working tree
    assert bool(payload["git_commit"])
    assert payload["working_tree_state"] == "DIRTY"
    assert "No commit performed" in payload["working_tree_note"]

    # Runtime environment
    runtime = payload["runtime_environment"]
    assert "3.11" in runtime["python_version"]
    assert runtime["packages"]["numpy"] == "2.2.6"
    assert runtime["packages"]["scipy"] == "1.17.1"
    assert runtime["packages"]["pandas"] == "2.3.3"
    assert runtime["packages"]["scikit_learn"] == "1.9.0"
    assert runtime["packages"]["xgboost"] == "3.2.0"
    assert runtime["packages"]["ortools"] == "9.15.6755"

    # Holdout governance
    gov = payload["holdout_governance"]
    assert gov["holdout_year"] == 2024
    assert gov["holdout_status"] == "SEALED_AND_PROTECTED"
    assert gov["data_access_denied_enforced"] is True
    assert gov["zero_2024_training_verified"] is True
    assert gov["zero_2024_hpo_verified"] is True
    assert gov["zero_2024_selection_verified"] is True

    # Hashes dictionaries
    for hash_dict_key in ["config_hashes", "feature_hashes", "model_code_hashes", "benchmark_manifest_hashes"]:
        assert hash_dict_key in payload
        for name, h in payload[hash_dict_key].items():
            if isinstance(h, str) and len(h) == 64:
                # Valid hex string
                int(h, 16)

    # Seeds and solvers
    assert payload["seed_registry"]["predetermined_deployment_seed"] == 202601
    assert payload["gate_optimization_weights"]["conflict_weight"] == 1000.0
    assert payload["monte_carlo_protocol"]["preregistered_counts"] == [100, 250, 500, 1000, 2500]


def test_2024_development_and_hpo_remain_strictly_blocked() -> None:
    """2024 access for development and HPO must continue to raise DataAccessDenied."""
    with pytest.raises(DataAccessDenied, match="sealed from development access"):
        assert_data_access_allowed(2024, "development")

    with pytest.raises(DataAccessDenied, match="HPO is blocked"):
        assert_data_access_allowed(2024, "hpo")
