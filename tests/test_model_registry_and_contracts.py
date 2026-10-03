"""Unit tests for Model Registry, Interfaces, Contracts, and Current State Consistency.

Protocol: docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md
          configs/current_state.yaml
"""

from __future__ import annotations

from pathlib import Path
import pytest
import yaml

from src.data.access_guard import DataAccessDenied, assert_data_access_allowed
from src.models.interfaces import (
    ModelSpec,
    ModelStatus,
    ModelTarget,
    ModelTask,
    ModelType,
)
from src.models.registry import (
    get_current_core_models,
    get_downstream_eligible_models,
    get_legacy_models,
    get_model_spec,
    get_point_models,
    get_probabilistic_models,
    list_models,
    validate_model_status,
)

ROOT = Path(__file__).resolve().parents[1]


# =============================================================================
# 1. Registry Consistency & Structure Tests
# =============================================================================

def test_registry_contains_required_models() -> None:
    """Verify that current core models, legacy models, and auxiliary models are present."""
    all_models = list_models()
    assert len(all_models) >= 10

    model_ids = {m.model_id for m in all_models}
    expected_core = {
        "arrival_linear_baseline_v1",
        "arrival_random_forest_baseline_v1",
        "arrival_hist_gradient_boosting_baseline_v1",
        "arrival_xgboost_baseline_v1",
        "arrival_random_forest_tuned_v1_1",
        "arrival_hist_gradient_boosting_tuned_v1_1",
        "arrival_xgboost_tuned_v1_1",
    }
    assert expected_core.issubset(model_ids)
    assert "b5_ngboost_student_t" in model_ids
    assert "departure_auxiliary_baseline_v1" in model_ids


def test_registry_lookup_exact() -> None:
    """Verify get_model_spec retrieves exact specifications."""
    spec = get_model_spec("arrival_xgboost_tuned_v1_1")
    assert spec.model_id == "arrival_xgboost_tuned_v1_1"
    assert spec.family == "xgboost"
    assert spec.task == ModelTask.CORE_ARRIVAL.value
    assert spec.status == ModelStatus.CURRENT_CORE.value
    assert spec.downstream_eligible is True
    assert spec.probabilistic is False


# =============================================================================
# 2. Historical & Legacy Model Classification Tests
# =============================================================================

def test_historical_model_classification() -> None:
    """Verify B5 NGBoost Student-T is classified as legacy_frozen, not current core."""
    b5_spec = get_model_spec("b5_ngboost_student_t")
    assert b5_spec.status == ModelStatus.LEGACY_FROZEN.value
    assert b5_spec.probabilistic is True
    assert b5_spec.supports_distribution is True

    # Ensure B5 is not returned as current core
    core_ids = {m.model_id for m in get_current_core_models()}
    assert "b5_ngboost_student_t" not in core_ids

    # Ensure B5 is returned as legacy model
    legacy_ids = {m.model_id for m in get_legacy_models()}
    assert "b5_ngboost_student_t" in legacy_ids


# =============================================================================
# 3. Task Consistency & Isolation Tests
# =============================================================================

def test_core_arrival_has_no_weather() -> None:
    """Verify all Core Arrival models operate with NO weather features."""
    arrival_models = list_models(task=ModelTask.CORE_ARRIVAL)
    assert len(arrival_models) >= 9

    for model in arrival_models:
        fs = model.feature_set.lower()
        has_weather = "with_weather" in fs or (
            "weather" in fs and "no_weather" not in fs and "without_weather" not in fs
        )
        assert not has_weather, (
            f"Core arrival model {model.model_id} violated no-weather protocol"
        )


def test_auxiliary_departure_isolation() -> None:
    """Verify Auxiliary Departure task is strictly isolated from downstream optimization."""
    dep_models = list_models(task=ModelTask.AUXILIARY_DEPARTURE)
    assert len(dep_models) >= 1

    for model in dep_models:
        assert model.downstream_eligible is False, (
            f"Auxiliary model {model.model_id} cannot be downstream eligible"
        )

    # Invariant: Attempting to create an auxiliary model with downstream_eligible=True must fail
    with pytest.raises(ValueError, match="cannot be downstream_eligible"):
        ModelSpec(
            model_id="invalid_dep_model",
            family="linear",
            task=ModelTask.AUXILIARY_DEPARTURE.value,
            target=ModelTarget.DEPARTURE_DELAY_BINARY_15.value,
            probabilistic=False,
            supports_predict=True,
            supports_predict_proba=True,
            supports_distribution=False,
            feature_set="departure_features",
            preprocessing="standard_scaler",
            seed_policy="fixed_seed_202601",
            hpo_policy="none",
            status=ModelStatus.RESEARCH_CANDIDATE.value,
            downstream_eligible=True,
        )


def test_core_arrival_cannot_have_weather_feature_set() -> None:
    """Verify ModelSpec construction fails closed if weather is included in Core Arrival."""
    with pytest.raises(ValueError, match="cannot contain weather"):
        ModelSpec(
            model_id="invalid_arrival_model",
            family="linear",
            task=ModelTask.CORE_ARRIVAL.value,
            target=ModelTarget.ARRIVAL_DELAY_SIGNED.value,
            probabilistic=False,
            supports_predict=True,
            supports_predict_proba=True,
            supports_distribution=False,
            feature_set="schedule_and_weather_v1",
            preprocessing="standard_scaler",
            seed_policy="fixed_seed_202601",
            hpo_policy="none",
            status=ModelStatus.RESEARCH_CANDIDATE.value,
            downstream_eligible=False,
        )


# =============================================================================
# 4. Fail-Closed Unknown Model & Status Tests
# =============================================================================

def test_unknown_model_id_fails_closed() -> None:
    """Verify get_model_spec raises KeyError on unknown model IDs."""
    with pytest.raises(KeyError, match="Unknown model_id"):
        get_model_spec("non_existent_model_v999")


def test_unknown_model_status_fails_closed() -> None:
    """Verify unknown model status strings fail closed."""
    with pytest.raises(ValueError, match="Invalid model status"):
        validate_model_status("unapproved_status_name")

    with pytest.raises(ValueError, match="Unknown model status"):
        ModelSpec(
            model_id="invalid_status_model",
            family="linear",
            task=ModelTask.CORE_ARRIVAL.value,
            target=ModelTarget.ARRIVAL_DELAY_SIGNED.value,
            probabilistic=False,
            supports_predict=True,
            supports_predict_proba=True,
            supports_distribution=False,
            feature_set="schedule_v1",
            preprocessing="standard_scaler",
            seed_policy="fixed_seed_202601",
            hpo_policy="none",
            status="unapproved_status",
            downstream_eligible=False,
        )


def test_unknown_model_task_fails_closed() -> None:
    """Verify unknown model task strings fail closed."""
    with pytest.raises(ValueError, match="Unknown model task"):
        ModelSpec(
            model_id="invalid_task_model",
            family="linear",
            task="unapproved_task",
            target=ModelTarget.ARRIVAL_DELAY_SIGNED.value,
            probabilistic=False,
            supports_predict=True,
            supports_predict_proba=True,
            supports_distribution=False,
            feature_set="schedule_v1",
            preprocessing="standard_scaler",
            seed_policy="fixed_seed_202601",
            hpo_policy="none",
            status=ModelStatus.RESEARCH_CANDIDATE.value,
            downstream_eligible=False,
        )


# =============================================================================
# 5. Access Guard 2024 Enforcement Tests
# =============================================================================

def test_2024_access_guard_enforcement() -> None:
    """Verify 2024 access guard strictly prevents development and HPO access."""
    with pytest.raises(DataAccessDenied, match="2024 is sealed from development access"):
        assert_data_access_allowed(2024, "development")

    with pytest.raises(DataAccessDenied, match="HPO is blocked"):
        assert_data_access_allowed(2024, "hpo")

    with pytest.raises(DataAccessDenied, match="freeze manifest"):
        assert_data_access_allowed(
            2024,
            "final_evaluation",
            freeze_manifest_path=Path("artifacts/manifests/nonexistent_freeze_manifest.json"),
        )


# =============================================================================
# 6. Machine-Readable Current State YAML Validation
# =============================================================================

def test_current_state_yaml_consistency() -> None:
    """Verify configs/current_state.yaml contains all required schema fields."""
    config_path = ROOT / "configs" / "current_state.yaml"
    assert config_path.exists(), "configs/current_state.yaml is missing"

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # Core required keys
    required_keys = {
        "architecture_protocol_version",
        "arrival_task",
        "departure_auxiliary_task",
        "cutoff",
        "temporal_roles",
        "current_core_models",
        "legacy_models",
        "downstream_policy",
        "weather_status",
        "chain_status",
        "holdout_status",
        "test_baseline",
        "next_phase",
        "generated_at",
    }
    assert required_keys.issubset(data.keys())

    # Task assertions
    assert data["arrival_task"]["population"] == "inbound DEST=ATL"
    assert data["arrival_task"]["cutoff"] == "CRS_DEP_TIME - 2h"
    assert data["arrival_task"]["feeds_downstream_optimizer"] is True
    assert "NO_WEATHER" in data["arrival_task"]["weather"]

    assert data["departure_auxiliary_task"]["population"] == "outbound ORIGIN=ATL"
    assert data["departure_auxiliary_task"]["feeds_downstream_optimizer"] is False

    # Holdout assertions
    assert data["holdout_status"]["state"] == "POST_HOLDOUT_STABILIZED"
    assert data["holdout_status"]["untouched_holdout"] is False

    # Core models match registry
    core_registry_ids = [m.model_id for m in get_current_core_models()]
    for cid in data["current_core_models"]:
        assert cid in core_registry_ids
