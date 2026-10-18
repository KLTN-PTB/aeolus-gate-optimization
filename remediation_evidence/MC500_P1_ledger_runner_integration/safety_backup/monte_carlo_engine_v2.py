"""Authoritative Remediated Monte Carlo Engine (Phase G2 Remediation).

Protocol: Aeolus Predict-then-Optimize V4.1 - Gate Remediation G2
Implements:
- Mode A: FIXED_PLAN_ROBUSTNESS (Frozen plan, 0 re-optimizations, explicit feasibility breakdown).
- Mode B1: RETROSPECTIVE_RECOURSE (Full-information hindsight recourse; explicitly labeled RETROSPECTIVE).
- Mode B2: ROLLING_HORIZON_ONLINE (Non-anticipative online event-driven recourse; strictly causal).
- Mode C-Heuristic: GREEDY_FULL_FORESIGHT_BENCHMARK (Heuristic foresight baseline, NOT global lower bound).
- Mode C-Oracle: OPTIMAL_FULL_FORESIGHT_ORACLE (CP-SAT proven optimal lower bound with proof verification).
- Feasibility Decomposition: Physical conflict, Buffer violation, Remote capacity, Unassigned, Static slot consistency.
- Common Random Numbers (CRN) preservation and paired delta statistics.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import math
import time
from typing import Any, Final, Optional

import numpy as np
import pandas as pd
from scipy import stats

from src.contracts.provenance import (
    DataOrigin,
    EvaluationRegime,
    EvidenceProvenance,
    InformationRegime,
    PairingSource,
    PredictionSource,
    ScenarioGeneration,
)
from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import (
    ConstraintDiagnostic,
    Flight,
    FlightTimeWindow,
    Gate,
    GateAssignment,
    GateResourceType,
    OptimizationResult,
    verify_hard_constraints_independently,
)
from src.optimization.evaluation import evaluate_gate_assignment
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver
from src.optimization.solvers.hybrid_solver import HybridGateSolver
from src.simulation.monte_carlo_engine_p09 import (
    CopulaDependenceModel,
    MonteCarloScenarioGenerator,
    RealizedScenario,
    apply_delays_to_flights,
)


class OnlineSolverStatus(str, Enum):
    """Canonical solver statuses for causal online simulation.

    Semantics:
    - ONLINE_FEASIBLE: Solution achieved composite feasibility without conflicts or capacity overruns.
    - ONLINE_INFEASIBLE_NO_CAPACITY: System capacity exhausted (finite remote stand full or no compatible gate open).
    - ONLINE_INFEASIBLE: Physical operational constraint violated ex-post.
    """

    ONLINE_FEASIBLE = "ONLINE_FEASIBLE"
    ONLINE_INFEASIBLE_NO_CAPACITY = "ONLINE_INFEASIBLE_NO_CAPACITY"
    ONLINE_INFEASIBLE = "ONLINE_INFEASIBLE"

    def __str__(self) -> str:
        return self.value


def canonicalize_legacy_solver_status(
    raw_status: str,
    feasibility: FeasibilityBreakdown | Mapping[str, Any] | None = None,
) -> str:
    """Explicit migration boundary for legacy solver statuses.

    Canonicalizes legacy status values like 'ONLINE_SOLVED' to standard canonical status
    ONLY when explicit feasibility metadata is provided and verifies feasibility.
    Never assumes feasible solely because the string contains 'SOLVED'.
    """
    s = str(raw_status).strip().upper()
    if s in (
        OnlineSolverStatus.ONLINE_FEASIBLE.value,
        OnlineSolverStatus.ONLINE_INFEASIBLE_NO_CAPACITY.value,
        OnlineSolverStatus.ONLINE_INFEASIBLE.value,
    ):
        return s

    if s == "ONLINE_SOLVED":
        if feasibility is not None:
            if isinstance(feasibility, FeasibilityBreakdown):
                is_feas = feasibility.composite_feasible
                no_cap = (
                    feasibility.unassigned_flight_count > 0
                    or feasibility.remote_capacity_violation
                )
            elif isinstance(feasibility, Mapping):
                is_feas = bool(feasibility.get("composite_feasible", False))
                no_cap = bool(
                    feasibility.get("unassigned_flight_count", 0) > 0
                    or feasibility.get("remote_capacity_violation", False)
                )
            else:
                is_feas = False
                no_cap = False

            if is_feas:
                return OnlineSolverStatus.ONLINE_FEASIBLE.value
            elif no_cap:
                return OnlineSolverStatus.ONLINE_INFEASIBLE_NO_CAPACITY.value
            else:
                return OnlineSolverStatus.ONLINE_INFEASIBLE.value
        return "LEGACY_ONLINE_SOLVED_UNVERIFIED"

    return s


class RemediatedSimulationMode(str, Enum):
    """Authoritative scientific mode identifiers for G2 Monte Carlo."""

    MODE_A_FIXED_PLAN = "MODE_A_FIXED_PLAN"
    MODE_B1_RETROSPECTIVE_RECOURSE = "MODE_B1_RETROSPECTIVE_RECOURSE"
    MODE_B2_ONLINE_RECOURSE = "MODE_B2_ONLINE_RECOURSE"
    MODE_C_GREEDY_FORESIGHT = "MODE_C_GREEDY_FORESIGHT"
    MODE_C_OPTIMAL_ORACLE = "MODE_C_OPTIMAL_ORACLE"


@dataclass(frozen=True)
class FeasibilityBreakdown:
    """Fine-grained decomposition of operational feasibility dimensions."""

    physical_contact_conflict_count: int
    buffer_violation_count: int
    max_concurrent_remote_usage: int
    remote_capacity_violation: bool
    unassigned_flight_count: int
    static_slot_consistency: bool
    composite_feasible: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RemediatedRealizationResult:
    """Comprehensive evaluation record for a single realization under a certified mode."""

    realization_id: str
    scenario_index: int
    initial_plan_solver: str
    recourse_solver: str
    recourse_policy: str
    information_regime: str
    mode: str
    objective_value: float
    decision_cost: float
    reporting_cost: float
    reassignment_count: int
    remote_count: int
    feasibility: FeasibilityBreakdown
    runtime_ms: float
    solver_status: str
    is_optimal_proven: bool
    realization_hash: str
    decision_trace: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    def to_flat_dict(self) -> dict[str, Any]:
        """Flatten record for CSV / DataFrame exports."""
        d = {
            "realization_id": self.realization_id,
            "scenario_index": self.scenario_index,
            "initial_plan_solver": self.initial_plan_solver,
            "recourse_solver": self.recourse_solver,
            "recourse_policy": self.recourse_policy,
            "information_regime": self.information_regime,
            "mode": self.mode,
            "objective_value": round(self.objective_value, 4),
            "decision_cost": round(self.decision_cost, 4),
            "reporting_cost": round(self.reporting_cost, 4),
            "reassignment_count": self.reassignment_count,
            "remote_count": self.remote_count,
            "physical_contact_conflict_count": self.feasibility.physical_contact_conflict_count,
            "buffer_violation_count": self.feasibility.buffer_violation_count,
            "max_concurrent_remote_usage": self.feasibility.max_concurrent_remote_usage,
            "remote_capacity_violation": self.feasibility.remote_capacity_violation,
            "unassigned_flight_count": self.feasibility.unassigned_flight_count,
            "static_slot_consistency": self.feasibility.static_slot_consistency,
            "composite_feasible": self.feasibility.composite_feasible,
            "runtime_ms": round(self.runtime_ms, 3),
            "solver_status": self.solver_status,
            "is_optimal_proven": self.is_optimal_proven,
            "realization_hash": self.realization_hash,
        }
        return d


@dataclass
class ExecutionLedgerEntry:
    """Immutable audit record for a single realization event in the execution ledger."""

    run_id: str
    scenario_id: str
    realization_hash: str
    initial_plan_solver: str
    recourse_mode: str
    generation_status: str  # "SUCCESS", "FAILURE"
    evaluation_status: str  # "SUCCESS", "FAILURE", "TIMEOUT", "NOT_EVALUATED"
    solver_status: str
    composite_feasible: bool
    timeout: bool
    exception_type: str | None = None
    failure_reason: str | None = None
    objective_value: float | None = None
    runtime_ms: float = 0.0
    timestamp_start: float = 0.0
    timestamp_end: float = 0.0
    source_config_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SimulationExecutionLedger:
    """Rigorous scientific execution accounting ledger for Monte Carlo simulations."""

    def __init__(self, run_id: str, requested_n: int, config_hash: str = "") -> None:
        self.run_id = str(run_id)
        self.requested_n = int(requested_n)
        self.config_hash = str(config_hash)
        self.entries: list[ExecutionLedgerEntry] = []
        self._seen_keys: set[tuple[str, str]] = set()
        self._scenario_ids: set[str] = set()

    def record_evaluation_success(
        self,
        scenario_id: str,
        realization_hash: str,
        initial_plan_solver: str,
        recourse_mode: str,
        solver_status: str,
        composite_feasible: bool,
        objective_value: float,
        runtime_ms: float = 0.0,
        start_time: float = 0.0,
        end_time: float = 0.0,
    ) -> ExecutionLedgerEntry:
        key = (scenario_id, initial_plan_solver)
        if key in self._seen_keys:
            raise ValueError(f"Duplicate scenario_id '{scenario_id}' for solver '{initial_plan_solver}' in ledger")
        self._seen_keys.add(key)
        self._scenario_ids.add(scenario_id)

        entry = ExecutionLedgerEntry(
            run_id=self.run_id,
            scenario_id=scenario_id,
            realization_hash=realization_hash,
            initial_plan_solver=initial_plan_solver,
            recourse_mode=recourse_mode,
            generation_status="SUCCESS",
            evaluation_status="SUCCESS",
            solver_status=str(solver_status),
            composite_feasible=bool(composite_feasible),
            timeout=False,
            objective_value=float(objective_value),
            runtime_ms=float(runtime_ms),
            timestamp_start=start_time,
            timestamp_end=end_time,
            source_config_hash=self.config_hash,
        )
        self.entries.append(entry)
        return entry

    def record_generation_failure(
        self,
        scenario_id: str,
        reason: str,
        realization_hash: str = "",
        initial_plan_solver: str = "ALL",
        recourse_mode: str = "ALL",
    ) -> ExecutionLedgerEntry:
        key = (scenario_id, initial_plan_solver)
        if key in self._seen_keys:
            raise ValueError(f"Duplicate scenario_id '{scenario_id}' for solver '{initial_plan_solver}' in ledger")
        self._seen_keys.add(key)
        self._scenario_ids.add(scenario_id)

        entry = ExecutionLedgerEntry(
            run_id=self.run_id,
            scenario_id=scenario_id,
            realization_hash=realization_hash,
            initial_plan_solver=initial_plan_solver,
            recourse_mode=recourse_mode,
            generation_status="FAILURE",
            evaluation_status="NOT_EVALUATED",
            solver_status="GENERATION_FAILURE",
            composite_feasible=False,
            timeout=False,
            failure_reason=str(reason),
            source_config_hash=self.config_hash,
        )
        self.entries.append(entry)
        return entry

    def record_evaluation_failure(
        self,
        scenario_id: str,
        reason: str,
        realization_hash: str = "",
        initial_plan_solver: str = "UNKNOWN",
        recourse_mode: str = "UNKNOWN",
        exception_type: str | None = None,
    ) -> ExecutionLedgerEntry:
        key = (scenario_id, initial_plan_solver)
        if key in self._seen_keys:
            raise ValueError(f"Duplicate scenario_id '{scenario_id}' for solver '{initial_plan_solver}' in ledger")
        self._seen_keys.add(key)
        self._scenario_ids.add(scenario_id)

        entry = ExecutionLedgerEntry(
            run_id=self.run_id,
            scenario_id=scenario_id,
            realization_hash=realization_hash,
            initial_plan_solver=initial_plan_solver,
            recourse_mode=recourse_mode,
            generation_status="SUCCESS",
            evaluation_status="FAILURE",
            solver_status="EVALUATION_FAILURE",
            composite_feasible=False,
            timeout=False,
            exception_type=exception_type,
            failure_reason=str(reason),
            source_config_hash=self.config_hash,
        )
        self.entries.append(entry)
        return entry

    def record_timeout(
        self,
        scenario_id: str,
        realization_hash: str = "",
        initial_plan_solver: str = "UNKNOWN",
        recourse_mode: str = "UNKNOWN",
        runtime_ms: float = 0.0,
    ) -> ExecutionLedgerEntry:
        key = (scenario_id, initial_plan_solver)
        if key in self._seen_keys:
            raise ValueError(f"Duplicate scenario_id '{scenario_id}' for solver '{initial_plan_solver}' in ledger")
        self._seen_keys.add(key)
        self._scenario_ids.add(scenario_id)

        entry = ExecutionLedgerEntry(
            run_id=self.run_id,
            scenario_id=scenario_id,
            realization_hash=realization_hash,
            initial_plan_solver=initial_plan_solver,
            recourse_mode=recourse_mode,
            generation_status="SUCCESS",
            evaluation_status="TIMEOUT",
            solver_status="ONLINE_INFEASIBLE_TIMEOUT",
            composite_feasible=False,
            timeout=True,
            failure_reason="TIMEOUT",
            runtime_ms=runtime_ms,
            source_config_hash=self.config_hash,
        )
        self.entries.append(entry)
        return entry

    def validate_ledger(self) -> None:
        """Validate that all requested scenarios are accounted for without omissions."""
        unique_scenarios = len(self._scenario_ids)
        if unique_scenarios < self.requested_n:
            missing = self.requested_n - unique_scenarios
            raise ValueError(
                f"Missing scenario accounting: expected {self.requested_n} scenarios, "
                f"but only {unique_scenarios} recorded in ledger ({missing} unaccounted for)"
            )

    def validate_paired_crn(self, required_solvers: Sequence[str]) -> bool:
        """Verify that every scenario has identical realizations across required solvers."""
        solvers_set = set(required_solvers)
        by_scen: dict[str, dict[str, str]] = {}
        for e in self.entries:
            if e.initial_plan_solver in solvers_set:
                by_scen.setdefault(e.scenario_id, {})[e.initial_plan_solver] = e.realization_hash

        for scen_id, s_map in by_scen.items():
            missing = solvers_set - set(s_map.keys())
            if missing:
                raise ValueError(f"Missing paired CRN realization for scenario '{scen_id}': solvers {missing} absent")
            hashes = list(s_map.values())
            if len(set(hashes)) > 1:
                raise ValueError(f"Mismatched CRN realization hashes for scenario '{scen_id}': {s_map}")
        return True

    def compute_summary(self) -> dict[str, Any]:
        """Compute complete statistical accounting summary."""
        n_gen_fail = sum(1 for e in self.entries if e.generation_status == "FAILURE")
        n_eval_fail = sum(1 for e in self.entries if e.evaluation_status == "FAILURE")
        n_timeout = sum(1 for e in self.entries if e.timeout)
        evaluated_entries = [e for e in self.entries if e.evaluation_status in ("SUCCESS", "TIMEOUT")]
        n_evaluated = len(evaluated_entries)
        n_generated = n_evaluated + n_eval_fail
        n_feasible = sum(1 for e in evaluated_entries if e.composite_feasible)
        n_infeasible = sum(1 for e in evaluated_entries if not e.composite_feasible)

        accounting = {
            "n_requested": self.requested_n,
            "n_generated": n_generated,
            "n_generation_failures": n_gen_fail,
            "n_evaluated": n_evaluated,
            "n_evaluation_failures": n_eval_fail,
            "n_timeouts": n_timeout,
            "n_feasible": n_feasible,
            "n_infeasible": n_infeasible,
        }
        return {"run_id": self.run_id, "accounting": accounting}

    def compute_rates(self) -> dict[str, dict[str, float | int]]:
        """Compute failure and feasibility rates with explicitly stated denominators."""
        summary = self.compute_summary()
        acc = summary["accounting"]
        n_req = acc["n_requested"]
        n_gen = acc["n_generated"]
        n_eval = acc["n_evaluated"]

        return {
            "generation_failure_rate": {
                "numerator": acc["n_generation_failures"],
                "denominator": n_req,
                "rate": acc["n_generation_failures"] / n_req if n_req > 0 else 0.0,
            },
            "evaluation_failure_rate": {
                "numerator": acc["n_evaluation_failures"],
                "denominator": n_gen,
                "rate": acc["n_evaluation_failures"] / n_gen if n_gen > 0 else 0.0,
            },
            "composite_feasible_rate": {
                "numerator": acc["n_feasible"],
                "denominator": n_eval,
                "rate": acc["n_feasible"] / n_eval if n_eval > 0 else 0.0,
            },
        }


def decompose_feasibility(
    assignments: Mapping[str, GateAssignment],
    flights: Sequence[Flight],
    gates: Sequence[Gate],
    config: GateOptimizationConfig,
    diag: ConstraintDiagnostic,
) -> FeasibilityBreakdown:
    """Analyze and decompose constraint violations into distinct orthogonal dimensions."""
    max_remote = diag.max_concurrent_remote_usage
    remote_viol = bool(max_remote > config.finite_remote_capacity)

    # Static slot consistency: Did flights occupy gates at exact planned schedule times?
    # Any positive or negative delay changes operational presence relative to baseline schedule
    static_consistent = bool(len(diag.timeline_mismatch_violations) == 0)

    # Physical contact conflicts: Actual overlapping occupancy of two aircraft on a contact gate
    phys_conflicts = diag.conflict_count

    # Composite operational feasibility:
    # A plan is physically operationally feasible under realized delays if:
    # 1. No physical contact gate collisions (phys_conflicts == 0)
    # 2. Remote apron does not exceed finite capacity (not remote_viol)
    # 3. All flights are accommodated (diag.unassigned_count == 0)
    # 4. Aircraft/carrier compatibility and gate availability are respected
    compat_avail_ok = bool(
        len(diag.incompatibility_violations) == 0
        and len(diag.availability_violations) == 0
        and len(diag.turnaround_violations) == 0
        and len(diag.unknown_gate_violations) == 0
    )
    composite = bool(
        phys_conflicts == 0
        and not remote_viol
        and diag.unassigned_count == 0
        and compat_avail_ok
    )

    return FeasibilityBreakdown(
        physical_contact_conflict_count=phys_conflicts,
        buffer_violation_count=len(diag.buffer_violations),
        max_concurrent_remote_usage=max_remote,
        remote_capacity_violation=remote_viol,
        unassigned_flight_count=diag.unassigned_count,
        static_slot_consistency=static_consistent,
        composite_feasible=composite,
    )


# ==============================================================================
# MODE A: FIXED PLAN ROBUSTNESS (ZERO RE-OPTIMIZATION)
# ==============================================================================
def evaluate_mode_a_fixed_plan_v2(
    frozen_assignments: Mapping[str, GateAssignment],
    realized_flights: Sequence[Flight],
    gates: Sequence[Gate],
    config: GateOptimizationConfig,
    realization: RealizedScenario,
    solver_name: str,
) -> RemediatedRealizationResult:
    """Mode A: Apply realized delays to frozen assignments with zero re-optimizations."""
    t0 = time.perf_counter()
    eval_res = evaluate_gate_assignment(
        assignments=frozen_assignments,
        flights=realized_flights,
        gates=gates,
        config=config,
        runtime_ms=0.0,
        solver_status="FIXED_PLAN",
        solver_name=f"ModeA_{solver_name}",
    )
    runtime_ms = (time.perf_counter() - t0) * 1000.0
    diag = eval_res.constraint_diagnostics

    feasibility = decompose_feasibility(
        assignments=frozen_assignments,
        flights=realized_flights,
        gates=gates,
        config=config,
        diag=diag,
    )

    reassignments = sum(
        1
        for f in realized_flights
        if f.nominal_gate_id is not None
        and frozen_assignments.get(f.flight_id) is not None
        and frozen_assignments[f.flight_id].gate_id != f.nominal_gate_id
    )

    return RemediatedRealizationResult(
        realization_id=realization.scenario_id,
        scenario_index=realization.scenario_index,
        initial_plan_solver=solver_name,
        recourse_solver="NONE",
        recourse_policy="FROZEN_ZERO_RECOURSE",
        information_regime=InformationRegime.PRE_OPERATIONAL.value,
        mode=RemediatedSimulationMode.MODE_A_FIXED_PLAN.value,
        objective_value=eval_res.objective_value,
        decision_cost=eval_res.objective_breakdown.decision_cost,
        reporting_cost=eval_res.objective_breakdown.reporting_cost,
        reassignment_count=reassignments,
        remote_count=diag.remote_count,
        feasibility=feasibility,
        runtime_ms=runtime_ms,
        solver_status="FIXED_PLAN",
        is_optimal_proven=False,
        realization_hash=realization.realization_hash,
    )


# ==============================================================================
# MODE B1: RETROSPECTIVE RECOURSE (FULL HINDSIGHT RECOURSE BENCHMARK)
# ==============================================================================
def evaluate_mode_b1_retrospective_recourse(
    initial_assignments: Mapping[str, GateAssignment],
    realized_flights: Sequence[Flight],
    gates: Sequence[Gate],
    config: GateOptimizationConfig,
    realization: RealizedScenario,
    initial_solver_name: str,
    recourse_solver_name: str = "DeterministicGreedy",
) -> RemediatedRealizationResult:
    """Mode B1: Retrospective recourse with full knowledge of all day's realized delays."""
    t0 = time.perf_counter()

    # Formulate recourse problem where nominal gate is the initial planned gate
    recourse_flights: list[Flight] = []
    for f in realized_flights:
        init_asgn = initial_assignments.get(f.flight_id)
        planned_gate = init_asgn.gate_id if init_asgn is not None else f.nominal_gate_id
        recourse_flights.append(
            Flight(
                flight_id=f.flight_id,
                flight_index=f.flight_index,
                carrier=f.carrier,
                flight_number=f.flight_number,
                scheduled_arrival_min=f.scheduled_arrival_min,
                scheduled_departure_min=f.scheduled_departure_min,
                predicted_arrival_min=f.predicted_arrival_min,
                nominal_gate_id=planned_gate,
                aircraft_type=f.aircraft_type,
                min_turnaround_min=f.min_turnaround_min,
                default_dwell_min=f.default_dwell_min,
                buffer_min=f.buffer_min,
                is_paired=f.is_paired,
                precomputed_gate_out_min=f.precomputed_gate_out_min,
            )
        )

    # Dispatch requested recourse solver
    solver_key = recourse_solver_name.lower()
    if "cpsat" in solver_key or "cp_sat" in solver_key:
        solver_instance = CPSatGateSolver(config=config)
    elif "hybrid" in solver_key:
        solver_instance = HybridGateSolver(config=config)
    else:
        solver_instance = DeterministicGreedyGateSolver(config=config)

    res_recourse = solver_instance.solve(
        flights=recourse_flights,
        gates=gates,
        allow_overflow=True,
    )
    runtime_ms = (time.perf_counter() - t0) * 1000.0

    eval_recourse = evaluate_gate_assignment(
        assignments=res_recourse.assignments,
        flights=realized_flights,
        gates=gates,
        config=config,
        runtime_ms=runtime_ms,
        solver_status=res_recourse.status.value if hasattr(res_recourse.status, "value") else str(res_recourse.status),
        solver_name=f"ModeB1_{recourse_solver_name}",
    )
    diag = eval_recourse.constraint_diagnostics

    feasibility = decompose_feasibility(
        assignments=res_recourse.assignments,
        flights=realized_flights,
        gates=gates,
        config=config,
        diag=diag,
    )

    reassignments_from_plan = sum(
        1
        for f in realized_flights
        if initial_assignments.get(f.flight_id) is not None
        and res_recourse.assignments.get(f.flight_id) is not None
        and res_recourse.assignments[f.flight_id].gate_id != initial_assignments[f.flight_id].gate_id
    )

    decision_trace = []
    for f in realized_flights:
        init_g = initial_assignments.get(f.flight_id)
        rec_g = res_recourse.assignments.get(f.flight_id)
        if init_g and rec_g and init_g.gate_id != rec_g.gate_id:
            decision_trace.append(
                {
                    "flight_id": f.flight_id,
                    "previous_gate": init_g.gate_id,
                    "reassigned_gate": rec_g.gate_id,
                    "reason": "RETROSPECTIVE_CONFLICT_AVOIDANCE",
                }
            )

    return RemediatedRealizationResult(
        realization_id=realization.scenario_id,
        scenario_index=realization.scenario_index,
        initial_plan_solver=initial_solver_name,
        recourse_solver=recourse_solver_name,
        recourse_policy="FULL_INFORMATION_RETROSPECTIVE",
        information_regime=InformationRegime.RETROSPECTIVE.value,
        mode=RemediatedSimulationMode.MODE_B1_RETROSPECTIVE_RECOURSE.value,
        objective_value=eval_recourse.objective_value,
        decision_cost=eval_recourse.objective_breakdown.decision_cost,
        reporting_cost=eval_recourse.objective_breakdown.reporting_cost,
        reassignment_count=reassignments_from_plan,
        remote_count=diag.remote_count,
        feasibility=feasibility,
        runtime_ms=runtime_ms,
        solver_status=str(res_recourse.status),
        is_optimal_proven=bool(getattr(res_recourse, "is_optimal_proven", False)),
        realization_hash=realization.realization_hash,
        decision_trace=tuple(decision_trace),
    )


# ==============================================================================
# MODE B2: CAUSAL ONLINE RECOURSE & OBSERVATION SNAPSHOT ARCHITECTURE (G12A)
# ==============================================================================
@dataclass(frozen=True)
class ObservableFlightSnapshot:
    """Strictly causal observation snapshot of flight attributes observable at epoch t.

    Prevents access to ground-truth future realized departure time or delays.
    """

    flight_id: str
    flight_index: int
    carrier: str
    flight_number: str
    aircraft_type: str | None
    scheduled_arrival_min: int
    scheduled_departure_min: int
    nominal_gate_id: str | None
    min_turnaround_min: int
    default_dwell_min: int
    buffer_min: int
    is_paired: bool
    observed_arrival_min: int
    estimated_departure_min: int
    is_docked: bool = False


@dataclass(frozen=True)
class CommittedReservationSnapshot:
    """Pre-arrival gate reservation within the operational commitment window [t, t + H_lock]."""

    flight_id: str
    gate_id: str
    planned_arrival_min: int
    estimated_vacate_min: int


@dataclass(frozen=True)
class GateOccupancySnapshot:
    """Physical occupancy of a gate as observed at decision epoch t."""

    gate_id: str
    is_occupied: bool
    docked_flight_id: str | None = None
    estimated_vacate_min: int | None = None


@dataclass(frozen=True)
class CausalObservationSnapshot:
    """Authoritative non-anticipative Information Set I_t at decision epoch t."""

    epoch_min: int
    current_flight: ObservableFlightSnapshot
    gate_occupancy: Mapping[str, GateOccupancySnapshot]
    committed_reservations: Sequence[CommittedReservationSnapshot]
    current_remote_usage: int
    finite_remote_capacity: int


def make_causal_recourse_decision(
    snapshot: CausalObservationSnapshot,
    current_assigned_gate_id: str,
    contact_gates: Sequence[Gate],
    remote_gate: Gate | None,
    config: GateOptimizationConfig,
    overflow_gate: Gate | None = None,
) -> tuple[str | None, str | None]:
    """Pure decision policy operating exclusively on CausalObservationSnapshot.

    Guarantees:
    - Zero access to future realized departure time.
    - Docked flights cannot be moved.
    - Committed reservations within lock horizon are protected.
    - Finite remote stand capacity is strictly respected under all configurations.
    - Carrier and aircraft type compatibility are strictly respected.
    - Operational availability windows are strictly respected.
    """
    f_curr = snapshot.current_flight
    t = snapshot.epoch_min
    t_vacate_curr = f_curr.estimated_departure_min + f_curr.buffer_min
    time_window = FlightTimeWindow(start_min=t, end_min=t_vacate_curr, buffer_min=f_curr.buffer_min)

    # 0. Check aircraft type, carrier compatibility, and operational availability on currently assigned gate
    assigned_gate = next((g for g in contact_gates if g.gate_id == current_assigned_gate_id), None)
    if assigned_gate is None and remote_gate is not None and remote_gate.gate_id == current_assigned_gate_id:
        assigned_gate = remote_gate
    if assigned_gate is None and overflow_gate is not None and overflow_gate.gate_id == current_assigned_gate_id:
        assigned_gate = overflow_gate

    has_conflict = False
    if assigned_gate is not None:
        if not assigned_gate.is_compatible_aircraft(f_curr.aircraft_type):
            has_conflict = True
        elif not assigned_gate.is_compatible_carrier(f_curr.carrier):
            has_conflict = True
        elif not assigned_gate.is_available_during(time_window):
            has_conflict = True
    else:
        has_conflict = True

    # 1. Check physical occupancy conflict on currently assigned gate
    if not has_conflict:
        if assigned_gate is not None and assigned_gate.resource_type == GateResourceType.FINITE_REMOTE_STAND:
            if snapshot.current_remote_usage >= snapshot.finite_remote_capacity:
                has_conflict = True
        elif assigned_gate is not None and assigned_gate.resource_type == GateResourceType.UNBOUNDED_OVERFLOW_APRON:
            pass
        else:
            assigned_occ = snapshot.gate_occupancy.get(current_assigned_gate_id)
            if assigned_occ and assigned_occ.is_occupied:
                has_conflict = True

    # 2. Check committed reservation overlap on currently assigned gate within lock horizon
    if not has_conflict and (assigned_gate is None or assigned_gate.resource_type == GateResourceType.CONTACT_GATE):
        for res in snapshot.committed_reservations:
            if res.flight_id != f_curr.flight_id and res.gate_id == current_assigned_gate_id:
                if max(t, res.planned_arrival_min) < min(t_vacate_curr, res.estimated_vacate_min):
                    has_conflict = True
                    break

    # If no conflict, keep currently assigned gate
    if not has_conflict:
        return current_assigned_gate_id, None

    # 3. Recourse: Search alternative contact gates
    chosen_gate_id: str | None = None
    for cand_gate in contact_gates:
        # Check aircraft compatibility
        if not cand_gate.is_compatible_aircraft(f_curr.aircraft_type):
            continue
        # Check carrier compatibility
        if not cand_gate.is_compatible_carrier(f_curr.carrier):
            continue
        # Check operational availability window
        if not cand_gate.is_available_during(time_window):
            continue

        # Check physical occupancy
        cand_occ = snapshot.gate_occupancy.get(cand_gate.gate_id)
        if cand_occ and cand_occ.is_occupied:
            continue

        # Check committed reservations within lock horizon
        cand_conflict = False
        for res in snapshot.committed_reservations:
            if res.flight_id == f_curr.flight_id:
                continue
            if res.gate_id == cand_gate.gate_id:
                if max(t, res.planned_arrival_min) < min(t_vacate_curr, res.estimated_vacate_min):
                    cand_conflict = True
                    break
        if cand_conflict:
            continue

        chosen_gate_id = cand_gate.gate_id
        break

    # 4. If no contact gate free, fallback to remote stand if capacity, compatibility, and availability permit
    if chosen_gate_id is None:
        if remote_gate is not None:
            remote_compatible = (
                remote_gate.is_compatible_aircraft(f_curr.aircraft_type)
                and remote_gate.is_compatible_carrier(f_curr.carrier)
                and remote_gate.is_available_during(time_window)
            )
            if not remote_compatible:
                return None, "REMOTE_INCOMPATIBLE"

            if snapshot.current_remote_usage < snapshot.finite_remote_capacity:
                chosen_gate_id = remote_gate.gate_id
            elif overflow_gate is not None and getattr(config, "allow_unbounded_overflow", True):
                overflow_compatible = (
                    overflow_gate.is_compatible_aircraft(f_curr.aircraft_type)
                    and overflow_gate.is_compatible_carrier(f_curr.carrier)
                    and overflow_gate.is_available_during(time_window)
                )
                if overflow_compatible:
                    return overflow_gate.gate_id, "OVERFLOW_APRON_RECOURSE"
                else:
                    return None, "NO_CAPACITY_EXHAUSTED"
            else:
                return None, "NO_CAPACITY_EXHAUSTED"
        elif overflow_gate is not None and getattr(config, "allow_unbounded_overflow", True):
            overflow_compatible = (
                overflow_gate.is_compatible_aircraft(f_curr.aircraft_type)
                and overflow_gate.is_compatible_carrier(f_curr.carrier)
                and overflow_gate.is_available_during(time_window)
            )
            if overflow_compatible:
                return overflow_gate.gate_id, "OVERFLOW_APRON_RECOURSE"
            else:
                return None, "NO_CAPACITY_EXHAUSTED"

    if chosen_gate_id is not None and chosen_gate_id != current_assigned_gate_id:
        return chosen_gate_id, "ONLINE_NON_ANTICIPATIVE_RECOURSE"
    if chosen_gate_id is None:
        return None, "NO_CAPACITY_EXHAUSTED"
    return current_assigned_gate_id, None


def evaluate_mode_b2_rolling_online_recourse(
    initial_assignments: Mapping[str, GateAssignment],
    realized_flights: Sequence[Flight],
    base_scheduled_flights: Sequence[Flight],
    gates: Sequence[Gate],
    config: GateOptimizationConfig,
    realization: RealizedScenario,
    initial_solver_name: str,
    lock_horizon_minutes: int = 45,
) -> RemediatedRealizationResult:
    """Mode B2: Event-driven online rolling-horizon recourse (strictly causal & non-anticipative).

    Non-anticipativity Invariants:
    1. At decision epoch t, only flights with realized arrival <= t have known realized delays.
    2. Future flights with planned start > t are assumed at scheduled/forecasted times.
    3. Flights that have already docked at their gate (occupancy_start <= t) are PHYSICALLY LOCKED.
    4. Committed future flights (<= t + lock_horizon) are protected from gate disruption.
    5. Policy operates strictly on CausalObservationSnapshot, with zero access to realized future gate-out.
    """
    t0 = time.perf_counter()

    flights_by_id = {f.flight_id: f for f in realized_flights}
    base_by_id = {f.flight_id: f for f in base_scheduled_flights}
    contact_gates = [g for g in gates if g.resource_type == GateResourceType.CONTACT_GATE]
    remote_gate = next(
        (g for g in gates if g.resource_type == GateResourceType.FINITE_REMOTE_STAND),
        None,
    )
    if remote_gate is None:
        remote_gate = next(
            (g for g in gates if g.is_overflow and g.resource_type != GateResourceType.UNBOUNDED_OVERFLOW_APRON),
            None,
        )
    overflow_gate = next(
        (g for g in gates if g.resource_type == GateResourceType.UNBOUNDED_OVERFLOW_APRON),
        None,
    )
    remote_gate_id = remote_gate.gate_id if remote_gate else ""
    overflow_gate_id = overflow_gate.gate_id if overflow_gate else ""

    active_assignments: dict[str, GateAssignment] = dict(initial_assignments)
    locked_flights: set[str] = set()
    decision_trace: list[dict[str, Any]] = []

    # Chronological event sweep: iterate over realized arrivals in real time
    event_order = sorted(realized_flights, key=lambda f: (f.predicted_arrival_min, f.flight_index))

    for current_flight in event_order:
        current_time = current_flight.predicted_arrival_min  # Decision epoch t

        # 1. Update physical gate occupancy at time t
        gate_occupancy: dict[str, GateOccupancySnapshot] = {}
        remote_usage_count = 0

        for f_id in list(locked_flights):
            fl = flights_by_id[f_id]
            fl_asgn = active_assignments.get(f_id)
            if fl_asgn is None:
                continue

            # Ground truth departure time of already arrived flight
            actual_dep = getattr(fl, "precomputed_gate_out_min", None)
            if actual_dep is None:
                actual_dep = fl.predicted_arrival_min + fl.default_dwell_min
            actual_vacate = actual_dep + fl.buffer_min

            if current_time < actual_vacate:
                # Gate is physically occupied at time t
                # Causal estimated vacate time (WITHOUT reading actual_dep)
                causal_est_dep = max(fl.scheduled_departure_min, fl.predicted_arrival_min + fl.min_turnaround_min, current_time)
                causal_est_vacate = causal_est_dep + fl.buffer_min
                gate_occupancy[fl_asgn.gate_id] = GateOccupancySnapshot(
                    gate_id=fl_asgn.gate_id,
                    is_occupied=True,
                    docked_flight_id=f_id,
                    estimated_vacate_min=causal_est_vacate,
                )
                if fl_asgn.gate_id == remote_gate_id:
                    remote_usage_count += 1

        # 2. Build committed reservations within lock horizon [current_time, current_time + lock_horizon_minutes]
        committed_reservations: list[CommittedReservationSnapshot] = []
        for f in realized_flights:
            if f.flight_id == current_flight.flight_id or f.flight_id in locked_flights:
                continue
            plan_arr = f.scheduled_arrival_min
            if current_time < plan_arr <= current_time + lock_horizon_minutes:
                asgn = active_assignments.get(f.flight_id)
                if asgn is not None:
                    causal_est_dep = max(f.scheduled_departure_min, plan_arr + f.min_turnaround_min)
                    causal_est_vacate = causal_est_dep + f.buffer_min
                    committed_reservations.append(
                        CommittedReservationSnapshot(
                            flight_id=f.flight_id,
                            gate_id=asgn.gate_id,
                            planned_arrival_min=plan_arr,
                            estimated_vacate_min=causal_est_vacate,
                        )
                    )

        # 3. Build observable snapshot for current_flight at epoch t
        causal_curr_est_dep = max(
            current_flight.scheduled_departure_min,
            current_time + current_flight.min_turnaround_min,
            current_time + current_flight.default_dwell_min,
        )
        curr_snapshot = ObservableFlightSnapshot(
            flight_id=current_flight.flight_id,
            flight_index=current_flight.flight_index,
            carrier=current_flight.carrier,
            flight_number=current_flight.flight_number,
            aircraft_type=current_flight.aircraft_type,
            scheduled_arrival_min=current_flight.scheduled_arrival_min,
            scheduled_departure_min=current_flight.scheduled_departure_min,
            nominal_gate_id=current_flight.nominal_gate_id,
            min_turnaround_min=current_flight.min_turnaround_min,
            default_dwell_min=current_flight.default_dwell_min,
            buffer_min=current_flight.buffer_min,
            is_paired=current_flight.is_paired,
            observed_arrival_min=current_time,
            estimated_departure_min=causal_curr_est_dep,
            is_docked=False,
        )

        finite_cap = getattr(remote_gate, "capacity", None) if remote_gate else None
        if finite_cap is None or math.isinf(finite_cap):
            finite_cap = getattr(config, "finite_remote_capacity", 5)

        obs_snapshot = CausalObservationSnapshot(
            epoch_min=current_time,
            current_flight=curr_snapshot,
            gate_occupancy=gate_occupancy,
            committed_reservations=committed_reservations,
            current_remote_usage=remote_usage_count,
            finite_remote_capacity=int(finite_cap),
        )

        # 4. Make policy decision
        current_asgn = active_assignments.get(current_flight.flight_id)
        if current_asgn is None:
            continue
        assigned_gate_id = current_asgn.gate_id

        # Invoke pure causal decision policy
        chosen_gate_id, reason = make_causal_recourse_decision(
            snapshot=obs_snapshot,
            current_assigned_gate_id=assigned_gate_id,
            contact_gates=contact_gates,
            remote_gate=remote_gate,
            config=config,
            overflow_gate=overflow_gate,
        )

        if chosen_gate_id is None:
            # Finite capacity exhausted: flight cannot be accommodated on contact gate or remote stand
            if current_flight.flight_id in active_assignments:
                del active_assignments[current_flight.flight_id]
            decision_trace.append(
                {
                    "flight_id": current_flight.flight_id,
                    "decision_epoch_min": current_time,
                    "previous_gate": assigned_gate_id,
                    "reassigned_gate": "UNASSIGNED",
                    "reason": reason or "NO_CAPACITY_EXHAUSTED",
                }
            )
        elif chosen_gate_id != assigned_gate_id:
            active_assignments[current_flight.flight_id] = GateAssignment(
                flight_id=current_flight.flight_id,
                gate_id=chosen_gate_id,
                occupancy_start_min=current_time,
                occupancy_end_min=causal_curr_est_dep + current_flight.buffer_min,
            )
            decision_trace.append(
                {
                    "flight_id": current_flight.flight_id,
                    "decision_epoch_min": current_time,
                    "previous_gate": assigned_gate_id,
                    "reassigned_gate": chosen_gate_id,
                    "reason": reason or "ONLINE_NON_ANTICIPATIVE_RECOURSE",
                }
            )
            locked_flights.add(current_flight.flight_id)
        else:
            # Flight retained initial assignment and docked
            locked_flights.add(current_flight.flight_id)

    runtime_ms = (time.perf_counter() - t0) * 1000.0

    eval_online = evaluate_gate_assignment(
        assignments=active_assignments,
        flights=realized_flights,
        gates=gates,
        config=config,
        runtime_ms=runtime_ms,
        solver_status=None,
        solver_name=f"ModeB2_{initial_solver_name}",
    )
    diag = eval_online.constraint_diagnostics

    feasibility = decompose_feasibility(
        assignments=active_assignments,
        flights=realized_flights,
        gates=gates,
        config=config,
        diag=diag,
    )

    if feasibility.composite_feasible:
        online_status = OnlineSolverStatus.ONLINE_FEASIBLE.value
    elif feasibility.unassigned_flight_count > 0 or feasibility.remote_capacity_violation:
        online_status = OnlineSolverStatus.ONLINE_INFEASIBLE_NO_CAPACITY.value
    else:
        online_status = OnlineSolverStatus.ONLINE_INFEASIBLE.value

    reassignments_count = sum(
        1
        for f in realized_flights
        if initial_assignments.get(f.flight_id) is not None
        and active_assignments.get(f.flight_id) is not None
        and active_assignments[f.flight_id].gate_id != initial_assignments[f.flight_id].gate_id
    )

    return RemediatedRealizationResult(
        realization_id=realization.scenario_id,
        scenario_index=realization.scenario_index,
        initial_plan_solver=initial_solver_name,
        recourse_solver="RollingOnlineGreedy",
        recourse_policy="ONLINE_NON_ANTICIPATIVE_EVENT_DRIVEN",
        information_regime=InformationRegime.ONLINE_RECOURSE.value,
        mode=RemediatedSimulationMode.MODE_B2_ONLINE_RECOURSE.value,
        objective_value=eval_online.objective_value,
        decision_cost=eval_online.objective_breakdown.decision_cost,
        reporting_cost=eval_online.objective_breakdown.reporting_cost,
        reassignment_count=reassignments_count,
        remote_count=diag.remote_count,
        feasibility=feasibility,
        runtime_ms=runtime_ms,
        solver_status=online_status,
        is_optimal_proven=False,
        realization_hash=realization.realization_hash,
        decision_trace=tuple(decision_trace),
    )


# ==============================================================================
# MODE C-1: HEURISTIC GREEDY FULL-FORESIGHT BENCHMARK (NOT GLOBAL OPTIMUM)
# ==============================================================================
def evaluate_mode_c_greedy_foresight(
    realized_flights: Sequence[Flight],
    gates: Sequence[Gate],
    config: GateOptimizationConfig,
    realization: RealizedScenario,
) -> RemediatedRealizationResult:
    """Mode C-Heuristic: Greedy foresight heuristic baseline (NOT globally optimal lower bound)."""
    t0 = time.perf_counter()
    oracle_solver = DeterministicGreedyGateSolver(config=config)
    res_oracle = oracle_solver.solve(flights=realized_flights, gates=gates, allow_overflow=True)
    runtime_ms = (time.perf_counter() - t0) * 1000.0

    eval_c = evaluate_gate_assignment(
        assignments=res_oracle.assignments,
        flights=realized_flights,
        gates=gates,
        config=config,
        runtime_ms=runtime_ms,
        solver_status=str(res_oracle.status),
        solver_name="ModeC_GreedyForesightBenchmark",
    )
    diag = eval_c.constraint_diagnostics

    feasibility = decompose_feasibility(
        assignments=res_oracle.assignments,
        flights=realized_flights,
        gates=gates,
        config=config,
        diag=diag,
    )

    reassignments = sum(
        1
        for f in realized_flights
        if f.nominal_gate_id is not None
        and res_oracle.assignments.get(f.flight_id) is not None
        and res_oracle.assignments[f.flight_id].gate_id != f.nominal_gate_id
    )

    return RemediatedRealizationResult(
        realization_id=realization.scenario_id,
        scenario_index=realization.scenario_index,
        initial_plan_solver="NONE",
        recourse_solver="DeterministicGreedy",
        recourse_policy="HEURISTIC_FULL_FORESIGHT_BENCHMARK",
        information_regime=InformationRegime.FULL_FORESIGHT.value,
        mode=RemediatedSimulationMode.MODE_C_GREEDY_FORESIGHT.value,
        objective_value=eval_c.objective_value,
        decision_cost=eval_c.objective_breakdown.decision_cost,
        reporting_cost=eval_c.objective_breakdown.reporting_cost,
        reassignment_count=reassignments,
        remote_count=diag.remote_count,
        feasibility=feasibility,
        runtime_ms=runtime_ms,
        solver_status=str(res_oracle.status),
        is_optimal_proven=False,  # Greedy NEVER proves mathematical global optimality
        realization_hash=realization.realization_hash,
    )


# ==============================================================================
# MODE C-2: CP-SAT MATHEMATICAL OPTIMAL FORESIGHT ORACLE
# ==============================================================================
def evaluate_mode_c_optimal_foresight(
    realized_flights: Sequence[Flight],
    gates: Sequence[Gate],
    config: GateOptimizationConfig,
    realization: RealizedScenario,
) -> RemediatedRealizationResult:
    """Mode C-Optimal: CP-SAT global optimization lower bound with mathematical optimality proof."""
    t0 = time.perf_counter()
    cpsat_solver = CPSatGateSolver(config=config)
    res_cpsat = cpsat_solver.solve(flights=realized_flights, gates=gates, allow_overflow=True)
    runtime_ms = (time.perf_counter() - t0) * 1000.0

    eval_opt = evaluate_gate_assignment(
        assignments=res_cpsat.assignments,
        flights=realized_flights,
        gates=gates,
        config=config,
        runtime_ms=runtime_ms,
        solver_status=str(res_cpsat.status),
        solver_name="ModeC_CPSatOptimalOracle",
    )
    diag = eval_opt.constraint_diagnostics

    feasibility = decompose_feasibility(
        assignments=res_cpsat.assignments,
        flights=realized_flights,
        gates=gates,
        config=config,
        diag=diag,
    )

    reassignments = sum(
        1
        for f in realized_flights
        if f.nominal_gate_id is not None
        and res_cpsat.assignments.get(f.flight_id) is not None
        and res_cpsat.assignments[f.flight_id].gate_id != f.nominal_gate_id
    )

    stat_str = res_cpsat.status.value if hasattr(res_cpsat.status, "value") else str(res_cpsat.status)
    is_optimal = bool(res_cpsat.optimality_proven and stat_str == "OPTIMAL")

    return RemediatedRealizationResult(
        realization_id=realization.scenario_id,
        scenario_index=realization.scenario_index,
        initial_plan_solver="NONE",
        recourse_solver="CPSatGateSolver",
        recourse_policy="PROVEN_MATHEMATICAL_OPTIMAL_FORESIGHT",
        information_regime=InformationRegime.FULL_FORESIGHT.value,
        mode=RemediatedSimulationMode.MODE_C_OPTIMAL_ORACLE.value,
        objective_value=eval_opt.objective_value,
        decision_cost=eval_opt.objective_breakdown.decision_cost,
        reporting_cost=eval_opt.objective_breakdown.reporting_cost,
        reassignment_count=reassignments,
        remote_count=diag.remote_count,
        feasibility=feasibility,
        runtime_ms=runtime_ms,
        solver_status=str(res_cpsat.status),
        is_optimal_proven=is_optimal,
        realization_hash=realization.realization_hash,
    )


# ==============================================================================
# REMEDIATED STATISTICAL SUMMARY & PAIRED DELTAS
# ==============================================================================
def compute_remediated_statistics(
    results: Sequence[RemediatedRealizationResult],
    requested_n: int = 500,
    generation_failures: int = 0,
    evaluation_failures: int = 0,
    timeouts: int = 0,
) -> dict[str, Any]:
    """Compute complete statistical summary with decomposed feasibility rates and risk metrics."""
    n_evaluated = len(results)
    n_generated = max(0, requested_n - generation_failures)
    n_failed = generation_failures + evaluation_failures

    n_feasible = sum(1 for r in results if r.feasibility.composite_feasible)
    n_infeasible = sum(1 for r in results if not r.feasibility.composite_feasible)
    n_capacity_exhausted = sum(
        1
        for r in results
        if r.solver_status == "ONLINE_INFEASIBLE_NO_CAPACITY"
        or r.feasibility.remote_capacity_violation
        or r.feasibility.unassigned_flight_count > 0
    )
    n_timeouts = sum(
        1 for r in results if "TIMEOUT" in str(r.solver_status).upper()
    ) + timeouts

    accounting = {
        "n_requested": requested_n,
        "n_generated": n_generated,
        "n_generation_failures": generation_failures,
        "n_evaluated": n_evaluated,
        "n_evaluation_failures": evaluation_failures,
        "n_timeouts": n_timeouts,
        "n_feasible": n_feasible,
        "n_infeasible": n_infeasible,
        "n_capacity_exhausted": n_capacity_exhausted,
    }

    if n_evaluated == 0:
        return {
            "n_requested": requested_n,
            "n_generated": n_generated,
            "n_evaluated": 0,
            "n_failed": n_failed,
            "accounting": accounting,
            "status": "EMPTY",
        }

    costs = np.array([r.objective_value for r in results], dtype=float)
    phys_conflicts = np.array([r.feasibility.physical_contact_conflict_count for r in results], dtype=int)
    remote_viols = np.array([1 if r.feasibility.remote_capacity_violation else 0 for r in results], dtype=int)
    composite_feasibles = np.array([1 if r.feasibility.composite_feasible else 0 for r in results], dtype=int)
    static_consistents = np.array([1 if r.feasibility.static_slot_consistency else 0 for r in results], dtype=int)
    reassigns = np.array([r.reassignment_count for r in results], dtype=int)
    remotes = np.array([r.remote_count for r in results], dtype=int)
    runtimes = np.array([r.runtime_ms for r in results], dtype=float)

    mean_c = float(np.mean(costs))
    median_c = float(np.median(costs))
    std_c = float(np.std(costs, ddof=1)) if n_evaluated > 1 else 0.0
    se_c = std_c / math.sqrt(n_evaluated) if n_evaluated > 1 else 0.0

    quantiles = np.quantile(costs, [0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99])
    q90 = quantiles[4]
    q95 = quantiles[5]
    cvar_90 = float(np.mean(costs[costs >= q90])) if np.any(costs >= q90) else q90
    cvar_95 = float(np.mean(costs[costs >= q95])) if np.any(costs >= q95) else q95

    return {
        "n_requested": requested_n,
        "n_generated": n_generated,
        "n_evaluated": n_evaluated,
        "n_failed": n_failed,
        "accounting": accounting,
        "mean_cost": round(mean_c, 4),
        "median_cost": round(median_c, 4),
        "cost_std": round(std_c, 4),
        "monte_carlo_se": round(se_c, 4),
        "ci_95_lower": round(mean_c - 1.96 * se_c, 4),
        "ci_95_upper": round(mean_c + 1.96 * se_c, 4),
        "cost_quantiles": {
            "p10": round(float(quantiles[0]), 4),
            "p25": round(float(quantiles[1]), 4),
            "p50": round(float(quantiles[2]), 4),
            "p75": round(float(quantiles[3]), 4),
            "p90": round(float(quantiles[4]), 4),
            "p95": round(float(quantiles[5]), 4),
            "p99": round(float(quantiles[6]), 4),
        },
        "cvar_90": round(cvar_90, 4),
        "cvar_95": round(cvar_95, 4),
        "feasibility_rates": {
            "composite_feasible_rate": round(float(np.mean(composite_feasibles)), 4),
            "physical_contact_conflict_rate": round(float(np.mean(phys_conflicts > 0)), 4),
            "mean_physical_conflict_count": round(float(np.mean(phys_conflicts)), 4),
            "remote_capacity_violation_rate": round(float(np.mean(remote_viols)), 4),
            "static_slot_consistency_rate": round(float(np.mean(static_consistents)), 4),
        },
        "mean_reassignment_count": round(float(np.mean(reassigns)), 4),
        "mean_remote_stand_usage": round(float(np.mean(remotes)), 4),
        "mean_runtime_ms": round(float(np.mean(runtimes)), 3),
    }


def compute_remediated_paired_comparison(
    results_a: Sequence[RemediatedRealizationResult],
    results_b: Sequence[RemediatedRealizationResult],
    label_a: str,
    label_b: str,
) -> dict[str, Any]:
    """Rigorous CRN paired comparison: Delta_s = Cost_A(s) - Cost_B(s)."""
    if len(results_a) != len(results_b):
        raise ValueError("Results lists must have identical lengths for paired comparison!")

    for ra, rb in zip(results_a, results_b):
        if ra.scenario_index != rb.scenario_index:
            raise ValueError(f"CRN alignment mismatch: {ra.scenario_index} vs {rb.scenario_index}")

    deltas = np.array([ra.objective_value - rb.objective_value for ra, rb in zip(results_a, results_b)], dtype=float)
    conflict_deltas = np.array(
        [ra.feasibility.physical_contact_conflict_count - rb.feasibility.physical_contact_conflict_count for ra, rb in zip(results_a, results_b)],
        dtype=float,
    )

    n = len(deltas)
    mean_d = float(np.mean(deltas))
    std_d = float(np.std(deltas, ddof=1)) if n > 1 else 0.0
    se_d = std_d / math.sqrt(n) if n > 1 else 0.0

    t_stat, p_val = stats.ttest_1samp(deltas, popmean=0.0) if n > 1 and std_d > 1e-8 else (0.0, 1.0)

    n_improved = int(np.sum(deltas > 1e-4))   # B has lower cost than A
    n_worsened = int(np.sum(deltas < -1e-4))  # B has higher cost than A
    n_tied = int(np.sum(np.abs(deltas) <= 1e-4))

    return {
        "model_a": label_a,
        "model_b": label_b,
        "n_scenarios": n,
        "mean_delta_cost": round(mean_d, 4),
        "median_delta_cost": round(float(np.median(deltas)), 4),
        "std_delta_cost": round(std_d, 4),
        "mc_se_delta": round(se_d, 4),
        "ci_95_lower": round(mean_d - 1.96 * se_d, 4),
        "ci_95_upper": round(mean_d + 1.96 * se_d, 4),
        "t_statistic": round(float(t_stat), 4),
        "p_value": float(p_val),
        "statistical_significance": bool(p_val < 0.05),
        "mean_delta_physical_conflicts": round(float(np.mean(conflict_deltas)), 4),
        "counts": {
            "improved": n_improved,
            "worsened": n_worsened,
            "tied": n_tied,
        },
        "proportions": {
            "improved_pct": round(n_improved / n * 100.0, 2),
            "worsened_pct": round(n_worsened / n * 100.0, 2),
            "tied_pct": round(n_tied / n * 100.0, 2),
        },
    }
