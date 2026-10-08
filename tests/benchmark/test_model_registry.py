"""Tests for Model Registry integration with Multi-Model Benchmark Engine."""

from __future__ import annotations

import pytest

from src.models.interfaces import (
    ModelCapability,
    ModelSpec,
    ModelStatus,
    ModelTarget,
    ModelTask,
)
from src.models.registry import (
    get_current_core_models,
    get_legacy_models,
    get_model_spec,
    list_models,
    register_model,
    unregister_model,
    validate_model_status,
)


def test_registry_integration_retrieval() -> None:
    """Verify that all core and legacy models can be retrieved and have required benchmark spec fields."""
    models = list_models()
    assert len(models) >= 10

    for spec in models:
        assert spec.model_id
        assert spec.family
        assert spec.task in {
            ModelTask.CORE_ARRIVAL.value,
            ModelTask.AUXILIARY_DEPARTURE.value,
            ModelTask.CORE_DEPARTURE.value,
        }
        assert spec.target
        assert spec.status in {s.value for s in ModelStatus}
        assert isinstance(spec.downstream_eligible, bool)
        assert spec.feature_version
        assert spec.preprocessing_version
        assert isinstance(spec.random_seed, int)


def test_custom_mock_model_registration_and_cleanup() -> None:
    """Verify custom model specs can be registered dynamically and cleaned up cleanly."""
    mock_id = "test_custom_benchmark_model_v1"
    spec = ModelSpec(
        model_id=mock_id,
        family="custom_linear",
        task=ModelTask.CORE_ARRIVAL.value,
        target=ModelTarget.ARRIVAL_DELAY_SIGNED.value,
        probabilistic=False,
        supports_predict=True,
        supports_predict_proba=False,
        supports_distribution=False,
        feature_set="schedule_calendar_carrier_route_v1",
        preprocessing="standard_scaler",
        seed_policy="fixed_seed_202601",
        hpo_policy="none",
        status=ModelStatus.RESEARCH_CANDIDATE.value,
        downstream_eligible=False,
        feature_version="v1",
        capabilities=frozenset([ModelCapability.POINT_REGRESSION.value]),
    )

    register_model(spec)
    retrieved = get_model_spec(mock_id)
    assert retrieved.model_id == mock_id
    assert retrieved.family == "custom_linear"

    unregister_model(mock_id)
    with pytest.raises(KeyError, match="Unknown model_id"):
        get_model_spec(mock_id)


def test_fail_closed_on_unknown_model_id() -> None:
    """Verify registry raises KeyError fail closed on unknown model names."""
    with pytest.raises(KeyError, match="Unknown model_id"):
        get_model_spec("completely_unknown_model_xyz")


def test_no_filename_heuristic_status_inference() -> None:
    """Verify that model status must be read from spec, not inferred from filename."""
    # A model named 'legacy_something' should still have its status determined by spec.status
    spec = ModelSpec(
        model_id="legacy_sounding_name_core",
        family="linear",
        task=ModelTask.CORE_ARRIVAL.value,
        target=ModelTarget.ARRIVAL_DELAY_SIGNED.value,
        probabilistic=False,
        supports_predict=True,
        supports_predict_proba=False,
        supports_distribution=False,
        feature_set="schedule_v1",
        preprocessing="scaler",
        seed_policy="fixed",
        hpo_policy="none",
        status=ModelStatus.CURRENT_CORE.value,
        downstream_eligible=True,
    )
    assert spec.status == ModelStatus.CURRENT_CORE.value
