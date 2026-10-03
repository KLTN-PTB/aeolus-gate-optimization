"""Stage 10 Runner — Full System Freeze Before 2024 Holdout.

Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 21 (Stage 10)
          docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md - Section 5 (Week 10)

Authoritative Inputs:
- Selected System Manifest: artifacts/manifests/selected_system_manifest_v1.json
- Stage 9 Gate Simulation Manifest: artifacts/manifests/probabilistic_stage9_gate_simulation_v1.json
- Stage 7 Candidates Manifest: artifacts/manifests/probabilistic_stage7_system_candidates_v1.json
- Stage 7.5 Joint Validation Manifest: artifacts/manifests/probabilistic_stage7_5_joint_validation_v1.json
- Feature Manifest: artifacts/manifests/feature_manifest_arrival_v1.json
- Representation Manifest: artifacts/manifests/representation_manifest_v1.json
- Seed Manifest: artifacts/manifests/seed_manifest_v1.json

Executes:
1. Loads and cross-validates all 7 prerequisite authoritative manifests.
2. Trains the frozen B5 NGBoost Student-T model strictly on 2016-2022
   development data and serializes weights via joblib.
3. Validates serialized model round-trip prediction integrity.
4. Verifies all 20 frozen system components and records SHA-256 hashes.
5. Runs pre-freeze assertion guards:
   - No undecided model choice remains.
   - No undecided dependence choice remains.
   - No undecided calibration choice remains.
   - No future-year data was used improperly.
   - 2024 remains 100% sealed.
6. Produces authoritative manifest: artifacts/manifests/full_system_freeze_manifest_v1.json.
7. Declares repository state as FINAL_SYSTEM_FROZEN.
8. Explicitly prohibits post-freeze changes.

Do NOT open or evaluate 2024 in this script.
Do NOT alter model/config after the freeze is declared.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sys
import time
from typing import Any

# Ensure repository root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import joblib
import numpy as np
import pandas as pd

from src.data.stratified_loader import load_stratified_fold_data
from src.models.probabilistic.baselines import B5NGBoostStudentT
from src.models.probabilistic.contracts import (
    DEFAULT_SIGMA_FLOOR,
    PROBABILISTIC_PREDICTOR_COLUMNS,
    ProbabilisticContractViolation,
)
from src.models.probabilistic.system_freeze import (
    FullSystemFreezeSpecification,
    SystemFreezeVerificationReport,
    compute_file_sha256,
    export_full_system_freeze_manifest,
    verify_and_build_system_freeze,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
LOGGER = logging.getLogger("stage10_system_freeze")

DEPLOYMENT_SEED = 202601


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Stage 10 Full System Freeze")
    parser.add_argument("--train-sample", type=int, default=1000,
                        help="Train samples per development year (2016-2022)")
    args = parser.parse_args()

    start_time = time.time()
    LOGGER.info("=" * 80)
    LOGGER.info("STAGE 10 — FULL SYSTEM FREEZE")
    LOGGER.info("Objective: Create formal full-system freeze checkpoint before 2024 is opened.")
    LOGGER.info("=" * 80)

    root = Path(__file__).resolve().parents[1]
    manifest_dir = root / "artifacts" / "manifests"
    prob_dir = root / "artifacts" / "probabilistic" / "ngboost_student_t"
    weights_path = prob_dir / "model_weights_frozen_v1.joblib"

    # =========================================================================
    # STEP 1: Train and Serialize Frozen Model Weights
    # =========================================================================
    LOGGER.info("\n--- STEP 1: Training & Serializing Frozen B5 NGBoost Student-T Model ---")
    LOGGER.info(f"Training strictly on outer window [2016, 2017, 2018, 2019, 2020, 2021, 2022]")
    LOGGER.info(f"Deployment seed: {DEPLOYMENT_SEED}")

    X_train, _, y_train_reg, _, X_val, _, y_val_reg, _ = load_stratified_fold_data(
        train_years=[2016, 2017, 2018, 2019, 2020, 2021, 2022],
        val_year=2023,
        sample_train_per_year=args.train_sample,
        sample_val=100,  # minimal placeholder, we don't evaluate here
        project_root=root,
        random_state=DEPLOYMENT_SEED,
        feature_set="v1",
    )

    LOGGER.info(f"Training instances: {len(X_train)} | Features: {X_train.shape[1]}")

    model = B5NGBoostStudentT(n_estimators=50, learning_rate=0.005, seed=DEPLOYMENT_SEED)
    model.fit(X_train, y_train_reg.to_numpy(dtype=np.float64))

    prob_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, weights_path)
    LOGGER.info(f"[SERIALIZED] Frozen model weights saved to {weights_path}")
    LOGGER.info(f"[SERIALIZED] File size: {weights_path.stat().st_size:,} bytes")

    weights_sha256 = compute_file_sha256(weights_path)
    LOGGER.info(f"[SERIALIZED] SHA-256: {weights_sha256}")

    # =========================================================================
    # STEP 2: Validate Serialized Model Round-Trip Integrity
    # =========================================================================
    LOGGER.info("\n--- STEP 2: Validating Model Serialization Round-Trip ---")

    pred_before = model.predict_distribution(X_train.head(20))

    model_reloaded = joblib.load(weights_path)
    pred_after = model_reloaded.predict_distribution(X_train.head(20))

    mu_match = np.allclose(pred_before["mu"], pred_after["mu"], atol=1e-12)
    sigma_match = np.allclose(pred_before["sigma"], pred_after["sigma"], atol=1e-12)
    df_match = np.allclose(pred_before["df"], pred_after["df"], atol=1e-12)

    roundtrip_pass = mu_match and sigma_match and df_match
    LOGGER.info(f"mu match: {mu_match} | sigma match: {sigma_match} | df match: {df_match}")

    if not roundtrip_pass:
        raise ProbabilisticContractViolation(
            "CRITICAL: Serialized model round-trip prediction mismatch detected!"
        )
    LOGGER.info("[PASS] Model serialization round-trip integrity verified.")

    # =========================================================================
    # STEP 3: Verify and Build Full System Freeze Specification
    # =========================================================================
    LOGGER.info("\n--- STEP 3: Building Full System Freeze Specification (20 Items) ---")

    freeze_spec = verify_and_build_system_freeze(
        project_root=root,
        model_weights_path=weights_path,
    )

    # =========================================================================
    # STEP 4: Pre-Freeze Assertion Guards
    # =========================================================================
    LOGGER.info("\n--- STEP 4: Pre-Freeze Assertion Guards ---")

    vr = freeze_spec.verification_report
    LOGGER.info(f"  No undecided model choice:       {vr.no_undecided_model_choice}")
    LOGGER.info(f"  No undecided dependence choice:   {vr.no_undecided_dependence_choice}")
    LOGGER.info(f"  No undecided calibration choice:  {vr.no_undecided_calibration_choice}")
    LOGGER.info(f"  No future-year data used:         {vr.no_future_year_data_used_improperly}")
    LOGGER.info(f"  2024 holdout sealed:              {vr.holdout_2024_sealed}")
    LOGGER.info(f"  All 20 items verified:            {vr.all_20_items_verified}")
    LOGGER.info(f"  Overall freeze status:            {vr.overall_freeze_status}")
    LOGGER.info(f"  Post-freeze changes permitted:    {vr.post_freeze_changes_permitted}")

    all_guards_pass = (
        vr.no_undecided_model_choice
        and vr.no_undecided_dependence_choice
        and vr.no_undecided_calibration_choice
        and vr.no_future_year_data_used_improperly
        and vr.holdout_2024_sealed
        and vr.all_20_items_verified
        and vr.overall_freeze_status == "FINAL_SYSTEM_FROZEN"
        and not vr.post_freeze_changes_permitted
    )

    if not all_guards_pass:
        raise ProbabilisticContractViolation(
            "CRITICAL: One or more pre-freeze assertion guards FAILED. "
            "Cannot declare FINAL_SYSTEM_FROZEN."
        )

    LOGGER.info("[PASS] All pre-freeze assertion guards verified.")

    # =========================================================================
    # STEP 5: Export Authoritative Freeze Manifest
    # =========================================================================
    LOGGER.info("\n--- STEP 5: Exporting Authoritative Full System Freeze Manifest ---")

    output_path = manifest_dir / "full_system_freeze_manifest_v1.json"
    export_full_system_freeze_manifest(freeze_spec, output_path)

    LOGGER.info(f"[EXPORTED] {output_path}")
    LOGGER.info(f"[EXPORTED] SHA-256: {compute_file_sha256(output_path)}")

    # =========================================================================
    # STEP 6: Verify exported manifest loads and is self-consistent
    # =========================================================================
    LOGGER.info("\n--- STEP 6: Post-Export Self-Consistency Verification ---")

    with open(output_path, "r", encoding="utf-8") as f:
        loaded_manifest = json.load(f)

    assert loaded_manifest["manifest_version"] == "full_system_freeze_manifest_v1"
    assert loaded_manifest["stage"] == "STAGE_10_FULL_SYSTEM_FREEZE"
    assert loaded_manifest["system_id"] == "SYS_B5_ngboost_student_t__DEP_D2_gaussian_copula"
    assert loaded_manifest["marginal_candidate_id"] == "B5_ngboost_student_t"
    assert loaded_manifest["dependence_candidate_id"] == "DEP_D2_gaussian_copula"

    # Verify all 20 items are present
    for i in range(1, 21):
        key = f"item_{i:02d}_"
        found = any(k.startswith(key) for k in loaded_manifest.keys())
        assert found, f"Missing frozen item {i} in manifest"
    LOGGER.info("[PASS] All 20 items present in exported manifest.")

    # Verify verification_report block
    ver_block = loaded_manifest["verification_report"]
    assert ver_block["overall_freeze_status"] == "FINAL_SYSTEM_FROZEN"
    assert ver_block["post_freeze_changes_permitted"] is False
    assert ver_block["holdout_2024_sealed"] is True
    assert ver_block["no_undecided_model_choice"] is True
    assert ver_block["no_undecided_dependence_choice"] is True
    assert ver_block["no_undecided_calibration_choice"] is True
    LOGGER.info("[PASS] Verification report block is self-consistent.")

    # Verify freeze_declaration
    assert "FINAL_SYSTEM_FROZEN" in loaded_manifest["freeze_declaration"]
    assert "STRICTLY PROHIBITED" in loaded_manifest["freeze_declaration"]
    LOGGER.info("[PASS] Freeze declaration contains required prohibitions.")

    # Verify weights hash in manifest matches serialized file
    manifest_weights_sha = loaded_manifest["item_06_model_weights"]["checkpoint_sha256"]
    actual_weights_sha = compute_file_sha256(weights_path)
    assert manifest_weights_sha == actual_weights_sha, "Weights hash mismatch!"
    LOGGER.info("[PASS] Model weights SHA-256 hash matches between manifest and file.")

    # Verify holdout guards
    assert loaded_manifest["verification_report"]["holdout_2024_sealed"] is True
    LOGGER.info("[PASS] 2024 holdout remains 100% sealed.")

    # =========================================================================
    # FINAL: Print summary
    # =========================================================================
    wall_sec = time.time() - start_time
    n_hashes = len(loaded_manifest.get("item_20_artifact_hashes", {}))

    LOGGER.info("\n" + "=" * 80)
    LOGGER.info("STAGE 10 — FULL SYSTEM FREEZE — COMPLETED")
    LOGGER.info("=" * 80)
    LOGGER.info(f"Frozen System:     {loaded_manifest['system_id']}")
    LOGGER.info(f"Marginal Model:    {loaded_manifest['marginal_candidate_id']}")
    LOGGER.info(f"Dependence Model:  {loaded_manifest['dependence_candidate_id']}")
    LOGGER.info(f"Weights SHA-256:   {manifest_weights_sha[:32]}...")
    LOGGER.info(f"Total Artifacts:   {n_hashes} SHA-256 hashes recorded")
    LOGGER.info(f"Freeze Status:     {ver_block['overall_freeze_status']}")
    LOGGER.info(f"Wall Clock:        {wall_sec:.2f}s")
    LOGGER.info(f"2024 Accessed:     False")
    LOGGER.info("")
    LOGGER.info("DECLARATION: Repository state is FINAL_SYSTEM_FROZEN.")
    LOGGER.info("Post-freeze modifications are STRICTLY PROHIBITED.")
    LOGGER.info("2024 remains sealed for Stage 11 final holdout evaluation.")
    LOGGER.info("=" * 80)


if __name__ == "__main__":
    main()
