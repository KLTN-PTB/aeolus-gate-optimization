"""Parity evaluation between ExhaustiveOracle and CP-SAT formulations (P06).

Outputs certified results to artifacts/remediation/cp_sat/parity_results.json.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import (
    Flight,
    Gate,
    GateResourceType,
)
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
from src.optimization.solvers.exhaustive_oracle import solve_exhaustive_oracle


def generate_parity_cases():
    cases = []

    # Case 1: 3 flights, 2 contact gates, tight overlap
    f1 = [
        Flight("F1", 0, "VN", "101", 100, 160, 45, "G1", 100, 160),
        Flight("F2", 1, "VN", "102", 120, 180, 45, "G1", 120, 180),
        Flight("F3", 2, "VN", "103", 200, 260, 45, "G2", 200, 260),
    ]
    g1 = [
        Gate("G1", 0, is_overflow=False, resource_type=GateResourceType.CONTACT_GATE, capacity=1),
        Gate("G2", 1, is_overflow=False, resource_type=GateResourceType.CONTACT_GATE, capacity=1),
    ]
    cases.append(("tight_overlap_feasible", f1, g1, True))

    # Case 2: 3 flights, 1 contact gate (infeasible without overflow)
    cases.append(("overlap_infeasible_without_overflow", f1[:2], [g1[0]], False))

    # Case 3: 3 flights, 1 contact + 1 finite remote (capacity=1)
    g3 = [
        Gate("G1", 0, is_overflow=False, resource_type=GateResourceType.CONTACT_GATE, capacity=1),
        Gate("R1", 1, is_overflow=True, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=1),
    ]
    cases.append(("contact_plus_finite_remote", f1, g3, True))

    # Case 4: 4 flights, carrier restriction
    f4 = [
        Flight("F1", 0, "VN", "101", 100, 160, 45, "G1", 100, 160),
        Flight("F2", 1, "VJ", "102", 100, 160, 45, "G2", 100, 160),
        Flight("F3", 2, "QH", "103", 100, 160, 45, "G1", 100, 160),
        Flight("F4", 3, "VN", "104", 170, 230, 45, "G1", 170, 230),
    ]
    g4 = [
        Gate("G1", 0, is_overflow=False, resource_type=GateResourceType.CONTACT_GATE, capacity=1, allowed_carriers=["VN"]),
        Gate("G2", 1, is_overflow=False, resource_type=GateResourceType.CONTACT_GATE, capacity=1, allowed_carriers=["VJ"]),
        Gate("R1", 2, is_overflow=True, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=1),
    ]
    cases.append(("carrier_restricted_multigate", f4, g4, True))

    # Case 5: 4 flights, 1 contact + 1 pooled remote (capacity=2)
    g5 = [
        Gate("G1", 0, is_overflow=False, resource_type=GateResourceType.CONTACT_GATE, capacity=1),
        Gate("R_POOL", 1, is_overflow=True, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=2),
    ]
    cases.append(("contact_plus_pooled_remote_cap2", f4, g5, True))

    # Case 6: Cross-midnight flight
    f6 = [
        Flight("F1", 0, "VN", "101", 1400, 60, 45, "G1", 1400, 60),
        Flight("F2", 1, "VN", "102", 1420, 120, 45, "G2", 1420, 120),
        Flight("F3", 2, "VN", "103", 100, 200, 45, "G1", 100, 200),
    ]
    g6 = [
        Gate("G1", 0, is_overflow=False, resource_type=GateResourceType.CONTACT_GATE, capacity=1),
        Gate("G2", 1, is_overflow=False, resource_type=GateResourceType.CONTACT_GATE, capacity=1),
    ]
    cases.append(("cross_midnight_overlap", f6, g6, True))

    # Case 7: 5 flights, 2 contact + 1 finite remote (tight schedule)
    f7 = [
        Flight("F1", 0, "VN", "101", 100, 150, 45, "G1", 100, 150),
        Flight("F2", 1, "VN", "102", 120, 170, 45, "G2", 120, 170),
        Flight("F3", 2, "VN", "103", 140, 190, 45, "G1", 140, 190),
        Flight("F4", 3, "VN", "104", 160, 210, 45, "G2", 160, 210),
        Flight("F5", 4, "VN", "105", 180, 230, 45, "G1", 180, 230),
    ]
    g7 = [
        Gate("G1", 0, is_overflow=False, resource_type=GateResourceType.CONTACT_GATE, capacity=1),
        Gate("G2", 1, is_overflow=False, resource_type=GateResourceType.CONTACT_GATE, capacity=1),
        Gate("R1", 2, is_overflow=True, resource_type=GateResourceType.FINITE_REMOTE_STAND, capacity=1),
    ]
    cases.append(("5flights_3gates_tight", f7, g7, True))

    return cases


def run_parity():
    out_dir = Path("artifacts/remediation/cp_sat")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "parity_results.json"

    cases = generate_parity_cases()
    config = GateOptimizationConfig(scale_factor=100, num_search_workers=1)

    formulations = ["sparse_interval", "sparse_pairwise", "dense_pairwise"]

    results = []

    for name, flights, gates, allow_overflow in cases:
        case_dict = {
            "case_name": name,
            "n_flights": len(flights),
            "n_gates": len(gates),
            "allow_overflow": allow_overflow,
        }

        # Oracle solve
        oracle_res = solve_exhaustive_oracle(flights, gates, config=config, allow_overflow=allow_overflow)
        case_dict["oracle"] = {
            "feasible": oracle_res.is_feasible,
            "optimal_objective": oracle_res.optimal_objective,
            "total_enumerated": oracle_res.total_assignments_enumerated,
            "feasible_count": oracle_res.feasible_assignments_count,
        }

        # Formulations solve
        for form in formulations:
            form_cfg = GateOptimizationConfig(
                scale_factor=100,
                num_search_workers=1,
                cp_sat_formulation=form,
            )
            solver = CPSatGateSolver(config=form_cfg)
            sol_res = solver.solve(flights, gates, allow_overflow=allow_overflow)

            # Check parity
            oracle_status = "OPTIMAL" if oracle_res.is_feasible else "INFEASIBLE"
            status_match = sol_res.status == oracle_status
            feas_match = sol_res.feasible == oracle_res.is_feasible
            if oracle_res.is_feasible:
                obj_match = (
                    sol_res.objective_value is not None
                    and abs(sol_res.objective_value - oracle_res.optimal_objective) < 1e-4
                )
            else:
                obj_match = sol_res.objective_value is None or sol_res.objective_value == float("inf")

            parity_passed = status_match and feas_match and obj_match

            case_dict[form] = {
                "status": sol_res.status,
                "feasible": sol_res.feasible,
                "objective_value": sol_res.objective_value,
                "runtime_ms": sol_res.runtime_ms,
                "model_construction_ms": sol_res.solver_configuration.get("model_construction_ms"),
                "search_time_ms": sol_res.solver_configuration.get("search_time_ms"),
                "parity_passed": parity_passed,
            }

        results.append(case_dict)

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "description": "Exhaustive combinatorial oracle mathematical parity results",
                "total_cases": len(results),
                "all_parity_passed": all(
                    all(c[form]["parity_passed"] for form in formulations) for c in results
                ),
                "cases": results,
            },
            f,
            indent=2,
        )

    print(f"Parity results saved to {out_file}")
    all_pass = all(all(c[form]["parity_passed"] for form in formulations) for c in results)
    print(f"Overall parity status: {'ALL PASSED' if all_pass else 'FAILED'}")


if __name__ == "__main__":
    run_parity()
