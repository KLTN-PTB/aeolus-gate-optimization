from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

IMMUTABLE_HASHES = {
    "artifacts/optuna_studies/week5_hpo_protocol_v1_1__random_forest_classification.sqlite3": "32dfdfe6fda85b1fc966ad6f8f4b7de02d793b5afc1f152e2a6c706acbb7c3d6",
    "artifacts/optuna_studies/week5_hpo_protocol_v1_1__random_forest_regression.sqlite3": "e775984504831acaf050f7c4fdf1f3126882617ce52ead1f14d7416aa06082e7",
    "artifacts/optuna_studies/week5_hpo_protocol_v1_1__random_forest_classification.execution.jsonl": "7ef13c979d0155c06af665b04c98a62a9dbe8e896fcb1bb03e23fa2a05e3b319",
    "artifacts/optuna_studies/week5_hpo_protocol_v1_1__random_forest_regression.execution.jsonl": "ce92457a41a8af5b568cf43972daae1bb1d0df18ca38984fbfc74e7cd4fdb0ba",
    "artifacts/manifests/week5_hpo_protocol_v1_1__random_forest_classification_result_v1.json": "2eb072c1aa6691d30c3576b138230a226942f972738f0e05c21d1252ed4589a1",
    "artifacts/manifests/week5_hpo_protocol_v1_1__random_forest_regression_result_v1.json": "2192444e3495a6080752619001b88bd733e7c42b109ff5924f06418f18cce85d",
    "artifacts/manifests/week5_hpo_protocol_v1_1.json": "b7eed99fd42f5e6c907cb9fc57e0c48c8e53f1806134f91741a7042cd1e740a6",
    "configs/week5_hpo_v1_1.yaml": "bcb6263f8a030fc149d72f409a912b17f1b4db20c638eb50a396c959726b973a",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _complete_trials_read_only(relative_path: str) -> int:
    uri = (ROOT / relative_path).resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        return int(
            connection.execute(
                "SELECT COUNT(*) FROM trials WHERE state = 'COMPLETE'"
            ).fetchone()[0]
        )


def test_historical_rf_production_evidence_remains_byte_identical() -> None:
    for relative_path, expected_hash in IMMUTABLE_HASHES.items():
        assert _sha256(ROOT / relative_path) == expected_hash

    assert _complete_trials_read_only(
        "artifacts/optuna_studies/week5_hpo_protocol_v1_1__random_forest_classification.sqlite3"
    ) == 10
    assert _complete_trials_read_only(
        "artifacts/optuna_studies/week5_hpo_protocol_v1_1__random_forest_regression.sqlite3"
    ) == 10


def test_cleanup_amendment_preserves_historical_truth_and_postcondition() -> None:
    amendment = json.loads(
        (
            ROOT
            / "artifacts/manifests/week5_hpo_guard_cleanup_provenance_amendment_v1.json"
        ).read_text(encoding="utf-8")
    )

    assert amendment["amendment_id"] == "week5_hpo_guard_cleanup_provenance_amendment_v1"
    assert amendment["amendment_type"] == "NON_STATISTICAL_PROVENANCE_AMENDMENT"
    assert amendment["statistical_protocol_changed"] is False
    assert amendment["model_results_changed"] is False
    assert amendment["hpo_rerun"] is False
    assert amendment["new_trials_created"] is False
    assert amendment["historical_cleanup_provenance"] == "INFERRED_ONLY"
    assert amendment["explicit_cleanup_event_available"] is False
    assert amendment["cleanup_postcondition"] == "VERIFIED_CLEAR"
    assert amendment["post_exit_power_request_audit"]["system_execution_state"] == 0
    assert amendment["post_exit_power_request_audit"]["rf_process_active"] is False


def test_summary_v4_adds_resolution_without_rewriting_v3_statistics() -> None:
    v3 = json.loads(
        (ROOT / "artifacts/manifests/week5_random_forest_hpo_v1_1_summary_v3.json").read_text(
            encoding="utf-8"
        )
    )
    v4 = json.loads(
        (ROOT / "artifacts/manifests/week5_random_forest_hpo_v1_1_summary_v4.json").read_text(
            encoding="utf-8"
        )
    )

    for key in (
        "protocol_version",
        "protocol_hash",
        "sampler",
        "pruner",
        "seed",
        "n_jobs",
        "timeout_seconds_per_study",
        "studies",
        "row_level_2023_accessed",
        "row_level_2024_accessed",
    ):
        assert v4[key] == v3[key]
    assert v4["source_summary_v3_sha256"] == _sha256(
        ROOT / "artifacts/manifests/week5_random_forest_hpo_v1_1_summary_v3.json"
    )
    assert v4["explicit_historical_cleanup_event"] is False
    assert v4["historical_cleanup_status"] == "INFERRED_ONLY"
    assert v4["post_exit_cleanup_postcondition"] == "VERIFIED_CLEAR"
    assert v4["cleanup_acceptance"] == "ACCEPTED_VIA_NON_STATISTICAL_AMENDMENT"
    assert v4["future_cleanup_logging_required"] is True
