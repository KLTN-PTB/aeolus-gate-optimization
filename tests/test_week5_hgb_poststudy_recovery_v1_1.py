from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from scripts.recover_week5_hgb_hpo_v1_1 import (
    CLASSIFICATION_EVIDENCE_HASHES,
    INCIDENT_TYPE,
    RECOVERY_AMENDMENT_ID,
    ROOT_CAUSE,
    build_recovery_amendment_payload,
    continue_regression_only,
    verify_classification_adoption,
    verify_fresh_regression_paths,
)
from scripts.run_week5_hist_gradient_boosting_hpo_v1_1 import _build_result_payload
from src.models.week5_contracts import load_week5_study_specs
from src.models.week5_hpo_protocol import Week5ProtocolViolation
from src.models.week5_hpo_protocol_v1_1 import load_week5_hpo_protocol_v1_1


ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def test_real_completed_classification_is_adoptable_without_mutation() -> None:
    protocol = load_week5_hpo_protocol_v1_1(project_root=ROOT)
    db = ROOT / "artifacts/optuna_studies/week5_hpo_protocol_v1_1__hist_gradient_boosting_classification.sqlite3"
    before = _sha256(db)

    evidence = verify_classification_adoption(ROOT, protocol)

    assert evidence["direction"] == "MAXIMIZE"
    assert evidence["state_counts"] == {
        "RUNNING": 0,
        "COMPLETE": 10,
        "PRUNED": 0,
        "FAIL": 0,
        "WAITING": 0,
    }
    assert evidence["best_trial"]["number"] == 7
    assert evidence["best_trial"]["value"] == pytest.approx(0.19206058881695232)
    assert evidence["recomputed_objective"] == pytest.approx(0.19206058881695232)
    assert evidence["objective_match"] is True
    assert _sha256(db) == before == CLASSIFICATION_EVIDENCE_HASHES["sqlite_sha256"]


def test_recovery_amendment_records_nonstatistical_incident() -> None:
    protocol = load_week5_hpo_protocol_v1_1(project_root=ROOT)
    evidence = verify_classification_adoption(ROOT, protocol)

    payload = build_recovery_amendment_payload(protocol, evidence)

    assert payload["amendment_id"] == RECOVERY_AMENDMENT_ID
    assert payload["incident_type"] == INCIDENT_TYPE
    assert payload["root_cause"] == ROOT_CAUSE
    assert payload["classification_rerun"] is False
    assert payload["classification_resume"] is False
    assert payload["classification_new_trials"] == 0
    assert payload["regression_started_before_failure"] is False
    assert payload["statistical_protocol_changed"] is False
    assert payload["model_results_changed"] is False
    assert payload["row_level_2023_accessed"] is False
    assert payload["row_level_2024_accessed"] is False


def test_classification_recovery_result_payload_marks_adoption_not_new_hpo() -> None:
    protocol = load_week5_hpo_protocol_v1_1(project_root=ROOT)
    spec = load_week5_study_specs(protocol)["hist_gradient_boosting_classification"]
    evidence = verify_classification_adoption(ROOT, protocol)

    payload = _build_result_payload(
        ROOT,
        protocol,
        spec,
        {"status": "COMPLETED", "resource_samples": []},
        recovery_amendment_id=RECOVERY_AMENDMENT_ID,
        generated_from_existing_completed_study=True,
        new_hpo_performed=False,
    )

    assert payload["recovery_amendment_id"] == RECOVERY_AMENDMENT_ID
    assert payload["generated_from_existing_completed_study"] is True
    assert payload["new_hpo_performed"] is False
    assert payload["new_training_performed"] is False
    assert payload["classification_rerun"] is False
    assert payload["classification_new_trials"] == 0
    assert payload["actual_trial_states"]["COMPLETE"] == 10
    assert payload["best_trial"] == 7
    assert payload["best_objective"] == pytest.approx(
        evidence["recomputed_objective"]
    )
    assert payload["objective_match"] is True
    assert payload["pruner"] == "NopPruner"
    assert payload["sampler"] == "TPESampler"


def test_continuation_can_invoke_only_regression() -> None:
    calls: list[str] = []

    outcome = continue_regression_only(
        lambda study_id: calls.append(study_id) or {"status": "COMPLETED"}
    )

    assert outcome == {"status": "COMPLETED"}
    assert calls == ["hist_gradient_boosting_regression"]


@pytest.mark.parametrize(
    "suffix",
    [".sqlite3", ".execution.jsonl", ".guard.jsonl"],
)
def test_regression_preflight_fails_closed_on_any_collision(
    tmp_path: Path, suffix: str
) -> None:
    protocol = load_week5_hpo_protocol_v1_1(project_root=ROOT)
    target = tmp_path / "artifacts/optuna_studies" / (
        "week5_hpo_protocol_v1_1__hist_gradient_boosting_regression" + suffix
    )
    target.parent.mkdir(parents=True)
    target.write_bytes(b"unexpected")

    with pytest.raises(Week5ProtocolViolation, match="Regression artifact collision"):
        verify_fresh_regression_paths(tmp_path, protocol)
