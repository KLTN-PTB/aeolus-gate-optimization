"""Test Suite for R20 Artifact Freshness and Anti-Stale Guard.

Protocol: Task R20 Freeze & Freshness Audit
Invariants:
1. Stale artifact rejected
2. Copied artifact rejected as fresh
3. Code/config mismatch detected
4. Missing provenance rejected
5. Run ID mismatch detected
"""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from src.audit.artifact_freshness import (
    FreshnessViolationError,
    ProvenanceMismatchError,
    StaleArtifactError,
    compute_file_sha256,
    verify_artifact_freshness,
)

REPO_ROOT = Path("D:/Study/Code/Python/Aelous")


@pytest.fixture
def temp_artifact_workspace(tmp_path: Path):
    """Create a temporary workspace with simulated artifacts."""
    art_dir = tmp_path / "artifacts"
    art_dir.mkdir()
    return art_dir


def test_stale_artifact_rejected(temp_artifact_workspace: Path):
    """Verify that an artifact older than run session cutoff or older than source input is rejected."""
    art_file = temp_artifact_workspace / "point_results.json"
    content = {
        "run_id": "RUN_20261002_001",
        "code_hash": "c99b3e84",
        "config_hash": "cfg_v2",
        "metrics": {"mae": 21.0}
    }
    with open(art_file, "w", encoding="utf-8") as f:
        json.dump(content, f)

    # Set min_timestamp in the future
    future_time = datetime.now(timezone.utc) + timedelta(hours=1)

    with pytest.raises(StaleArtifactError, match="older than run session start"):
        verify_artifact_freshness(
            art_file,
            expected_run_id="RUN_20261002_001",
            min_timestamp_utc=future_time
        )


def test_copied_artifact_rejected_as_fresh(temp_artifact_workspace: Path):
    """Verify that an artifact with a hash matching a known historical stale artifact is rejected."""
    art_file = temp_artifact_workspace / "copied_benchmark.json"
    content = {"status": "SUCCESS", "data": [1, 2, 3]}
    with open(art_file, "w", encoding="utf-8") as f:
        json.dump(content, f)

    art_hash = compute_file_sha256(art_file)
    known_stale = {art_hash, "some_other_stale_hash_12345"}

    with pytest.raises(StaleArtifactError, match="matches a known stale historical artifact"):
        verify_artifact_freshness(
            art_file,
            known_stale_hashes=known_stale
        )


def test_code_config_mismatch_detected(temp_artifact_workspace: Path):
    """Verify that code_hash or config_hash mismatches raise ProvenanceMismatchError."""
    art_file = temp_artifact_workspace / "model_selection.json"
    content = {
        "run_id": "RUN_SELECTION_01",
        "code_hash": "code_v1_old",
        "config_hash": "cfg_v1_old"
    }
    with open(art_file, "w", encoding="utf-8") as f:
        json.dump(content, f)

    # 1. Code hash mismatch
    with pytest.raises(ProvenanceMismatchError, match="Code hash mismatch"):
        verify_artifact_freshness(
            art_file,
            expected_code_hash="code_v2_current",
            expected_config_hash="cfg_v1_old"
        )

    # 2. Config hash mismatch
    with pytest.raises(ProvenanceMismatchError, match="Config hash mismatch"):
        verify_artifact_freshness(
            art_file,
            expected_code_hash="code_v1_old",
            expected_config_hash="cfg_v2_current"
        )


def test_missing_provenance_rejected(temp_artifact_workspace: Path):
    """Verify that artifacts missing mandatory cryptographic provenance fields are rejected."""
    art_file = temp_artifact_workspace / "unvetted_result.json"
    content = {"mae": 22.5}  # Missing run_id, code_hash, config_hash
    with open(art_file, "w", encoding="utf-8") as f:
        json.dump(content, f)

    # 1. Missing run_id
    with pytest.raises(ProvenanceMismatchError, match="missing run_id"):
        verify_artifact_freshness(art_file, expected_run_id="RUN_EXPECTED")

    # 2. Missing code_hash
    with pytest.raises(ProvenanceMismatchError, match="missing code_hash"):
        verify_artifact_freshness(art_file, expected_code_hash="code_hash_123")

    # 3. Missing config_hash
    with pytest.raises(ProvenanceMismatchError, match="missing config_hash"):
        verify_artifact_freshness(art_file, expected_config_hash="cfg_hash_123")


def test_run_id_mismatch_detected(temp_artifact_workspace: Path):
    """Verify that run_id mismatch between caller and artifact raises ProvenanceMismatchError."""
    art_file = temp_artifact_workspace / "downstream_run.json"
    content = {
        "run_id": "RUN_HISTORICAL_R10",
        "code_hash": "code_valid",
        "config_hash": "cfg_valid"
    }
    with open(art_file, "w", encoding="utf-8") as f:
        json.dump(content, f)

    with pytest.raises(ProvenanceMismatchError, match="Artifact run_id mismatch"):
        verify_artifact_freshness(
            art_file,
            expected_run_id="RUN_R21_FRESH"
        )


def test_valid_fresh_artifact_passes(temp_artifact_workspace: Path):
    """Verify that an authentic, newly computed artifact passes all freshness guards."""
    src_file = temp_artifact_workspace / "source_data.parquet"
    with open(src_file, "wb") as f:
        f.write(b"source_data_bytes")

    art_file = temp_artifact_workspace / "fresh_result.json"
    content = {
        "run_id": "RUN_R21_FRESH",
        "code_hash": "code_sha256_active",
        "config_hash": "cfg_sha256_active",
        "metrics": {"mae": 21.02}
    }
    with open(art_file, "w", encoding="utf-8") as f:
        json.dump(content, f)

    res = verify_artifact_freshness(
        art_file,
        expected_run_id="RUN_R21_FRESH",
        expected_code_hash="code_sha256_active",
        expected_config_hash="cfg_sha256_active",
        source_artifacts=[src_file],
        known_stale_hashes={"stale_hash_1", "stale_hash_2"}
    )

    assert res["status"] == "PASS"
    assert "sha256_computed" in res["verified_checks"]
