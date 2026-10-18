"""Scientific validation and experiment compatibility guards.

Enforces zero-data-leakage, fair comparison boundaries, and mathematical integrity.
"""

from typing import Any, Dict, List, Optional, Set

from dashboard.core.contracts import SolverRunView


class DataLeakageError(Exception):
    """Raised when ground-truth actual delay labels appear in planning mode."""


class IncompatibleComparisonError(Exception):
    """Raised when attempting to rank or directly compare incompatible experiments."""


class ScientificValidator:
    """Authoritative scientific boundary validator."""

    # Prohibited actual arrival delay column names in planning mode
    FORBIDDEN_ACTUAL_DELAY_COLUMNS: Set[str] = {
        "arr_delay",
        "arr_delay_new",
        "actual_arr_delay",
        "actual_arr_delay_min",
        "actual_delay_min",
        "actual_arrival_min",
        "realized_arrival_min",
        "dep_delay",
        "dep_delay_new",
        "actual_dep_delay",
        "actual_dep_delay_min",
    }

    @classmethod
    def check_prediction_data_leakage(cls, data_columns_or_keys: List[str] | Set[str]) -> None:
        """Verify that prediction input data contains no target leakage columns."""
        lower_cols = {str(c).lower().strip() for c in data_columns_or_keys}
        leaked = lower_cols.intersection(cls.FORBIDDEN_ACTUAL_DELAY_COLUMNS)
        if leaked:
            raise DataLeakageError(
                f"Target leakage detected in planning view! Prohibited actual columns found: {sorted(leaked)}. "
                "In planning mode, the dispatcher must only observe scheduled times and predicted delays."
            )

    @classmethod
    def validate_solver_ranking_compatibility(
        cls, run_a: SolverRunView, run_b: SolverRunView
    ) -> None:
        """Ensure two solver runs are scientifically fair to rank against each other."""
        # 1. Infeasible or UNKNOWN runs cannot be ranked by objective
        if run_a.status in ("INFEASIBLE", "UNKNOWN") or run_b.status in ("INFEASIBLE", "UNKNOWN"):
            raise IncompatibleComparisonError(
                f"Cannot rank runs with status '{run_a.status}' or '{run_b.status}'; only verified feasible runs can be ranked."
            )

        # 2. Scenario alignment
        if run_a.scenario_id != run_b.scenario_id:
            raise IncompatibleComparisonError(
                f"Scenario mismatch: '{run_a.scenario_id}' vs '{run_b.scenario_id}'. "
                "Runs on different scenarios cannot be ranked directly."
            )

        # 3. Objective formulation, policy, and weights compatibility
        config_a = run_a.solver_config
        config_b = run_b.solver_config
        if config_a and config_b:
            for key in [
                "w_pref",
                "w_remote",
                "buffer_time_min",
                "finite_remote_capacity",
                "objective_version",
                "capacity_policy",
            ]:
                val_a = config_a.get(key)
                val_b = config_b.get(key)
                if val_a is not None and val_b is not None and val_a != val_b:
                    raise IncompatibleComparisonError(
                        f"Objective parameter mismatch for '{key}': {val_a} vs {val_b}. "
                        "Runs with different parameters or policies cannot be ranked together."
                    )

    @classmethod
    def compute_relative_improvement(
        cls, baseline_cost: float, optimized_cost: float
    ) -> Optional[float]:
        """Compute relative percentage cost improvement.

        If baseline_cost is 0.0, returns None ('N/A') rather than claiming 0% or dividing by zero.
        """
        if baseline_cost <= 0.0:
            return None
        return (baseline_cost - optimized_cost) / baseline_cost

    @classmethod
    def validate_benchmark_record_compatibility(
        cls, record_a: Dict[str, Any], record_b: Dict[str, Any]
    ) -> None:
        """Validate whether two benchmark records can be fairly ranked or directly compared.

        Enforces Task R06-B:
        - Must be verified feasible (rejects UNKNOWN / INFEASIBLE).
        - Must have identical scenario_id / workload.
        - Must have identical gate inventory / capacity policy / objective definition.
        """
        # 1. Status feasibility check
        status_a = str(record_a.get("solver_status", record_a.get("status", "UNKNOWN"))).upper()
        status_b = str(record_b.get("solver_status", record_b.get("status", "UNKNOWN"))).upper()
        feasible_a = record_a.get("feasible", status_a in ("OPTIMAL", "FEASIBLE"))
        feasible_b = record_b.get("feasible", status_b in ("OPTIMAL", "FEASIBLE"))

        if not feasible_a or not feasible_b or status_a in ("UNKNOWN", "INFEASIBLE") or status_b in ("UNKNOWN", "INFEASIBLE"):
            raise IncompatibleComparisonError(
                f"Cannot rank runs with status '{status_a}' or '{status_b}'; only verified feasible runs can be ranked."
            )

        # 2. Scenario / workload alignment
        scen_a = record_a.get("scenario_id") or record_a.get("workload_id")
        scen_b = record_b.get("scenario_id") or record_b.get("workload_id")
        if scen_a and scen_b and scen_a != scen_b:
            raise IncompatibleComparisonError(
                f"Scenario mismatch: '{scen_a}' vs '{scen_b}'. "
                "Runs on different scenarios/workloads cannot be ranked directly."
            )

        # 3. Flight population count alignment
        n_fl_a = record_a.get("n_flights") or record_a.get("flight_count")
        n_fl_b = record_b.get("n_flights") or record_b.get("flight_count")
        if n_fl_a is not None and n_fl_b is not None and n_fl_a != n_fl_b:
            raise IncompatibleComparisonError(
                f"Flight population mismatch: {n_fl_a} vs {n_fl_b} flights. "
                "Cannot rank solvers across different problem sizes."
            )

        # 4. Gate inventory / capacity policy alignment
        for key in ["gate_inventory", "n_gates", "capacity_policy", "objective_version", "prediction_source"]:
            val_a = record_a.get(key)
            val_b = record_b.get(key)
            if val_a is not None and val_b is not None and val_a != val_b:
                raise IncompatibleComparisonError(
                    f"Benchmark configuration mismatch for '{key}': '{val_a}' vs '{val_b}'. "
                    "Runs with different problem formulations or policies cannot be ranked together."
                )

    @classmethod
    def compute_pareto_frontier(
        cls,
        points: List[Dict[str, Any]],
        cost_key: str = "cost",
        time_key: str = "time_ms",
    ) -> List[Dict[str, Any]]:
        """Compute the Pareto non-dominated set for biobjective minimization (cost and runtime).

        Point A dominates Point B iff:
        cost(A) <= cost(B) and time(A) <= time(B) with at least one strict inequality (<).
        """
        import math

        valid_points = [
            p for p in points
            if p.get(cost_key) is not None
            and p.get(time_key) is not None
            and math.isfinite(p[cost_key])
            and math.isfinite(p[time_key])
        ]
        if not valid_points:
            return []

        non_dominated: List[Dict[str, Any]] = []
        for i, p_i in enumerate(valid_points):
            is_dominated = False
            c_i, t_i = p_i[cost_key], p_i[time_key]
            for j, p_j in enumerate(valid_points):
                if i == j:
                    continue
                c_j, t_j = p_j[cost_key], p_j[time_key]
                if (c_j <= c_i and t_j <= t_i) and (c_j < c_i or t_j < t_i):
                    is_dominated = True
                    break
            if not is_dominated:
                non_dominated.append(p_i)

        return sorted(non_dominated, key=lambda p: (p[time_key], p[cost_key]))

    @classmethod
    def is_status_feasible_for_ranking(cls, status: Any) -> bool:
        """Check if solver status is verified feasible/optimal and eligible for cost ranking."""
        stat_str = str(status).upper().strip()
        if stat_str in {"OPTIMAL", "FEASIBLE", "FEASIBLE_FOUND", "OPTIMAL_PROVEN"}:
            return True
        return False

    @classmethod
    def is_objective_defined(cls, status: str) -> bool:
        """Check if an objective value is mathematically defined for the given status."""
        status_norm = str(status).upper()
        if status_norm in {"UNKNOWN", "INFEASIBLE", "TIMEOUT_NO_SOLUTION", "MODEL_INVALID"}:
            return False
        return True

    @classmethod
    def validate_single_solver_dataframe(
        cls,
        df: Any,
        target_solver: Optional[str] = "CPSat",
        allow_filter: bool = True,
    ) -> Any:
        """Validate that a Monte Carlo DataFrame is homogeneous (contains only a single solver).

        Prevents cross-solver contamination when plotting Monte Carlo empirical distributions.

        Args:
            df: Monte Carlo scenarios DataFrame.
            target_solver: Solver name to filter by if multi-solver contamination is detected.
            allow_filter: If True, filters cleanly to target_solver. If False, raises IncompatibleComparisonError.

        Returns:
            Filtered single-solver DataFrame.

        Raises:
            IncompatibleComparisonError: If allow_filter is False and multiple solvers are present.
        """
        import pandas as pd

        if not isinstance(df, pd.DataFrame) or df.empty:
            return df
        if "solver_name" not in df.columns:
            return df

        unique_solvers = df["solver_name"].dropna().unique()
        if len(unique_solvers) <= 1:
            return df

        if not allow_filter:
            raise IncompatibleComparisonError(
                f"Multi-solver contamination detected: DataFrame contains multiple solvers {list(unique_solvers)}. "
                "Monte Carlo statistical analysis requires homogeneous single-solver datasets."
            )

        if target_solver and target_solver in unique_solvers:
            return df[df["solver_name"] == target_solver].copy()

        return df[df["solver_name"] == unique_solvers[0]].copy()
