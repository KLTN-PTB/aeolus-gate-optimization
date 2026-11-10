"""Unit and Regression Tests for Step 4: Holdout / Fold Guard Correction.

Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Sections 2.2, 18, 21, 22
Verifies:
1. Exact fold rules:
   - Fold 1: train <= 2018 (val 2019)
   - Fold 2: train <= 2019 (val 2020)
   - Fold 3: train <= 2020 (val 2021)
   - Fold 4: train <= 2021 (val 2022)
2. Final pre-holdout training through 2022 (Stage 10 Full System Freeze) is explicitly authorized.
3. Unauthorized future years (> 2024) strictly fail-closed across all roles.
4. Any training set containing 2024 strictly fails.
5. 2024 calibration strictly fails.
6. 2024 selection strictly fails.
7. 2023 selection succeeds, but 2023 training/calibration strictly fails.
8. Explicit POST_HOLDOUT status is preserved across all validation reports.
"""

from __future__ import annotations

import pytest

from src.audit.protocol_guards import (
    POST_HOLDOUT_STATUS_DECLARATION,
    DatasetRole,
    OperationType,
    ProtocolComplianceGuard,
    TemporalProtocolViolation,
    assert_dataset_role_and_years,
    validate_dataset_role_and_years,
)


def test_each_canonical_fold_valid_under_role_guard() -> None:
    """Verify that each canonical cross-validation fold adheres strictly to its temporal boundary."""
    # Fold 1: train 2016-2018 (max 2018), val 2019
    res_f1 = validate_dataset_role_and_years(DatasetRole.FOLD_1_TRAIN, [2016, 2017, 2018], OperationType.TRAINING)
    assert res_f1["is_valid"] is True
    assert res_f1["max_year"] == 2018

    res_f1_val = validate_dataset_role_and_years(DatasetRole.FOLD_1_VAL, 2019, OperationType.HOLDOUT_EVALUATION)
    assert res_f1_val["is_valid"] is True

    # Fold 2: train 2016-2019 (max 2019), val 2020
    res_f2 = validate_dataset_role_and_years(DatasetRole.FOLD_2_TRAIN, [2016, 2017, 2018, 2019], OperationType.TRAINING)
    assert res_f2["is_valid"] is True
    assert res_f2["max_year"] == 2019

    res_f2_val = validate_dataset_role_and_years(DatasetRole.FOLD_2_VAL, 2020, OperationType.HOLDOUT_EVALUATION)
    assert res_f2_val["is_valid"] is True

    # Fold 3: train 2016-2020 (max 2020), val 2021
    res_f3 = validate_dataset_role_and_years(DatasetRole.FOLD_3_TRAIN, [2016, 2017, 2018, 2019, 2020], OperationType.TRAINING)
    assert res_f3["is_valid"] is True
    assert res_f3["max_year"] == 2020

    res_f3_val = validate_dataset_role_and_years(DatasetRole.FOLD_3_VAL, 2021, OperationType.HOLDOUT_EVALUATION)
    assert res_f3_val["is_valid"] is True

    # Fold 4: train 2016-2021 (max 2021), val 2022
    res_f4 = validate_dataset_role_and_years(DatasetRole.FOLD_4_TRAIN, [2016, 2017, 2018, 2019, 2020, 2021], OperationType.TRAINING)
    assert res_f4["is_valid"] is True
    assert res_f4["max_year"] == 2021

    res_f4_val = validate_dataset_role_and_years(DatasetRole.FOLD_4_VAL, 2022, OperationType.HOLDOUT_EVALUATION)
    assert res_f4_val["is_valid"] is True


def test_fold_leakage_beyond_fold_boundary_fails() -> None:
    """A naive universal max-year shortcut would miss fold-level leakage; role guards catch it."""
    # Attempting to train Fold 1 with year 2019 (val year) must fail
    res1 = validate_dataset_role_and_years("fold_1_train", [2016, 2017, 2018, 2019], "training")
    assert res1["is_valid"] is False
    assert "outside allowed years" in res1["error"]

    # Attempting to train Fold 2 with year 2020 must fail
    res2 = validate_dataset_role_and_years("fold_2_train", [2016, 2017, 2018, 2019, 2020], "training")
    assert res2["is_valid"] is False
    assert "outside allowed years" in res2["error"]

    # Attempting to train Fold 3 with year 2021 must fail
    res3 = validate_dataset_role_and_years("fold_3_train", [2016, 2017, 2018, 2019, 2020, 2021], "training")
    assert res3["is_valid"] is False
    assert "outside allowed years" in res3["error"]

    # Attempting to train Fold 4 with year 2022 must fail
    res4 = validate_dataset_role_and_years("fold_4_train", [2016, 2017, 2018, 2019, 2020, 2021, 2022], "training")
    assert res4["is_valid"] is False
    assert "outside allowed years" in res4["error"]


def test_final_pre_holdout_training_authorized_through_2022() -> None:
    """Pre-holdout full system freeze training through 2022 is explicitly authorized by Section 2.2."""
    train_years_full = [2016, 2017, 2018, 2019, 2020, 2021, 2022]
    res = validate_dataset_role_and_years("final_pre_holdout_train", train_years_full, "training")
    assert res["is_valid"] is True
    assert res["max_year"] == 2022
    assert res["post_holdout_status"] == POST_HOLDOUT_STATUS_DECLARATION

    # Adding 2023 to final pre-holdout training must fail (2023 is selection only)
    res_with_2023 = validate_dataset_role_and_years("final_pre_holdout_train", train_years_full + [2023], "training")
    assert res_with_2023["is_valid"] is False
    assert "2023 is DEVELOPMENT_MODEL_SELECTION" in res_with_2023["error"]

    # Adding 2024 to final pre-holdout training must fail (2024 is holdout only)
    res_with_2024 = validate_dataset_role_and_years("final_pre_holdout_train", train_years_full + [2024], "training")
    assert res_with_2024["is_valid"] is False
    assert "2024 is FINAL_HOLDOUT" in res_with_2024["error"]


def test_unauthorized_future_year_fails() -> None:
    """Any year greater than 2024 is outside protocol scope and must fail fail-closed."""
    for future_yr in [2025, 2026, 2030]:
        res_train = validate_dataset_role_and_years("final_pre_holdout_train", [2016, future_yr], "training")
        assert res_train["is_valid"] is False
        assert "Unauthorized future year" in res_train["error"]

        res_sel = validate_dataset_role_and_years("development_model_selection", [future_yr], "selection")
        assert res_sel["is_valid"] is False
        assert "Unauthorized future year" in res_sel["error"]

        res_holdout = validate_dataset_role_and_years("final_holdout", [future_yr], "holdout_evaluation")
        assert res_holdout["is_valid"] is False
        assert "Unauthorized future year" in res_holdout["error"]


def test_any_training_containing_2024_fails() -> None:
    """2024 is FINAL_HOLDOUT: ANY training configuration containing 2024 must fail."""
    test_cases = [
        ("fold_1_train", [2016, 2024]),
        ("fold_2_train", [2016, 2017, 2024]),
        ("fold_3_train", [2016, 2017, 2018, 2024]),
        ("fold_4_train", [2016, 2017, 2018, 2019, 2020, 2021, 2024]),
        ("final_pre_holdout_train", [2024]),
        ("final_pre_holdout_train", [2016, 2017, 2018, 2019, 2020, 2021, 2022, 2024]),
    ]
    for role, yrs in test_cases:
        res = validate_dataset_role_and_years(role, yrs, operation="training")
        assert res["is_valid"] is False
        assert "2024 is FINAL_HOLDOUT" in res["error"]


def test_2024_calibration_fails() -> None:
    """Calibration on 2024 must fail fail-closed."""
    res = validate_dataset_role_and_years("final_pre_holdout_train", [2024], operation="calibration")
    assert res["is_valid"] is False
    assert "Calibration on 2024 is strictly forbidden" in res["error"]

    res_fold = validate_dataset_role_and_years("fold_4_train", [2024], operation="calibration")
    assert res_fold["is_valid"] is False
    assert "Calibration on 2024 is strictly forbidden" in res_fold["error"]


def test_2024_selection_fails() -> None:
    """Selection on 2024 must fail fail-closed (selection belongs to 2023)."""
    res = validate_dataset_role_and_years("development_model_selection", [2024], operation="selection")
    assert res["is_valid"] is False
    assert "Selection on 2024 is strictly forbidden" in res["error"]


def test_2023_training_and_calibration_fails_but_selection_passes() -> None:
    """2023 is reserved strictly for complete-system selection, never for training/calibration."""
    # Training on 2023 fails
    res_train = validate_dataset_role_and_years("final_pre_holdout_train", [2023], operation="training")
    assert res_train["is_valid"] is False
    assert "2023 is DEVELOPMENT_MODEL_SELECTION" in res_train["error"]

    # Calibration on 2023 fails
    res_cal = validate_dataset_role_and_years("final_pre_holdout_train", [2023], operation="calibration")
    assert res_cal["is_valid"] is False
    assert "2023 is DEVELOPMENT_MODEL_SELECTION" in res_cal["error"]

    # Selection on 2023 succeeds
    res_sel = validate_dataset_role_and_years("development_model_selection", [2023], operation="selection")
    assert res_sel["is_valid"] is True
    assert res_sel["error"] is None


def test_assert_dataset_role_and_years_raises_temporal_protocol_violation() -> None:
    """assert_dataset_role_and_years must raise TemporalProtocolViolation on failure."""
    with pytest.raises(TemporalProtocolViolation, match="2024 is FINAL_HOLDOUT"):
        assert_dataset_role_and_years("final_pre_holdout_train", [2016, 2024], "training")

    with pytest.raises(TemporalProtocolViolation, match="Unauthorized future year"):
        assert_dataset_role_and_years("final_pre_holdout_train", [2025], "training")

    # Valid call does not raise
    assert_dataset_role_and_years("final_pre_holdout_train", [2016, 2017, 2018, 2019, 2020, 2021, 2022], "training")


def test_protocol_compliance_guard_full_suite() -> None:
    """ProtocolComplianceGuard must pass all checks and confirm role-based temporal isolation."""
    guard = ProtocolComplianceGuard()
    res = guard.run_all_checks()

    assert res["guard_status"] == "PASS"
    assert res["passed_checks"] == res["total_checks"]
    assert res["failed_checks"] == 0
    assert res["post_holdout_status"] == POST_HOLDOUT_STATUS_DECLARATION

    # Check isolation details
    check_map = {c["check"]: c for c in res["details"]}
    assert "holdout_2024_not_in_training" in check_map
    h_check = check_map["holdout_2024_not_in_training"]
    assert h_check["role_based_validation"] is True
    assert h_check["fold_validations_passed"] is True
    assert h_check["final_pre_holdout_train_authorized"] is True
    assert h_check["training_2024_rejected"] is True
    assert h_check["calibration_2024_rejected"] is True
    assert h_check["selection_2024_rejected"] is True
    assert h_check["future_years_rejected"] is True
