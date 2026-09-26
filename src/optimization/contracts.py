"""Data contracts for the gate optimization and simulation modules.

Aligned with project contracts style (e.g. src/models/contracts.py).
Enforces valid model-derived predictions and prohibits direct usage of raw target labels.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Optional


class GateOptimizationContractViolation(ValueError):
    """Raised when a gate optimization contract or data instance is invalid."""


@dataclass
class Flight:
    """Represents a flight movement requiring gate assignment.

    Input attributes `p_delay` and `delay_est_min` MUST originate from ML model outputs
    (dual prediction architecture), NEVER from raw ground truth labels ARR_DELAY or DEP_DELAY.
    """

    flight_id: str
    direction: str = "ARR"  # "ARR" | "DEP"
    aircraft_type: str = "ALL"
    sched_time_min: int = 0
    p_delay: float = 0.0
    delay_est_min: float = 0.0
    dwell_time_min: int = 45
    chain_group_id: Optional[str] = None
    current_gate: Optional[str] = None
    priority_weight: float = 1.0

    def __post_init__(self) -> None:
        if not self.flight_id or not isinstance(self.flight_id, str):
            raise GateOptimizationContractViolation("flight_id must be a non-empty string")
        if self.direction not in ("ARR", "DEP"):
            raise GateOptimizationContractViolation(
                f"direction must be 'ARR' or 'DEP', got {self.direction!r}"
            )
        if not self.aircraft_type or not isinstance(self.aircraft_type, str):
            raise GateOptimizationContractViolation("aircraft_type must be a non-empty string")
        if self.sched_time_min < 0:
            raise GateOptimizationContractViolation("sched_time_min cannot be negative")
        if not (0.0 <= self.p_delay <= 1.0):
            raise GateOptimizationContractViolation(
                f"p_delay must be in [0.0, 1.0], got {self.p_delay}"
            )
        if self.dwell_time_min <= 0:
            raise GateOptimizationContractViolation("dwell_time_min must be positive")
        if self.priority_weight <= 0.0:
            raise GateOptimizationContractViolation("priority_weight must be positive")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Flight:
        return cls(**data)


@dataclass
class Gate:
    """Represents an airport gate resource."""

    gate_id: str
    compatible_types: list[str] = field(default_factory=lambda: ["ALL"])
    is_contact_gate: bool = True
    available_from_min: int = 0
    available_to_min: int = 1440
    adjacent_gates: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.gate_id or not isinstance(self.gate_id, str):
            raise GateOptimizationContractViolation("gate_id must be a non-empty string")
        if not isinstance(self.compatible_types, list) or not self.compatible_types:
            raise GateOptimizationContractViolation("compatible_types must be a non-empty list of strings")
        if self.available_from_min < 0 or self.available_to_min <= self.available_from_min:
            raise GateOptimizationContractViolation(
                f"invalid availability interval: [{self.available_from_min}, {self.available_to_min}]"
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Gate:
        return cls(**data)


@dataclass
class CostParams:
    """Cost parameters for optimization objective and soft penalties."""

    buffer_time_min: int = 15
    delay_cost_weight: float = 1.0
    reassignment_cost_default: float = 50.0
    remote_gate_cost: float = 20.0

    def __post_init__(self) -> None:
        if self.buffer_time_min < 0:
            raise GateOptimizationContractViolation("buffer_time_min cannot be negative")
        if self.delay_cost_weight < 0.0:
            raise GateOptimizationContractViolation("delay_cost_weight cannot be negative")
        if self.reassignment_cost_default < 0.0:
            raise GateOptimizationContractViolation("reassignment_cost_default cannot be negative")
        if self.remote_gate_cost < 0.0:
            raise GateOptimizationContractViolation("remote_gate_cost cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CostParams:
        return cls(**data)


# Alias for backward compatibility
CostParameters = CostParams


@dataclass
class ProblemInstance:
    """Full optimization problem instance encapsulating flights, gates, and parameters."""

    airport: str = "ATL"
    planning_date: str = "2026-09-20"
    horizon_min: int = 1440
    flights: list[Flight] = field(default_factory=list)
    gates: list[Gate] = field(default_factory=list)
    cost_params: CostParams = field(default_factory=CostParams)


    def __post_init__(self) -> None:
        if not self.airport or not isinstance(self.airport, str):
            raise GateOptimizationContractViolation("airport must be a non-empty string")
        if not self.planning_date or not isinstance(self.planning_date, str):
            raise GateOptimizationContractViolation("planning_date must be a non-empty string")
        if self.horizon_min <= 0:
            raise GateOptimizationContractViolation("horizon_min must be positive")
        if not isinstance(self.flights, list) or not self.flights:
            raise GateOptimizationContractViolation("flights must be a non-empty list of Flight instances")
        if not isinstance(self.gates, list) or not self.gates:
            raise GateOptimizationContractViolation("gates must be a non-empty list of Gate instances")

        # Check unique flight and gate identifiers
        flight_ids = [f.flight_id for f in self.flights]
        if len(flight_ids) != len(set(flight_ids)):
            raise GateOptimizationContractViolation("duplicate flight_id detected in ProblemInstance")

        gate_ids = [g.gate_id for g in self.gates]
        if len(gate_ids) != len(set(gate_ids)):
            raise GateOptimizationContractViolation("duplicate gate_id detected in ProblemInstance")

    def to_dict(self) -> dict[str, Any]:
        return {
            "airport": self.airport,
            "planning_date": self.planning_date,
            "horizon_min": self.horizon_min,
            "flights": [f.to_dict() for f in self.flights],
            "gates": [g.to_dict() for g in self.gates],
            "cost_params": self.cost_params.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProblemInstance:
        return cls(
            airport=data.get("airport", "ATL"),
            planning_date=data.get("planning_date", "2026-09-20"),
            horizon_min=data.get("horizon_min", 1440),
            flights=[Flight.from_dict(f) for f in data["flights"]],
            gates=[Gate.from_dict(g) for g in data["gates"]],
            cost_params=CostParams.from_dict(data["cost_params"]),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> ProblemInstance:
        return cls.from_dict(json.loads(json_str))

