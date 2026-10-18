"""Multi-dimensional data provenance and evidence lineage contracts for Aeolus.

Protocol: Aeolus Dual Core Architecture Protocol V4
Task: AEOLUS-G1 Data Provenance, Temporal Contracts & Evidence Lineage
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Final, Optional


class DataOrigin(str, Enum):
    """Primary physical origin of flight and operational records."""

    REAL_AEOLUS = "REAL_AEOLUS"
    REAL_DERIVED = "REAL_DERIVED"
    SYNTHETIC = "SYNTHETIC"
    UNKNOWN = "UNKNOWN"


class PredictionSource(str, Enum):
    """Mechanism producing delay predictions or probabilistic distributions."""

    NATIVE_INFERENCE = "NATIVE_INFERENCE"
    PRECOMPUTED = "PRECOMPUTED"
    HEURISTIC = "HEURISTIC"
    NONE = "NONE"
    UNKNOWN = "UNKNOWN"


class PairingSource(str, Enum):
    """Origin of aircraft turn / tail-to-flight linkage evidence."""

    VERIFIED_ROTATION = "VERIFIED_ROTATION"
    INFERRED = "INFERRED"
    SYNTHETIC_PAIR = "SYNTHETIC_PAIR"
    UNPAIRED = "UNPAIRED"
    UNKNOWN = "UNKNOWN"


class ScenarioGeneration(str, Enum):
    """Technique employed to synthesize or construct the operational scenario."""

    HISTORICAL_REPLAY = "HISTORICAL_REPLAY"
    PARAMETRIC_SIMULATION = "PARAMETRIC_SIMULATION"
    SCALABILITY_GENERATOR = "SCALABILITY_GENERATOR"
    UNKNOWN = "UNKNOWN"


class InformationRegime(str, Enum):
    """Information barrier regime active during planning and decision making."""

    PRE_OPERATIONAL = "PRE_OPERATIONAL"
    ONLINE_RECOURSE = "ONLINE_RECOURSE"
    FULL_FORESIGHT = "FULL_FORESIGHT"
    RETROSPECTIVE = "RETROSPECTIVE"
    UNKNOWN = "UNKNOWN"


class EvaluationRegime(str, Enum):
    """Scientific evaluation regime governance."""

    DEVELOPMENT = "DEVELOPMENT"
    SELECTION_2023 = "SELECTION_2023"
    POST_HOLDOUT_2024 = "POST_HOLDOUT_2024"
    SYNTHETIC_TEST = "SYNTHETIC_TEST"
    UNKNOWN = "UNKNOWN"


class DataLineageError(ValueError):
    """Raised when data lineage or provenance verification fails."""


class SilentFallbackError(RuntimeError):
    """Raised when an unapproved silent fallback from real to synthetic data occurs."""


class ProvenanceMismatchError(ValueError):
    """Raised when claimed provenance does not match verified source evidence."""


@dataclass(frozen=True)
class EvidenceProvenance:
    """Standardized 6-dimensional evidence provenance for all Aeolus data pipelines."""

    data_origin: DataOrigin = DataOrigin.UNKNOWN
    prediction_source: PredictionSource = PredictionSource.UNKNOWN
    pairing_source: PairingSource = PairingSource.UNKNOWN
    scenario_generation: ScenarioGeneration = ScenarioGeneration.UNKNOWN
    information_regime: InformationRegime = InformationRegime.UNKNOWN
    evaluation_regime: EvaluationRegime = EvaluationRegime.UNKNOWN
    source_artifact: Optional[str] = None
    created_at_utc: Optional[str] = None
    notes: str = ""

    @property
    def is_synthetic(self) -> bool:
        """Return True if any aspect of the data or scenario is synthetic."""
        return (
            self.data_origin == DataOrigin.SYNTHETIC
            or self.scenario_generation in (
                ScenarioGeneration.PARAMETRIC_SIMULATION,
                ScenarioGeneration.SCALABILITY_GENERATOR,
            )
            or self.pairing_source == PairingSource.SYNTHETIC_PAIR
        )

    @property
    def is_real(self) -> bool:
        """Return True only if data originates strictly from real BTS/Aeolus records without synthetic pairing/generation."""
        return (
            self.data_origin in (DataOrigin.REAL_AEOLUS, DataOrigin.REAL_DERIVED)
            and self.pairing_source in (PairingSource.VERIFIED_ROTATION, PairingSource.UNPAIRED)
            and self.scenario_generation in (ScenarioGeneration.HISTORICAL_REPLAY, ScenarioGeneration.UNKNOWN)
            and self.scenario_generation != ScenarioGeneration.SCALABILITY_GENERATOR
            and self.scenario_generation != ScenarioGeneration.PARAMETRIC_SIMULATION
            and self.pairing_source != PairingSource.SYNTHETIC_PAIR
        )

    @property
    def is_verified(self) -> bool:
        """Return True if no provenance dimension remains UNKNOWN."""
        return (
            self.data_origin != DataOrigin.UNKNOWN
            and self.prediction_source != PredictionSource.UNKNOWN
            and self.pairing_source != PairingSource.UNKNOWN
            and self.scenario_generation != ScenarioGeneration.UNKNOWN
            and self.information_regime != InformationRegime.UNKNOWN
            and self.evaluation_regime != EvaluationRegime.UNKNOWN
        )

    def validate_fail_closed(
        self,
        *,
        require_real: bool = False,
        require_native: bool = False,
        forbid_unknown: bool = False,
    ) -> None:
        """Validate provenance under strict fail-closed criteria."""
        if forbid_unknown and not self.is_verified:
            unknown_dims = [
                dim_name
                for dim_name, val in [
                    ("data_origin", self.data_origin),
                    ("prediction_source", self.prediction_source),
                    ("pairing_source", self.pairing_source),
                    ("scenario_generation", self.scenario_generation),
                    ("information_regime", self.information_regime),
                    ("evaluation_regime", self.evaluation_regime),
                ]
                if val == "UNKNOWN"
            ]
            raise DataLineageError(
                f"Provenance contains unverified dimensions: {', '.join(unknown_dims)}"
            )

        if require_real and not self.is_real:
            raise SilentFallbackError(
                f"Real data required, but provenance indicates synthetic or derived components "
                f"(data_origin={self.data_origin.value}, scenario_generation={self.scenario_generation.value}, "
                f"pairing_source={self.pairing_source.value})."
            )

        if require_native and self.prediction_source != PredictionSource.NATIVE_INFERENCE:
            raise ProvenanceMismatchError(
                f"Native live inference required, but prediction_source is {self.prediction_source.value}."
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert provenance object to clean dictionary."""
        return {
            "data_origin": self.data_origin.value,
            "prediction_source": self.prediction_source.value,
            "pairing_source": self.pairing_source.value,
            "scenario_generation": self.scenario_generation.value,
            "information_regime": self.information_regime.value,
            "evaluation_regime": self.evaluation_regime.value,
            "source_artifact": self.source_artifact,
            "created_at_utc": self.created_at_utc,
            "notes": self.notes,
            "is_synthetic": self.is_synthetic,
            "is_real": self.is_real,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> EvidenceProvenance:
        """Construct EvidenceProvenance from dictionary with non-breaking fallback to UNKNOWN."""
        def _parse_enum(enum_cls: Any, key: str, default: Any) -> Any:
            raw = data.get(key)
            if raw is None:
                return default
            try:
                return enum_cls(str(raw))
            except (ValueError, KeyError):
                # Search by name or value
                for member in enum_cls:
                    if member.name == str(raw) or member.value == str(raw):
                        return member
                return default

        return cls(
            data_origin=_parse_enum(DataOrigin, "data_origin", DataOrigin.UNKNOWN),
            prediction_source=_parse_enum(PredictionSource, "prediction_source", PredictionSource.UNKNOWN),
            pairing_source=_parse_enum(PairingSource, "pairing_source", PairingSource.UNKNOWN),
            scenario_generation=_parse_enum(ScenarioGeneration, "scenario_generation", ScenarioGeneration.UNKNOWN),
            information_regime=_parse_enum(InformationRegime, "information_regime", InformationRegime.UNKNOWN),
            evaluation_regime=_parse_enum(EvaluationRegime, "evaluation_regime", EvaluationRegime.UNKNOWN),
            source_artifact=str(data["source_artifact"]) if data.get("source_artifact") else None,
            created_at_utc=str(data["created_at_utc"]) if data.get("created_at_utc") else None,
            notes=str(data.get("notes", "")),
        )


# Canonical Pre-configured Lineage Presets for Authoritative Scenarios & Artifacts
CANONICAL_P09_SCALABILITY_PROVENANCE: Final[EvidenceProvenance] = EvidenceProvenance(
    data_origin=DataOrigin.REAL_DERIVED,
    prediction_source=PredictionSource.NONE,
    pairing_source=PairingSource.UNPAIRED,
    scenario_generation=ScenarioGeneration.SCALABILITY_GENERATOR,
    information_regime=InformationRegime.PRE_OPERATIONAL,
    evaluation_regime=EvaluationRegime.SELECTION_2023,
    notes="Generated via scalability_scenario.py from sampled BTS 2023 inbound records.",
)

CANONICAL_P07_DUAL_CORE_PROVENANCE: Final[EvidenceProvenance] = EvidenceProvenance(
    data_origin=DataOrigin.REAL_DERIVED,
    prediction_source=PredictionSource.NATIVE_INFERENCE,
    pairing_source=PairingSource.SYNTHETIC_PAIR,
    scenario_generation=ScenarioGeneration.PARAMETRIC_SIMULATION,
    information_regime=InformationRegime.PRE_OPERATIONAL,
    evaluation_regime=EvaluationRegime.SELECTION_2023,
    source_artifact="artifacts/remediation/native_dual_core/turn_pairing_audit.json",
    notes="Dual-Core native predictions with synthetic pairing session.",
)

CANONICAL_REAL_AEOLUS_PROVENANCE: Final[EvidenceProvenance] = EvidenceProvenance(
    data_origin=DataOrigin.REAL_AEOLUS,
    prediction_source=PredictionSource.NONE,
    pairing_source=PairingSource.VERIFIED_ROTATION,
    scenario_generation=ScenarioGeneration.HISTORICAL_REPLAY,
    information_regime=InformationRegime.PRE_OPERATIONAL,
    evaluation_regime=EvaluationRegime.DEVELOPMENT,
    notes="Direct replay of authentic historical BTS/Aeolus operational records.",
)
