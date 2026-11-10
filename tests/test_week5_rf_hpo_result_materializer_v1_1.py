from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.materialize_week5_rf_hpo_results_v1_1 import (
    ProvenanceRepairError,
    build_post_run_payloads,
    classify_guard_cleanup_evidence,
    materialize_post_run_payloads,
)


ROOT = Path(__file__).resolve().parents[1]
CLASSIFICATION_DB = ROOT / "artifacts/optuna_studies" / (
    "week5_hpo_protocol_v1_1__random_forest_classification.sqlite3"
)
REGRESSION_DB = ROOT / "artifacts/optuna_studies" / (
    "week5_hpo_protocol_v1_1__random_forest_regression.sqlite3"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize(
    ("events", "clean_exit", "expected"),
    [
        ([{"guard_cleanup_success": True}], True, "EXPLICIT_PASS"),
        ([], True, "INFERRED_ONLY"),
        ([], False, "NOT_FOUND"),
        ([{"guard_cleanup_success": False}], True, "EXPLICIT_FAILURE"),
    ],
)
def test_cleanup_evidence_classification_preserves_evidence_strength(
    events: list[dict[str, object]], clean_exit: bool, expected: str
) -> None:
    """Catches inferred cleanup being promoted to explicit evidence."""

    assert classify_guard_cleanup_evidence(events, clean_exit=clean_exit) == expected


def test_payloads_match_existing_sqlite_without_mutating_production_evidence() -> None:
    """Catches changed objectives/trials or writes to immutable production DBs."""

    before = (_sha256(CLASSIFICATION_DB), _sha256(REGRESSION_DB))

    payloads = build_post_run_payloads(ROOT)

    after = (_sha256(CLASSIFICATION_DB), _sha256(REGRESSION_DB))
    classification = payloads["classification"]
    regression = payloads["regression"]
    assert after == before
    assert classification["best_trial"] == 9
    assert classification["best_objective"] == 0.18856511611502808
    assert classification["recomputed_objective"] == 0.18856511611502808
    assert classification["objective_match"] is True
    assert classification["complete_trials"] == 10
    assert regression["best_trial"] == 3
    assert regression["best_objective"] == 19.25971111931776
    assert regression["recomputed_objective"] == 19.25971111931776
    assert regression["objective_match"] is True
    assert regression["complete_trials"] == 10


def test_protocol_provenance_uses_frozen_constructor_not_reloaded_study_pruner() -> None:
    """Catches treating Optuna's non-persisted reload default as runtime provenance."""

    payloads = build_post_run_payloads(ROOT)

    for result in (payloads["classification"], payloads["regression"]):
        assert result["sampler"] == "TPESampler"
        assert result["seed"] == 202601
        assert result["pruner"] == "NopPruner"
        assert result["n_jobs"] == {"optuna": 1, "random_forest": 1}
        assert result["timeout_seconds_per_study"] == 14400
        assert result["sqlite_pruner_metadata"] == "NOT_PERSISTED_NOT_AUTHORITATIVE"
        assert "reloaded_study.pruner" not in result["pruner_evidence_source"]


def test_materializer_has_no_training_hpo_or_blocked_year_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catches provenance repair accidentally invoking HPO, models, or data access."""

    import optuna
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
    from src.data import access_guard

    forbidden = lambda *args, **kwargs: pytest.fail("production action was invoked")
    monkeypatch.setattr(optuna.study.Study, "optimize", forbidden)
    monkeypatch.setattr(RandomForestClassifier, "fit", forbidden)
    monkeypatch.setattr(RandomForestClassifier, "predict_proba", forbidden)
    monkeypatch.setattr(RandomForestRegressor, "fit", forbidden)
    monkeypatch.setattr(RandomForestRegressor, "predict", forbidden)
    monkeypatch.setattr(access_guard, "assert_data_access_allowed", forbidden)

    payloads = build_post_run_payloads(ROOT)

    for result in (payloads["classification"], payloads["regression"]):
        assert result["row_level_2023_accessed"] is False
        assert result["row_level_2024_accessed"] is False
        assert result["new_training_performed"] is False
        assert result["new_hpo_performed"] is False


def test_materialization_is_immutable_reusable_and_conflicts_fail_closed(
    tmp_path: Path,
) -> None:
    """Catches silent overwrite of completed result or summary artifacts."""

    payloads = build_post_run_payloads(ROOT)

    first = materialize_post_run_payloads(payloads, output_directory=tmp_path)
    second = materialize_post_run_payloads(payloads, output_directory=tmp_path)
    assert set(first.values()) == {"CREATED"}
    assert set(second.values()) == {"REUSE"}

    target = tmp_path / (
        "week5_hpo_protocol_v1_1__random_forest_classification_result_v1.json"
    )
    conflict = json.loads(target.read_text(encoding="utf-8"))
    conflict["best_trial"] = 0
    target.write_text(json.dumps(conflict), encoding="utf-8")
    with pytest.raises(ProvenanceRepairError, match="conflicting immutable artifact"):
        materialize_post_run_payloads(payloads, output_directory=tmp_path)


def test_enriched_summary_references_both_results_and_keeps_cleanup_inferred() -> None:
    """Catches incomplete summary provenance or fabricated cleanup success."""

    summary = build_post_run_payloads(ROOT)["summary"]

    assert summary["amendment_id"] == "week5_hpo_execution_amendment_v1"
    assert summary["statistical_protocol_changed"] is False
    assert summary["execution_protocol_changed"] is True
    assert summary["sampler"] == "TPESampler"
    assert summary["pruner"] == "NopPruner"
    assert summary["seed"] == 202601
    assert summary["n_jobs"] == {"optuna": 1, "random_forest": 1}
    assert summary["timeout_seconds_per_study"] == 14400
    assert summary["classification_result_manifest"].endswith(
        "random_forest_classification_result_v1.json"
    )
    assert summary["regression_result_manifest"].endswith(
        "random_forest_regression_result_v1.json"
    )
    assert summary["guard_cleanup_provenance"] == {
        "classification": "INFERRED_ONLY",
        "regression": "INFERRED_ONLY",
    }
    assert summary["provenance_complete"] is False


def test_summary_records_exact_serialized_result_manifest_hashes() -> None:
    """Catches canonical payload hashes being mislabeled as artifact byte hashes."""

    payloads = build_post_run_payloads(ROOT)
    summary = payloads["summary"]

    for task in ("classification", "regression"):
        encoded = (
            json.dumps(
                payloads[task], ensure_ascii=False, indent=2, sort_keys=True
            )
            + "\n"
        ).encode("utf-8")
        expected = hashlib.sha256(encoded).hexdigest()
        assert summary[f"{task}_result_manifest_sha256"] == expected
