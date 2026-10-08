"""Dual Core Gate Optimizer Adapter with Role-Based Access Control.

Protocol: Aeolus Dual Core Architecture Protocol V2
Phase: P8 Dual Core Gate Optimizer Integration & Solver Parity
Enforces:
1. Strict Role-Based Access Control (RBAC):
   - Auxiliary Departure models (ModelTask.AUXILIARY_DEPARTURE) are strictly forbidden from
     downstream optimization; attempting to use them raises RoleAccessViolationError.
   - Core Departure models must have certified selection_role="GATE_OUT_PREDICTION" and
     downstream_eligible=True; uncertified or unknown models raise UncertifiedModelError.
   - Core Arrival models must have downstream_eligible=True; uncertified models raise UncertifiedModelError.
2. Feature-Flagged Legacy Parity:
   - When config.dual_core_gate_enabled is False, preserves 100% legacy behavior (precomputed_gate_out_min=None).
   - When config.dual_core_gate_enabled is True, validates model certification, applies precomputed_gate_out_min,
     and enforces physical feasibility (D_gate_out >= A_pred + T_min).
3. Independent Verification:
   - Every solution is audited by verify_hard_constraints_independently outside the solver.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping, Sequence

from src.models.interfaces import ModelCategory, ModelSpec, ModelStatus, ModelTask
from src.models.registry import _MODEL_CATALOG, get_model_spec, is_downstream_eligible
from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import (
    ConstraintDiagnostic,
    Flight,
    Gate,
    GateAssignment,
    OptimizationResult,
    verify_hard_constraints_independently,
)
from src.optimization.evaluation import evaluate_gate_assignment
from src.simulation.dual_prediction_turn import DualAircraftTurn, SimulationMode

LOGGER = logging.getLogger(__name__)


class RoleAccessViolationError(PermissionError):
    """Raised when an auxiliary or unauthorized model attempts downstream gate optimization."""


class UncertifiedModelError(ValueError):
    """Raised when a model is uncertified, unknown, or lacks GATE_OUT_PREDICTION certification."""


class DualCoreGateOptimizerAdapter:
    """Adapter bridging DualAircraftTurn simulation entities to solver Flight entities.

    Enforces strict role-based access control, downstream model certification,
    physical feasibility invariants, and feature-flagged legacy parity.
    """

    def __init__(self, config: GateOptimizationConfig | None = None) -> None:
        self.config = config or GateOptimizationConfig()

    def validate_departure_model(self, model_id: str) -> ModelSpec:
        """Validate that a departure model is registered and certified for downstream gate optimization.

        Fails closed with:
        - UncertifiedModelError if model_id is not in registry or invalid.
        - RoleAccessViolationError if model is an Auxiliary Departure model.
        - RoleAccessViolationError if model is not a CORE_DEPARTURE task.
        - UncertifiedModelError if model lacks GATE_OUT_PREDICTION role or downstream_eligible=True.
        """
        if not model_id or not isinstance(model_id, str):
            raise UncertifiedModelError(f"Invalid model_id '{model_id}'. Must be a non-empty string.")

        if model_id not in _MODEL_CATALOG:
            raise UncertifiedModelError(
                f"Model '{model_id}' is unknown or not registered. "
                "Fail-closed: uncertified model cannot be used for gate optimization."
            )

        spec = get_model_spec(model_id)

        # 1. Auxiliary Departure is strictly forbidden from downstream gate optimization
        if (
            spec.task == ModelTask.AUXILIARY_DEPARTURE.value
            or spec.category == ModelCategory.AUXILIARY_DEPARTURE.value
        ):
            raise RoleAccessViolationError(
                f"Model '{model_id}' is an Auxiliary Departure model (task={spec.task}). "
                "Auxiliary departure models are research-only and strictly forbidden from downstream optimization."
            )

        # 2. Must be Core Departure task
        if spec.task != ModelTask.CORE_DEPARTURE.value:
            raise RoleAccessViolationError(
                f"Model '{model_id}' has task '{spec.task}', expected '{ModelTask.CORE_DEPARTURE.value}'."
            )

        # 3. Must have certified selection_role = 'GATE_OUT_PREDICTION'
        if spec.selection_role != "GATE_OUT_PREDICTION":
            raise UncertifiedModelError(
                f"Core Departure model '{model_id}' has role '{spec.selection_role}'. "
                "Requires certified selection_role='GATE_OUT_PREDICTION' to feed gate optimization."
            )

        # 4. Must be downstream_eligible
        if not spec.downstream_eligible:
            raise UncertifiedModelError(
                f"Core Departure model '{model_id}' has downstream_eligible=False. "
                "Only certified downstream-eligible models can feed gate optimization."
            )

        return spec

    def validate_arrival_model(self, model_id: str) -> ModelSpec:
        """Validate that an arrival model is registered and downstream-eligible."""
        if not model_id or not isinstance(model_id, str):
            raise UncertifiedModelError(f"Invalid arrival model_id '{model_id}'. Must be a non-empty string.")

        if model_id not in _MODEL_CATALOG:
            raise UncertifiedModelError(
                f"Arrival model '{model_id}' is unknown or not registered. Fail-closed."
            )

        spec = get_model_spec(model_id)
        if spec.task != ModelTask.CORE_ARRIVAL.value:
            raise RoleAccessViolationError(
                f"Model '{model_id}' has task '{spec.task}', expected '{ModelTask.CORE_ARRIVAL.value}'."
            )

        if not spec.downstream_eligible:
            raise UncertifiedModelError(
                f"Arrival model '{model_id}' has downstream_eligible=False. Fail-closed."
            )

        return spec

    def turns_to_flights(
        self,
        turns: Sequence[DualAircraftTurn],
        *,
        departure_model_id: str | None = None,
        arrival_model_id: str | None = None,
    ) -> list[Flight]:
        """Convert DualAircraftTurn simulation entities to optimization Flight domain objects.

        If config.dual_core_gate_enabled is False:
            - Preserves 100% legacy parity.
            - precomputed_gate_out_min is None.
            - Departure model validation is bypassed (departure models are unused).
        If config.dual_core_gate_enabled is True:
            - Validates departure_model_id via validate_departure_model.
            - If arrival_model_id is provided, validates it via validate_arrival_model.
            - Converts turns with dual_core_enabled=True.
            - Flight domain enforces physical feasibility D_gate_out >= A_pred + T_min.
        """
        if not self.config.dual_core_gate_enabled:
            # Legacy Parity Mode: ignore departure models, yield precomputed_gate_out_min=None
            return [
                turn.to_flight(flight_index=idx, dual_core_enabled=False)
                for idx, turn in enumerate(turns)
            ]

        # Dual Core Enabled Mode: strictly enforce model certification
        if departure_model_id is None:
            raise ValueError(
                "departure_model_id is required when dual_core_gate_enabled is True."
            )

        self.validate_departure_model(departure_model_id)

        if arrival_model_id is not None:
            self.validate_arrival_model(arrival_model_id)

        flights: list[Flight] = []
        for idx, turn in enumerate(turns):
            flight = turn.to_flight(flight_index=idx, dual_core_enabled=True)
            flights.append(flight)

        return flights

    def solve(
        self,
        solver: Any,
        turns: Sequence[DualAircraftTurn],
        gates: Sequence[Gate],
        *,
        departure_model_id: str | None = None,
        arrival_model_id: str | None = None,
        allow_overflow: bool = True,
    ) -> OptimizationResult:
        """Translate turns, solve gate assignment with specified solver, and independently audit."""
        flights = self.turns_to_flights(
            turns,
            departure_model_id=departure_model_id,
            arrival_model_id=arrival_model_id,
        )
        result = solver.solve(flights, gates, allow_overflow=allow_overflow)

        # Independent verification audit outside solver
        diag = verify_hard_constraints_independently(
            flights=flights,
            gates=gates,
            assignments=result.assignments,
        )
        if not diag.is_valid:
            LOGGER.error(
                "Independent hard constraint audit failed: violations=%d, conflicts=%d",
                diag.hard_constraint_violations_count,
                diag.conflict_count,
            )

        return result
