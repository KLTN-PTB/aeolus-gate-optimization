from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import optuna
import pytest
import scripts.run_week5_hist_gradient_boosting_hpo_v1_1 as hgb_runner

from scripts.run_week5_hist_gradient_boosting_hpo_v1_1 import (
    HGB_STUDY_IDS,
    _sqlite_state_evidence,
    explicit_guard_cleanup_success,
    preflight_v1_1,
    run_and_materialize_hgb_sequence,
    run_hgb_sequence,
)
from src.models.week5_hpo_protocol import Week5ProtocolViolation
from src.models.week5_hpo_protocol_v1_1 import (
    deterministic_v1_1_storage_path,
    load_week5_hpo_protocol_v1_1,
)


def test_hgb_sequence_never_starts_regression_after_invalid_classification() -> None:
    called: list[str] = []

    def run_study(study_id: str) -> dict[str, str]:
        called.append(study_id)
        return {"status": "ENVIRONMENTAL_EXECUTION_INVALID"}

    assert run_hgb_sequence(run_study) == [{"status": "ENVIRONMENTAL_EXECUTION_INVALID"}]
    assert called == ["hist_gradient_boosting_classification"]
    assert HGB_STUDY_IDS == (
        "hist_gradient_boosting_classification",
        "hist_gradient_boosting_regression",
    )


def test_hgb_sequence_materializes_classification_before_regression() -> None:
    events: list[str] = []

    def run_study(study_id: str) -> dict[str, str]:
        events.append(f"run:{study_id}")
        return {"status": "COMPLETED"}

    def materialize(study_id: str, _outcome: dict[str, str]) -> None:
        events.append(f"manifest:{study_id}")

    run_and_materialize_hgb_sequence(run_study, materialize)

    assert events == [
        "run:hist_gradient_boosting_classification",
        "manifest:hist_gradient_boosting_classification",
        "run:hist_gradient_boosting_regression",
        "manifest:hist_gradient_boosting_regression",
    ]


def test_hgb_preflight_rejects_any_storage_or_journal_collision(tmp_path: Path) -> None:
    protocol = load_week5_hpo_protocol_v1_1()
    storage = deterministic_v1_1_storage_path(tmp_path, "hist_gradient_boosting_classification")
    storage.parent.mkdir(parents=True)
    storage.with_suffix(".guard.jsonl").write_text("{}\n", encoding="utf-8")

    with pytest.raises(Week5ProtocolViolation, match="collision"):
        preflight_v1_1(tmp_path, protocol)


def test_cleanup_success_requires_study_scoped_explicit_event(tmp_path: Path) -> None:
    journal = tmp_path / "classification.guard.jsonl"
    journal.write_text(
        json.dumps(
            {
                "timestamp_utc": "2026-09-17T00:00:00+00:00",
                "protocol_version": "week5_hpo_protocol_v1_1",
                "study_id": "hist_gradient_boosting_classification",
                "event": "GUARD_CLEANUP_SUCCESS",
                "requested_flags": 2147483648,
                "set_thread_execution_state_return_value": 1,
                "success": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    evidence = explicit_guard_cleanup_success(
        journal,
        protocol_version="week5_hpo_protocol_v1_1",
        study_id="hist_gradient_boosting_classification",
    )

    assert evidence["status"] == "EXPLICIT_PASS"
    assert evidence["event"]["requested_flags"] == 2147483648


def test_cleanup_success_rejects_inferred_or_wrong_study_event(tmp_path: Path) -> None:
    journal = tmp_path / "classification.guard.jsonl"
    journal.write_text(
        json.dumps(
            {
                "timestamp_utc": "2026-09-17T00:00:00+00:00",
                "protocol_version": "week5_hpo_protocol_v1_1",
                "study_id": "other",
                "event": "GUARD_CLEANUP_SUCCESS",
                "requested_flags": 2147483648,
                "set_thread_execution_state_return_value": 1,
                "success": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(Week5ProtocolViolation, match="cleanup"):
        explicit_guard_cleanup_success(
            journal,
            protocol_version="week5_hpo_protocol_v1_1",
            study_id="hist_gradient_boosting_classification",
        )


def test_active_runner_detection_ignores_the_current_process_ancestry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Process:
        def __init__(self, pid: int, command: str) -> None:
            self.info = {"pid": pid, "cmdline": [command]}

    class CurrentProcess:
        pid = 100

        @staticmethod
        def parents() -> list[object]:
            return [type("Parent", (), {"pid": 99})()]

    monkeypatch.setattr(hgb_runner.psutil, "Process", lambda: CurrentProcess())
    monkeypatch.setattr(
        hgb_runner.psutil,
        "process_iter",
        lambda _attrs: [
            Process(99, "uv run python scripts/run_week5_hist_gradient_boosting_hpo_v1_1.py --preflight"),
            Process(101, "unrelated command"),
        ],
    )

    assert hgb_runner._active_hgb_runner() is False


@pytest.mark.parametrize(
    ("direction", "expected"),
    [("maximize", "MAXIMIZE"), ("minimize", "MINIMIZE")],
)
def test_completed_study_reader_uses_optuna_semantics_not_studies_direction(
    tmp_path: Path, direction: str, expected: str
) -> None:
    storage_path = tmp_path / f"{direction}.sqlite3"
    study_name = f"temporary_{direction}"
    storage = f"sqlite:///{storage_path.as_posix()}"
    study = optuna.create_study(
        study_name=study_name,
        storage=storage,
        direction=direction,
    )

    def objective(trial: optuna.Trial) -> float:
        value = trial.suggest_float("value", 0.1, 0.9)
        trial.set_user_attr("per_fold_objective", [value] * 4)
        trial.set_user_attr("audit_marker", "present")
        return value

    study.optimize(objective, n_trials=2)
    with sqlite3.connect(storage_path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(studies)").fetchall()
        }
    assert "direction" not in columns

    evidence = _sqlite_state_evidence(storage_path, study_name)

    assert evidence["direction"] == expected
    assert evidence["state_counts"] == {
        "RUNNING": 0,
        "COMPLETE": 2,
        "PRUNED": 0,
        "FAIL": 0,
        "WAITING": 0,
    }
    assert evidence["best_trial"]["number"] in {0, 1}
    assert evidence["best_trial"]["value"] == study.best_value
    assert evidence["best_trial"]["params"] == study.best_params
    assert evidence["best_trial"]["user_attrs"]["audit_marker"] == "present"
    assert evidence["best_trial"]["datetime_start"] is not None
    assert evidence["best_trial"]["datetime_complete"] is not None
    assert len(evidence["trials"]) == 2
    assert all(item["state"] == "COMPLETE" for item in evidence["trials"])
    assert all(item["datetime_start"] is not None for item in evidence["trials"])
    assert all(item["datetime_complete"] is not None for item in evidence["trials"])
    assert all(item["user_attrs"]["audit_marker"] == "present" for item in evidence["trials"])
