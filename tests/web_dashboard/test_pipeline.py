import pandas as pd
import pytest

from web_dashboard.contracts import RunRequest
from web_dashboard.normalization import normalize_files
from web_dashboard.pipeline import ROOT, run_pipeline


@pytest.mark.skipif(not (ROOT / "artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib").exists(),
                    reason="Frozen native checkpoint not installed")
def test_native_e2e_and_outcomes_never_feed_predictions(tmp_path, raw_table):
    raw = tmp_path / "raw.parquet"
    raw_table.to_parquet(raw, index=False)
    frame, report = normalize_files([raw])
    request = RunRequest(dataset_id="a" * 32, service_date="2026-07-01", solver="greedy")
    result = run_pipeline(frame, request, tmp_path / "first", report)
    assert result["summary"]["movement_count"] == 4
    assert result["summary"]["occupancy_count"] == 3
    assert result["summary"]["assigned_count"] == 3
    assert result["summary"]["independent_verifier_valid"]
    assert result["summary"]["estimated_occupancies"] == 2
    assert all(p["provenance_mode"] == "NATIVE_INFERENCE" for p in result["predictions"])
    frame["ARR_DELAY"] = 10000
    frame["DEP_DELAY"] = -10000
    changed = run_pipeline(frame, request, tmp_path / "changed", report)
    assert [p["predicted_delay_min"] for p in result["predictions"]] == [p["predicted_delay_min"] for p in changed["predictions"]]
    assert result["assignments"] == changed["assignments"]
    assert (tmp_path / "first/bundle.zip").is_file()
    assert len(pd.read_parquet(tmp_path / "first/predictions.parquet")) == 4


@pytest.mark.parametrize("direction", ["ARR", "DEP"])
def test_single_direction_never_loses_legs(tmp_path, raw_table, direction):
    raw = tmp_path / "raw.parquet"
    rows = raw_table.loc[raw_table.DEST.eq("ATL") if direction == "ARR" else raw_table.ORIGIN.eq("ATL")]
    rows.to_parquet(raw, index=False)
    frame, report = normalize_files([raw])
    result = run_pipeline(frame, RunRequest(dataset_id="a" * 32, service_date="2026-07-01", solver="greedy"),
                          tmp_path / "run", report)
    assert len(result["predictions"]) == len(result["assignments"]) == 2


def test_fallback_is_not_presented_as_cp_sat_or_optimal(tmp_path, raw_table, monkeypatch):
    from dataclasses import replace
    from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver
    import web_dashboard.pipeline as module
    class BudgetedSolver:
        def __init__(self, config):
            assert config.cp_sat_fallback_to_greedy
            self.config = config
        def solve(self, flights, gates, **kwargs):
            greedy = DeterministicGreedyGateSolver(self.config).solve(flights, gates, **kwargs)
            return replace(greedy, solver_configuration={**greedy.solver_configuration,
                           "fallback_used": True, "raw_solver_status": "UNKNOWN"})
    monkeypatch.setattr(module, "CPSatGateSolver", BudgetedSolver)
    raw = tmp_path / "raw.parquet"
    raw_table.to_parquet(raw, index=False)
    frame, report = normalize_files([raw])
    result = run_pipeline(frame, RunRequest(dataset_id="a" * 32, service_date="2026-07-01"), tmp_path / "run", report)
    assert result["summary"]["fallback_used"]
    assert result["summary"]["actual_solver"] == "Deterministic Greedy (CP-SAT fallback)"
    assert not result["summary"]["optimality_proven"]
    assert result["summary"]["raw_solver_status"] == "UNKNOWN"
