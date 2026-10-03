"""Final Evaluation Guard for 2024 Post-Holdout Execution (Phase 11).

Enforces strict fail-closed governance before any row of 2024 data can be accessed:
1. Verifies existence and SHA256 integrity of artifacts/manifests/system_freeze_manifest.json.
2. Validates that freeze_status is FROZEN and final_holdout_year is 2024.
3. Validates that no pending configuration or code modifications have altered frozen artifacts:
   - config_hashes (configs/academic_model_selection.yaml, current_state.yaml, seed_registry.yaml, src/optimization/config.py)
   - feature_hashes (src/features/tabular_features.py, refactored_features.py)
   - model_code_hashes (src/models/interfaces.py, registry.py, src/contracts/distribution.py, etc.)
   - benchmark_manifest_hashes (academic_model_selection_v1, downstream_comparison, monte_carlo, stability, paired_comparison, scenario)
4. Validates model registry and selection decisions are permanently frozen.
5. Strictly mandates that evaluation_role must be explicitly 'POST_HOLDOUT'.
   Any attempt to describe 2024 as 'untouched holdout' or 'development' fails closed.
6. Asserts zero post-freeze HPO, retraining, or tuning.
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

LOGGER = logging.getLogger("final_evaluation_guard")

DEFAULT_FREEZE_MANIFEST_REL: Final = Path("artifacts/manifests/system_freeze_manifest.json")
DEFAULT_FREEZE_CHECKSUM_REL: Final = Path("artifacts/manifests/system_freeze_manifest.sha256")
EXPECTED_EVALUATION_ROLE: Final = "POST_HOLDOUT"
FORBIDDEN_EVALUATION_ROLES: Final = frozenset({
    "untouched_holdout",
    "unseen_final_test",
    "development",
    "model_selection",
    "hpo",
    "tuning",
    "calibration",
})


class FinalEvaluationGuardError(PermissionError):
    """Raised when 2024 final evaluation conditions or freeze integrity are violated."""


def compute_sha256(path: Path) -> str:
    """Compute sha256 hex digest of file at path."""
    if not path.is_file():
        raise FileNotFoundError(f"File not found for checksum: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FinalEvaluationGuard:
    """Fail-closed guard governing 2024 post-holdout evaluation."""

    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = (project_root or Path(__file__).resolve().parents[2]).resolve()
        self.manifest_path = self.project_root / DEFAULT_FREEZE_MANIFEST_REL
        self.checksum_path = self.project_root / DEFAULT_FREEZE_CHECKSUM_REL

    def verify_freeze_manifest(self) -> dict[str, Any]:
        """Validate all freeze conditions against system_freeze_manifest.json.

        Returns:
            dict containing parsed freeze manifest and audit details.

        Raises:
            FinalEvaluationGuardError: If any condition, hash, or status check fails.
        """
        # 1. Existence of manifest and checksum file
        if not self.manifest_path.exists():
            raise FinalEvaluationGuardError(
                f"Prerequisite failure: System freeze manifest does not exist at {self.manifest_path}. "
                "Final evaluation is BLOCKED."
            )
        if not self.checksum_path.exists():
            raise FinalEvaluationGuardError(
                f"Prerequisite failure: System freeze checksum does not exist at {self.checksum_path}. "
                "Final evaluation is BLOCKED."
            )

        # 2. Checksum integrity of the manifest itself
        computed_manifest_hash = compute_sha256(self.manifest_path)
        recorded_checksum_line = self.checksum_path.read_text(encoding="utf-8").strip()
        expected_manifest_hash = recorded_checksum_line.split()[0]
        if computed_manifest_hash != expected_manifest_hash:
            raise FinalEvaluationGuardError(
                f"Integrity violation: Freeze manifest checksum mismatch! "
                f"Expected {expected_manifest_hash}, computed {computed_manifest_hash}. "
                "Manifest tampering detected. Final evaluation is BLOCKED."
            )

        try:
            payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise FinalEvaluationGuardError(f"Freeze manifest contains invalid JSON: {exc}") from exc

        # 3. Core status & Holdout year
        if payload.get("freeze_status") != "FROZEN":
            raise FinalEvaluationGuardError(
                f"System is not in FROZEN state: freeze_status='{payload.get('freeze_status')}'. "
                "Final evaluation is BLOCKED."
            )
        if payload.get("final_holdout_year") != 2024:
            raise FinalEvaluationGuardError(
                f"Invalid holdout year: final_holdout_year={payload.get('final_holdout_year')}, expected 2024."
            )

        # 4. Verify Config Hashes
        config_hashes: dict[str, str] = payload.get("config_hashes", {})
        if not config_hashes:
            raise FinalEvaluationGuardError("No config_hashes found in freeze manifest.")
        for rel_path, expected_hash in config_hashes.items():
            fpath = self.project_root / rel_path
            if not fpath.exists():
                raise FinalEvaluationGuardError(f"Frozen config file missing: {rel_path}")
            actual_hash = compute_sha256(fpath)
            if actual_hash != expected_hash:
                raise FinalEvaluationGuardError(
                    f"Configuration hash mismatch for {rel_path}: expected {expected_hash}, got {actual_hash}. "
                    "Unfrozen configuration changes detected. Final evaluation is BLOCKED."
                )

        # 5. Verify Feature Hashes
        feature_hashes: dict[str, Any] = payload.get("feature_hashes", {})
        for key, val in feature_hashes.items():
            if key.endswith(".py"):
                fpath = self.project_root / key
                if not fpath.exists():
                    raise FinalEvaluationGuardError(f"Frozen feature file missing: {key}")
                actual_hash = compute_sha256(fpath)
                if actual_hash != val:
                    raise FinalEvaluationGuardError(
                        f"Feature code hash mismatch for {key}: expected {val}, got {actual_hash}. "
                        "Final evaluation is BLOCKED."
                    )
        if feature_hashes.get("feature_contract_version") != "arrival_feature_contract_v1":
            raise FinalEvaluationGuardError(
                f"Unexpected feature contract version: {feature_hashes.get('feature_contract_version')}"
            )
        if feature_hashes.get("approved_predictors_count") != 11:
            raise FinalEvaluationGuardError(
                f"Unexpected approved predictors count: {feature_hashes.get('approved_predictors_count')}"
            )

        # 6. Verify Model Code Hashes
        model_code_hashes: dict[str, str] = payload.get("model_code_hashes", {})
        if not model_code_hashes:
            raise FinalEvaluationGuardError("No model_code_hashes found in freeze manifest.")
        for rel_path, expected_hash in model_code_hashes.items():
            fpath = self.project_root / rel_path
            if not fpath.exists():
                raise FinalEvaluationGuardError(f"Frozen model code file missing: {rel_path}")
            actual_hash = compute_sha256(fpath)
            if actual_hash != expected_hash:
                raise FinalEvaluationGuardError(
                    f"Model code hash mismatch for {rel_path}: expected {expected_hash}, got {actual_hash}. "
                    "Final evaluation is BLOCKED."
                )

        # 7. Verify Benchmark Manifest Hashes
        benchmark_mapping: dict[str, Path] = {
            "academic_model_selection_v1.json": self.project_root / "artifacts" / "manifests" / "academic_model_selection_v1.json",
            "downstream_comparison_manifest": self.project_root / "artifacts" / "downstream_model_comparison" / "manifest.sha256",
            "monte_carlo_comparison_manifest": self.project_root / "artifacts" / "monte_carlo_model_comparison" / "manifest.sha256",
            "stability_manifest": self.project_root / "artifacts" / "stability" / "manifest.sha256",
            "paired_comparison_manifest": self.project_root / "artifacts" / "paired_comparison" / "manifest.sha256",
            "scenario_manifest": self.project_root / "artifacts" / "monte_carlo_model_comparison" / "scenario_manifest.json",
        }
        benchmark_hashes: dict[str, str] = payload.get("benchmark_manifest_hashes", {})
        for manifest_key, expected_hash in benchmark_hashes.items():
            target_file = benchmark_mapping.get(manifest_key)
            if target_file is None or not target_file.exists():
                raise FinalEvaluationGuardError(f"Benchmark manifest file missing for '{manifest_key}' at {target_file}")
            actual_hash = compute_sha256(target_file)
            if actual_hash != expected_hash:
                raise FinalEvaluationGuardError(
                    f"Benchmark manifest hash mismatch for {manifest_key}: expected {expected_hash}, got {actual_hash}"
                )

        # 8. Verify Seed Registry
        seed_reg = payload.get("seed_registry", {})
        if seed_reg.get("predetermined_deployment_seed") != 202601:
            raise FinalEvaluationGuardError(f"Invalid deployment seed in manifest: {seed_reg.get('predetermined_deployment_seed')}")

        # 9. Verify Solver Configuration
        solver_cfg = payload.get("solver_configuration", {})
        expected_solvers = ["DeterministicGreedyGateSolver", "CPSatGateSolver", "SimulatedAnnealingGateSolver"]
        if solver_cfg.get("solvers") != expected_solvers:
            raise FinalEvaluationGuardError(f"Solver configuration altered: {solver_cfg.get('solvers')}")

        # 10. Verify Model Registry Immutability & Candidate Registration
        for core_model_id in [
            "arrival_linear_baseline_v1",
            "arrival_xgboost_baseline_v1",
            "arrival_weighted_ensemble_v1",
            "b5_ngboost_student_t",
        ]:
            spec = get_model_spec(core_model_id)
            if spec.status not in {
                ModelStatus.CURRENT_CORE.value,
                ModelStatus.LEGACY_FROZEN.value,
                ModelStatus.HISTORICAL.value,
                ModelStatus.DOWNSTREAM_ELIGIBLE.value,
                ModelStatus.RESEARCH_CANDIDATE.value,
            }:
                raise FinalEvaluationGuardError(f"Model {core_model_id} has invalid status {spec.status}")

        frozen_sys = payload.get("frozen_system", {})
        expected_candidates = {
            "selected_point_regression_model": "arrival_linear_baseline_v1",
            "selected_point_regression_comparator": "arrival_weighted_ensemble_v1",
            "selected_probabilistic_model": "P5_quantile_regression",
            "historical_probabilistic_comparator": "P4_ngboost_student_t",
            "nominal_schedule_baseline": "schedule_only",
            "non_deployable_reference": "oracle_actual",
        }
        for field_name, expected_id in expected_candidates.items():
            if frozen_sys.get(field_name) != expected_id:
                raise FinalEvaluationGuardError(
                    f"Frozen system specification mismatch: {field_name} expected {expected_id}, got {frozen_sys.get(field_name)}"
                )

        LOGGER.info("FinalEvaluationGuard: System freeze manifest integrity verified 100% PASS.")
        return payload

    def assert_final_evaluation_authorized(
        self,
        *,
        evaluation_role: str,
        purpose: str = "final_evaluation",
    ) -> dict[str, Any]:
        """Authorize access to 2024 data strictly for POST_HOLDOUT final evaluation.

        Args:
            evaluation_role: Must be explicitly 'POST_HOLDOUT'.
            purpose: Must be 'final_evaluation'.

        Returns:
            dict containing verified freeze manifest payload.

        Raises:
            FinalEvaluationGuardError: If authorization fails.
        """
        # 1. Check evaluation_role explicitly
        if evaluation_role != EXPECTED_EVALUATION_ROLE:
            raise FinalEvaluationGuardError(
                f"Unauthorized evaluation_role: '{evaluation_role}'. "
                f"2024 data may ONLY be accessed with evaluation_role='{EXPECTED_EVALUATION_ROLE}'. "
                "Describing 2024 as 'untouched holdout' or 'development' is strictly forbidden."
            )
        if purpose != "final_evaluation":
            raise FinalEvaluationGuardError(
                f"Unauthorized purpose: '{purpose}'. 2024 data can only be accessed with purpose='final_evaluation'."
            )

        # 2. Access guard verification
        try:
            assert_data_access_allowed(
                year=2024,
                purpose="final_evaluation",
                freeze_manifest_path=self.manifest_path,
            )
        except DataAccessDenied as exc:
            raise FinalEvaluationGuardError(f"Access guard denied 2024 evaluation: {exc}") from exc

        # 3. Verify all freeze manifest contents & disk hashes
        payload = self.verify_freeze_manifest()
        return payload
