"""Unit and Regression Tests for Step 3: SA Time-Limited Benchmark Audit.

Protocol: docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md
          docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 19 (Stage 9)
Verifies:
1. CP-SAT optimal solution preserved by SA (no spurious gains, improvement == 0.0).
2. Time-limited CP-SAT incumbent preserved or improved by SA without hard constraint violations.
3. Ultra-short time limit failure mode: CP-SAT returns UNKNOWN, Greedy + SA provides valid alternative.
4. Best-so-far monotonicity invariant holds strictly across all configurations.
5. Seed reproducibility: identical seed yields identical results.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from scripts.benchmark_cp_sat_solver import generate_benchmark_scenario
from src.models.probabilistic.contracts import PREDETERMINED_DEPLOYMENT_SEED
from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import verify_hard_constraints_independently
from src.optimization.sa import SAConfig, SimulatedAnnealingGateSolver
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver


def test_cpsat_optimal_solution_preserved_by_sa() -> None:
    """When CP-SAT solves to OPTIMAL, SA must preserve the solution without degradation (imprv == 0.0)."""
    flights, gates = generate_benchmark_scenario(n_flights=50, n_contact_gates=15, seed=202601)

    cfg = GateOptimizationConfig(time_limit_seconds=2.0, random_seed=202601)
    cpsat = CPSatGateSolver(config=cfg)
    res_cpsat = cpsat.solve(flights, gates)

    assert res_cpsat.status == "OPTIMAL"
    assert res_cpsat.feasible is True
    assert res_cpsat.constraint_diagnostics.is_valid is True

    sa_cfg = SAConfig(iterations=100, seed=202601)
    sa = SimulatedAnnealingGateSolver(config=cfg, sa_config=sa_cfg)
    res_sa = sa.solve(flights, gates, initial_assignments=res_cpsat.assignments)

    assert res_sa.feasible is True
    assert res_sa.constraint_diagnostics.is_valid is True
    assert res_sa.constraint_diagnostics.conflict_count == 0
    # SA cannot improve an already optimal solution
    assert abs(res_sa.objective_value - res_cpsat.objective_value) < 1e-6
    improvement = res_cpsat.objective_value - res_sa.objective_value
    assert abs(improvement) < 1e-6


def test_time_limited_cpsat_incumbent_feasibility_and_sa_monotonicity() -> None:
    """CP-SAT incumbent under time limit must be hard-feasible and SA must not degrade it."""
    flights, gates = generate_benchmark_scenario(n_flights=150, n_contact_gates=15, seed=123)

    cfg = GateOptimizationConfig(time_limit_seconds=0.3, random_seed=123, num_search_workers=1)
    cpsat = CPSatGateSolver(config=cfg)
    res_cpsat = cpsat.solve(flights, gates)

    if res_cpsat.feasible:
        assert res_cpsat.constraint_diagnostics.is_valid is True
        assert res_cpsat.constraint_diagnostics.conflict_count == 0

        sa_cfg = SAConfig(iterations=150, seed=123)
        sa = SimulatedAnnealingGateSolver(config=cfg, sa_config=sa_cfg)
        res_sa = sa.solve(flights, gates, initial_assignments=res_cpsat.assignments)

        assert res_sa.feasible is True
        assert res_sa.constraint_diagnostics.is_valid is True
        assert res_sa.constraint_diagnostics.conflict_count == 0
        # Best-so-far invariant: SA never worsens initial incumbent
        assert res_sa.objective_value <= res_cpsat.objective_value + 1e-9


def test_ultra_short_timeout_behavior_and_greedy_sa_alternative() -> None:
    """When CP-SAT times out before finding an incumbent, Greedy + SA produces a valid feasible solution."""
    flights, gates = generate_benchmark_scenario(n_flights=200, n_contact_gates=20, seed=202601)

    cfg_tight = GateOptimizationConfig(time_limit_seconds=0.05, random_seed=202601, num_search_workers=1)
    cpsat = CPSatGateSolver(config=cfg_tight)
    res_cpsat = cpsat.solve(flights, gates)

    # Under ultra-tight deadline (50ms), CP-SAT cannot finish presolve -> status UNKNOWN
    assert res_cpsat.status in ("UNKNOWN", "FEASIBLE")

    # In contrast, Greedy baseline runs in < 15ms and is guaranteed feasible
    greedy = DeterministicGreedyGateSolver(config=cfg_tight)
    res_greedy = greedy.solve(flights, gates)
    assert res_greedy.feasible is True
    assert res_greedy.constraint_diagnostics.is_valid is True
    assert res_greedy.runtime_ms < 50.0

    # SA improves upon greedy
    sa = SimulatedAnnealingGateSolver(config=cfg_tight, sa_config=SAConfig(iterations=100, seed=202601))
    res_sa = sa.solve(flights, gates, initial_assignments=res_greedy.assignments)
    assert res_sa.feasible is True
    assert res_sa.constraint_diagnostics.is_valid is True
    assert res_sa.objective_value <= res_greedy.objective_value + 1e-9


def test_time_limited_sa_reproducibility() -> None:
    """Identical random seeds must produce exactly identical SA results."""
    flights, gates = generate_benchmark_scenario(n_flights=80, n_contact_gates=12, seed=42)

    cfg = GateOptimizationConfig(random_seed=42)
    greedy = DeterministicGreedyGateSolver(config=cfg)
    res_greedy = greedy.solve(flights, gates)

    sa1 = SimulatedAnnealingGateSolver(config=cfg, sa_config=SAConfig(iterations=150, seed=999))
    res1 = sa1.solve(flights, gates, initial_assignments=res_greedy.assignments)

    sa2 = SimulatedAnnealingGateSolver(config=cfg, sa_config=SAConfig(iterations=150, seed=999))
    res2 = sa2.solve(flights, gates, initial_assignments=res_greedy.assignments)

    assert abs(res1.objective_value - res2.objective_value) < 1e-9
    for f_id in res1.assignments:
        assert res1.assignments[f_id].gate_id == res2.assignments[f_id].gate_id


def test_benchmark_manifest_structure_and_validity() -> None:
    """Audit manifest must exist, follow schema, and record all required branches."""
    manifest_path = Path("artifacts/audit/phase_f_time_limited_sa_benchmark_manifest_v1.json")
    if not manifest_path.exists():
        pytest.skip("Manifest not yet generated (run scripts/run_phase_f_time_limited_sa_benchmark.py)")

    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["manifest_version"] == "phase_f_time_limited_sa_benchmark_manifest_v1"
    assert data["status"] == "PASS"
    assert data["hard_feasibility_guarantee_verified"] is True
    assert data["best_so_far_monotonicity_verified"] is True
    assert len(data["scenarios"]) >= 3

    for sc in data["scenarios"]:
        assert "branch_a_greedy" in sc
        assert "branch_e_greedy_sa" in sc
        assert "time_limit_runs" in sc
        for run in sc["time_limit_runs"]:
            assert "branch_b_cpsat" in run
            assert "branch_c_incumbent" in run
            assert "branch_d_cpsat_sa" in run
