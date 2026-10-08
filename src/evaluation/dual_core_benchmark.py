"""End-to-End Dual Core Benchmark and Scalability Evaluation Engine.

Protocol: Aeolus Dual Core Architecture Protocol V2
Phase: P9 End-to-End Dual Core Validation, Fair Benchmark & Scalability
Provides:
1. Four-Branch Fair Comparison:
   - Branch A: SCHEDULE_ONLY (nominal schedule, zero ML predictions)
   - Branch B: ARRIVAL_P4_ONLY_LEGACY (Core Arrival ML, legacy turnaround)
   - Branch C: DUAL_POINT (Core Arrival + Core Departure point forecasts)
   - Branch D: DUAL_PROBABILISTIC (predictive distributions under sensitivity couplings)
2. Authoritative Multi-Solver Execution:
   - DeterministicGreedyGateSolver
   - CPSatGateSolver
   - SimulatedAnnealingGateSolver
   - HybridGateSolver
3. Independent Verification & Realized Post-Hoc Audit:
   - Planned hard-constraint verification outside the solver.
   - Post-hoc evaluation of planned gate assignments against realized operational actuals.
4. Profiling and Scalability Stress Testing:
   - Separate model construction time vs search time.
   - RSS RAM, CPU time, and ladder scalability evaluation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
import logging
import math
import os
from pathlib import Path
import time
from typing import Any, Final, Mapping, Sequence

import numpy as np
import pandas as pd
import psutil

from src.contracts.turn_contracts import FlightLeg, LegDirection, PairType, TurnPair
from src.data.pairing_validator import validate_cpsat_turnaround_schedule_csv
from src.optimization.adapter import (
    DualCoreGateOptimizerAdapter,
    RoleAccessViolationError,
    UncertifiedModelError,
)
from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import (
    ConstraintDiagnostic,
    Flight,
    Gate,
    GateAssignment,
    OptimizationResult,
    verify_hard_constraints_independently,
)
from src.optimization.evaluation import evaluate_gate_assignment
from src.optimization.sa import SAConfig, SimulatedAnnealingGateSolver
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver
from src.optimization.solvers.hybrid_solver import HybridGateSolver
from src.simulation.dual_prediction_turn import (
    CouplingAssumption,
    DualAircraftTurn,
    DualTurnEngine,
    SimulationMode,
)

LOGGER = logging.getLogger("dual_core_benchmark")
DEFAULT_SCHEDULE_CSV: Final[Path] = Path("src/artifacts/predictions/atl_1500_flights_cpsat_turnaround_schedule.csv")


class BenchmarkBranch(str, Enum):
    """Operational forecasting and simulation branches for fair benchmark."""

    SCHEDULE_ONLY = "SCHEDULE_ONLY"
    ARRIVAL_P4_ONLY_LEGACY = "ARRIVAL_P4_ONLY_LEGACY"
    DUAL_POINT = "DUAL_POINT"
    DUAL_PROBABILISTIC = "DUAL_PROBABILISTIC"


def get_process_metrics() -> tuple[float, float]:
    """Return (rss_mb, cpu_time_seconds) for current process."""
    proc = psutil.Process(os.getpid())
    rss = proc.memory_info().rss / (1024.0 * 1024.0)
    cpu_t = proc.cpu_times()
    cpu_total = cpu_t.user + cpu_t.system
    return rss, cpu_total


def generate_contact_gates(n_contact_gates: int, *, allow_overflow: bool = True, max_overflow: int | None = None) -> list[Gate]:
    """Generate standard contact gates G01..Gnn plus optional overflow stand(s)."""
    gates: list[Gate] = []
    for i in range(1, n_contact_gates + 1):
        gates.append(
            Gate(
                gate_id=f"G{i:02d}",
                gate_index=i - 1,
                is_overflow=False,
            )
        )
    if allow_overflow:
        if max_overflow is None or max_overflow <= 1:
            gates.append(Gate(gate_id="OVERFLOW_APRON", gate_index=len(gates), is_overflow=True))
        else:
            for ov_idx in range(1, max_overflow + 1):
                gates.append(
                    Gate(
                        gate_id=f"OVERFLOW_STAND_{ov_idx:02d}",
                        gate_index=len(gates),
                        is_overflow=True,
                    )
                )
    return gates


@dataclass
class TurnDataBundle:
    """Bundle containing turns, planned flights for a branch, and realized actual flights."""

    branch: BenchmarkBranch
    turns: list[DualAircraftTurn]
    planned_flights: list[Flight]
    realized_flights: list[Flight]
    gates: list[Gate]


def load_and_build_branch_turns(
    csv_path: Path = DEFAULT_SCHEDULE_CSV,
    *,
    branch: BenchmarkBranch = BenchmarkBranch.DUAL_POINT,
    coupling_assumption: CouplingAssumption = CouplingAssumption.INDEPENDENT,
    seed: int = 202601,
    n_contact_gates: int = 50,
    max_turns: int | None = None,
    allow_overflow: bool = True,
    max_overflow: int | None = None,
) -> TurnDataBundle:
    """Load schedule CSV, construct turns under specified branch, and build realized actual flights."""
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing schedule CSV at {csv_path}")

    parsed = validate_cpsat_turnaround_schedule_csv(csv_path)
    legs: dict[str, FlightLeg] = parsed["legs"]
    pairs: list[TurnPair] = parsed["pairs"]

    if max_turns is not None and max_turns < len(pairs):
        pairs = pairs[:max_turns]

    # Pre-extract delay lookup from legs raw_metadata
    pred_delays: dict[str, float] = {}
    actual_delays: dict[str, float] = {}
    df = pd.read_csv(csv_path)
    for _, r in df.iterrows():
        fkey = str(r["flight_key"])
        s_min = int(r["sched_time_min"])
        p_min = int(r["pred_time_min"])
        a_min = int(r["actual_time_min"])
        pred_delays[fkey] = float(p_min - s_min)
        actual_delays[fkey] = float(a_min - s_min)

    engine = DualTurnEngine(min_turnaround_min=40, separation_buffer_min=15)
    turns: list[DualAircraftTurn] = []
    rng = np.random.RandomState(seed)

    for pair in pairs:
        # Determine predictions based on branch
        if branch == BenchmarkBranch.SCHEDULE_ONLY:
            arr_p = 0.0
            dep_p = 0.0
            mode = SimulationMode.DUAL_POINT
        elif branch == BenchmarkBranch.ARRIVAL_P4_ONLY_LEGACY:
            arr_p = pred_delays.get(pair.arrival_leg_id, 0.0) if pair.arrival_leg_id else 0.0
            dep_p = 0.0
            mode = SimulationMode.ARRIVAL_ONLY_LEGACY
        elif branch == BenchmarkBranch.DUAL_POINT:
            arr_p = pred_delays.get(pair.arrival_leg_id, 0.0) if pair.arrival_leg_id else 0.0
            dep_p = pred_delays.get(pair.departure_leg_id, 0.0) if pair.departure_leg_id else 0.0
            mode = SimulationMode.DUAL_POINT
        elif branch == BenchmarkBranch.DUAL_PROBABILISTIC:
            base_arr = pred_delays.get(pair.arrival_leg_id, 0.0) if pair.arrival_leg_id else 0.0
            base_dep = pred_delays.get(pair.departure_leg_id, 0.0) if pair.departure_leg_id else 0.0
            # Sample perturbation under coupling assumption
            if coupling_assumption == CouplingAssumption.INDEPENDENT:
                arr_noise = rng.normal(0.0, 10.0)
                dep_noise = rng.normal(0.0, 15.0)
            elif coupling_assumption == CouplingAssumption.COMONOTONIC:
                u = rng.uniform(0.01, 0.99)
                arr_noise = float(10.0 * np.sqrt(2) * (u - 0.5) * 3)
                dep_noise = float(15.0 * np.sqrt(2) * (u - 0.5) * 3)
            elif coupling_assumption == CouplingAssumption.COUNTERMONOTONIC:
                u = rng.uniform(0.01, 0.99)
                arr_noise = float(10.0 * np.sqrt(2) * (u - 0.5) * 3)
                dep_noise = float(15.0 * np.sqrt(2) * ((1.0 - u) - 0.5) * 3)
            else:
                arr_noise, dep_noise = 0.0, 0.0
            arr_p = base_arr + arr_noise
            dep_p = base_dep + dep_noise
            mode = SimulationMode.DUAL_PROBABILISTIC
        else:
            raise ValueError(f"Unknown branch {branch}")

        turn = engine.synthesize_turn(
            pair=pair,
            legs=legs,
            arrival_prediction=arr_p,
            departure_prediction=dep_p,
            mode=mode,
            coupling_assumption=coupling_assumption if branch == BenchmarkBranch.DUAL_PROBABILISTIC else None,
        )
        turns.append(turn)

    # Convert turns to planned Flight domain entities
    dual_enabled = branch in (BenchmarkBranch.DUAL_POINT, BenchmarkBranch.DUAL_PROBABILISTIC)
    cfg = GateOptimizationConfig(dual_core_gate_enabled=dual_enabled, random_seed=seed)
    adapter = DualCoreGateOptimizerAdapter(config=cfg)

    planned_flights = adapter.turns_to_flights(
        turns,
        departure_model_id="departure_certified_point_v1" if dual_enabled else None,
    )

    # Build realized actual flights using actual ground truth delays
    realized_flights: list[Flight] = []
    for idx, turn in enumerate(turns):
        arr_act_del = actual_delays.get(turn.arrival_leg_id, 0.0) if turn.arrival_leg_id else 0.0
        dep_act_del = actual_delays.get(turn.departure_leg_id, 0.0) if turn.departure_leg_id else 0.0

        act_arr_min = turn.scheduled_arrival_min + int(round(arr_act_del))
        act_dep_sched = turn.scheduled_departure_min + int(round(dep_act_del))
        earliest_pushback = act_arr_min + turn.min_turnaround_min
        act_gate_out = max(act_dep_sched, earliest_pushback)

        r_fl = Flight(
            flight_id=turn.turn_id,
            flight_index=idx,
            carrier=turn.carrier,
            flight_number=turn.flight_number,
            scheduled_arrival_min=turn.scheduled_arrival_min,
            scheduled_departure_min=turn.scheduled_departure_min,
            predicted_arrival_min=act_arr_min,
            aircraft_type=turn.aircraft_type,
            nominal_gate_id=turn.nominal_gate_id,
            min_turnaround_min=turn.min_turnaround_min,
            default_dwell_min=turn.default_dwell_min,
            buffer_min=turn.separation_buffer_min,
            is_paired=turn.pair_type in (PairType.VERIFIED_PAIR, PairType.SYNTHETIC_PAIR),
            precomputed_gate_out_min=act_gate_out,
        )
        realized_flights.append(r_fl)

    gates = generate_contact_gates(n_contact_gates, allow_overflow=allow_overflow, max_overflow=max_overflow)

    return TurnDataBundle(
        branch=branch,
        turns=turns,
        planned_flights=planned_flights,
        realized_flights=realized_flights,
        gates=gates,
    )


@dataclass
class SolverExecutionMetrics:
    """Execution metrics from evaluating a solver under a benchmark branch."""

    solver_name: str
    branch: str
    status: str
    feasible: bool
    objective_value: float
    model_construction_ms: float
    solver_execution_ms: float
    total_runtime_ms: float
    cpu_time_ms: float
    peak_rss_mb: float
    memory_delta_mb: float
    contact_assignments: int
    remote_assignments: int
    unassigned_turns: int
    reassignments: int
    planned_hard_violations: int
    planned_conflicts: int
    realized_post_hoc_conflicts: int
    realized_overlap_minutes: float
    independent_audit_valid: bool
    iterations: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_solver_on_bundle(
    solver_name: str,
    bundle: TurnDataBundle,
    *,
    time_limit_seconds: float = 2.0,
    seed: int = 202601,
    sa_iterations: int = 500,
) -> SolverExecutionMetrics:
    """Evaluate a single solver on a TurnDataBundle with fine-grained profiling and post-hoc audit."""
    rss_start, cpu_start = get_process_metrics()
    t_start = time.perf_counter()

    cfg = GateOptimizationConfig(
        time_limit_seconds=time_limit_seconds,
        random_seed=seed,
        num_search_workers=1,
        dual_core_gate_enabled=bundle.branch in (BenchmarkBranch.DUAL_POINT, BenchmarkBranch.DUAL_PROBABILISTIC),
    )

    # 1. Instantiate Solver & measure model construction
    t_construct_start = time.perf_counter()
    if solver_name == "DeterministicGreedy":
        solver = DeterministicGreedyGateSolver(config=cfg)
    elif solver_name == "CPSat":
        solver = CPSatGateSolver(config=cfg)
    elif solver_name == "SimulatedAnnealing":
        solver = SimulatedAnnealingGateSolver(config=cfg, sa_config=SAConfig(iterations=sa_iterations, seed=seed))
    elif solver_name == "HybridCPSatSA":
        solver = HybridGateSolver(config=cfg, sa_config=SAConfig(iterations=sa_iterations, seed=seed), cp_ratio=0.5)
    else:
        raise ValueError(f"Unknown solver {solver_name}")
    t_construct_end = time.perf_counter()
    model_construct_ms = (t_construct_end - t_construct_start) * 1000.0

    # 2. Execute Solver Search
    t_search_start = time.perf_counter()
    result: OptimizationResult = solver.solve(bundle.planned_flights, bundle.gates, allow_overflow=True)
    t_search_end = time.perf_counter()
    solver_search_ms = (t_search_end - t_search_start) * 1000.0

    total_wall_clock_ms = (time.perf_counter() - t_start) * 1000.0
    rss_end, cpu_end = get_process_metrics()
    cpu_time_ms = (cpu_end - cpu_start) * 1000.0
    mem_delta_mb = rss_end - rss_start

    # 3. Independent Verification on Planned Flights
    diag_planned = verify_hard_constraints_independently(
        flights=bundle.planned_flights,
        gates=bundle.gates,
        assignments=result.assignments,
    )

    # 4. Post-Hoc Audit against Realized Actual Flights
    diag_realized = verify_hard_constraints_independently(
        flights=bundle.planned_flights,
        gates=bundle.gates,
        assignments=result.assignments,
        realized_flights=bundle.realized_flights,
    )

    contact_count = sum(1 for a in result.assignments.values() if not a.is_overflow)
    remote_count = sum(1 for a in result.assignments.values() if a.is_overflow)
    unassigned = len(bundle.planned_flights) - len(result.assignments)
    reassign = sum(1 for a in result.assignments.values() if a.is_reassignment)

    realized_overlap_min = sum(c.get("overlap_min", 0.0) for c in diag_realized.realized_conflict_details)

    return SolverExecutionMetrics(
        solver_name=solver_name,
        branch=bundle.branch.value,
        status=result.status,
        feasible=result.feasible,
        objective_value=round(result.objective_value, 4),
        model_construction_ms=round(model_construct_ms, 2),
        solver_execution_ms=round(solver_search_ms, 2),
        total_runtime_ms=round(total_wall_clock_ms, 2),
        cpu_time_ms=round(cpu_time_ms, 2),
        peak_rss_mb=round(rss_end, 2),
        memory_delta_mb=round(mem_delta_mb, 2),
        contact_assignments=contact_count,
        remote_assignments=remote_count,
        unassigned_turns=unassigned,
        reassignments=reassign,
        planned_hard_violations=diag_planned.hard_constraint_violations_count,
        planned_conflicts=diag_planned.conflict_count,
        realized_post_hoc_conflicts=diag_realized.realized_post_hoc_conflicts_count,
        realized_overlap_minutes=round(realized_overlap_min, 1),
        independent_audit_valid=diag_planned.is_valid,
        iterations=sa_iterations if solver_name in ("SimulatedAnnealing", "HybridCPSatSA") else None,
    )
