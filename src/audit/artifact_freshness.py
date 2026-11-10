"""Artifact Freshness and Anti-Stale Guard for Aeolus (Task R20).

Prevents accidental reuse or masquerading of stale historical artifacts in R21 rebuild:
1. Validates presence of cryptographic code_hash and config_hash.
2. Validates that artifact timestamp is newer than source inputs.
3. Detects and rejects copied/cached artifacts from previous runs.
4. Detects run_id and metadata provenance mismatches.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Sequence


class FreshnessViolationError(Exception):
    """Base exception for artifact freshness and provenance violations."""
    pass


class StaleArtifactError(FreshnessViolationError):
    """Raised when an artifact is determined to be stale or reused without recomputation."""
    pass


class ProvenanceMismatchError(FreshnessViolationError):
    """Raised when code_hash, config_hash, or run_id does not match the active execution."""
    pass


def compute_file_sha256(path: Path) -> str:
    """Compute sha256 hex digest of a file."""
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def verify_artifact_freshness(
    artifact_path: Path,
    expected_run_id: str | None = None,
    expected_code_hash: str | None = None,
    expected_config_hash: str | None = None,
    source_artifacts: Sequence[Path] | None = None,
    min_timestamp_utc: datetime | None = None,
    known_stale_hashes: set[str] | None = None,
) -> dict[str, Any]:
    """Verify that an artifact is authentic, newly computed, and not a stale/copied artifact.

    Args:
        artifact_path: Path to the artifact to verify.
        expected_run_id: Run ID that must match metadata.
        expected_code_hash: Expected cryptographic code hash.
        expected_config_hash: Expected cryptographic config hash.
        source_artifacts: List of upstream source artifacts (must be older than artifact_path).
        min_timestamp_utc: Minimum valid creation timestamp.
        known_stale_hashes: Set of known historical sha256 hashes that cannot be claimed as fresh.

    Returns:
        dict with verification details and status="PASS".

    Raises:
        StaleArtifactError: If artifact is stale, copied, or older than sources.
        ProvenanceMismatchError: If hashes or run_id mismatch.
    """
    if not artifact_path.exists():
        raise FileNotFoundError(f"Artifact does not exist: {artifact_path}")

    current_hash = compute_file_sha256(artifact_path)

    # 1. Anti-copy check against known historical artifacts
    if known_stale_hashes and current_hash in known_stale_hashes:
        raise StaleArtifactError(
            f"Artifact {artifact_path.name} sha256 ({current_hash}) matches a known stale historical artifact! "
            "Artifact copying or masquerading is strictly prohibited."
        )

    # 2. Parse JSON metadata if artifact is json
    metadata: dict[str, Any] = {}
    if artifact_path.suffix == ".json":
        try:
            with open(artifact_path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                metadata = data
        except Exception as exc:
            raise FreshnessViolationError(f"Could not parse JSON artifact {artifact_path}: {exc}") from exc

    # 3. Provenance check: run_id
    if expected_run_id is not None:
        art_run_id = metadata.get("run_id") or metadata.get("experiment_id")
        if art_run_id is None:
            raise ProvenanceMismatchError(f"Artifact {artifact_path.name} is missing run_id/experiment_id metadata.")
        if art_run_id != expected_run_id:
            raise ProvenanceMismatchError(
                f"Artifact run_id mismatch in {artifact_path.name}: expected '{expected_run_id}', got '{art_run_id}'."
            )

    # 4. Provenance check: code_hash
    if expected_code_hash is not None:
        art_code_hash = metadata.get("code_hash")
        if art_code_hash is None:
            raise ProvenanceMismatchError(f"Artifact {artifact_path.name} is missing code_hash metadata.")
        if art_code_hash != expected_code_hash:
            raise ProvenanceMismatchError(
                f"Code hash mismatch in {artifact_path.name}: expected '{expected_code_hash}', got '{art_code_hash}'."
            )

    # 5. Provenance check: config_hash
    if expected_config_hash is not None:
        art_config_hash = metadata.get("config_hash")
        if art_config_hash is None:
            raise ProvenanceMismatchError(f"Artifact {artifact_path.name} is missing config_hash metadata.")
        if art_config_hash != expected_config_hash:
            raise ProvenanceMismatchError(
                f"Config hash mismatch in {artifact_path.name}: expected '{expected_config_hash}', got '{art_config_hash}'."
            )

    # 6. Timestamp verification
    art_mtime = datetime.fromtimestamp(artifact_path.stat().st_mtime, tz=timezone.utc)
    if min_timestamp_utc is not None:
        if art_mtime < min_timestamp_utc:
            raise StaleArtifactError(
                f"Artifact {artifact_path.name} mtime ({art_mtime.isoformat()}) is older than "
                f"run session start ({min_timestamp_utc.isoformat()}). Stale artifact detected."
            )

    # 7. Upstream dependency temporal order check
    if source_artifacts:
        for src in source_artifacts:
            if not src.exists():
                raise FileNotFoundError(f"Upstream source artifact does not exist: {src}")
            src_mtime = datetime.fromtimestamp(src.stat().st_mtime, tz=timezone.utc)
            if art_mtime < src_mtime:
                raise StaleArtifactError(
                    f"Temporal order inversion: artifact {artifact_path.name} (mtime {art_mtime.isoformat()}) "
                    f"is older than its upstream source {src.name} (mtime {src_mtime.isoformat()})!"
                )

    return {
        "status": "PASS",
        "artifact_path": str(artifact_path),
        "sha256": current_hash,
        "mtime_utc": art_mtime.isoformat(),
        "verified_checks": [
            "sha256_computed",
            "not_in_known_stale_hashes",
            "run_id_matched" if expected_run_id else "run_id_check_skipped",
            "code_hash_matched" if expected_code_hash else "code_hash_check_skipped",
            "config_hash_matched" if expected_config_hash else "config_hash_check_skipped",
            "timestamp_fresh" if min_timestamp_utc else "min_timestamp_check_skipped",
            "upstream_temporal_order_verified" if source_artifacts else "upstream_check_skipped",
        ],
    }
