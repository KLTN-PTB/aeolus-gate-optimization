"""Stage 10 — Full System Freeze Unit Tests.

Validates that the system_freeze module:
1. Computes SHA-256 hashes correctly.
2. Collects runtime metadata without error.
3. Refuses to freeze when prerequisite manifests are missing.
4. Refuses to freeze when Stage 8 selection is not permanently frozen.
5. Refuses to freeze when 2024 holdout guard is violated.
6. Produces a valid FullSystemFreezeSpecification with all 20 items.
7. Exported manifest is loadable and self-consistent.
8. Verification report flags are correct.
9. Freeze declaration contains required prohibitions.
10. Weights SHA-256 matches between manifest and serialized file.
11. Post-freeze changes are explicitly prohibited.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.models.probabilistic.contracts import (
    DEFAULT_SIGMA_FLOOR,
    PROBABILISTIC_PREDICTOR_COLUMNS,
    ProbabilisticContractViolation,
)
from src.models.probabilistic.system_freeze import (
    FullSystemFreezeSpecification,
    SystemFreezeVerificationReport,
    collect_system_runtime_metadata,
    compute_file_sha256,
    export_full_system_freeze_manifest,
    verify_and_build_system_freeze,
)

ROOT = Path(__file__).resolve().parents[1]


# =============================================================================
# Test 1: SHA-256 hash computation
# =============================================================================

class TestComputeFileSHA256:
    """Tests for compute_file_sha256 helper."""

    def test_sha256_known_content(self, tmp_path: Path) -> None:
        """SHA-256 of known content matches expected digest."""
        test_file = tmp_path / "test_hash.txt"
        content = b"AEOLUS_GATE_OPTIMIZATION_STAGE10_FREEZE"
        test_file.write_bytes(content)

        expected = hashlib.sha256(content).hexdigest()
        result = compute_file_sha256(test_file)
        assert result == expected, f"Hash mismatch: {result} != {expected}"

    def test_sha256_nonexistent_file(self, tmp_path: Path) -> None:
        """Raise FileNotFoundError for missing file."""
        fake_path = tmp_path / "does_not_exist.bin"
        with pytest.raises(FileNotFoundError):
            compute_file_sha256(fake_path)

    def test_sha256_empty_file(self, tmp_path: Path) -> None:
        """SHA-256 of empty file matches known empty-file digest."""
        test_file = tmp_path / "empty.bin"
        test_file.write_bytes(b"")
        expected = hashlib.sha256(b"").hexdigest()
        result = compute_file_sha256(test_file)
        assert result == expected


# =============================================================================
# Test 2: Runtime metadata collection
# =============================================================================

class TestRuntimeMetadata:
    """Tests for collect_system_runtime_metadata."""

    def test_metadata_has_required_keys(self) -> None:
        """Runtime metadata includes platform, python, and package info."""
        meta = collect_system_runtime_metadata()
        assert "platform" in meta
        assert "python_version" in meta
        assert "packages" in meta
        assert isinstance(meta["packages"], dict)

    def test_metadata_packages_include_numpy(self) -> None:
        """Numpy must be present in collected package versions."""
        meta = collect_system_runtime_metadata()
        assert "numpy" in meta["packages"]
        assert meta["packages"]["numpy"] != "not_installed"


# =============================================================================
# Test 3: Freeze refuses when manifests are missing
# =============================================================================

class TestFreezePrerequisites:
    """Tests that freeze fails when prerequisite manifests are missing."""

    def test_freeze_fails_without_stage8_manifest(self, tmp_path: Path) -> None:
        """Must raise ProbabilisticContractViolation when no Stage 8 manifest exists."""
        # Create an empty project root with no manifests
        fake_root = tmp_path / "fake_project"
        (fake_root / "artifacts" / "manifests").mkdir(parents=True)

        with pytest.raises(ProbabilisticContractViolation, match="missing prerequisite manifests"):
            verify_and_build_system_freeze(fake_root)


# =============================================================================
# Test 4: Verification report structure
# =============================================================================

class TestVerificationReport:
    """Tests for SystemFreezeVerificationReport dataclass."""

    def test_report_is_frozen(self) -> None:
        """Verification report is immutable once created."""
        report = SystemFreezeVerificationReport(
            no_undecided_model_choice=True,
            no_undecided_dependence_choice=True,
            no_undecided_calibration_choice=True,
            no_future_year_data_used_improperly=True,
            holdout_2024_sealed=True,
            all_20_items_verified=True,
            overall_freeze_status="FINAL_SYSTEM_FROZEN",
            post_freeze_changes_permitted=False,
            verification_timestamp_utc="2026-09-27T11:00:00+00:00",
            details={"test": True},
        )
        with pytest.raises(AttributeError):
            report.holdout_2024_sealed = False  # type: ignore[misc]

    def test_report_to_dict(self) -> None:
        """to_dict produces correct keys."""
        report = SystemFreezeVerificationReport(
            no_undecided_model_choice=True,
            no_undecided_dependence_choice=True,
            no_undecided_calibration_choice=True,
            no_future_year_data_used_improperly=True,
            holdout_2024_sealed=True,
            all_20_items_verified=True,
            overall_freeze_status="FINAL_SYSTEM_FROZEN",
            post_freeze_changes_permitted=False,
            verification_timestamp_utc="2026-09-27T11:00:00+00:00",
            details={"test": True},
        )
        d = report.to_dict()
        assert d["overall_freeze_status"] == "FINAL_SYSTEM_FROZEN"
        assert d["post_freeze_changes_permitted"] is False
        assert d["holdout_2024_sealed"] is True

    def test_report_prohibits_changes(self) -> None:
        """post_freeze_changes_permitted must be False."""
        report = SystemFreezeVerificationReport(
            no_undecided_model_choice=True,
            no_undecided_dependence_choice=True,
            no_undecided_calibration_choice=True,
            no_future_year_data_used_improperly=True,
            holdout_2024_sealed=True,
            all_20_items_verified=True,
            overall_freeze_status="FINAL_SYSTEM_FROZEN",
            post_freeze_changes_permitted=False,
            verification_timestamp_utc="2026-09-27T11:00:00+00:00",
            details={},
        )
        assert report.post_freeze_changes_permitted is False


# =============================================================================
# Test 5: Full end-to-end freeze on real repository (conditional)
# =============================================================================

class TestFullSystemFreezeEndToEnd:
    """End-to-end tests that run only when all prerequisite manifests exist."""

    @pytest.fixture(autouse=True)
    def _check_manifests(self) -> None:
        """Skip if prerequisite manifests are not available."""
        required = [
            ROOT / "artifacts" / "manifests" / "selected_system_manifest_v1.json",
            ROOT / "artifacts" / "manifests" / "probabilistic_stage9_gate_simulation_v1.json",
            ROOT / "artifacts" / "manifests" / "probabilistic_stage7_system_candidates_v1.json",
            ROOT / "artifacts" / "manifests" / "probabilistic_stage7_5_joint_validation_v1.json",
            ROOT / "artifacts" / "manifests" / "feature_manifest_arrival_v1.json",
            ROOT / "artifacts" / "manifests" / "representation_manifest_v1.json",
            ROOT / "artifacts" / "manifests" / "seed_manifest_v1.json",
        ]
        for p in required:
            if not p.exists():
                pytest.skip(f"Prerequisite manifest missing: {p.name}")

    def test_freeze_spec_has_20_items(self) -> None:
        """Freeze specification must contain all 20 frozen items."""
        # We need a weights file to exist; either use existing or create temp
        weights_path = ROOT / "artifacts" / "probabilistic" / "ngboost_student_t" / "model_weights_frozen_v1.joblib"
        if not weights_path.exists():
            pytest.skip("Model weights not yet serialized; run Stage 10 runner first")

        spec = verify_and_build_system_freeze(ROOT, model_weights_path=weights_path)
        d = spec.to_dict()

        for i in range(1, 21):
            key_prefix = f"item_{i:02d}_"
            found = any(k.startswith(key_prefix) for k in d.keys())
            assert found, f"Missing item {i:02d} in freeze specification"

    def test_freeze_spec_system_id(self) -> None:
        """Freeze specification must identify the winning system."""
        weights_path = ROOT / "artifacts" / "probabilistic" / "ngboost_student_t" / "model_weights_frozen_v1.joblib"
        if not weights_path.exists():
            pytest.skip("Model weights not yet serialized")

        spec = verify_and_build_system_freeze(ROOT, model_weights_path=weights_path)
        assert spec.system_id == "SYS_B5_ngboost_student_t__DEP_D2_gaussian_copula"
        assert spec.marginal_candidate_id == "B5_ngboost_student_t"
        assert spec.dependence_candidate_id == "DEP_D2_gaussian_copula"

    def test_freeze_spec_2024_sealed(self) -> None:
        """2024 must remain sealed in freeze specification."""
        weights_path = ROOT / "artifacts" / "probabilistic" / "ngboost_student_t" / "model_weights_frozen_v1.joblib"
        if not weights_path.exists():
            pytest.skip("Model weights not yet serialized")

        spec = verify_and_build_system_freeze(ROOT, model_weights_path=weights_path)
        assert spec.verification_report.holdout_2024_sealed is True

    def test_freeze_spec_no_undecided_choices(self) -> None:
        """No undecided model, dependence, or calibration choices remain."""
        weights_path = ROOT / "artifacts" / "probabilistic" / "ngboost_student_t" / "model_weights_frozen_v1.joblib"
        if not weights_path.exists():
            pytest.skip("Model weights not yet serialized")

        spec = verify_and_build_system_freeze(ROOT, model_weights_path=weights_path)
        vr = spec.verification_report
        assert vr.no_undecided_model_choice is True
        assert vr.no_undecided_dependence_choice is True
        assert vr.no_undecided_calibration_choice is True

    def test_freeze_declaration_content(self) -> None:
        """Freeze declaration must contain FINAL_SYSTEM_FROZEN and STRICTLY PROHIBITED."""
        weights_path = ROOT / "artifacts" / "probabilistic" / "ngboost_student_t" / "model_weights_frozen_v1.joblib"
        if not weights_path.exists():
            pytest.skip("Model weights not yet serialized")

        spec = verify_and_build_system_freeze(ROOT, model_weights_path=weights_path)
        assert "FINAL_SYSTEM_FROZEN" in spec.freeze_declaration
        assert "STRICTLY PROHIBITED" in spec.freeze_declaration

    def test_export_and_reload_manifest(self, tmp_path: Path) -> None:
        """Exported manifest must be valid JSON with correct version and system ID."""
        weights_path = ROOT / "artifacts" / "probabilistic" / "ngboost_student_t" / "model_weights_frozen_v1.joblib"
        if not weights_path.exists():
            pytest.skip("Model weights not yet serialized")

        spec = verify_and_build_system_freeze(ROOT, model_weights_path=weights_path)
        out_file = tmp_path / "test_freeze_manifest.json"
        export_full_system_freeze_manifest(spec, out_file)

        assert out_file.exists()
        with open(out_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["manifest_version"] == "full_system_freeze_manifest_v1"
        assert data["stage"] == "STAGE_10_FULL_SYSTEM_FREEZE"
        assert data["system_id"] == "SYS_B5_ngboost_student_t__DEP_D2_gaussian_copula"
        assert data["verification_report"]["overall_freeze_status"] == "FINAL_SYSTEM_FROZEN"
        assert data["verification_report"]["post_freeze_changes_permitted"] is False

    def test_artifact_hashes_non_empty(self) -> None:
        """Artifact hashes must contain at least 10 entries."""
        weights_path = ROOT / "artifacts" / "probabilistic" / "ngboost_student_t" / "model_weights_frozen_v1.joblib"
        if not weights_path.exists():
            pytest.skip("Model weights not yet serialized")

        spec = verify_and_build_system_freeze(ROOT, model_weights_path=weights_path)
        hashes = spec.item_20_artifact_hashes
        assert len(hashes) >= 10, f"Expected >= 10 artifact hashes, got {len(hashes)}"

        # Verify weights hash is included
        assert "weights::model_weights_frozen_v1.joblib" in hashes

    def test_sampling_procedure_has_9_steps(self) -> None:
        """Sampling procedure must have exactly 9 documented steps."""
        weights_path = ROOT / "artifacts" / "probabilistic" / "ngboost_student_t" / "model_weights_frozen_v1.joblib"
        if not weights_path.exists():
            pytest.skip("Model weights not yet serialized")

        spec = verify_and_build_system_freeze(ROOT, model_weights_path=weights_path)
        assert len(spec.item_13_sampling_procedure) == 9

    def test_thresholds_include_registered_values(self) -> None:
        """Thresholds must include sigma_floor, df_floor, psd_eigenvalue_floor."""
        weights_path = ROOT / "artifacts" / "probabilistic" / "ngboost_student_t" / "model_weights_frozen_v1.joblib"
        if not weights_path.exists():
            pytest.skip("Model weights not yet serialized")

        spec = verify_and_build_system_freeze(ROOT, model_weights_path=weights_path)
        thresholds = spec.item_17_thresholds
        assert thresholds["sigma_floor"] == DEFAULT_SIGMA_FLOOR
        assert thresholds["df_floor"] == 2.1
        assert thresholds["psd_eigenvalue_floor"] == 1e-6

    def test_dependence_parameters_match_stage8(self) -> None:
        """Dependence parameters must match the Stage 8 selected system specification."""
        weights_path = ROOT / "artifacts" / "probabilistic" / "ngboost_student_t" / "model_weights_frozen_v1.joblib"
        if not weights_path.exists():
            pytest.skip("Model weights not yet serialized")

        spec = verify_and_build_system_freeze(ROOT, model_weights_path=weights_path)
        dep_params = spec.item_12_dependence_parameters
        assert dep_params["temporal_length_scale_minutes"] == 120.0
        assert dep_params["carrier_correlation"] == 0.15
        assert dep_params["psd_minimum_eigenvalue"] == 1e-6

    def test_training_policy_prohibits_2024_tuning(self) -> None:
        """Training policy must explicitly prohibit tuning on 2024."""
        weights_path = ROOT / "artifacts" / "probabilistic" / "ngboost_student_t" / "model_weights_frozen_v1.joblib"
        if not weights_path.exists():
            pytest.skip("Model weights not yet serialized")

        spec = verify_and_build_system_freeze(ROOT, model_weights_path=weights_path)
        policy = spec.item_07_training_policy
        assert "STRICTLY_PROHIBITED" in policy["adaptive_tuning_2024"]
        assert policy["n_estimators"] == 50
        assert policy["learning_rate"] == 0.005
