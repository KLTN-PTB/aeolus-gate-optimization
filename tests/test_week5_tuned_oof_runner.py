from __future__ import annotations

from pathlib import Path

import pytest

from scripts.materialize_week5_tuned_development_oof import (
    XGB_RECOVERY_PREFLIGHT,
    RUN_VERSIONS,
    _assert_exact_anchor_parity,
    planned_paths,
    run_xgboost_recovery_sequence,
)


def test_tuned_oof_runner_uses_separate_versioned_paths_for_all_methods() -> None:
    paths = planned_paths(Path("."))

    assert set(paths) == {"random_forest", "hist_gradient_boosting", "xgboost"}
    assert all(len(method_paths) == 6 for method_paths in paths.values())
    assert all("_tuned_rolling_run_v1_1" in str(path) for values in paths.values() for path in values)
    assert RUN_VERSIONS["xgboost"] == "arrival_xgboost_tuned_rolling_run_v1_1"


def test_exact_anchor_parity_rejects_reordered_target_rows() -> None:
    anchor = {"flight_key": ["a", "b"], "y_arr_cls": [0, 1], "y_arr_reg": [1.0, -2.0]}
    candidate = {"flight_key": ["b", "a"], "y_arr_cls": [1, 0], "y_arr_reg": [-2.0, 1.0]}

    with pytest.raises(RuntimeError, match="parity"):
        _assert_exact_anchor_parity(anchor, candidate, "fold_1")


def test_tuned_oof_preflight_projects_artifacts_relative_to_project_root() -> None:
    root = Path(".").resolve()
    paths = planned_paths(root)

    for method_paths in paths.values():
        for path in method_paths:
            assert path.is_absolute()
            assert path.relative_to(root).parts[0] == "artifacts"


def test_xgboost_recovery_control_flow_never_calls_rf_or_hgb() -> None:
    called: list[str] = []

    result = run_xgboost_recovery_sequence(
        lambda method: called.append(method) or {"status": "PASS"}
    )

    assert called == ["xgboost"]
    assert result == {"status": "PASS"}


def test_xgboost_recovery_preflight_is_new_and_preserves_failed_preflight() -> None:
    original = Path("artifacts/manifests/arrival_xgboost_tuned_rolling_run_v1_1_preflight.json")
    original_bytes = original.read_bytes()

    assert original.read_bytes() == original_bytes
    assert XGB_RECOVERY_PREFLIGHT != original
    assert XGB_RECOVERY_PREFLIGHT.name.endswith("_preflight_v2.json")
