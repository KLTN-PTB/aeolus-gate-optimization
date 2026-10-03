"""Configuration and Weight Specifications for Gate Assignment Optimization.

Protocol: docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md
          docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 19 (Stage 9)
Provides:
1. Decomposed soft objective weights (reassignment, overflow, delay, conflict, risk).
2. Solver runtime and determinism configuration.
3. Separation of configuration from hardcoded solver constants.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from src.models.probabilistic.contracts import PREDETERMINED_DEPLOYMENT_SEED


@dataclass(frozen=True)
class GateOptimizationConfig:
    """Configurable weights and operational settings for CP-SAT gate assignment."""

    # Soft objective component weights
    reassignment_weight: float = 10.0
    overflow_weight: float = 200.0
    delay_weight: float = 1.0
    conflict_weight: float = 1000.0
    risk_weight: float = 2.0

    # Operational timeline defaults (minutes)
    min_turnaround_minutes: int = 45
    default_dwell_minutes: int = 60
    separation_buffer_minutes: int = 15

    # Solver execution settings
    time_limit_seconds: float = 10.0
    num_search_workers: int = 1  # 1 worker guarantees strict reproducibility
    random_seed: int = PREDETERMINED_DEPLOYMENT_SEED
    log_search_progress: bool = False
    scale_factor: int = 100  # Multiplier to scale floating costs to integer objective

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
