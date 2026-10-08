"""Google OR-Tools CP-SAT Gate Assignment Solver (V2 Optimized - Phase P06).

Protocol: docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md
          docs/remediation/06_cp_sat_scalability_report.md
Architecture & Optimizations (P06):
1. OPT-A (Sparse Assignment Variables):
   - Computes candidate gates per flight according to carrier, aircraft type compatibility,
     and operational availability windows.
   - Eliminates useless Cartesian product variables and redundant x[f, g] == 0 constraints.
   - Immediate detection of flights with 0 eligible candidates (CP13).
2. OPT-B (Overlap Constraint Reformulation):
   - Configurable formulations:
     * "sparse_interval": Native optional interval variables with AddNoOverlap (contact/remote cap=1)
       and AddCumulative (pooled remote stands cap > 1).
     * "sparse_pairwise": Sparse binary variables + sparse pairwise conflict mutexes.
     * "dense_pairwise": Legacy dense formulation for differential baseline audit.
3. OPT-C (Finite Resource Capacity):
   - Capacity 1: AddNoOverlap or pairwise x[i, g] + x[j, g] <= 1.
   - Pooled capacity K > 1: AddCumulative with demand 1 and capacity K.
   - Unbounded overflow apron: Infinite capacity, zero overlap constraints.
4. OPT-D (Greedy Solution Hints / Warm Start):
   - Warm start hints from DeterministicGreedyGateSolver via AddHint(x[f, g], 1).
   - Time to generate hint is strictly measured and recorded in end-to-end wall clock.
5. OPT-F & Section VI (Deadline & Resource-Bounded Fallback):
   - Respects search_budget, model_build_budget, and total_wall_clock_budget.
   - Configurable fallback to Greedy if CP-SAT search times out without incumbent.
   - Fallback results never falsely certified as OPTIMAL.
6. Independent Verification:
   - Certified by verify_hard_constraints_independently() outside the solver.
"""

from __future__ import annotations

from dataclasses import replace
import logging
import math
import time
from typing import Any, Mapping, Sequence

import numpy as np
from ortools.sat.python import cp_model

from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import (
    ConstraintDiagnostic,
    Flight,
    Gate,
    GateAssignment,
    GateResourceType,
    ObjectiveBreakdown,
    OptimizationResult,
    SolverStatus,
    TerminationReason,
    verify_hard_constraints_independently,
)
from src.optimization.evaluation import evaluate_gate_assignment
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver

LOGGER = logging.getLogger("cp_sat_solver")


class CPSatGateSolver:
    """Exact Constraint Programming gate assignment solver backed by Google OR-Tools CP-SAT."""

    def __init__(self, config: GateOptimizationConfig | None = None) -> None:
        self.config = config or GateOptimizationConfig()

    def solve(
        self,
        flights: Sequence[Flight],
        gates: Sequence[Gate],
        *,
        allow_overflow: bool = True,
        initial_assignments: Mapping[str, GateAssignment] | None = None,
    ) -> OptimizationResult:
        """Solve optimal gate assignment problem for a batch of flights and gates.

        Args:
            flights: Sequence of Flight domain entities with computed time windows.
            gates: Sequence of Gate entities (contact gates and optional overflow stands).
            allow_overflow: If True and no overflow gate is in gates, adds an overflow stand.
            initial_assignments: Optional precomputed assignment mapping for warm-start hints.

        Returns:
            OptimizationResult evaluated by authoritative common evaluator.
        """
        t0 = time.perf_counter()
        t0_ns = time.perf_counter_ns()

        n_flights = len(flights)
        if n_flights == 0:
            return OptimizationResult(
                status=SolverStatus.OPTIMAL.value,
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
                termination_reason=TerminationReason.OPTIMAL_PROVEN,
                optimality_proven=True,
                best_bound=0.0,
            )

        # Prepare working gate list
        gate_list = list(gates)
        has_overflow = any(g.is_overflow for g in gate_list)
        if allow_overflow and not has_overflow:
            if getattr(self.config, "allow_unbounded_overflow", True):
                overflow_gate = Gate(
                    gate_id="OVERFLOW_APRON",
                    gate_index=len(gate_list),
                    resource_type=GateResourceType.UNBOUNDED_OVERFLOW_APRON,
                    capacity=math.inf,
                    is_overflow=True,
                )
                gate_list.append(overflow_gate)

        n_gates = len(gate_list)
        t_build_start_ns = time.perf_counter_ns()
        formulation = getattr(self.config, "cp_sat_formulation", "sparse_interval")

        # =====================================================================
        # STEP 1: CANDIDATE FILTERING (OPT-A) & ZERO-CANDIDATE DETECTION (CP13)
        # =====================================================================
        eligible_candidates_map: dict[int, list[int]] = {}
        for f_idx, fl in enumerate(flights):
            candidates: list[int] = []
            for g_idx, gate in enumerate(gate_list):
                if (
                    gate.is_compatible_carrier(fl.carrier)
                    and gate.is_compatible_aircraft(fl.aircraft_type)
                    and gate.is_available_during(fl.time_window)
                ):
                    candidates.append(g_idx)
            eligible_candidates_map[f_idx] = candidates

        # Check for flights with zero eligible gates
        zero_candidate_indices = [
            f_idx for f_idx in range(n_flights) if not eligible_candidates_map[f_idx]
        ]
        if zero_candidate_indices:
            zero_fl_ids = [flights[idx].flight_id for idx in zero_candidate_indices]
            LOGGER.info(f"Flights with zero eligible gates: {zero_fl_ids}")
            total_wall_clock_ms = (time.perf_counter_ns() - t0_ns) / 1_000_000.0
            return OptimizationResult(
                status=SolverStatus.INFEASIBLE.value,
                objective_value=None,
                objective_breakdown=ObjectiveBreakdown(
                    total_cost=float("inf"),
                    reassignment_cost=0.0,
                    overflow_cost=0.0,
                    delay_cost=0.0,
                    conflict_cost=0.0,
                    risk_cost=0.0,
                    weights=self.config.to_dict(),
                ),
                feasible=False,
                runtime_ms=total_wall_clock_ms,
                optimality_gap=None,
                assignments={},
                constraint_diagnostics=verify_hard_constraints_independently(
                    flights=flights, gates=gate_list, assignments={}
                ),
                solver_configuration={
                    **self.config.to_dict(),
                    "raw_solver_status": "INFEASIBLE",
                    "model_construction_ms": (time.perf_counter_ns() - t_build_start_ns) / 1_000_000.0,
                    "search_time_ms": 0.0,
                    "validation_time_ms": 0.0,
                    "total_wall_clock_ms": total_wall_clock_ms,
                    "infeasible_reason": f"Zero eligible gates for flights: {zero_fl_ids}",
                },
                termination_reason=TerminationReason.PROVEN_INFEASIBLE,
                optimality_proven=False,
                best_bound=None,
            )

        # =====================================================================
        # STEP 2: DECISION VARIABLES & MODEL CONSTRUCTION
        # =====================================================================
        model = cp_model.CpModel()
        x: dict[tuple[int, int], cp_model.IntVar] = {}

        if formulation == "dense_pairwise":
            # Baseline dense allocation
            for f_idx in range(n_flights):
                for g_idx in range(n_gates):
                    x[f_idx, g_idx] = model.NewBoolVar(f"x_{f_idx}_{g_idx}")

            # Availability and compatibility constraints (equality cuts)
            for f_idx, fl in enumerate(flights):
                for g_idx, gate in enumerate(gate_list):
                    if (
                        not gate.is_available_during(fl.time_window)
                        or not gate.is_compatible_carrier(fl.carrier)
                        or not gate.is_compatible_aircraft(fl.aircraft_type)
                    ):
                        model.Add(x[f_idx, g_idx] == 0)

            # Exactly one gate per flight
            for f_idx in range(n_flights):
                model.Add(sum(x[f_idx, g_idx] for g_idx in range(n_gates)) == 1)

        else:
            # OPT-A Sparse variables: Only create variables for eligible candidates
            for f_idx in range(n_flights):
                for g_idx in eligible_candidates_map[f_idx]:
                    x[f_idx, g_idx] = model.NewBoolVar(f"x_{f_idx}_{g_idx}")

            # Exactly one gate per flight (CP03)
            for f_idx in range(n_flights):
                cand = eligible_candidates_map[f_idx]
                model.Add(sum(x[f_idx, g_idx] for g_idx in cand) == 1)

        # =====================================================================
        # STEP 3: OVERLAP & CAPACITY CONSTRAINTS (OPT-B & OPT-C)
        # =====================================================================
        if formulation == "sparse_interval":
            # OPT-B: Native interval variables with AddNoOverlap & AddCumulative
            for g_idx, gate in enumerate(gate_list):
                if gate.resource_type == GateResourceType.UNBOUNDED_OVERFLOW_APRON or gate.is_unbounded:
                    continue  # Unbounded overflow apron has infinite capacity

                gate_intervals: list[cp_model.IntervalVar] = []
                for f_idx in range(n_flights):
                    if (f_idx, g_idx) in x:
                        fl = flights[f_idx]
                        start = int(fl.time_window.start_min)
                        end = int(fl.time_window.end_min)
                        size = max(1, end - start)
                        iv = model.NewOptionalIntervalVar(
                            start, size, end, x[f_idx, g_idx], f"iv_{f_idx}_{g_idx}"
                        )
                        gate_intervals.append(iv)

                if gate_intervals:
                    if gate.capacity == 1:
                        # Contact gate or discrete finite remote stand (CP04, CP05)
                        if len(gate_intervals) > 1:
                            model.AddNoOverlap(gate_intervals)
                    elif math.isfinite(gate.capacity) and gate.capacity > 1:
                        # Pooled finite remote stand with capacity K > 1 (CP05)
                        demands = [1] * len(gate_intervals)
                        model.AddCumulative(gate_intervals, demands, int(gate.capacity))

        else:
            # Pairwise conflict constraints (sparse_pairwise or dense_pairwise)
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
                if gate.resource_type == GateResourceType.UNBOUNDED_OVERFLOW_APRON or gate.is_unbounded:
                    continue

                if gate.capacity == 1:
                    for i, j in overlapping_pairs:
                        if (i, g_idx) in x and (j, g_idx) in x:
                            model.Add(x[i, g_idx] + x[j, g_idx] <= 1)
                elif math.isfinite(gate.capacity) and gate.capacity > 1:
                    cap = int(gate.capacity)
                    seen_subsets: set[tuple[int, ...]] = set()
                    for i in range(n_flights):
                        t = flights[i].time_window.start_min
                        active_tuple = tuple(
                            k
                            for k in range(n_flights)
                            if flights[k].time_window.start_min <= t < flights[k].time_window.end_min
                            and (k, g_idx) in x
                        )
                        if len(active_tuple) > cap and active_tuple not in seen_subsets:
                            seen_subsets.add(active_tuple)
                            model.Add(sum(x[k, g_idx] for k in active_tuple) <= cap)

        # =====================================================================
        # STEP 4: SOFT OBJECTIVE FUNCTION (CP11, CP12)
        # =====================================================================
        sf = self.config.scale_factor
        objective_terms = []

        for f_idx, fl in enumerate(flights):
            nom_gate_id = fl.nominal_gate_id
            cands = range(n_gates) if formulation == "dense_pairwise" else eligible_candidates_map[f_idx]

            for g_idx in cands:
                if (f_idx, g_idx) not in x:
                    continue
                gate = gate_list[g_idx]
                var = x[f_idx, g_idx]
                cost = 0.0

                # Reassignment penalty (deviation from nominal plan)
                if not gate.is_overflow:
                    if nom_gate_id is not None and gate.gate_id != nom_gate_id:
                        cost += self.config.reassignment_weight

                # Overflow penalty (remote stand / apron)
                if gate.is_overflow:
                    cost += self.config.overflow_weight
                    if nom_gate_id is not None:
                        cost += self.config.reassignment_weight

                int_coeff = int(round(cost * sf))
                if int_coeff != 0:
                    objective_terms.append(int_coeff * var)

        if objective_terms:
            model.Minimize(sum(objective_terms))

        # =====================================================================
        # STEP 5: WARM-START HINTS (OPT-D & CP10)
        # =====================================================================
        warm_start_used = False
        warm_start_time_ms = 0.0
        use_warm_start = getattr(self.config, "cp_sat_use_warm_start", False) or (initial_assignments is not None)

        if use_warm_start:
            t_ws0 = time.perf_counter()
            if initial_assignments is not None:
                hint_assignments = dict(initial_assignments)
            else:
                greedy_solver = DeterministicGreedyGateSolver(config=self.config)
                greedy_res = greedy_solver.solve(flights, gate_list, allow_overflow=allow_overflow)
                hint_assignments = dict(greedy_res.assignments) if greedy_res.feasible else {}

            warm_start_time_ms = (time.perf_counter() - t_ws0) * 1000.0

            if hint_assignments and len(hint_assignments) == n_flights:
                gate_to_idx = {g.gate_id: idx for idx, g in enumerate(gate_list)}
                for fl in flights:
                    asgn = hint_assignments.get(fl.flight_id)
                    if asgn is not None and asgn.gate_id in gate_to_idx:
                        g_idx = gate_to_idx[asgn.gate_id]
                        if (fl.flight_index, g_idx) in x:
                            model.AddHint(x[fl.flight_index, g_idx], 1)
                warm_start_used = True

        t_build_end_ns = time.perf_counter_ns()
        model_construction_ms = (t_build_end_ns - t_build_start_ns) / 1_000_000.0 + warm_start_time_ms
        n_constraints = len(model.Proto().constraints)

        # =====================================================================
        # STEP 6: DEADLINE & BUDGET MANAGEMENT (Section VI, CP19)
        # =====================================================================
        search_budget_seconds = float(self.config.time_limit_seconds)
        total_wall_clock_budget = getattr(self.config, "total_wall_clock_budget_seconds", None)

        if total_wall_clock_budget is not None:
            elapsed_sec = (time.perf_counter_ns() - t0_ns) / 1_000_000_000.0
            remaining_sec = total_wall_clock_budget - elapsed_sec
            if remaining_sec <= 0.001:
                # Wall-clock budget exceeded during model build
                total_wall_clock_ms = (time.perf_counter_ns() - t0_ns) / 1_000_000.0
                return OptimizationResult(
                    status=SolverStatus.TIMEOUT_NO_SOLUTION.value,
                    objective_value=None,
                    objective_breakdown=ObjectiveBreakdown(
                        total_cost=float("inf"),
                        reassignment_cost=0.0,
                        overflow_cost=0.0,
                        delay_cost=0.0,
                        conflict_cost=0.0,
                        risk_cost=0.0,
                        weights=self.config.to_dict(),
                    ),
                    feasible=False,
                    runtime_ms=total_wall_clock_ms,
                    optimality_gap=None,
                    assignments={},
                    constraint_diagnostics=verify_hard_constraints_independently(
                        flights=flights, gates=gate_list, assignments={}
                    ),
                    solver_configuration={
                        **self.config.to_dict(),
                        "raw_solver_status": "TIMEOUT",
                        "model_construction_ms": model_construction_ms,
                        "search_time_ms": 0.0,
                        "validation_time_ms": 0.0,
                        "total_wall_clock_ms": total_wall_clock_ms,
                        "termination_reason": TerminationReason.TIME_LIMIT.value,
                    },
                    termination_reason=TerminationReason.TIME_LIMIT,
                    optimality_proven=False,
                    best_bound=None,
                )
            search_budget_seconds = min(search_budget_seconds, remaining_sec)

        # =====================================================================
        # STEP 7: SOLVER EXECUTION
        # =====================================================================
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = float(search_budget_seconds)
        solver.parameters.num_search_workers = int(self.config.num_search_workers)
        solver.parameters.random_seed = int(self.config.random_seed)
        solver.parameters.log_search_progress = bool(self.config.log_search_progress)

        t_search_start_ns = time.perf_counter_ns()
        raw_status = solver.Solve(model)
        t_search_end_ns = time.perf_counter_ns()
        search_time_ms = (t_search_end_ns - t_search_start_ns) / 1_000_000.0

        status_map = {
            cp_model.OPTIMAL: SolverStatus.OPTIMAL.value,
            cp_model.FEASIBLE: SolverStatus.FEASIBLE.value,
            cp_model.INFEASIBLE: SolverStatus.INFEASIBLE.value,
            cp_model.MODEL_INVALID: SolverStatus.MODEL_INVALID.value,
            cp_model.UNKNOWN: SolverStatus.UNKNOWN.value,
        }
        raw_status_str = status_map.get(raw_status, SolverStatus.UNKNOWN.value)
        is_solver_feasible = raw_status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        # =====================================================================
        # STEP 8: EXTRACT ASSIGNMENTS OR INVOKE FALLBACK (OPT-F, CP21)
        # =====================================================================
        assignments: dict[str, GateAssignment] = {}
        fallback_used = False
        initial_source = "CP_SAT"

        if is_solver_feasible:
            for f_idx, fl in enumerate(flights):
                cands = range(n_gates) if formulation == "dense_pairwise" else eligible_candidates_map[f_idx]
                for g_idx in cands:
                    if (f_idx, g_idx) in x and solver.BooleanValue(x[f_idx, g_idx]):
                        gate = gate_list[g_idx]
                        is_reassign = bool(
                            fl.nominal_gate_id is not None
                            and gate.gate_id != fl.nominal_gate_id
                        )
                        assignments[fl.flight_id] = GateAssignment(
                            flight_id=fl.flight_id,
                            gate_id=gate.gate_id,
                            flight_index=f_idx,
                            gate_index=g_idx,
                            is_overflow=gate.is_overflow,
                            is_reassignment=is_reassign,
                            occupancy_start_min=fl.time_window.start_min,
                            occupancy_end_min=fl.time_window.end_min,
                        )
                        break

        elif getattr(self.config, "cp_sat_fallback_to_greedy", False) and raw_status_str in ("UNKNOWN", "MODEL_INVALID"):
            # Resource-bounded fallback to Greedy (OPT-F)
            LOGGER.info("CP-SAT yielded no incumbent; invoking configured Greedy fallback.")
            greedy_solver = DeterministicGreedyGateSolver(config=self.config)
            greedy_res = greedy_solver.solve(flights, gate_list, allow_overflow=allow_overflow)
            if greedy_res.feasible and len(greedy_res.assignments) == n_flights:
                assignments = dict(greedy_res.assignments)
                fallback_used = True
                initial_source = "GREEDY_FALLBACK"

        # =====================================================================
        # STEP 9: INDEPENDENT EVALUATION & CONTRACT CERTIFICATION
        # =====================================================================
        t_val_start_ns = time.perf_counter_ns()
        total_wall_clock_ms = (time.perf_counter_ns() - t0_ns) / 1_000_000.0

        if assignments and len(assignments) == n_flights:
            eval_result = evaluate_gate_assignment(
                assignments=assignments,
                flights=flights,
                gates=gate_list,
                config=self.config,
                runtime_ms=total_wall_clock_ms,
                solver_status=raw_status_str if not fallback_used else SolverStatus.FEASIBLE.value,
                solver_name="CPSatGateSolver",
            )
        else:
            # No feasible assignment found
            eval_result = OptimizationResult(
                status=SolverStatus.UNKNOWN.value if raw_status_str == "UNKNOWN" else raw_status_str,
                objective_value=float("inf"),
                objective_breakdown=ObjectiveBreakdown(
                    total_cost=float("inf"),
                    reassignment_cost=0.0,
                    overflow_cost=0.0,
                    delay_cost=0.0,
                    conflict_cost=0.0,
                    risk_cost=0.0,
                    weights=self.config.to_dict(),
                ),
                feasible=False,
                runtime_ms=total_wall_clock_ms,
                optimality_gap=None,
                assignments={},
                constraint_diagnostics=verify_hard_constraints_independently(
                    flights=flights, gates=gate_list, assignments={}
                ),
                solver_configuration=self.config.to_dict(),
            )

        t_val_end_ns = time.perf_counter_ns()
        validation_time_ms = (t_val_end_ns - t_val_start_ns) / 1_000_000.0

        # Independent feasibility certification: Certified by independent verifier (CP04, CP05)
        feasible = bool(eval_result.feasible and len(assignments) == n_flights)

        scaled_integer_objective = None
        raw_decision_cost = None
        if is_solver_feasible and not fallback_used and objective_terms:
            scaled_integer_objective = solver.ObjectiveValue()
            raw_decision_cost = solver.ObjectiveValue() / sf

        # Status and optimality certification (CP22):
        # Only certify OPTIMAL if raw solver status == OPTIMAL AND independent verifier passed AND no fallback used!
        if raw_status == cp_model.OPTIMAL and feasible and not fallback_used:
            final_status = SolverStatus.OPTIMAL.value
            term_reason = TerminationReason.OPTIMAL_PROVEN
            optimality_proven = True
            gap = 0.0
            best_bound = float(eval_result.objective_value)
        elif feasible:
            final_status = SolverStatus.FEASIBLE.value
            term_reason = TerminationReason.FEASIBLE_FOUND
            optimality_proven = False
            if is_solver_feasible and not fallback_used and objective_terms:
                best_decision_bound = solver.BestObjectiveBound() / sf
                decision_obj = solver.ObjectiveValue() / sf
                best_bound = float(best_decision_bound + eval_result.objective_breakdown.reporting_cost)
                gap = float(abs(decision_obj - best_decision_bound) / decision_obj) if decision_obj > 1e-6 else 0.0
            else:
                best_bound = None
                gap = None
        elif raw_status == cp_model.INFEASIBLE:
            final_status = SolverStatus.INFEASIBLE.value
            term_reason = TerminationReason.PROVEN_INFEASIBLE
            optimality_proven = False
            best_bound = None
            gap = None
        else:
            final_status = SolverStatus.UNKNOWN.value
            term_reason = TerminationReason.TIME_LIMIT
            optimality_proven = False
            best_bound = None
            gap = None

        try:
            solver_wall_time = solver.WallTime()
        except Exception:
            solver_wall_time = search_time_ms / 1000.0

        return OptimizationResult(
            status=final_status,
            objective_value=eval_result.objective_value if feasible else None,
            objective_breakdown=eval_result.objective_breakdown,
            feasible=feasible,
            runtime_ms=total_wall_clock_ms,
            optimality_gap=gap,
            assignments=eval_result.assignments if feasible else {},
            constraint_diagnostics=eval_result.constraint_diagnostics,
            solver_configuration={
                **eval_result.solver_configuration,
                "raw_solver_status": raw_status_str,
                "formulation": formulation,
                "scale_factor": sf,
                "scale_tolerance": 1.0 / sf,
                "raw_decision_cost": raw_decision_cost,
                "scaled_integer_objective": scaled_integer_objective,
                "n_variables": len(x),
                "n_constraints": n_constraints,
                "model_construction_ms": round(model_construction_ms, 2),
                "search_time_ms": round(search_time_ms, 2),
                "validation_time_ms": round(validation_time_ms, 2),
                "total_wall_clock_ms": round(total_wall_clock_ms, 2),
                "solver_wall_time_seconds": solver_wall_time,
                "warm_start_used": warm_start_used,
                "warm_start_time_ms": round(warm_start_time_ms, 2),
                "fallback_used": fallback_used,
                "initial_solution_source": initial_source,
                "best_bound": best_bound,
            },
            best_bound=best_bound,
            termination_reason=term_reason,
            optimality_proven=optimality_proven,
        )
