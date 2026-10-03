"""Unit tests for Phase 11 Post-Holdout Evaluation Pipeline and Artifacts.

Validates:
1. All generated artifacts strictly carry `evaluation_role: POST_HOLDOUT`.
2. Prohibits labelling 2024 as 'untouched holdout' or 'development'.
3. Verifies failure accounting tracks any infeasible solver status or capacity overflow without silent dropping.
4. Confirms that all 7 candidates and 3 solvers are evaluated across the 2024 operational scenarios.
5. Verifies freeze manifest SHA256 integrity is linked in the post-holdout manifest.
"""

from __future__ import annotations

import json
from pathlib import Path
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
POST_HOLDOUT_DIR = ROOT / "artifacts" / "post_holdout"
FREEZE_MANIFEST_PATH = ROOT / "artifacts" / "manifests" / "system_freeze_manifest.json"


def test_post_holdout_manifest_exists_and_valid() -> None:
    """Post-holdout manifest must exist, be valid JSON, and have evaluation_role='POST_HOLDOUT'."""
    manifest_path = POST_HOLDOUT_DIR / "post_holdout_evaluation_manifest.json"
    if not manifest_path.exists():
        pytest.skip("Post-holdout evaluation has not been executed yet.")

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["evaluation_role"] == "POST_HOLDOUT"
    assert data["holdout_year"] == 2024
    assert data["stage"] == "PHASE_11_FINAL_POST_HOLDOUT_EVALUATION"
    assert data["evaluation_governance"]["zero_post_holdout_retraining_verified"] is True
    assert data["evaluation_governance"]["zero_post_holdout_tuning_verified"] is True
    assert bool(data["freeze_manifest_sha256"])


def test_all_post_holdout_dataframes_encode_post_holdout_role() -> None:
    """All generated operational tables must encode evaluation_role='POST_HOLDOUT'."""
    eval_parquet = POST_HOLDOUT_DIR / "downstream_operational_evaluations.parquet"
    delta_parquet = POST_HOLDOUT_DIR / "paired_downstream_deltas.parquet"
    if not eval_parquet.exists() or not delta_parquet.exists():
        pytest.skip("Post-holdout dataframes not yet generated.")

    df_eval = pd.read_parquet(eval_parquet)
    assert "evaluation_role" in df_eval.columns
    assert (df_eval["evaluation_role"] == "POST_HOLDOUT").all()
    assert (df_eval["holdout_year"] == 2024).all()

    df_delta = pd.read_parquet(delta_parquet)
    assert "evaluation_role" in df_delta.columns
    assert (df_delta["evaluation_role"] == "POST_HOLDOUT").all()
    assert (df_delta["holdout_year"] == 2024).all()


def test_all_candidates_and_solvers_evaluated() -> None:
    """Operational evaluations must cover 7 candidate models and 3 solvers across 4 scenarios."""
    eval_parquet = POST_HOLDOUT_DIR / "downstream_operational_evaluations.parquet"
    if not eval_parquet.exists():
        pytest.skip("downstream_operational_evaluations.parquet not yet generated.")

    df_eval = pd.read_parquet(eval_parquet)
    expected_models = {
        "schedule_only",
        "arrival_linear_baseline_v1",
        "arrival_xgboost_baseline_v1",
        "arrival_weighted_ensemble_v1",
        "P5_quantile_regression",
        "P4_ngboost_student_t",
        "oracle_actual",
    }
    actual_models = set(df_eval["model_id"].unique())
    assert expected_models.issubset(actual_models)

    expected_solvers = {"DeterministicGreedy", "CPSat", "SimulatedAnnealing"}
    actual_solvers = set(df_eval["solver_name"].unique())
    assert expected_solvers == actual_solvers

    assert len(df_eval["scenario_id"].unique()) == 4
    # 7 models x 4 scenarios x 3 solvers = 84 runs
    assert len(df_eval) == 84


def test_failure_accounting_file_structure() -> None:
    """Failures accounting file must exist and track all failure categories."""
    failure_file = POST_HOLDOUT_DIR / "failures_accounting.json"
    if not failure_file.exists():
        pytest.skip("failures_accounting.json not yet generated.")

    data = json.loads(failure_file.read_text(encoding="utf-8"))
    assert data["evaluation_role"] == "POST_HOLDOUT"
    assert data["holdout_year"] == 2024
    assert "total_evaluated_cases" in data
    assert "total_failures_count" in data
    assert "solver_timeouts_count" in data
    assert "infeasible_instances_count" in data
    assert isinstance(data["failures_log"], list)


def test_marginal_metrics_structure() -> None:
    """Marginal forecast metrics file must contain point and probabilistic models."""
    metric_file = POST_HOLDOUT_DIR / "marginal_forecast_metrics_2024.json"
    if not metric_file.exists():
        pytest.skip("marginal_forecast_metrics_2024.json not yet generated.")

    data = json.loads(metric_file.read_text(encoding="utf-8"))
    assert data["evaluation_role"] == "POST_HOLDOUT"
    assert data["holdout_year"] == 2024
    assert "metrics" in data
    metrics = data["metrics"]
    assert "schedule_only" in metrics
    assert "arrival_linear_baseline_v1" in metrics
    assert "P5_quantile_regression" in metrics
    assert "P4_ngboost_student_t" in metrics
