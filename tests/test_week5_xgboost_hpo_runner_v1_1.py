from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import optuna
import pytest

import scripts.run_week5_xgboost_hpo_v1_1 as xgb_runner
from scripts.run_week5_xgboost_hpo_v1_1 import (
    XGB_STUDY_IDS,
    _sqlite_state_evidence,
    explicit_guard_cleanup_success,
    preflight_v1_1,
    run_and_materialize_xgboost_sequence,
    run_xgboost_sequence,
)
from src.models.week5_hpo_protocol import Week5ProtocolViolation
from src.models.week5_hpo_protocol_v1_1 import (
    deterministic_v1_1_storage_path,
    load_week5_hpo_protocol_v1_1,
)


def test_xgboost_sequence_never_starts_regression_after_invalid_classification() -> None:
    called: list[str] = []

    def run_study(study_id: str) -> dict[str, str]:
        called.append(study_id)
        return {"status": "ENVIRONMENTAL_EXECUTION_INVALID"}

    assert run_xgboost_sequence(run_study) == [{"status": "ENVIRONMENTAL_EXECUTION_INVALID"}]
    assert called == ["xgboost_classification"]
    assert XGB_STUDY_IDS == ("xgboost_classification", "xgboost_regression")


def test_xgboost_sequence_materializes_classification_before_regression() -> None:
    events: list[str] = []

    def run_study(study_id: str) -> dict[str, str]:
        events.append(f"run:{study_id}")
        return {"status": "COMPLETED"}

    def materialize(study_id: str, _outcome: dict[str, str]) -> None:
        events.append(f"manifest:{study_id}")

    run_and_materialize_xgboost_sequence(run_study, materialize)

    assert events == [
        "run:xgboost_classification",
        "manifest:xgboost_classification",
        "run:xgboost_regression",
        "manifest:xgboost_regression",
    ]


def test_xgboost_preflight_rejects_any_storage_or_journal_collision(tmp_path: Path) -> None:
    protocol = load_week5_hpo_protocol_v1_1()
    storage = deterministic_v1_1_storage_path(tmp_path, "xgboost_classification")
    storage.parent.mkdir(parents=True)
    storage.with_suffix(".guard.jsonl").write_text("{}\n", encoding="utf-8")

    with pytest.raises(Week5ProtocolViolation, match="collision"):
        preflight_v1_1(tmp_path, protocol)


def test_xgboost_cleanup_success_requires_study_scoped_explicit_event(tmp_path: Path) -> None:
    journal = tmp_path / "classification.guard.jsonl"
    journal.write_text(
        json.dumps(
            {
                "timestamp_utc": "2026-09-17T00:00:00+00:00",
                "protocol_version": "week5_hpo_protocol_v1_1",
                "study_id": "xgboost_classification",
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
        study_id="xgboost_classification",
    )

    assert evidence["status"] == "EXPLICIT_PASS"


@pytest.mark.parametrize(
    ("direction", "expected"), [("maximize", "MAXIMIZE"), ("minimize", "MINIMIZE")]
)
def test_xgboost_completed_study_reader_uses_optuna_public_api(
    tmp_path: Path, direction: str, expected: str
) -> None:
    storage_path = tmp_path / f"{direction}.sqlite3"
    study_name = f"temporary_{direction}"
    storage = f"sqlite:///{storage_path.as_posix()}"
    study = optuna.create_study(study_name=study_name, storage=storage, direction=direction)

    def objective(trial: optuna.Trial) -> float:
        value = trial.suggest_float("value", 0.1, 0.9)
        trial.set_user_attr("per_fold_objective", [value] * 4)
        return value

    study.optimize(objective, n_trials=2)
    with sqlite3.connect(storage_path) as connection:
        assert "direction" not in {
            row[1] for row in connection.execute("PRAGMA table_info(studies)").fetchall()
        }

    evidence = _sqlite_state_evidence(storage_path, study_name)

    assert evidence["direction"] == expected
    assert evidence["state_counts"]["COMPLETE"] == 2
    assert evidence["best_trial"]["value"] == study.best_value
    assert len(evidence["trials"]) == 2


def test_active_runner_detection_ignores_current_process_ancestry(
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

    monkeypatch.setattr(xgb_runner.psutil, "Process", lambda: CurrentProcess())
    monkeypatch.setattr(
        xgb_runner.psutil,
        "process_iter",
        lambda _attrs: [
            Process(99, "uv run python scripts/run_week5_xgboost_hpo_v1_1.py --preflight"),
            Process(101, "unrelated command"),
        ],
    )

    assert xgb_runner._active_xgb_runner() is False
