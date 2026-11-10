from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
import yaml

from src.data.access_guard import DataAccessDenied
from src.models.week5_hpo_protocol import canonical_protocol_hash
from src.models.week5_hpo_protocol_v1_1 import (
    EXPECTED_PROTOCOL_HASH,
    assert_hpo_year_allowed,
    load_week5_hpo_protocol_v1_1,
)


ROOT = Path(__file__).resolve().parents[1]
V1_CONFIG = ROOT / "configs" / "week5_hpo.yaml"
V1_1_CONFIG = ROOT / "configs" / "week5_hpo_v1_1.yaml"
V1_1_MANIFEST = ROOT / "artifacts" / "manifests" / "week5_hpo_protocol_v1_1.json"
AMENDMENT_MANIFEST = (
    ROOT / "artifacts" / "manifests" / "week5_hpo_execution_amendment_v1.json"
)
EXPERIMENT_LOG = ROOT / "docs" / "experiments" / "experiment_log.md"
FROZEN_V1_1_HASH = "b987c0489c5d18b02500f34c786c01359f45e50b2b32bdea3de4332a161556e5"


def _yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _statistical_projection(config: dict[str, Any]) -> dict[str, Any]:
    studies = deepcopy(config["studies"])
    for study in studies.values():
        study.pop("study_name")
    return {
        "task_contract": config["task_contract"],
        "scope_guards": config["scope_guards"],
        "dependencies": config["dependencies"],
        "folds": config["folds"],
        "data_contract": config["data_contract"],
        "budget": config["budget"],
        "randomness": config["randomness"],
        "objectives": config["objectives"],
        "studies": studies,
        "forbidden_tuning_dimensions": config["forbidden_tuning_dimensions"],
    }


def test_v1_1_preserves_the_complete_v1_statistical_protocol() -> None:
    """Catches any v1.1 change to budget, objectives, folds, or search spaces."""

    v1 = _yaml(V1_CONFIG)
    v1_1 = _yaml(V1_1_CONFIG)

    assert _statistical_projection(v1_1) == _statistical_projection(v1)
    assert v1_1["protocol_version"] == "week5_hpo_protocol_v1_1"
    assert v1_1["parent_protocol"] == {
        "version": "week5_hpo_protocol_v1",
        "hash": "b00ddf190776a12032b1e6b5b284beff8b48204017fe4c397140ac7a4da6844a",
    }
    assert [entry["study_name"] for entry in v1_1["studies"].values()] == [
        f"week5_hpo_protocol_v1_1__{study_id}" for study_id in v1_1["studies"]
    ]
    assert v1_1["execution"] == {
        "production_platform": "windows",
        "prevent_system_sleep": True,
        "heartbeat_interval_seconds": 30,
        "suspend_gap_threshold_seconds": 120,
        "suspend_detection": {
            "enabled": True,
            "state_on_detection": "ENVIRONMENTAL_EXECUTION_INVALID",
            "primary_active_time_source": "QueryUnbiasedInterruptTime",
        },
        "fresh_study_required": True,
        "parent_protocol_resume_forbidden": True,
        "parent_trials_carry_forward_forbidden": True,
        "non_windows_production_behavior": "FAIL_CLOSED",
    }


def test_v1_1_loader_recomputes_and_validates_the_frozen_manifest_hash() -> None:
    """Catches config drift or a hand-written/stale v1.1 protocol hash."""

    protocol = load_week5_hpo_protocol_v1_1(project_root=ROOT)

    assert EXPECTED_PROTOCOL_HASH == FROZEN_V1_1_HASH
    assert protocol.protocol_hash == FROZEN_V1_1_HASH
    assert canonical_protocol_hash(protocol.config) == FROZEN_V1_1_HASH
    assert protocol.manifest["protocol_sha256"] == FROZEN_V1_1_HASH
    assert protocol.manifest["parent_protocol_hash"] == (
        "b00ddf190776a12032b1e6b5b284beff8b48204017fe4c397140ac7a4da6844a"
    )
    assert protocol.manifest["studies"] == protocol.config["studies"]
    assert protocol.manifest["execution"] == protocol.config["execution"]
    assert protocol.manifest["statistical_protocol_changed"] is False
    assert protocol.manifest["execution_protocol_changed"] is True


def test_v1_1_hpo_guard_rejects_2023_and_2024() -> None:
    """Catches temporal leakage in the execution-amended protocol."""

    assert_hpo_year_allowed(2022)
    with pytest.raises(DataAccessDenied, match="HPO is blocked"):
        assert_hpo_year_allowed(2023)
    with pytest.raises(DataAccessDenied, match="HPO is blocked"):
        assert_hpo_year_allowed(2024)


def test_execution_amendment_manifest_is_factual_and_carries_no_v1_results() -> None:
    """Catches result-driven amendment fields and accidental v1 trial reuse."""

    manifest = json.loads(AMENDMENT_MANIFEST.read_text(encoding="utf-8"))

    assert manifest["amendment_id"] == "week5_hpo_execution_amendment_v1"
    assert manifest["amendment_type"] == "EXECUTION_RELIABILITY_AMENDMENT"
    assert manifest["parent_protocol"] == "week5_hpo_protocol_v1"
    assert manifest["parent_protocol_hash"] == (
        "b00ddf190776a12032b1e6b5b284beff8b48204017fe4c397140ac7a4da6844a"
    )
    assert manifest["new_protocol"] == "week5_hpo_protocol_v1_1"
    assert manifest["new_protocol_hash"] == FROZEN_V1_1_HASH
    assert manifest["statistical_protocol_changed"] is False
    assert manifest["execution_protocol_changed"] is True
    assert manifest["root_cause"] == "ENVIRONMENTAL_WALL_CLOCK_INTERRUPTION"
    assert manifest["original_attempt"] == "BLOCKED_INCOMPLETE"
    assert manifest["original_rf_classification_complete_trials"] == 3
    assert manifest["system_sleep_duration_seconds_approximate"] == 14824
    assert manifest["hpo_implementation_failure"] is False
    assert manifest["model_failure"] is False
    assert manifest["v1_resume_allowed"] is False
    assert manifest["v1_trials_carry_forward"] is False
    assert manifest["v1_best_params_enqueued"] is False
    assert manifest["fresh_studies_required"] is True
    assert manifest["row_level_2023_accessed"] is False
    assert manifest["row_level_2024_accessed"] is False
    assert "best_params" not in manifest
    assert "best_objective" not in manifest


def test_experiment_log_records_amendment_without_claiming_production_hpo() -> None:
    """Catches missing provenance or a false claim that v1.1 HPO already ran."""

    text = EXPERIMENT_LOG.read_text(encoding="utf-8")
    week4 = text.index("## Week 4 final acceptance audit")
    amendment = text.index("## Week 5 — HPO execution reliability amendment")

    assert amendment > week4
    section = text[amendment:]
    assert "`BLOCKED_INCOMPLETE`, 3/10 COMPLETE" in section
    assert "`ENVIRONMENTAL_WALL_CLOCK_INTERRUPTION`" in section
    assert "Statistical protocol changed:** NO" in section
    assert "Execution protocol changed:** YES" in section
    assert "v1 study resumed:** NO" in section
    assert "v1 trials carried forward:** NO" in section
    assert "Production v1.1 HPO run performed during amendment implementation:** NO" in section
    assert "Targeted amendment/Week-5 verification:** 70 passed" in section
    assert "Full regression suite:** 312 passed" in section
