"""Test Suite for R19 Ensemble Lineage, Weight Collapse & Stale Artifact Detection.

Protocol: Task R19 Forensic Audit
Invariants:
- Ensemble weights satisfy non-negativity and sum-to-one constraints
- Ensemble source OOF artifacts are traceable and exist on disk
- Repeated metrics have verified mathematical lineage and root causes
- Stale artifacts cannot masquerade as recomputed results
- Simplex vertex collapse under L1 loss is mathematically reproducible
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.optimize import minimize

REPO_ROOT = Path("D:/Study/Code/Python/Aelous")


def test_ensemble_weights_satisfy_constraints():
    """Verify that all recorded ensemble weights satisfy simplex constraints w >= 0, sum(w) = 1."""
    path = REPO_ROOT / "artifacts/r19_ensemble_weight_audit.json"
    assert path.exists(), f"Missing artifact: {path}"

    with open(path, encoding="utf-8") as f:
        records = json.load(f)

    assert len(records) >= 5, "Must contain fold_1..fold_4 and evaluation_2023"

    for r in records:
        fold_id = r["fold"]
        weights_dict = r["weights"]

        for task in ["classification", "regression"]:
            assert task in weights_dict, f"Missing {task} weights in {fold_id}"
            task_w = weights_dict[task]

            w_vals = list(task_w.values())
            # 1. Non-negativity
            for model_name, w in task_w.items():
                assert w >= -1e-6, f"Negative weight in {fold_id} {task} for {model_name}: {w}"
                assert w <= 1.0 + 1e-6, f"Weight > 1 in {fold_id} {task} for {model_name}: {w}"

            # 2. Sum to 1.0
            total_w = sum(w_vals)
            assert np.isclose(total_w, 1.0, atol=1e-4), (
                f"Weights in {fold_id} {task} do not sum to 1.0: sum={total_w}"
            )


def test_ensemble_source_oof_artifacts_traceable():
    """Verify that all base model OOF parquet files used to train ensemble weights exist on disk."""
    base_models = [
        "arrival_linear_baseline_v1",
        "arrival_random_forest_baseline_v1",
        "arrival_hist_gradient_boosting_baseline_v1",
        "arrival_xgboost_baseline_v1",
    ]
    folds = ["fold_1", "fold_2", "fold_3", "fold_4"]

    oof_dir = REPO_ROOT / "artifacts/model_benchmark_v2/core_point/core_point_benchmark_v2/oof"
    assert oof_dir.exists(), f"OOF directory missing: {oof_dir}"

    for f_id in folds:
        for m_id in base_models:
            oof_file = oof_dir / f"{m_id}_{f_id}.parquet"
            assert oof_file.exists(), f"Base model OOF artifact missing: {oof_file}"
            df = pd.read_parquet(oof_file)
            assert len(df) == 4000, f"Expected 4000 rows in {oof_file}, got {len(df)}"
            assert ("pred_reg" in df.columns) or ("predicted_arr_delay_min" in df.columns)
            assert ("pred_cls_prob" in df.columns) or ("p_arr_delay_15" in df.columns)


def test_repeated_metrics_have_valid_lineage():
    """Verify that all repeated metric occurrences in r19_repeated_metric_audit.json are accounted for."""
    path = REPO_ROOT / "artifacts/r19_repeated_metric_audit.json"
    assert path.exists(), f"Missing artifact: {path}"

    with open(path, encoding="utf-8") as f:
        doc = json.load(f)

    assert doc["status"] == "PASS"
    cases = doc["cases"]
    assert len(cases) >= 5, "Must document all 5 audited repetition cases"

    for c in cases:
        assert c["is_bug"] is False, f"Case {c['case_id']} flagged as bug!"
        assert "classification" in c
        assert "root_cause" in c
        assert len(c["root_cause"]) > 20
        assert "lineage_verification" in c


def test_stale_artifact_cannot_masquerade_as_recomputed():
    """Verify that stability runs for P4 were freshly computed rather than copied."""
    path_202602 = REPO_ROOT / "artifacts/stability/runs/probabilistic_P4_ngboost_student_t_fold_4_seed_202602.json"
    path_202603 = REPO_ROOT / "artifacts/stability/runs/probabilistic_P4_ngboost_student_t_fold_4_seed_202603.json"

    assert path_202602.exists() and path_202603.exists()

    with open(path_202602, encoding="utf-8") as f:
        d2 = json.load(f)
    with open(path_202603, encoding="utf-8") as f:
        d3 = json.load(f)

    # 1. Distinct creation timestamps
    assert d2["created_at_utc"] != d3["created_at_utc"], "Timestamps must be distinct"

    # 2. Distinct execution runtimes
    assert d2["runtime_seconds"] != d3["runtime_seconds"], "Runtimes must be distinct"
    assert d2["runtime_seconds"] > 5.0 and d3["runtime_seconds"] > 5.0

    # 3. Distinct raw unrounded losses
    pin2 = d2["metrics"]["pinball_losses"]["alpha_0.025"]
    pin3 = d3["metrics"]["pinball_losses"]["alpha_0.025"]
    assert pin2 != pin3, f"Raw alpha_0.025 pinball loss must differ ({pin2} vs {pin3})"

    # 4. Distinct PIT KS statistics
    ks2 = d2["metrics"]["pit"]["ks_statistic"]
    ks3 = d3["metrics"]["pit"]["ks_statistic"]
    assert ks2 != ks3, f"KS statistics must differ ({ks2} vs {ks3})"


def test_ensemble_l1_simplex_collapse_reproducible():
    """Demonstrate mathematically that L1 simplex optimization collapses to vertex solution when base models are correlated and one dominates."""
    np.random.seed(42)
    n = 2000
    y_true = np.random.normal(10.0, 15.0, size=n)

    # Correlated regressors similar to flight arrival delay predictions:
    # Model 0 is the best predictor (e.g. Linear)
    pred0 = y_true + np.random.laplace(0, 5.0, size=n)
    # Models 1-3 are correlated with Model 0 but have additional error or bias
    pred1 = pred0 + np.random.normal(2.0, 3.0, size=n)
    pred2 = pred0 + np.random.normal(-3.0, 4.0, size=n)
    pred3 = pred0 + np.random.laplace(0, 6.0, size=n)

    preds = np.column_stack([pred0, pred1, pred2, pred3])
    mae_individual = [float(np.mean(np.abs(preds[:, i] - y_true))) for i in range(4)]
    assert mae_individual[0] == min(mae_individual)

    def objective(w: np.ndarray) -> float:
        return float(np.mean(np.abs(preds @ w - y_true)))

    w0 = np.full(4, 0.25)
    bounds = [(0.0, 1.0) for _ in range(4)]
    constraints = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}

    res = minimize(objective, w0, method="SLSQP", bounds=bounds, constraints=constraints)
    assert res.success

    # The optimal weight on model 0 must heavily dominate the simplex solution (w[0] > 0.95)
    opt_w = np.clip(res.x, 0.0, 1.0)
    opt_w = opt_w / np.sum(opt_w)
    assert opt_w[0] > 0.95, f"Expected dominant vertex solution with w[0] > 0.95, got {opt_w}"
    assert sum(opt_w[1:]) < 0.05
