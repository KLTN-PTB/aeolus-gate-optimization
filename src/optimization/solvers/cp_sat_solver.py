"""Google OR-Tools CP-SAT Gate Assignment Solver.

Protocol: docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md
          docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 19 (Stage 9)
Provides:
1. Decision variables: x[f, g] in {0, 1} where x[f, g] = 1 iff flight f is assigned to gate g.
2. Hard constraints:
   - Exactly one gate per flight
   - Overlap prevention on contact gates
   - Gate operational availability windows
   - Carrier and aircraft type compatibility
3. Decomposed soft objective:
   - Reassignment penalty (deviation from nominal plan)
   - Remote stand / overflow apron penalty
   - Operational delay and turnaround risk penalties
4. Independent verification of all hard constraints outside the solver.
5. Deterministic reproducibility via seed-controlled single-worker search.
"""

from __future__ import annotations

import time
from typing import Any, Sequence

import numpy as np
from ortools.sat.python import cp_model

from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import (
    ConstraintDiagnostic,
    Flight,
    Gate,
    GateAssignment,
    ObjectiveBreakdown,
    OptimizationResult,
    verify_hard_constraints_independently,
)
from src.optimization.evaluation import evaluate_gate_assignment


class CPSatGateSolver:
    """Exact Constraint Programming gate assignment solver backed by OR-Tools CP-SAT."""

    def __init__(self, config: GateOptimizationConfig | None = None) -> None:
        self.config = config or GateOptimizationConfig()

    def solve(
        self,
        flights: Sequence[Flight],
        gates: Sequence[Gate],
        *,
        allow_overflow: bool = True,
    ) -> OptimizationResult:
        """Solve optimal gate assignment problem for a batch of flights and gates.

        Args:
            flights: Sequence of Flight domain entities with computed time windows.
            gates: Sequence of Gate entities (contact gates and optional overflow stands).
            allow_overflow: If True and no overflow gate is in gates, adds an overflow stand.

        Returns:
            OptimizationResult containing status, objective breakdown, assignments,
            and independent hard-constraint verification diagnostics.
        """
        t0 = time.perf_counter()

        n_flights = len(flights)
        if n_flights == 0:
            return OptimizationResult(
                status="FEASIBLE",
                objective_value=0.0,
                objective_breakdown=ObjectiveBreakdown(
                    total_cost=0.0,
                    reassignment_cost=0.0,
                    overflow_cost=0.0,
                    delay_cost=0.0,
                    conflict_cost=0.0,
                    risk_cost=0.0,
                    weights=self.config.to_dict(),
                ),
                feasible=True,
                runtime_ms=0.0,
                optimality_gap=0.0,
                assignments={},
                constraint_diagnostics=ConstraintDiagnostic(
                    all_flights_assigned=True,
                    no_contact_gate_conflicts=True,
                    gate_availability_satisfied=True,
                    gate_compatibility_satisfied=True,
                    turnaround_valid=True,
                    conflict_count=0,
                    conflict_pairs=[],
                    incompatibility_violations=[],
                    availability_violations=[],
                ),
                solver_configuration=self.config.to_dict(),
            )

        # Prepare gate list
        gate_list = list(gates)
        has_overflow = any(g.is_overflow for g in gate_list)
        if allow_overflow and not has_overflow:
            overflow_gate = Gate(
                gate_id="OVERFLOW_APRON",
                gate_index=len(gate_list),
                is_overflow=True,
            )
            gate_list.append(overflow_gate)

        n_gates = len(gate_list)
        model = cp_model.CpModel()

        # =====================================================================
        # STEP 3: DECISION VARIABLES: x[f, g] in {0, 1}
        # =====================================================================
        x: dict[tuple[int, int], cp_model.IntVar] = {}
        for f_idx in range(n_flights):
            for g_idx in range(n_gates):
                x[f_idx, g_idx] = model.NewBoolVar(f"x_{f_idx}_{g_idx}")

        # =====================================================================
        # STEP 4: HARD CONSTRAINTS
        # =====================================================================
        # 1. Exactly one gate per flight
        for f_idx in range(n_flights):
            model.Add(sum(x[f_idx, g_idx] for g_idx in range(n_gates)) == 1)

        # 2. Overlapping occupancy intervals cannot use the same contact gate
        sorted_indices = sorted(range(n_flights), key=lambda idx: flights[idx].time_window.start_min)
        overlapping_pairs: list[tuple[int, int]] = []
        for a, i in enumerate(sorted_indices):
            w_i = flights[i].time_window
            for b in range(a + 1, n_flights):
                j = sorted_indices[b]
                if flights[j].time_window.start_min >= w_i.end_min:
                    break
                if w_i.overlaps(flights[j].time_window):
                    overlapping_pairs.append((i, j))

        for g_idx, gate in enumerate(gate_list):
            if gate.is_overflow:
                continue  # Overflow stand has infinite capacity / no conflict

            for i, j in overlapping_pairs:
                model.Add(x[i, g_idx] + x[j, g_idx] <= 1)

        # 3. Gate operational availability windows
        for f_idx, fl in enumerate(flights):
            for g_idx, gate in enumerate(gate_list):
                if not gate.is_available_during(fl.time_window):
                    model.Add(x[f_idx, g_idx] == 0)

        # 4. Gate carrier and aircraft type compatibility
        for f_idx, fl in enumerate(flights):
            for g_idx, gate in enumerate(gate_list):
                if not gate.is_compatible_carrier(fl.carrier):
                    model.Add(x[f_idx, g_idx] == 0)
                elif not gate.is_compatible_aircraft(fl.aircraft_type):
                    model.Add(x[f_idx, g_idx] == 0)

        # =====================================================================
        # STEP 5: DECOMPOSED SOFT OBJECTIVE
        # =====================================================================
        # Scale factor converts float weights into integers for CP-SAT
        sf = self.config.scale_factor
        objective_terms = []

        for f_idx, fl in enumerate(flights):
            nom_gate_id = fl.nominal_gate_id

            for g_idx, gate in enumerate(gate_list):
                var = x[f_idx, g_idx]
                cost = 0.0

                # A. Reassignment cost (deviation from nominal plan on contact gate)
                if not gate.is_overflow:
                    if nom_gate_id is not None and gate.gate_id != nom_gate_id:
                        cost += self.config.reassignment_weight

                # B. Overflow penalty (remote stand)
                if gate.is_overflow:
                    cost += self.config.overflow_weight
                    if nom_gate_id is not None:
                        cost += self.config.reassignment_weight

                # Note: delay_cost and risk_cost are exogenous reporting metrics
                # (constant across all gate choices g for flight f since sum_g x[f, g] = 1).
                # They are evaluated in evaluate_gate_assignment() and not added to CP-SAT
                # decision variables to prevent integer scaling distortion.

                int_coeff = int(round(cost * sf))
                if int_coeff != 0:
                    objective_terms.append(int_coeff * var)

        if objective_terms:
            model.Minimize(sum(objective_terms))

        # =====================================================================
        # SOLVER EXECUTION
        # =====================================================================
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = float(self.config.time_limit_seconds)
        solver.parameters.num_search_workers = int(self.config.num_search_workers)
        solver.parameters.random_seed = int(self.config.random_seed)
        solver.parameters.log_search_progress = bool(self.config.log_search_progress)

        raw_status = solver.Solve(model)
        runtime_ms = (time.perf_counter() - t0) * 1000.0

        status_map = {
            cp_model.OPTIMAL: "OPTIMAL",
            cp_model.FEASIBLE: "FEASIBLE",
            cp_model.INFEASIBLE: "INFEASIBLE",
            cp_model.MODEL_INVALID: "MODEL_INVALID",
            cp_model.UNKNOWN: "UNKNOWN",
        }
        raw_status_str = status_map.get(raw_status, "UNKNOWN")
        is_solver_feasible = raw_status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        # =====================================================================
        # EXTRACT ASSIGNMENTS
        # =====================================================================
        assignments: dict[str, GateAssignment] = {}

        if is_solver_feasible:
            for f_idx, fl in enumerate(flights):
                for g_idx, gate in enumerate(gate_list):
                    if solver.BooleanValue(x[f_idx, g_idx]):
                        is_reassign = (
                            fl.nominal_gate_id is not None
                            and gate.gate_id != fl.nominal_gate_id
                        )
                        assignment = GateAssignment(
                            flight_id=fl.flight_id,
                            gate_id=gate.gate_id,
                            flight_index=f_idx,
                            gate_index=g_idx,
                            is_overflow=gate.is_overflow,
                            is_reassignment=is_reassign,
                            occupancy_start_min=fl.time_window.start_min,
                            occupancy_end_min=fl.time_window.end_min,
                        )
                        assignments[fl.flight_id] = assignment
                        break

        # Evaluate solution via common evaluator (runs independent verifier)
        eval_result = evaluate_gate_assignment(
            assignments=assignments,
            flights=flights,
            gates=gate_list,
            config=self.config,
            runtime_ms=runtime_ms,
            solver_status=raw_status_str,
            solver_name="CPSatGateSolver",
        )

        # Independent feasibility certification:
        # Feasibility is strictly certified by the independent verifier, not the solver output.
        feasible = bool(eval_result.feasible)

        # Status certification:
        # Only report OPTIMAL if actual solver status == cp_model.OPTIMAL AND verifier passes.
        if raw_status == cp_model.OPTIMAL and feasible:
            final_status = "OPTIMAL"
        elif raw_status in (cp_model.OPTIMAL, cp_model.FEASIBLE) and feasible:
            final_status = "FEASIBLE"
        elif raw_status == cp_model.INFEASIBLE:
            final_status = "INFEASIBLE"
        elif raw_status == cp_model.MODEL_INVALID:
            final_status = "MODEL_INVALID"
        else:
            final_status = "UNKNOWN" if not feasible else "FEASIBLE"

        # Optimality gap & Best bound computation
        gap: float | None = None
        best_bound: float | None = None

        if raw_status == cp_model.OPTIMAL and feasible:
            gap = 0.0
            best_bound = float(eval_result.objective_value)
        elif raw_status == cp_model.FEASIBLE and feasible:
            best_decision_bound = solver.BestObjectiveBound() / sf if objective_terms else 0.0
            decision_obj = solver.ObjectiveValue() / sf if objective_terms else 0.0
            best_bound = float(best_decision_bound + eval_result.objective_breakdown.reporting_cost)
            if decision_obj > 1e-6:
                gap = float(abs(decision_obj - best_decision_bound) / decision_obj)
            else:
                gap = 0.0

        return OptimizationResult(
            status=final_status,
            objective_value=eval_result.objective_value,
            objective_breakdown=eval_result.objective_breakdown,
            feasible=feasible,
            runtime_ms=eval_result.runtime_ms,
            optimality_gap=gap,
            assignments=eval_result.assignments,
            constraint_diagnostics=eval_result.constraint_diagnostics,
            solver_configuration={
                **eval_result.solver_configuration,
                "raw_solver_status": raw_status_str,
                "scale_factor": sf,
                "best_bound": best_bound,
            },
            best_bound=best_bound,
        )
