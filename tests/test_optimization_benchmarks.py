"""Tests for Optimization Benchmarking and Operational Scale Verification.

Protocol: docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md
          docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 19 (Stage 9)
Verifies:
1. Operational instance generation at scale (100+ flights across realistic daily window).
2. Solver returns feasible/optimal solution satisfying all hard constraints.
3. Zero contact gate conflicts independently verified.
"""

from __future__ import annotations

import pytest

from scripts.benchmark_cp_sat_solver import generate_benchmark_scenario
from src.optimization.config import GateOptimizationConfig
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver


def test_benchmark_instance_generation_and_solve() -> None:
    """Verify that a 100-flight, 20-gate operational scenario solves cleanly."""
    flights, gates = generate_benchmark_scenario(n_flights=100, n_contact_gates=20, seed=202601)

    assert len(flights) == 100
    assert len(gates) == 21  # 20 contact gates + 1 overflow stand

    config = GateOptimizationConfig(
        time_limit_seconds=10.0,
        num_search_workers=1,
        random_seed=202601,
    )
    solver = CPSatGateSolver(config=config)
    result = solver.solve(flights, gates)

    assert result.feasible is True
    assert result.status in ("OPTIMAL", "FEASIBLE")
    assert result.constraint_diagnostics.is_valid is True
    assert result.constraint_diagnostics.no_contact_gate_conflicts is True
    assert result.constraint_diagnostics.conflict_count == 0
    assert len(result.assignments) == 100
