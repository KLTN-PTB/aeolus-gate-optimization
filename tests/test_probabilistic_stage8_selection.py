"""Unit tests for Stage 8 — 2023 One-Time Full-System Selection.

Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 18, 21, 23
Authoritative Inputs:
- artifacts/manifests/probabilistic_stage7_system_candidates_v1.json
- artifacts/manifests/probabilistic_stage7_5_joint_validation_v1.json
- artifacts/manifests/seed_manifest_v1.json
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import pytest

from src.models.probabilistic.contracts import ProbabilisticContractViolation
from src.models.probabilistic.system_selection import (
    Candidate2023EvaluationResult,
    apply_stage8_gating,
    build_selected_system_manifest,
    resolve_system_tie_break,
    verify_system_freeze_before_2023,
)

ROOT = Path(__file__).resolve().parents[1]


def test_pre_touch_verification_on_repository():
    """Verify that current repository passes the pre-touch freeze verification checklist."""
    report = verify_system_freeze_before_2023(ROOT)
    assert report.audit_passed is True
    assert report.manifests_exist is True
    assert report.all_candidates_frozen is True
    assert report.seed_set_frozen is True
    assert report.dependence_mechanisms_frozen is True
    assert report.calibration_method_frozen is True
    assert report.simulation_interfaces_frozen is True
    assert report.holdout_2024_sealed is True


def test_pre_touch_verification_missing_manifest_raises():
    """Verify that missing freeze manifest triggers contract violation."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_root = Path(tmp_dir)
        m_dir = tmp_root / "artifacts" / "manifests"
        m_dir.mkdir(parents=True)
        # Empty manifest directory
        with pytest.raises(ProbabilisticContractViolation, match="required manifests missing"):
            verify_system_freeze_before_2023(tmp_root)


def _make_dummy_eval(
    candidate_id: str,
    marginal_crps: float,
    cov_80: float = 0.81,
    cov_90: float = 0.91,
    brier_60: float = 0.045,
    agg_crps: float = 165.0,
    std_ratio: float = 0.95,
    psd_passed: bool = True,
    dependence_id: str = "DEP_D2_gaussian_copula",
) -> Candidate2023EvaluationResult:
    return Candidate2023EvaluationResult(
        candidate_id=candidate_id,
        marginal_candidate_id=candidate_id.split("__DEP_")[0].replace("SYS_", ""),
        dependence_candidate_id=dependence_id,
        marginal_crps=marginal_crps,
        marginal_nll=3.5,
        marginal_cov_50=0.51,
        marginal_cov_80=cov_80,
        marginal_cov_90=cov_90,
        marginal_cov_95=0.95,
        marginal_width_80=35.0,
        marginal_width_90=50.0,
        brier_15=0.18,
        brier_60=brier_60,
        brier_120=0.015,
        pinball_90=4.2,
        pinball_95=2.8,
        daily_aggregate_crps=agg_crps,
        aggregate_std_ratio=std_ratio,
        co_exceedance_abs_error=0.001,
        p_n60_ge1_empirical=0.48,
        p_n60_ge1_simulated=0.46,
        p_n60_ge2_empirical=0.32,
        p_n60_ge2_simulated=0.25,
        p_n120_ge1_empirical=0.32,
        p_n120_ge1_simulated=0.20,
        psd_all_passed=psd_passed,
        marginal_calibration_gate=False,
        proper_scoring_gate=False,
        tail_event_gate=False,
        joint_validity_gate=False,
        overall_gate_passed=False,
        rejection_reasons=[],
    )


def test_stage8_gating_logic():
    """Verify that gating rules correctly filter candidates."""
    evals = {
        "good_cand": _make_dummy_eval("good_cand", marginal_crps=14.10),
        "bad_calibration": _make_dummy_eval("bad_calibration", marginal_crps=14.12, cov_80=0.55),
        "bad_crps": _make_dummy_eval("bad_crps", marginal_crps=14.45),  # exceeds 14.10 + 0.20
        "bad_tail": _make_dummy_eval("bad_tail", marginal_crps=14.11, brier_60=0.080),  # exceeds 0.045 + 0.010
        "bad_psd": _make_dummy_eval("bad_psd", marginal_crps=14.12, psd_passed=False),
        "bad_volatility": _make_dummy_eval("bad_volatility", marginal_crps=14.11, std_ratio=0.30),
    }

    gated = apply_stage8_gating(evals)

    assert gated["good_cand"].overall_gate_passed is True
    assert gated["bad_calibration"].overall_gate_passed is False
    assert gated["bad_crps"].overall_gate_passed is False
    assert gated["bad_tail"].overall_gate_passed is False
    assert gated["bad_psd"].overall_gate_passed is False
    assert gated["bad_volatility"].overall_gate_passed is False


def test_system_tie_break_resolution():
    """Verify that tie-breaking follows pre-registered hierarchy."""
    cand1 = _make_dummy_eval(
        "SYS_seed_ensemble_3__DEP_D2_gaussian_copula",
        marginal_crps=14.12,
        agg_crps=160.0,
        std_ratio=0.96,
    )
    cand2 = _make_dummy_eval(
        "SYS_D3_k3_mixture__with_year__DEP_D2_gaussian_copula",
        marginal_crps=14.10,  # slightly better marginal CRPS by 0.02m (within delta=0.10m)
        agg_crps=180.0,  # worse aggregate CRPS
        std_ratio=0.70,
    )

    winner, rationale = resolve_system_tie_break([cand1, cand2])
    # cand1 should win because it is within delta=0.10m and has superior joint risk representation
    assert winner.candidate_id == "SYS_seed_ensemble_3__DEP_D2_gaussian_copula"
    assert "superior joint portfolio risk accuracy" in rationale


def test_manifest_construction_and_immutability():
    """Verify selected system manifest structure and 2024 seal assertion."""
    report = verify_system_freeze_before_2023(ROOT)
    winner = _make_dummy_eval("SYS_seed_ensemble_3__DEP_D2_gaussian_copula", marginal_crps=14.12)
    winner.overall_gate_passed = True

    evals = {winner.candidate_id: winner}

    manifest = build_selected_system_manifest(
        winning_candidate=winner,
        selection_rationale="Test winning rationale",
        all_evaluations=evals,
        pre_touch_audit=report,
        complete_system_meta={"candidate_id": winner.candidate_id},
        total_wall_seconds=12.5,
    )

    assert manifest["manifest_version"] == "selected_system_manifest_v1"
    assert manifest["selection_status"] == "SELECTED_AND_PERMANENTLY_FROZEN"
    assert "NO FURTHER SYSTEM SELECTION" in manifest["selection_declaration"]
    assert manifest["holdout_guards"]["2023_accessed"] is True
    assert manifest["holdout_guards"]["2024_accessed"] is False
    assert manifest["stage_status"] == "PASS"
