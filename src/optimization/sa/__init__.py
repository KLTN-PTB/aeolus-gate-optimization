"""Simulated Annealing Gate Assignment Optimization Package.

Protocol: docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md
          docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 19 (Stage 9)
Provides:
- SAState, create_initial_state
- compute_state_objective, evaluate_state
- try_move_flight, try_swap_flights, repair_state, generate_neighbor
- SAConfig, SALogEntry, SimulatedAnnealingGateSolver
"""

from __future__ import annotations

from src.optimization.sa.annealer import (
    SAConfig,
    SALogEntry,
    SimulatedAnnealingGateSolver,
)
from src.optimization.sa.neighborhood import (
    generate_neighbor,
    repair_state,
    try_move_flight,
    try_swap_flights,
)
from src.optimization.sa.objective import (
    compute_state_objective,
    evaluate_state,
)
from src.optimization.sa.state import (
    SAState,
    create_initial_state,
)

__all__ = [
    "SAState",
    "create_initial_state",
    "compute_state_objective",
    "evaluate_state",
    "try_move_flight",
    "try_swap_flights",
    "repair_state",
    "generate_neighbor",
    "SAConfig",
    "SALogEntry",
    "SimulatedAnnealingGateSolver",
]
