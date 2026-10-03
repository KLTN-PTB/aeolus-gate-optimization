"""Unit tests for Model Catalog v2, Invariants, and Downstream Eligibility.

Governed by:
- docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md
- configs/model_catalog_v2.yaml
- src/models/registry.py
- src/models/interfaces.py
"""

from __future__ import annotations

from pathlib import Path
import pytest
import yaml

from src.models.interfaces import (
    ModelCapability,
    ModelCategory,
    ModelSpec,
    ModelStatus,
    ModelTarget,
    ModelTask,
)
from src.models.registry import (
    _MODEL_CATALOG,
    assert_downstream_eligible,
    get_auxiliary_models,
    get_core_point_families,
    get_core_point_models,
    get_downstream_eligible_models,
    get_legacy_models,
    get_model_spec,
    get_probabilistic_candidates,
    get_tuned_variants,
    is_downstream_eligible,
    list_models,
    register_model,
    unregister_model,
)

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "configs" / "model_catalog_v2.yaml"


@pytest.fixture(scope="module")
def catalog_yaml_data() -> dict:
    """Load configs/model_catalog_v2.yaml."""
    assert CATALOG_PATH.exists(), f"Missing catalog file: {CATALOG_PATH}"
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# =============================================================================
# 1. test_core_method_cap_is_5
# =============================================================================

def test_core_method_cap_is_5(catalog_yaml_data: dict) -> None:
    """Verify that Core Point methods are strictly capped at 5 canonical families.

    The 5 families are:
    1. Linear / Ridge family (arrival_linear_baseline_v1)
    2. Random Forest (arrival_random_forest_baseline_v1)
    3. HistGradientBoosting (arrival_hist_gradient_boosting_baseline_v1)
    4. XGBoost (arrival_xgboost_baseline_v1)
    5. Weighted Ensemble (arrival_weighted_ensemble_v1)

    Tuned models (e.g. *_tuned_v1_1) are parameterization variants of base families,
    not distinct Core families inflating the count.
    """
    # 1. Check YAML catalog declaration
    assert catalog_yaml_data.get("core_method_cap") == 5

    # 2. Check Python registry helper
    core_models = get_core_point_models()
    assert len(core_models) == 5, f"Expected exactly 5 Core Point models, got {len(core_models)}"

    # 3. Check exact model IDs
    expected_core_ids = {
        "arrival_linear_baseline_v1",
        "arrival_random_forest_baseline_v1",
        "arrival_hist_gradient_boosting_baseline_v1",
        "arrival_xgboost_baseline_v1",
        "arrival_weighted_ensemble_v1",
    }
    actual_core_ids = {m.model_id for m in core_models}
    assert actual_core_ids == expected_core_ids

    # 4. Check families
    expected_families = {
        "linear",
        "random_forest",
        "hist_gradient_boosting",
        "xgboost",
        "weighted_ensemble",
    }
    actual_families = {m.family for m in core_models}
    assert actual_families == expected_families
    assert set(get_core_point_families()) == expected_families

    # 5. Verify tuned variants do not inflate core count
    tuned_variants = get_tuned_variants()
    assert len(tuned_variants) == 3
    for tv in tuned_variants:
        assert tv.category == ModelCategory.TUNED_VARIANT.value
        assert tv.variant_of is not None
        assert tv.variant_of in expected_core_ids


# =============================================================================
# 2. test_legacy_b5_is_not_current_core
# =============================================================================

def test_legacy_b5_is_not_current_core(catalog_yaml_data: dict) -> None:
    """Verify B5 NGBoost Student-T is classified as LEGACY_FROZEN, not in Core Point."""
    spec = get_model_spec("b5_ngboost_student_t")
    assert spec.status == ModelStatus.LEGACY_FROZEN.value
    assert spec.category == ModelCategory.LEGACY_FROZEN.value
    assert spec.probabilistic is True

    # Not in Core Point models
    core_ids = {m.model_id for m in get_core_point_models()}
    assert "b5_ngboost_student_t" not in core_ids

    # Present in legacy models
    legacy_ids = {m.model_id for m in get_legacy_models()}
    assert "b5_ngboost_student_t" in legacy_ids

    # Belongs to distinct legacy system in catalog
    legacy_sys = catalog_yaml_data["system_identities"]["AEOLUS_LEGACY_PROBABILISTIC_B5"]
    assert legacy_sys["system_id"] == "SYS_B5_ngboost_student_t__DEP_D2_gaussian_copula"
    assert legacy_sys["status"] == "LEGACY_FROZEN"


# =============================================================================
# 3. test_unknown_model_fails_closed
# =============================================================================

def test_unknown_model_fails_closed() -> None:
    """Verify that querying or evaluating unknown model IDs fails closed."""
    unknown_id = "non_existent_unregistered_model_xyz"

    # get_model_spec raises KeyError
    with pytest.raises(KeyError, match="Unknown model_id"):
        get_model_spec(unknown_id)

    # is_downstream_eligible returns False (fail closed, rejected)
    assert is_downstream_eligible(unknown_id) is False

    # assert_downstream_eligible raises KeyError
    with pytest.raises(KeyError, match="not registered"):
        assert_downstream_eligible(unknown_id)


# =============================================================================
# 4. test_auxiliary_departure_not_downstream
# =============================================================================

def test_auxiliary_departure_not_downstream() -> None:
    """Verify Auxiliary Departure models are strictly prohibited from downstream optimization."""
    dep_spec = get_model_spec("departure_auxiliary_baseline_v1")
    assert dep_spec.task == ModelTask.AUXILIARY_DEPARTURE.value
    assert dep_spec.downstream_eligible is False
    assert dep_spec.category == ModelCategory.AUXILIARY_DEPARTURE.value

    # is_downstream_eligible must return False
    assert is_downstream_eligible("departure_auxiliary_baseline_v1") is False

    # assert_downstream_eligible must raise ValueError
    with pytest.raises(ValueError, match="is NOT downstream eligible"):
        assert_downstream_eligible("departure_auxiliary_baseline_v1")

    # Invariant: ModelSpec construction must reject downstream_eligible=True for auxiliary departure
    with pytest.raises(ValueError, match="cannot be downstream_eligible"):
        ModelSpec(
            model_id="illegal_departure_model",
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
            category=ModelCategory.AUXILIARY_DEPARTURE.value,
            downstream_eligible=True,
        )


# =============================================================================
# 5. test_downstream_eligibility_is_explicit
# =============================================================================

def test_downstream_eligibility_is_explicit(catalog_yaml_data: dict) -> None:
    """Verify that every model in the catalog declares explicit downstream eligibility."""
    models_dict = catalog_yaml_data.get("models", {})
    assert len(models_dict) >= 15

    for mid, mdata in models_dict.items():
        assert "downstream_eligible" in mdata, f"Model {mid} missing downstream_eligible"
        assert isinstance(mdata["downstream_eligible"], bool), (
            f"Model {mid} downstream_eligible must be a strict boolean"
        )

        # Cross-check with registry
        spec = get_model_spec(mid)
        assert spec.downstream_eligible == mdata["downstream_eligible"]
        assert is_downstream_eligible(mid) == mdata["downstream_eligible"]


# =============================================================================
# 6. test_model_family_is_not_inferred_from_filename
# =============================================================================

def test_model_family_is_not_inferred_from_filename() -> None:
    """Verify that model family and properties are read from spec, not string-inferred."""
    # Register a model with a misleading name to prove no substring heuristic is used
    misleading_spec = ModelSpec(
        model_id="core_arrival_fake_prefix_but_auxiliary",
        family="linear",
        task=ModelTask.AUXILIARY_DEPARTURE.value,
        target=ModelTarget.DEPARTURE_DELAY_BINARY_15.value,
        probabilistic=False,
        supports_predict=True,
        supports_predict_proba=True,
        supports_distribution=False,
        feature_set="departure_features_v1",
        preprocessing="scaler",
        seed_policy="fixed_seed_202601",
        hpo_policy="none",
        status=ModelStatus.RESEARCH_CANDIDATE.value,
        category=ModelCategory.AUXILIARY_DEPARTURE.value,
        downstream_eligible=False,
    )
    register_model(misleading_spec)

    try:
        retrieved = get_model_spec("core_arrival_fake_prefix_but_auxiliary")
        # Despite name containing 'core_arrival', task is AUXILIARY_DEPARTURE
        assert retrieved.task == ModelTask.AUXILIARY_DEPARTURE.value
        assert is_downstream_eligible("core_arrival_fake_prefix_but_auxiliary") is False
    finally:
        unregister_model("core_arrival_fake_prefix_but_auxiliary")


# =============================================================================
# 7. test_no_duplicate_system_identity
# =============================================================================

def test_no_duplicate_system_identity(catalog_yaml_data: dict) -> None:
    """Verify system identities are distinct and never conflated across architectures."""
    system_identities = catalog_yaml_data.get("system_identities", {})
    assert "AEOLUS_V4_CORE_ARRIVAL" in system_identities
    assert "AEOLUS_LEGACY_PROBABILISTIC_B5" in system_identities

    v4_sys = system_identities["AEOLUS_V4_CORE_ARRIVAL"]
    b5_sys = system_identities["AEOLUS_LEGACY_PROBABILISTIC_B5"]

    # System IDs must be strictly different
    assert v4_sys["system_id"] != b5_sys["system_id"]
    assert v4_sys["system_id"] == "SYS_V4_CORE_ARRIVAL"
    assert b5_sys["system_id"] == "SYS_B5_ngboost_student_t__DEP_D2_gaussian_copula"

    # All registered system IDs must be unique
    all_sys_ids = [sys_info["system_id"] for sys_info in system_identities.values()]
    assert len(all_sys_ids) == len(set(all_sys_ids)), "Duplicate system_id detected"


# =============================================================================
# 8. test_core_arrival_task_boundary
# =============================================================================

def test_core_arrival_task_boundary() -> None:
    """Verify Core Arrival models operate strictly within audited task boundaries.

    Invariants:
    - Task: core_arrival (DEST=ATL)
    - Target: arrival_delay_signed or arrival_delay_binary_15
    """
    arrival_models = list_models(task=ModelTask.CORE_ARRIVAL)
    assert len(arrival_models) >= 10

    valid_targets = {
        ModelTarget.ARRIVAL_DELAY_SIGNED.value,
        ModelTarget.ARRIVAL_DELAY_BINARY_15.value,
    }
    for model in arrival_models:
        assert model.task == ModelTask.CORE_ARRIVAL.value
        assert model.target in valid_targets, (
            f"Model {model.model_id} targets {model.target}, expected arrival delay"
        )


# =============================================================================
# 9. test_arrival_no_weather
# =============================================================================

def test_arrival_no_weather(catalog_yaml_data: dict) -> None:
    """Verify Core Arrival models strictly prohibit Weather features in predictors."""
    # 1. Check Python registry models
    arrival_models = list_models(task=ModelTask.CORE_ARRIVAL)
    for model in arrival_models:
        fs = model.feature_set.lower()
        has_weather = "with_weather" in fs or (
            "weather" in fs and "no_weather" not in fs and "without_weather" not in fs
        )
        assert not has_weather, f"Model {model.model_id} contains weather features in feature_set"

    # 2. Check catalog YAML declarations
    models_dict = catalog_yaml_data.get("models", {})
    for mid, mdata in models_dict.items():
        if mdata.get("task") == "core_arrival":
            assert mdata.get("weather_included") is False, (
                f"Catalog model {mid} must have weather_included: false"
            )

    # 3. ModelSpec validator rejects weather
    with pytest.raises(ValueError, match="cannot contain weather"):
        ModelSpec(
            model_id="illegal_weather_model",
            family="linear",
            task=ModelTask.CORE_ARRIVAL.value,
            target=ModelTarget.ARRIVAL_DELAY_SIGNED.value,
            probabilistic=False,
            supports_predict=True,
            supports_predict_proba=True,
            supports_distribution=False,
            feature_set="schedule_and_weather_v1",
            preprocessing="scaler",
            seed_policy="fixed_seed_202601",
            hpo_policy="none",
            status=ModelStatus.RESEARCH_CANDIDATE.value,
            category=ModelCategory.CORE_POINT.value,
            downstream_eligible=False,
        )


# =============================================================================
# 10. test_arrival_no_departure_prediction
# =============================================================================

def test_arrival_no_departure_prediction(catalog_yaml_data: dict) -> None:
    """Verify Core Arrival models do NOT take predicted or actual departure delay as input.

    Cutoff is CRS_DEP_TIME - 2h. Actual departure delay is unavailable,
    and predicted departure delay is not an audited feature of Core Arrival.
    """
    models_dict = catalog_yaml_data.get("models", {})
    for mid, mdata in models_dict.items():
        if mdata.get("task") == "core_arrival":
            assert mdata.get("departure_delay_predictor_included") is False, (
                f"Core Arrival model {mid} must not include departure delay predictor"
            )

    # All Core Arrival models in registry use schedule_calendar_carrier_route
    arrival_models = list_models(task=ModelTask.CORE_ARRIVAL)
    for model in arrival_models:
        fs = model.feature_set.lower()
        assert "dep_delay" not in fs
        assert "predicted_dep" not in fs
