from __future__ import annotations

import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = (
    ROOT / "artifacts" / "manifests" / "weather_point_in_time_contract_v1.json"
)


def _load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_weather_contract_manifest_locks_disabled_auxiliary_boundary() -> None:
    contract = _load_manifest()

    assert contract["contract_version"] == "weather_point_in_time_contract_v1"
    assert contract["protocol_version"] == "Research Protocol V4.0"
    assert contract["task"] == "departure_auxiliary"
    assert contract["hub"] == "ATL"
    assert contract["flow"] == "ORIGIN=ATL"
    assert contract["target"] == "y_dep_cls = 1[DEP_DELAY >= 15]"
    assert contract["cutoff"] == "CRS_DEP_TIME - 2 hours"
    assert contract["provider_status"] == "TBD"
    assert contract["provider"] == "TBD"
    assert contract["audit_status"] == "AUDIT_REQUIRED"
    assert contract["enabled"] is False
    assert contract["raw_aeolus_weather_allowed"] is False
    assert contract["core_arrival_weather_allowed"] is False
    assert contract["feeds_optimizer"] is False
    assert contract["2024_accessed"] is False


def test_manifest_requires_all_time_and_semantic_classes() -> None:
    contract = _load_manifest()

    assert contract["required_time_fields"] == [
        "issue_time",
        "publication_time",
        "available_time",
        "valid_time",
    ]
    assert contract["timezone_policy"]["canonical_storage"] == "UTC"
    assert contract["timezone_policy"]["naive_timestamp_policy"] == "FAIL_CLOSED"
    assert set(contract["weather_semantic_classes"]) == {
        "FORECAST",
        "OBSERVATION",
        "REANALYSIS",
        "MODEL_ANALYSIS",
        "MODEL_FILL",
    }
    assert contract["join_rules"]["availability_condition"] == (
        "available_time <= target_prediction_cutoff"
    )
    assert contract["join_rules"]["valid_time_alone_is_sufficient"] is False
    assert contract["row_parity_required"] is True


def test_manifest_defines_all_or_nothing_w1_w15_audit() -> None:
    contract = _load_manifest()
    gates = contract["audit_gates"]

    assert set(gates) == {f"W{index}" for index in range(1, 16)}
    assert all(gate["critical"] is True for gate in gates.values())
    assert contract["pass_decision"] == {
        "required": "ALL_CRITICAL_GATES_PASS",
        "point_in_time_weather_provenance": "PASS",
        "dep_b": "ENABLED_FOR_CONTROLLED_EXPERIMENT",
    }
    assert contract["fail_decision"] == {
        "trigger": "ANY_CRITICAL_GATE_FAILS_OR_IS_UNPROVEN",
        "point_in_time_weather_provenance": "FAIL_OR_INSUFFICIENT_EVIDENCE",
        "dep_b": "BLOCKED_NOT_CORE_FAILURE",
        "core_arrival": "CONTINUE",
    }


def test_base_config_references_contract_without_enabling_weather() -> None:
    config = yaml.safe_load((ROOT / "configs" / "base.yaml").read_text(encoding="utf-8"))
    source = config["prediction"]["departure_auxiliary"]["weather"][
        "point_in_time_source"
    ]

    assert source == {
        "artifact_version": "weather_point_in_time_v1",
        "contract_version": "weather_point_in_time_contract_v1",
        "contract_path": (
            "artifacts/manifests/weather_point_in_time_contract_v1.json"
        ),
        "provider": "TBD",
        "status": "audit_required",
        "enabled": False,
        "row_parity_required": True,
    }


def test_registry_records_contract_without_claiming_weather_evidence_pass() -> None:
    registry = (ROOT / "docs" / "decisions" / "decision_registry.md").read_text(
        encoding="utf-8"
    )

    assert "| I004 | Point-in-Time Weather Contract V1 |" in registry
    assert "LOCKED_IMPLEMENTATION_CONTRACT" in registry
    assert "E007" not in registry

