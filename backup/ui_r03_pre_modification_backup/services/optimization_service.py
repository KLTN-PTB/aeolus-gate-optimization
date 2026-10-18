"""Safe gate optimization solver execution service with scenario size guards and verification.

Adheres strictly to the P10-00 concrete API signatures. Never executes on module import.
"""

import time
from typing import Any, Dict, List, Optional, Tuple

from dashboard.adapters.solver_result_adapter import adapt_solver_result_to_view
from dashboard.core.config import DEFAULT_CONFIG, DashboardConfig
from dashboard.core.contracts import ProvenanceType, SolverRunView
from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import Flight, Gate
from src.optimization.evaluation import verify_hard_constraints_independently
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver
from src.optimization.solvers.hybrid_solver import HybridGateSolver


class ScenarioSizeLimitExceeded(ValueError):
    """Raised when an interactive live solve requests more flights than the safety budget."""


class OptimizationService:
    """Safe execution service for live gate optimization solvers."""

    def __init__(self, config: Optional[DashboardConfig] = None) -> None:
        self.config = config or DEFAULT_CONFIG

    def solve(
        self,
        flights: List[Flight],
        gates: List[Gate],
        solver_name: str = "cpsat",
        scenario_id: str = "SCEN_LIVE_CUSTOM",
        params: Optional[Dict[str, Any]] = None,
        provenance: ProvenanceType = ProvenanceType.NATIVE_INFERENCE,
    ) -> Tuple[SolverRunView, bool, List[str]]:
        """Safely execute a gate allocation solver with size guards and independent verification.

        Returns:
            Tuple[SolverRunView, bool, List[str]]: (solution_view, is_valid, violation_reasons)
        """
        # 1. Size guard enforcement
        if len(flights) > self.config.max_live_solving_flights:
            raise ScenarioSizeLimitExceeded(
                f"Scenario size {len(flights)} exceeds live interactive safety limit "
                f"({self.config.max_live_solving_flights} flights). "
                "Large mega-hub batches must be served via precomputed artifacts."
            )

        clean_params = params or {}
        w_pref = float(clean_params.get("w_pref", self.config.default_w_pref))
        w_remote = float(clean_params.get("w_remote", self.config.default_w_remote))
        buffer_min = int(clean_params.get("buffer_time_min", self.config.default_buffer_time_min))
        time_limit = float(
            clean_params.get("time_limit_sec", self.config.default_cp_sat_time_limit_sec)
        )
        allow_overflow = bool(
            clean_params.get("allow_overflow", self.config.default_allow_unbounded_overflow)
        )

        # 2. Build authoritative GateOptimizationConfig
        opt_config = GateOptimizationConfig(
            reassignment_weight=w_pref,
            overflow_weight=w_remote,
            conflict_weight=1000.0,
            separation_buffer_minutes=buffer_min,
            allow_unbounded_overflow=allow_overflow,
            time_limit_seconds=time_limit,
            num_search_workers=self.config.default_cp_sat_num_workers,
            cp_sat_formulation="sparse_interval",
            cp_sat_fallback_to_greedy=True,
        )

        # 3. Instantiate solver according to audited contract (Task R02-E)
        name_lower = solver_name.lower().strip()
        if "greedy" in name_lower:
            solver = DeterministicGreedyGateSolver(opt_config)
            requested_solver_canonical = "greedy"
            actual_solver_name = "Deterministic Greedy"
        elif "hybrid" in name_lower:
            solver = HybridGateSolver(opt_config)
            requested_solver_canonical = "hybrid"
            actual_solver_name = "Hybrid (Greedy+CP-SAT)"
        elif "cpsat" in name_lower or "cp-sat" in name_lower or "cp_sat" in name_lower:
            solver = CPSatGateSolver(opt_config)
            requested_solver_canonical = "cpsat"
            actual_solver_name = "CP-SAT (Sparse Interval)"
        else:
            raise ValueError(
                f"Unsupported or unknown solver: '{solver_name}'. "
                "Supported solvers: ['cpsat', 'greedy', 'hybrid']. "
                "Silent fallback to CP-SAT is rejected under UI-R02 safety rules."
            )

        # 4. Timed execution
        t0 = time.perf_counter()
        raw_result = solver.solve(flights, gates, allow_overflow=allow_overflow)
        t_elapsed = time.perf_counter() - t0

        # Check solver-level fallback (CP-SAT fallback to greedy)
        raw_cfg = getattr(raw_result, "solver_configuration", {})
        fallback_used = bool(raw_cfg.get("fallback_used", False) if isinstance(raw_cfg, dict) else False)
        effective_solver_name = "Deterministic Greedy" if fallback_used else actual_solver_name

        # 5. Independent Hard Constraint Verification
        diag = verify_hard_constraints_independently(
            flights=flights,
            gates=gates,
            assignments=raw_result.assignments,
        )

        is_valid = bool(diag.hard_constraint_violations_count == 0 and diag.all_flights_assigned)
        violations: List[str] = []
        if not is_valid:
            if not diag.all_flights_assigned:
                violations.append("Not all flights were assigned to a gate")
            for pair in diag.conflict_pairs:
                violations.append(f"Gate conflict between flights: {pair}")
            for incomp in diag.incompatibility_violations:
                violations.append(f"Aircraft incompatibility: {incomp}")

        # 6. Compute Mathematical Identity Digests (Task R02-B)
        from dashboard.core.contracts import ExecutionIdentity, ProblemIdentity
        from dashboard.services.scenario_service import compute_canonical_scenario_digest

        scenario_digest = compute_canonical_scenario_digest(flights, gates, scenario_id)
        prob_identity = ProblemIdentity(
            scenario_digest=scenario_digest,
            objective_version="P10_STANDARD",
            w_pref=w_pref,
            w_remote=w_remote,
            w_conflict=1000.0,
            buffer_time_min=buffer_min,
            allow_overflow=allow_overflow,
            finite_remote_capacity=True,
            prediction_source="SCHEDULE_BASELINE",
            schema_version="2.0",
        )
        problem_digest = prob_identity.problem_digest

        run_id = f"run_{scenario_id}_{requested_solver_canonical}_{int(time.time())}"
        exec_identity = ExecutionIdentity(
            problem_digest=problem_digest,
            requested_solver=requested_solver_canonical,
            effective_solver=effective_solver_name,
            formulation="sparse_interval",
            time_limit_sec=time_limit,
            warm_start=False,
            solver_seed=42,
            fallback_policy="greedy_fallback",
            run_id=run_id,
            schema_version="2.0",
        )
        execution_digest = exec_identity.execution_digest

        # 7. Adapt to View Model with Full Provenance
        verifier_diag_dict = diag.to_dict() if hasattr(diag, "to_dict") else {}
        view = adapt_solver_result_to_view(
            result=raw_result,
            solver_name=effective_solver_name if fallback_used else actual_solver_name,
            scenario_id=scenario_id,
            solver_config={
                "w_pref": w_pref,
                "w_remote": w_remote,
                "buffer_time_min": buffer_min,
                "allow_overflow": allow_overflow,
                "time_limit_sec": time_limit,
                "solver_name": requested_solver_canonical,
                "scenario_id": scenario_id,
            },
            conflicts=[v.split()[0] for v in violations] if not is_valid else [],
            provenance=provenance,
            requested_solver=actual_solver_name,
            effective_solver=effective_solver_name,
            fallback_used=fallback_used,
            problem_digest=problem_digest,
            execution_digest=execution_digest,
            run_id=run_id,
            verifier_diagnostics=verifier_diag_dict,
        )

        return view, is_valid, violations
