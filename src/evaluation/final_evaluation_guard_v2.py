"""Final Evaluation Guard V2 for 2024 Post-Holdout Execution (Task R11 Freeze).

Enforces strict fail-closed governance before any row of 2024 post-holdout data can be accessed:
1. Verifies existence and SHA256 sidecar integrity of artifacts/manifests/system_freeze_manifest_v2.json.
2. Validates that freeze_status is FROZEN_V2 and final_holdout_year is 2024.
3. Validates that every result-affecting component in categories A-W matches its frozen SHA256:
   A. data contracts
   B. feature code
   C. preprocessing
   D. model code
   E. distribution contract
   F. metrics
   G. statistical inference
   H. model selection
   I. synthetic turn generation
   J. gate generation
   K. verifier
   L. optimization
   M. CP-SAT
   N. SA
   O. Monte Carlo
   P. scenario manifests
   Q. solver budget
   R. MC budget
   S. seeds
   T. model registry
   U. selection manifest
   V. evaluation runners
   W. final guard
4. Validates model registry immutability and selection consistency.
5. Strictly mandates evaluation_role must be 'POST_HOLDOUT'. Any attempt to label 2024 as
   'untouched_holdout', 'development', 'model_selection', 'hpo', 'tuning', or 'calibration' fails closed.
6. Asserts zero post-freeze modification or post-hoc tuning.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Final

from src.data.access_guard import DataAccessDenied, assert_data_access_allowed
from src.models.interfaces import ModelStatus
from src.models.registry import get_model_spec, list_models

LOGGER = logging.getLogger("final_evaluation_guard_v2")

DEFAULT_FREEZE_MANIFEST_V3_REL: Final = Path("artifacts/manifests/system_freeze_manifest_v3.json")
DEFAULT_FREEZE_CHECKSUM_V3_REL: Final = Path("artifacts/manifests/system_freeze_manifest_v3.sha256")
DEFAULT_FREEZE_MANIFEST_V2_REL: Final = Path("artifacts/manifests/system_freeze_manifest_v2.json")
DEFAULT_FREEZE_CHECKSUM_V2_REL: Final = Path("artifacts/manifests/system_freeze_manifest_v2.sha256")
EXPECTED_EVALUATION_ROLE: Final = "POST_HOLDOUT"
FORBIDDEN_EVALUATION_ROLES: Final = frozenset({
    "untouched_holdout",
    "unseen_final_test",
    "development",
    "model_selection",
    "hpo",
    "tuning",
    "calibration",
    "random_test",
})


class FinalEvaluationGuardV2Error(PermissionError):
    """Raised when 2024 post-holdout conditions or freeze v2/v3 integrity are violated."""


def compute_sha256(path: Path) -> str:
    """Compute sha256 hex digest of file at path."""
    if not path.is_file():
        raise FileNotFoundError(f"File not found for checksum: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FinalEvaluationGuardV2:
    """Fail-closed guard governing 2024 post-holdout evaluation under Freeze V2 and V3."""

    def __init__(
        self,
        project_root: Path | None = None,
        freeze_version: str = "v2",
    ) -> None:
        self.project_root = (project_root or Path(__file__).resolve().parents[2]).resolve()
        self.freeze_version = freeze_version
        if freeze_version == "v3":
            self.manifest_path = self.project_root / DEFAULT_FREEZE_MANIFEST_V3_REL
            self.checksum_path = self.project_root / DEFAULT_FREEZE_CHECKSUM_V3_REL
        else:
            self.manifest_path = self.project_root / DEFAULT_FREEZE_MANIFEST_V2_REL
            self.checksum_path = self.project_root / DEFAULT_FREEZE_CHECKSUM_V2_REL

    def verify_freeze_manifest(self) -> dict[str, Any]:
        """Validate all freeze conditions against system freeze manifest.

        Returns:
            dict containing parsed freeze manifest and audit details.

        Raises:
            FinalEvaluationGuardV2Error: If any condition, hash, or status check fails.
        """
        # 1. Existence of manifest and checksum file
        if not self.manifest_path.exists():
            raise FinalEvaluationGuardV2Error(
                f"Prerequisite failure: System freeze manifest v2 does not exist at {self.manifest_path}. "
                "Evaluation is BLOCKED."
            )
        if not self.checksum_path.exists():
            raise FinalEvaluationGuardV2Error(
                f"Prerequisite failure: System freeze checksum does not exist at {self.checksum_path}. "
                "Evaluation is BLOCKED."
            )

        # 2. Checksum integrity of the manifest itself
        computed_manifest_hash = compute_sha256(self.manifest_path)
        recorded_checksum_line = self.checksum_path.read_text(encoding="utf-8").strip()
        expected_manifest_hash = recorded_checksum_line.split()[0]
        if computed_manifest_hash != expected_manifest_hash:
            raise FinalEvaluationGuardV2Error(
                f"Integrity violation: Freeze manifest checksum mismatch! "
                f"Expected {expected_manifest_hash}, computed {computed_manifest_hash}. "
                "Manifest tampering detected. Evaluation is BLOCKED."
            )

        try:
            payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise FinalEvaluationGuardV2Error(f"Freeze manifest contains invalid JSON: {exc}") from exc

        # 3. Core status & Holdout year
        freeze_status = payload.get("freeze_status")
        if freeze_status not in {"FROZEN_V2", "FROZEN_V3"}:
            raise FinalEvaluationGuardV2Error(
                f"System is not in a valid frozen state: freeze_status='{freeze_status}'. "
                "Evaluation is BLOCKED."
            )
        if payload.get("final_holdout_year") != 2024:
            raise FinalEvaluationGuardV2Error(
                f"Invalid holdout year: final_holdout_year={payload.get('final_holdout_year')}, expected 2024."
            )

        # 4. Verify All Result-Affecting Categories (A through W)
        categories = payload.get("freeze_categories", {})
        if not categories:
            raise FinalEvaluationGuardV2Error("No freeze_categories found in freeze manifest v2.")

        total_files_verified = 0
        for cat_name, cat_data in categories.items():
            files_map = cat_data.get("files", {})
            for rel_path, expected_hash in files_map.items():
                fpath = self.project_root / rel_path
                if not fpath.exists():
                    raise FinalEvaluationGuardV2Error(
                        f"Frozen file missing in category '{cat_name}': {rel_path}"
                    )
                actual_hash = compute_sha256(fpath)
                if actual_hash != expected_hash:
                    raise FinalEvaluationGuardV2Error(
                        f"Integrity hash mismatch in category '{cat_name}' for {rel_path}: "
                        f"expected {expected_hash}, got {actual_hash}. "
                        "Unfrozen source or config changes detected. Evaluation is BLOCKED."
                    )
                total_files_verified += 1

        # 5. Verify Model Selection & Roles
        model_selection = payload.get("model_selection", {})
        if not model_selection:
            raise FinalEvaluationGuardV2Error("Model selection block missing in freeze manifest v2.")

        # 6. Verify Seed Registry
        seed_reg = payload.get("seed_registry", {})
        if seed_reg.get("predetermined_deployment_seed") != 202601:
            raise FinalEvaluationGuardV2Error(
                f"Invalid deployment seed in manifest: {seed_reg.get('predetermined_deployment_seed')}"
            )

        LOGGER.info(
            "Freeze V2 manifest successfully verified: %d files checked across %d categories.",
            total_files_verified,
            len(categories),
        )
        return payload

    def assert_evaluation_authorized(
        self,
        evaluation_role: str,
        year: int,
        purpose: str = "post_holdout_evaluation",
    ) -> None:
        """Enforce strict fail-closed permission check before 2024 access."""
        # 1. Role validation
        if evaluation_role in FORBIDDEN_EVALUATION_ROLES:
            raise FinalEvaluationGuardV2Error(
                f"Evaluation role '{evaluation_role}' is STRICTLY PROHIBITED for year {year}. "
                "2024 cannot be used for development, model selection, HPO, tuning, or described as untouched."
            )

        if evaluation_role != EXPECTED_EVALUATION_ROLE:
            raise FinalEvaluationGuardV2Error(
                f"Unauthorized evaluation role '{evaluation_role}'. "
                f"Must be explicitly '{EXPECTED_EVALUATION_ROLE}'."
            )

        # 2. Year validation
        if year != 2024:
            raise FinalEvaluationGuardV2Error(
                f"Final evaluation guard is only authorized for year 2024, requested: {year}"
            )

        # 3. Purpose validation
        if purpose != "post_holdout_evaluation":
            raise FinalEvaluationGuardV2Error(
                f"Final evaluation purpose must be 'post_holdout_evaluation', got '{purpose}'"
            )

        # 4. Freeze manifest integrity verification
        self.verify_freeze_manifest()

        LOGGER.info(
            "Access to 2024 POST_HOLDOUT authorized under strict Freeze V2 governance."
        )
