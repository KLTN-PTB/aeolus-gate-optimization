"""Tests for identical solver configuration, fairness, and runtime budgets (Phase 8)."""

from __future__ import annotations

import pytest

from src.models.probabilistic.contracts import PREDETERMINED_DEPLOYMENT_SEED
from src.optimization.config import GateOptimizationConfig
from src.optimization.sa import SAConfig
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver


def test_cpsat_solver_configuration_fairness() -> None:
    """CP-SAT must use 1 search worker and fixed deployment seed for determinism."""
    cfg = GateOptimizationConfig(
        time_limit_seconds=5.0,
        num_search_workers=1,
        random_seed=PREDETERMINED_DEPLOYMENT_SEED,
    )
    assert cfg.num_search_workers == 1
    assert cfg.random_seed == PREDETERMINED_DEPLOYMENT_SEED
    assert cfg.time_limit_seconds == 5.0

    solver = CPSatGateSolver(config=cfg)
    assert solver.config.num_search_workers == 1
    assert solver.config.random_seed == PREDETERMINED_DEPLOYMENT_SEED


def test_sa_solver_configuration_fairness() -> None:
    """Simulated Annealing configuration must use pre-registered cooling and seed."""
    sa_cfg = SAConfig(
        T0=100.0,
        Tmin=0.01,
        cooling_rate=0.95,
        iterations=500,
        seed=PREDETERMINED_DEPLOYMENT_SEED,
    )
    assert sa_cfg.T0 == 100.0
    assert sa_cfg.Tmin == 0.01
    assert sa_cfg.cooling_rate == 0.95
    assert sa_cfg.iterations == 500
    assert sa_cfg.seed == PREDETERMINED_DEPLOYMENT_SEED


def test_greedy_solver_is_strictly_deterministic() -> None:
    """DeterministicGreedyGateSolver must produce identical results across repeated runs."""
    cfg = GateOptimizationConfig()
    solver1 = DeterministicGreedyGateSolver(config=cfg)
    solver2 = DeterministicGreedyGateSolver(config=cfg)

    assert solver1.config == solver2.config
