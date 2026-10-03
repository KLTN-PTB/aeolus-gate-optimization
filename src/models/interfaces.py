"""Model interfaces, specifications, and classification standards for Aeolus Gate Optimization.

Protocol: docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md
          docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path
from typing import Any, Final, Sequence
import joblib
import numpy as np
import pandas as pd


class ModelStatus(str, Enum):
    """Rigorous classification status for all models in the repository.

    Categories:
    - HISTORICAL: Prior exploratory baselines preserved for audit trail.
    - LEGACY_FROZEN: Pre-existing frozen candidates (e.g. Stage 10 B5 NGBoost Student-T);
      evaluated historically on 2024 holdout, preserved for research benchmarks,
      not automatically the V4 core champion.
    - RESEARCH_CANDIDATE: Active research or ablation models under evaluation.
    - CURRENT_CORE: V4 authoritative production models (Week 4 baselines & Week 5 HPO tuned).
    - TUNED_VARIANT: Parameterization variants resulting from locked HPO under a core family.
    - DOWNSTREAM_ELIGIBLE: Models certified to provide arrival predictions to the
      downstream turn simulation and gate optimization engine.
    """

    HISTORICAL = "historical"
    LEGACY_FROZEN = "legacy_frozen"
    RESEARCH_CANDIDATE = "research_candidate"
    CURRENT_CORE = "current_core"
    TUNED_VARIANT = "tuned_variant"
    DOWNSTREAM_ELIGIBLE = "downstream_eligible"


class ModelCategory(str, Enum):
    """Authoritative architectural categories for model catalog v2."""

    CORE_POINT = "CORE_POINT"
    TUNED_VARIANT = "TUNED_VARIANT"
    PROBABILISTIC_CANDIDATE = "PROBABILISTIC_CANDIDATE"
    LEGACY_FROZEN = "LEGACY_FROZEN"
    AUXILIARY_DEPARTURE = "AUXILIARY_DEPARTURE"
    RESEARCH_CANDIDATE = "RESEARCH_CANDIDATE"


class ModelTask(str, Enum):
    """Operational task classification with strict population boundaries."""

    CORE_ARRIVAL = "core_arrival"  # Inbound DEST=ATL at CRS_DEP_TIME - 2h
    AUXILIARY_DEPARTURE = "auxiliary_departure"  # Outbound ORIGIN=ATL, research only


class ModelType(str, Enum):
    """Model output paradigm."""

    POINT = "point"
    PROBABILISTIC = "probabilistic"


class ModelTarget(str, Enum):
    """Audited target definitions."""

    ARRIVAL_DELAY_SIGNED = "arrival_delay_signed"  # Signed minutes, no absolute, no clip
    ARRIVAL_DELAY_BINARY_15 = "arrival_delay_binary_15"  # 1[ARR_DELAY >= 15]
    DEPARTURE_DELAY_BINARY_15 = "departure_delay_binary_15"  # 1[DEP_DELAY >= 15]


class ModelCapability(str, Enum):
    """Explicit capability declarations for research models."""

    POINT_REGRESSION = "point_regression"
    POINT_CLASSIFICATION = "point_classification"
    PROBABILISTIC = "probabilistic"
    SAMPLING = "sampling"
    CALIBRATED_PROBABILITY = "calibrated_probability"


class UnsupportedCapabilityError(NotImplementedError):
    """Raised when an operation is invoked on a model that does not declare that capability."""


@dataclass(frozen=True)
class ModelSpec:
    """Immutable specification for a registered model in Aeolus.

    Defines architectural capabilities, task boundaries, data requirements,
    and eligibility for downstream gate optimization without training in-place.
    """

    model_id: str
    family: str
    task: str
    target: str
    probabilistic: bool
    supports_predict: bool
    supports_predict_proba: bool
    supports_distribution: bool
    feature_set: str
    preprocessing: str
    seed_policy: str
    hpo_policy: str
    status: str
    downstream_eligible: bool
    feature_version: str = "v1"
    preprocessing_version: str = "v1"
    random_seed: int = 202601
    hpo_budget: int | dict[str, Any] | str = "10_trials"
    artifact_version: str = "v1.0"
    capabilities: frozenset[str] = field(default_factory=frozenset)
    category: str = ""
    selection_role: str = ""
    development_period: str = "2016-2022"
    distribution_capability: str = ""
    source_path: str = ""
    implementation_class: str = ""
    variant_of: str | None = None

    def __post_init__(self) -> None:
        """Validate specification invariants and fail-closed on unknown categories."""
        # Fail closed on unknown task
        valid_tasks = {t.value for t in ModelTask}
        if self.task not in valid_tasks:
            raise ValueError(
                f"Unknown model task '{self.task}' for {self.model_id}. Must be one of {valid_tasks}."
            )

        # Fail closed on unknown status
        valid_statuses = {s.value for s in ModelStatus}
        if self.status not in valid_statuses:
            raise ValueError(
                f"Unknown model status '{self.status}' for {self.model_id}. Must be one of {valid_statuses}."
            )

        # Validate category if specified
        if self.category:
            valid_categories = {c.value for c in ModelCategory}
            if self.category not in valid_categories:
                raise ValueError(
                    f"Unknown model category '{self.category}' for {self.model_id}. Must be one of {valid_categories}."
                )

        # Invariant: Auxiliary departure models must NEVER be downstream-eligible
        if self.task == ModelTask.AUXILIARY_DEPARTURE.value and self.downstream_eligible:
            raise ValueError(
                f"Auxiliary departure model '{self.model_id}' cannot be downstream_eligible. "
                "Only Core Arrival (DEST=ATL) feeds downstream gate optimization."
            )

        # Invariant: Core arrival feature set must NOT contain weather
        fs_lower = self.feature_set.lower()
        if self.task == ModelTask.CORE_ARRIVAL.value:
            if "with_weather" in fs_lower or (
                "weather" in fs_lower
                and "no_weather" not in fs_lower
                and "without_weather" not in fs_lower
            ):
                raise ValueError(
                    f"Core arrival model '{self.model_id}' feature_set cannot contain weather. "
                    "Arrival task strictly operates with no Weather features."
                )

    def compute_sha256(self) -> str:
        """Deterministic sha256 hash of the model specification."""
        import hashlib
        payload = {
            "model_id": self.model_id,
            "family": self.family,
            "task": self.task,
            "target": self.target,
            "probabilistic": self.probabilistic,
            "feature_set": self.feature_set,
            "preprocessing": self.preprocessing,
            "seed_policy": self.seed_policy,
            "hpo_policy": self.hpo_policy,
            "status": self.status,
            "category": self.category,
            "downstream_eligible": self.downstream_eligible,
        }
        raw = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class BaseModel(ABC):
    """Abstract base interface for all models evaluated in the Aeolus Benchmark Engine.

    Allows diverse model paradigms (linear, tree-ensembles, deep neural nets,
    and probabilistic distribution heads) to be benchmarked under an identical protocol.
    Models declare their capabilities explicitly; unsupported calls fail closed with
    UnsupportedCapabilityError.
    """

    def __init__(
        self,
        model_id: str,
        *,
        capabilities: Sequence[ModelCapability | str] | None = None,
        random_seed: int = 202601,
        spec: ModelSpec | None = None,
    ) -> None:
        self.model_id = model_id
        self.random_seed = random_seed
        self.spec = spec
        self._capabilities: set[str] = set()
        if capabilities:
            for c in capabilities:
                val = c.value if isinstance(c, ModelCapability) else str(c)
                self._capabilities.add(val)
        self.is_fitted_: bool = False

    @property
    def capabilities(self) -> set[str]:
        """Return declared capability strings for this model."""
        return set(self._capabilities)

    def has_capability(self, capability: ModelCapability | str) -> bool:
        """Check whether the model declares a specific capability."""
        val = capability.value if isinstance(capability, ModelCapability) else str(capability)
        return val in self._capabilities

    @abstractmethod
    def fit(self, X: pd.DataFrame | np.ndarray, y: pd.Series | np.ndarray) -> BaseModel:
        """Fit the model to training data."""
        raise NotImplementedError

    def predict(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        """Generate point predictions. Raises UnsupportedCapabilityError if unsupported."""
        if not (self.has_capability(ModelCapability.POINT_REGRESSION) or self.has_capability(ModelCapability.POINT_CLASSIFICATION)):
            raise UnsupportedCapabilityError(
                f"Model '{self.model_id}' does not support point predict(). Capabilities: {self.capabilities}"
            )
        raise NotImplementedError

    def predict_proba(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        """Generate class probability predictions."""
        if not (self.has_capability(ModelCapability.POINT_CLASSIFICATION) or self.has_capability(ModelCapability.CALIBRATED_PROBABILITY)):
            raise UnsupportedCapabilityError(
                f"Model '{self.model_id}' does not support predict_proba(). Capabilities: {self.capabilities}"
            )
        raise NotImplementedError

    def predict_distribution(self, X: pd.DataFrame | np.ndarray) -> dict[str, Any]:
        """Generate parametric distribution forecasts."""
        if not self.has_capability(ModelCapability.PROBABILISTIC):
            raise UnsupportedCapabilityError(
                f"Model '{self.model_id}' does not support predict_distribution(). Capabilities: {self.capabilities}"
            )
        raise NotImplementedError

    def sample(
        self,
        X: pd.DataFrame | np.ndarray,
        n_samples: int = 100,
        seed: int | None = None,
    ) -> np.ndarray:
        """Draw Monte Carlo delay samples from the predictive distribution."""
        if not (self.has_capability(ModelCapability.SAMPLING) or self.has_capability(ModelCapability.PROBABILISTIC)):
            raise UnsupportedCapabilityError(
                f"Model '{self.model_id}' does not support sample(). Capabilities: {self.capabilities}"
            )
        raise NotImplementedError

    def metadata(self) -> dict[str, Any]:
        """Return serializable metadata describing model instance status and capabilities."""
        return {
            "model_id": self.model_id,
            "random_seed": self.random_seed,
            "capabilities": sorted(list(self._capabilities)),
            "is_fitted": self.is_fitted_,
            "class_name": self.__class__.__name__,
            "spec": self.spec.model_id if self.spec else None,
        }

    def save_artifact(self, path: Path | str) -> Path:
        """Serialize model weights and metadata to file path."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "metadata": self.metadata(),
            "model_state": self.__dict__,
        }
        joblib.dump(payload, p)
        return p

    @classmethod
    def load_artifact(cls, path: Path | str) -> BaseModel:
        """Deserialize model from file path."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Model artifact not found at {p}")
        payload = joblib.load(p)
        model = cls.__new__(cls)
        model.__dict__.update(payload.get("model_state", {}))
        return model
