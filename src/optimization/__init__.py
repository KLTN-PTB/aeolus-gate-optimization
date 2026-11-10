"""Gate Assignment Optimization Package.

Protocol: docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md
          docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 19 (Stage 9)
Provides:
- Flight, Gate, GateAssignment, FlightTimeWindow, OptimizationResult
- ConstraintDiagnostic, verify_hard_constraints_independently
- ObjectiveBreakdown, GateOptimizationConfig
- evaluate_gate_assignment
- CPSatGateSolver, DeterministicGreedyGateSolver
"""

from __future__ import annotations

from src.optimization.adapter import (
    DualCoreGateOptimizerAdapter,
    RoleAccessViolationError,
    UncertifiedModelError,
)
from src.optimization.config import (
    GateOptimizationConfig,
    assert_compatible_objective_version,
    compute_improvement_pct,
)
from src.optimization.domain import (
    ConstraintDiagnostic,
    Flight,
    FlightTimeWindow,
    Gate,
    GateAssignment,
    GateAssignmentState,
    GateResourceType,
    ObjectiveBreakdown,
    OptimizationResult,
    SolverStatus,
    TerminationReason,
    validate_assignments_contract,
    validate_flights_collection,
    validate_gates_collection,
    verify_hard_constraints_independently,
)
from src.optimization.evaluation import evaluate_gate_assignment
from src.optimization.sa import SAConfig, SimulatedAnnealingGateSolver
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver
from src.optimization.solvers.hybrid_solver import HybridGateSolver

__all__ = [
    "Flight",
    "Gate",
    "GateResourceType",
    "FlightTimeWindow",
    "GateAssignment",
    "GateAssignmentState",
    "SolverStatus",
    "TerminationReason",
    "ConstraintDiagnostic",
    "ObjectiveBreakdown",
    "OptimizationResult",
    "GateOptimizationConfig",
    "SAConfig",
    "CPSatGateSolver",
    "DeterministicGreedyGateSolver",
    "SimulatedAnnealingGateSolver",
    "HybridGateSolver",
    "DualCoreGateOptimizerAdapter",
    "RoleAccessViolationError",
    "UncertifiedModelError",
    "validate_flights_collection",
    "validate_gates_collection",
    "validate_assignments_contract",
    "verify_hard_constraints_independently",
    "evaluate_gate_assignment",
    "compute_improvement_pct",
    "assert_compatible_objective_version",
]
