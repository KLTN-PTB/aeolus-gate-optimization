"""Configuration and Weight Specifications for Gate Assignment Optimization.

Protocol: docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md
          docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 19 (Stage 9)
Provides:
1. Decomposed soft objective weights (reassignment, overflow, delay, conflict, risk).
2. Solver runtime and determinism configuration.
3. Separation of configuration from hardcoded solver constants.
4. Objective contract versioning and parameter validation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any

from src.models.probabilistic.contracts import PREDETERMINED_DEPLOYMENT_SEED


@dataclass(frozen=True)
class GateOptimizationConfig:
    """Configurable weights and operational settings for gate assignment optimization."""

    # Soft objective component weights (cost points)
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
    dual_core_gate_enabled: bool = False  # Feature flag for Dual Core gate optimization (default OFF)

    # Capacity and overflow semantics (P01 / P02 configuration hooks)
    finite_remote_capacity: int = 1
    allow_unbounded_overflow: bool = True
    enforce_remote_capacity: bool = False  # Default False preserves legacy behavior; activated in P02

    # Objective contract versioning (P04)
    objective_version: str = "v1"

    # CP-SAT Formulation and Scalability Settings (P06)
    cp_sat_formulation: str = "sparse_interval"  # "sparse_interval", "sparse_pairwise", "dense_pairwise"
    cp_sat_use_warm_start: bool = False
    cp_sat_fallback_to_greedy: bool = False
    total_wall_clock_budget_seconds: float | None = None

    def __post_init__(self) -> None:
        """Validate weights, timeline settings, and numerical parameters."""
        weights = [
            ("reassignment_weight", self.reassignment_weight),
            ("overflow_weight", self.overflow_weight),
            ("delay_weight", self.delay_weight),
            ("conflict_weight", self.conflict_weight),
            ("risk_weight", self.risk_weight),
        ]
        for w_name, w_val in weights:
            if not isinstance(w_val, (int, float)) or not math.isfinite(w_val):
                raise ValueError(f"{w_name} must be a finite float, got {w_val}")
            if w_val < 0.0:
                raise ValueError(f"{w_name} must be non-negative, got {w_val}")

        if not math.isfinite(self.time_limit_seconds) or self.time_limit_seconds <= 0:
            raise ValueError(f"time_limit_seconds must be a positive finite float, got {self.time_limit_seconds}")
        if not isinstance(self.scale_factor, int) or self.scale_factor <= 0:
            raise ValueError(f"scale_factor must be a positive integer, got {self.scale_factor}")
        if self.min_turnaround_minutes < 0:
            raise ValueError(f"min_turnaround_minutes must be >= 0, got {self.min_turnaround_minutes}")
        if self.default_dwell_minutes < 0:
            raise ValueError(f"default_dwell_minutes must be >= 0, got {self.default_dwell_minutes}")
        if self.separation_buffer_minutes < 0:
            raise ValueError(f"separation_buffer_minutes must be >= 0, got {self.separation_buffer_minutes}")
        if not isinstance(self.objective_version, str) or not self.objective_version.strip():
            raise ValueError(f"objective_version must be a non-empty string, got {self.objective_version}")
        if self.cp_sat_formulation not in ("sparse_interval", "sparse_pairwise", "dense_pairwise"):
            raise ValueError(
                f"cp_sat_formulation must be one of ('sparse_interval', 'sparse_pairwise', 'dense_pairwise'), "
                f"got '{self.cp_sat_formulation}'"
            )
        if self.total_wall_clock_budget_seconds is not None:
            if not math.isfinite(self.total_wall_clock_budget_seconds) or self.total_wall_clock_budget_seconds <= 0:
                raise ValueError(
                    f"total_wall_clock_budget_seconds must be positive finite float or None, got {self.total_wall_clock_budget_seconds}"
                )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compute_improvement_pct(baseline_cost: float, optimized_cost: float) -> float:
    """Compute percentage improvement safely without division by zero.

    Args:
        baseline_cost: Objective cost of the reference or initial solution.
        optimized_cost: Objective cost of the optimized candidate solution.

    Returns:
        ((baseline_cost - optimized_cost) / baseline_cost) * 100.0 if baseline_cost > 1e-9 else 0.0.
    """
    if not math.isfinite(baseline_cost) or baseline_cost <= 1e-9:
        return 0.0
    return float(((baseline_cost - optimized_cost) / baseline_cost) * 100.0)


def assert_compatible_objective_version(
    config_a: GateOptimizationConfig,
    config_b: GateOptimizationConfig,
) -> None:
    """Ensure two optimization configs have compatible objective versions for benchmark comparison.

    Raises:
        ValueError: If objective versions differ.
    """
    if config_a.objective_version != config_b.objective_version:
        raise ValueError(
            f"Cannot compare results with different objective versions: "
            f"'{config_a.objective_version}' vs '{config_b.objective_version}'"
        )
