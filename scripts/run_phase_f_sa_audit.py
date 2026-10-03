"""Phase F — Comparative Audit: Simulated Annealing vs Greedy Baseline & CP-SAT.

Protocol: docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md
          docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 19 (Stage 9)
Compares:
1. Deterministic Greedy Heuristic Baseline (Phase E)
2. Simulated Annealing Metaheuristic (Phase F)
3. Exact CP-SAT Solver (Phase D)
Under:
- Exact same flights, occupancy intervals, and gates.
- Exact same hard constraints (independent verification).
- Exact same common evaluator: evaluate_gate_assignment().
- Decomposed soft objective breakdown.
- Emits artifacts/audit/phase_f_simulated_annealing_manifest_v1.json.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

# Ensure repo root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.benchmark_cp_sat_solver import generate_benchmark_scenario
from src.models.probabilistic.contracts import PREDETERMINED_DEPLOYMENT_SEED
from src.optimization.config import GateOptimizationConfig
from src.optimization.sa import SAConfig, SimulatedAnnealingGateSolver
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver


def run_phase_f_audit() -> dict[str, Any]:
    """Execute head-to-head comparison across Greedy, SA, and CP-SAT."""
    print("=" * 80)
    print("STARTING PHASE F: SIMULATED ANNEALING METAHEURISTIC COMPARATIVE AUDIT")
    print("Protocol: docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md")
    print("=" * 80)

    config = GateOptimizationConfig(
        reassignment_weight=10.0,
        overflow_weight=200.0,
        delay_weight=1.0,
        conflict_weight=1000.0,
        risk_weight=2.0,
        time_limit_seconds=15.0,
        num_search_workers=1,
        random_seed=PREDETERMINED_DEPLOYMENT_SEED,
    )

    sa_config = SAConfig(
        T0=100.0,
        Tmin=0.01,
        cooling_rate=0.98,
        iterations=1000,
        seed=PREDETERMINED_DEPLOYMENT_SEED,
    )

    greedy_solver = DeterministicGreedyGateSolver(config=config)
    sa_solver = SimulatedAnnealingGateSolver(config=config, sa_config=sa_config)
    cpsat_solver = CPSatGateSolver(config=config)

    test_matrix = [
        (100, 20),
        (100, 30),
        (200, 20),
        (200, 30),
    ]

    comparisons: list[dict[str, Any]] = []

    for n_fl, n_gt in test_matrix:
        scenario_id = f"F{n_fl}_G{n_gt}"
        print(f"\n--- Scenario {scenario_id} ({n_fl} flights, {n_gt} gates) ---")

        flights, gates = generate_benchmark_scenario(
            n_flights=n_fl,
            n_contact_gates=n_gt,
            seed=PREDETERMINED_DEPLOYMENT_SEED + n_fl * 10 + n_gt,
        )

        # 1. Greedy
        res_greedy = greedy_solver.solve(flights, gates)
        assert res_greedy.constraint_diagnostics.is_valid is True
        assert res_greedy.constraint_diagnostics.conflict_count == 0

        # 2. Simulated Annealing (initialized with greedy)
        res_sa = sa_solver.solve(flights, gates, initial_assignments=res_greedy.assignments)
        assert res_sa.constraint_diagnostics.is_valid is True
        assert res_sa.constraint_diagnostics.conflict_count == 0

        # 3. CP-SAT (exact)
        res_cpsat = cpsat_solver.solve(flights, gates)
        assert res_cpsat.constraint_diagnostics.is_valid is True
        assert res_cpsat.constraint_diagnostics.conflict_count == 0

        obj_greedy = res_greedy.objective_value
        obj_sa = res_sa.objective_value
        obj_cpsat = res_cpsat.objective_value

        sa_imprv_over_greedy = ((obj_greedy - obj_sa) / max(obj_greedy, 1e-6)) * 100.0
        cpsat_imprv_over_greedy = ((obj_greedy - obj_cpsat) / max(obj_greedy, 1e-6)) * 100.0

        greedy_reassigns = sum(1 for a in res_greedy.assignments.values() if a.is_reassignment)
        sa_reassigns = sum(1 for a in res_sa.assignments.values() if a.is_reassignment)
        cpsat_reassigns = sum(1 for a in res_cpsat.assignments.values() if a.is_reassignment)

        greedy_ovf = sum(1 for a in res_greedy.assignments.values() if a.is_overflow)
        sa_ovf = sum(1 for a in res_sa.assignments.values() if a.is_overflow)
        cpsat_ovf = sum(1 for a in res_cpsat.assignments.values() if a.is_overflow)

        rec = {
            "scenario": scenario_id,
            "n_flights": n_fl,
            "n_gates": n_gt,
            "greedy_objective": obj_greedy,
            "sa_objective": obj_sa,
            "cpsat_objective": obj_cpsat,
            "sa_improvement_over_greedy_pct": sa_imprv_over_greedy,
            "cpsat_improvement_over_greedy_pct": cpsat_imprv_over_greedy,
            "greedy_runtime_ms": res_greedy.runtime_ms,
            "sa_runtime_ms": res_sa.runtime_ms,
            "cpsat_runtime_ms": res_cpsat.runtime_ms,
            "greedy_reassignments": greedy_reassigns,
            "sa_reassignments": sa_reassigns,
            "cpsat_reassignments": cpsat_reassigns,
            "greedy_overflows": greedy_ovf,
            "sa_overflows": sa_ovf,
            "cpsat_overflows": cpsat_ovf,
            "all_hard_constraints_satisfied": True,
            "zero_contact_conflicts": True,
        }
        comparisons.append(rec)

        print(f"  Greedy: Obj={obj_greedy:.2f}, Time={res_greedy.runtime_ms:.1f}ms, Reassign={greedy_reassigns}, OVF={greedy_ovf}")
        print(f"  SA:     Obj={obj_sa:.2f}, Time={res_sa.runtime_ms:.1f}ms, Reassign={sa_reassigns}, OVF={sa_ovf} (Imprv: {sa_imprv_over_greedy:.1f}%)")
        print(f"  CP-SAT: Obj={obj_cpsat:.2f}, Time={res_cpsat.runtime_ms:.1f}ms, Reassign={cpsat_reassigns}, OVF={cpsat_ovf} (Imprv: {cpsat_imprv_over_greedy:.1f}%)")

    audit_dir = PROJECT_ROOT / "artifacts" / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = audit_dir / "phase_f_simulated_annealing_manifest_v1.json"

    manifest_content = {
        "manifest_version": "phase_f_simulated_annealing_manifest_v1",
        "phase": "PHASE_F",
        "status": "PASS",
        "protocol_reference": "docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md",
        "evaluation_protocol": "evaluate_gate_assignment (common evaluator)",
        "sa_config": sa_config.to_dict(),
        "all_hard_constraints_satisfied": all(c["all_hard_constraints_satisfied"] for c in comparisons),
        "zero_contact_conflicts_verified": all(c["zero_contact_conflicts"] for c in comparisons),
        "total_comparisons": len(comparisons),
        "comparisons": comparisons,
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_content, f, indent=2)

    print(f"\n[Artifact Created] Phase F Manifest written to: {manifest_path}")
    print("\n" + "=" * 80)
    print("PHASE F SIMULATED ANNEALING AUDIT: PASS")
    print("=" * 80)

    return manifest_content


if __name__ == "__main__":
    run_phase_f_audit()
