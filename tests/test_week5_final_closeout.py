from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from scripts.materialize_week5_final_closeout import (
    build_week5_closeout,
    render_week5_report,
    validate_study_contract,
    validate_week6_boundary,
)


def _valid_studies() -> list[dict[str, object]]:
    studies: list[dict[str, object]] = []
    for method in ("random_forest", "hist_gradient_boosting", "xgboost"):
        for task, direction in (
            ("classification", "MAXIMIZE"),
            ("regression", "MINIMIZE"),
        ):
            studies.append(
                {
                    "method": method,
                    "task": task,
                    "direction": direction,
                    "complete_trials": 10,
                    "failed_trials": 0,
                    "running_trials": 0,
                    "protocol_version": "week5_hpo_protocol_v1_1",
                    "protocol_hash": "b987c0489c5d18b02500f34c786c01359f45e50b2b32bdea3de4332a161556e5",
                    "sampler": "TPESampler",
                    "seed": 202601,
                    "pruner": "NopPruner",
                    "n_jobs": 1,
                    "timeout_seconds_per_study": 14400,
                    "objective_match": True,
                    "cleanup": (
                        "ACCEPTED_VIA_NON_STATISTICAL_AMENDMENT"
                        if method == "random_forest"
                        else "GUARD_CLEANUP_SUCCESS"
                    ),
                }
            )
    return studies


def test_closeout_requires_exactly_six_complete_studies() -> None:
    studies = _valid_studies()
    studies[0]["complete_trials"] = 9

    with pytest.raises(RuntimeError, match="10 COMPLETE"):
        validate_study_contract(studies)


def test_closeout_requires_direct_hgb_xgb_cleanup() -> None:
    studies = _valid_studies()
    studies[2]["cleanup"] = "INFERRED_ONLY"

    with pytest.raises(RuntimeError, match="GUARD_CLEANUP_SUCCESS"):
        validate_study_contract(studies)


def test_closeout_rejects_started_week6_work() -> None:
    boundary = {
        "weighted_ensemble_started": False,
        "selection_2023_started": False,
        "shap_started": False,
        "arr_ablation_started": False,
        "dep_weather_ablation_started": False,
        "core_champion_selected": False,
    }
    boundary["weighted_ensemble_started"] = True

    with pytest.raises(RuntimeError, match="Week 6"):
        validate_week6_boundary(boundary)


def test_report_labels_metrics_as_development_only() -> None:
    summary = {
        "week5_final_status": "PASS",
        "protocol": {"version": "week5_hpo_protocol_v1_1", "hash": "abc"},
        "studies": [],
        "oof": {"methods": {}, "common_rows": 1_254_518},
        "temporal": {},
        "week6_boundary": {},
        "limitations": [],
    }

    report = render_week5_report(summary)

    assert "development OOF" in report
    assert "not final test results" in report


def test_production_week5_evidence_satisfies_closeout_contract() -> None:
    summary = build_week5_closeout(Path("."))

    assert summary["week5_final_status"] == "PASS"
    assert len(summary["studies"]) == 6
    assert all(study["complete_trials"] == 10 for study in summary["studies"])
    assert summary["oof"]["common_rows"] == 1_254_518
    assert summary["oof"]["row_parity"] == "PASS"
    assert summary["oof"]["target_parity"] == "PASS"
    assert not any(summary["week6_boundary"].values())
