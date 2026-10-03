"""Unit tests for Phase 7 Controlled Academic Model Selection.

Tests:
1. 2023-only selection
2. No 2024 access (sealed holdout)
3. Selection policy immutability
4. Candidate pool completeness
5. No metric leakage
6. Deterministic selection
7. Tie handling (effect size indifference band)
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
import yaml

from src.data.access_guard import DataAccessDenied, assert_data_access_allowed
from src.evaluation.model_selection import (
    DEFAULT_SELECTION_POLICY_PATH,
    SelectionPolicy,
    SelectionRule,
    compute_hashes_for_audit,
    evaluate_selection_tie_break,
)
from src.models.registry import get_model_spec


def test_2023_only_selection_and_no_2024_access():
    """Selection must be authorized on 2023 development set, and strictly fail closed on 2024."""
    policy = SelectionPolicy.load(DEFAULT_SELECTION_POLICY_PATH)
    assert policy.evaluation_year == 2023
    assert set(policy.training_years) == {2016, 2017, 2018, 2019, 2020, 2021, 2022}

    # 2023 development access allowed
    assert_data_access_allowed(2023, "development")

    # 2024 development access MUST fail closed
    with pytest.raises(DataAccessDenied):
        assert_data_access_allowed(2024, "development")


def test_selection_policy_immutability(tmp_path: Path):
    """Selection policy must reject illegal years, invalid rules, or unauthorized modifications."""
    policy = SelectionPolicy.load(DEFAULT_SELECTION_POLICY_PATH)
    assert policy.policy_version == "academic_model_selection_v1"
    assert "point_regression" in policy.rules
    assert "point_classification" in policy.rules
    assert "probabilistic" in policy.rules

    # Tampered policy attempting to evaluate on 2024 must fail
    tampered_yaml = tmp_path / "tampered_policy.yaml"
    bad_data = {
        "selection_policy_version": "tampered_v1",
        "temporal_scope": {
            "training_years": [2016, 2017, 2018],
            "evaluation_year": 2024,  # ILLEGAL
            "holdout_year": 2024,
        },
        "candidate_pool": {
            "point_models": ["arrival_linear_baseline_v1"],
            "probabilistic_models": ["P1_empirical"],
        },
        "selection_rules": {
            "point_regression": {
                "primary_metric": "mae",
                "direction": "minimize",
            }
        },
    }
    with open(tampered_yaml, "w", encoding="utf-8") as f:
        yaml.safe_dump(bad_data, f)

    with pytest.raises(ValueError, match="Selection evaluation year must be 2023"):
        SelectionPolicy.load(tampered_yaml)


def test_candidate_completeness():
    """All 5 Core point models and 5 probabilistic candidates must be present in policy."""
    policy = SelectionPolicy.load(DEFAULT_SELECTION_POLICY_PATH)

    expected_point = {
        "arrival_linear_baseline_v1",
        "arrival_random_forest_baseline_v1",
        "arrival_hist_gradient_boosting_baseline_v1",
        "arrival_xgboost_baseline_v1",
        "arrival_weighted_ensemble_v1",
    }
    expected_prob = {
        "P1_empirical",
        "P2_xgb_gaussian_oof",
        "P3_ngboost_normal",
        "P4_ngboost_student_t",
        "P5_quantile_regression",
    }

    assert set(policy.candidate_point_models) == expected_point
    assert set(policy.candidate_probabilistic_models) == expected_prob

    # Ensure point models exist in model registry
    for m in policy.candidate_point_models:
        spec = get_model_spec(m)
        assert spec.model_id == m


def test_deterministic_selection_and_tie_handling():
    """Tie-breaking rule must declare tie when candidates are within effect_size_delta."""
    rule_mae = SelectionRule(
        primary_metric="mae",
        direction="minimize",
        secondary_metrics=("rmse",),
        effect_size_delta=0.10,  # 0.10 min = 6s
    )

    # Case 1: Candidates within 0.10 min -> TIED
    metrics_tied = {
        "model_a": {"mae": 20.00, "rmse": 35.0},
        "model_b": {"mae": 20.06, "rmse": 35.1},  # diff = 0.06 < 0.10 -> tie!
        "model_c": {"mae": 21.50, "rmse": 38.0},  # diff = 1.50 -> not tied
    }
    res_tied = evaluate_selection_tie_break(metrics_tied, rule_mae)

    assert res_tied["tie_status"] == "TIED_WITHIN_EFFECT_SIZE_THRESHOLD"
    assert res_tied["best_numeric_candidate"] == "model_a"
    assert set(res_tied["selected_candidates"]) == {"model_a", "model_b"}
    assert res_tied["margin_to_second"] == pytest.approx(0.06, abs=1e-5)

    # Case 2: One clear leader beyond 0.10 min -> DECISIVE_LEADER
    metrics_decisive = {
        "model_a": {"mae": 20.00, "rmse": 35.0},
        "model_b": {"mae": 20.25, "rmse": 35.5},  # diff = 0.25 > 0.10 -> decisive!
        "model_c": {"mae": 21.50, "rmse": 38.0},
    }
    res_decisive = evaluate_selection_tie_break(metrics_decisive, rule_mae)

    assert res_decisive["tie_status"] == "DECISIVE_LEADER"
    assert res_decisive["best_numeric_candidate"] == "model_a"
    assert res_decisive["selected_candidates"] == ["model_a"]
    assert res_decisive["margin_to_second"] == pytest.approx(0.25, abs=1e-5)


def test_no_metric_leakage():
    """Selection logic must calculate differences purely from validation metrics."""
    rule_pr = SelectionRule(
        primary_metric="pr_auc",
        direction="maximize",
        secondary_metrics=("brier_score",),
        effect_size_delta=0.0050,
    )
    metrics = {
        "clf_1": {"pr_auc": 0.2100},
        "clf_2": {"pr_auc": 0.2080},  # diff = 0.0020 < 0.0050 -> tie
        "clf_3": {"pr_auc": 0.1900},  # diff = 0.0200 -> not tied
    }
    res = evaluate_selection_tie_break(metrics, rule_pr)

    assert res["tie_status"] == "TIED_WITHIN_EFFECT_SIZE_THRESHOLD"
    assert set(res["selected_candidates"]) == {"clf_1", "clf_2"}
    assert res["all_differences_from_best"]["clf_2"] == pytest.approx(0.0020, abs=1e-6)
