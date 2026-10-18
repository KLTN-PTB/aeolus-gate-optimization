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
