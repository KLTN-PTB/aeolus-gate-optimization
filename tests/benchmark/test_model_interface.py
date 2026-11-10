"""Tests for common Model Interface, Capability Declarations, and Artifact Serialization."""

from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.models.interfaces import (
    BaseModel,
    ModelCapability,
    UnsupportedCapabilityError,
)
from tests.benchmark.conftest import (
    MockPointRegressor,
    MockProbabilisticModel,
    MockTreeClassifier,
)


def test_model_capability_declaration() -> None:
    """Verify models declare their capabilities and has_capability returns correct boolean."""
    regressor = MockPointRegressor()
    assert regressor.has_capability(ModelCapability.POINT_REGRESSION) is True
    assert regressor.has_capability(ModelCapability.POINT_CLASSIFICATION) is False
    assert regressor.has_capability(ModelCapability.PROBABILISTIC) is False

    prob_model = MockProbabilisticModel()
    assert prob_model.has_capability(ModelCapability.PROBABILISTIC) is True
    assert prob_model.has_capability(ModelCapability.SAMPLING) is True
    assert prob_model.has_capability(ModelCapability.POINT_REGRESSION) is True
    assert prob_model.has_capability(ModelCapability.POINT_CLASSIFICATION) is False


def test_unsupported_capability_fails_closed() -> None:
    """Calling an undeclared capability method must raise UnsupportedCapabilityError."""
    regressor = MockPointRegressor()
    dummy_x = pd.DataFrame({"feat1": [1.0, 2.0]})

    with pytest.raises(UnsupportedCapabilityError, match="does not support predict_proba"):
        regressor.predict_proba(dummy_x)

    with pytest.raises(UnsupportedCapabilityError, match="does not support predict_distribution"):
        regressor.predict_distribution(dummy_x)

    with pytest.raises(UnsupportedCapabilityError, match="does not support sample"):
        regressor.sample(dummy_x, n_samples=10)


def test_model_metadata_serialization() -> None:
    """Verify model metadata returns valid serializable dictionary."""
    model = MockTreeClassifier(model_id="test_cls_model", random_seed=42)
    meta = model.metadata()

    assert meta["model_id"] == "test_cls_model"
    assert meta["random_seed"] == 42
    assert "point_classification" in meta["capabilities"]
    assert meta["is_fitted"] is False
    assert meta["class_name"] == "MockTreeClassifier"


def test_model_artifact_save_and_load(tmp_path: Path) -> None:
    """Verify save_artifact and load_artifact round-trip preserving state."""
    model = MockPointRegressor(model_id="save_load_test", random_seed=123)
    X = pd.DataFrame({"feature": [1.0, 2.0, 3.0]})
    y = pd.Series([10.0, 20.0, 30.0])
    model.fit(X, y)
    assert model.is_fitted_ is True
    assert model.mean_ == 20.0

    art_path = tmp_path / "saved_model.joblib"
    saved = model.save_artifact(art_path)
    assert saved.exists()

    loaded = MockPointRegressor.load_artifact(art_path)
    assert loaded.model_id == "save_load_test"
    assert loaded.is_fitted_ is True
    assert loaded.mean_ == 20.0

    # Predictions must match
    pred_orig = model.predict(X)
    pred_loaded = loaded.predict(X)
    np.testing.assert_allclose(pred_orig, pred_loaded)
