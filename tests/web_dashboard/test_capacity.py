import pandas as pd
import pytest

from web_dashboard.contracts import RunRequest
from web_dashboard.normalization import normalize_files
from web_dashboard.pipeline import run_pipeline


@pytest.mark.parametrize("solver", ["greedy", "cpsat", "hybrid"])
@pytest.mark.parametrize("remote", [0, 1])
def test_finite_capacity_and_no_fake_complete_solution(tmp_path, raw_table, solver, remote):
    # Two overlapping inbound-only occupancies require exactly two positions.
    raw_table = pd.concat([raw_table.head(1), raw_table.head(1)], ignore_index=True)
    raw_table.loc[1, "OP_CARRIER_FL_NUM"] = 999
    raw_table["TAIL_NUM"] = None
    raw = tmp_path / "raw.parquet"
    raw_table.to_parquet(raw, index=False)
    frame, report = normalize_files([raw])
    request = RunRequest(dataset_id="a" * 32, service_date="2026-07-01", preset="custom", contact_gates=1,
                         remote_gates=remote, solver=solver, time_limit_sec=1)
    result = run_pipeline(frame, request, tmp_path / "run", report)
    assert result["summary"]["feasible"] == bool(remote)
    if remote:
        assert result["summary"]["remote_count"] == 1
        assert result["summary"]["independent_verifier_valid"]
        assert {a["gate_id"] for a in result["assignments"]} == {"G001", "R001"}
    else:
        assert result["assignments"] == []
        assert result["summary"]["decision_cost"] is None
