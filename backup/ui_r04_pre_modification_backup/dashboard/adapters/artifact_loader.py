"""Safe, read-only artifact loader with path allowlist and schema verification.

Guarantees path traversal prevention, zero code execution, and structured error reporting.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import pandas as pd

from dashboard.core.config import DEFAULT_CONFIG, DashboardConfig


class ArtifactNotFoundError(FileNotFoundError):
    """Raised when an allowlisted artifact does not exist on disk."""


class ArtifactValidationError(ValueError):
    """Raised when an artifact has invalid syntax, missing columns, or corrupt records."""


class ArtifactLoader:
    """Read-only loader for persistent research artifacts."""

    def __init__(self, config: Optional[DashboardConfig] = None) -> None:
        self.config = config or DEFAULT_CONFIG
        self.project_root = self.config.project_root

    def _resolve_and_verify_path(self, relative_path: Path | str) -> Path:
        """Verify path is strictly within project boundaries and allowlist."""
        full_path = (self.project_root / relative_path).resolve()
        if not self.config.is_path_allowlisted(full_path):
            raise PermissionError(
                f"Path traversal or unapproved directory access blocked: {relative_path}"
            )
        if not full_path.exists():
            raise ArtifactNotFoundError(f"Artifact not found on disk: {relative_path}")
        if not full_path.is_file():
            raise ArtifactValidationError(f"Expected a file but found directory: {relative_path}")
        return full_path

    def load_json(
        self, relative_path: str, required_keys: Optional[Set[str]] = None
    ) -> Dict[str, Any] | List[Any]:
        """Safely load and validate a JSON artifact."""
        path = self._resolve_and_verify_path(relative_path)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as exc:
            raise ArtifactValidationError(
                f"Corrupt JSON syntax in artifact {relative_path}: {exc}"
            ) from exc

        if required_keys and isinstance(data, dict):
            missing = required_keys - set(data.keys())
            if missing:
                raise ArtifactValidationError(
                    f"Artifact {relative_path} is missing required keys: {sorted(missing)}"
                )
        return data

    def load_csv(
        self, relative_path: str, required_columns: Optional[Set[str]] = None
    ) -> pd.DataFrame:
        """Safely load and validate a CSV artifact."""
        path = self._resolve_and_verify_path(relative_path)
        try:
            df = pd.read_csv(path)
        except Exception as exc:
            raise ArtifactValidationError(
                f"Corrupt CSV syntax or unreadable table in {relative_path}: {exc}"
            ) from exc

        if df.empty:
            raise ArtifactValidationError(f"Artifact {relative_path} is empty (0 rows)")

        if required_columns:
            missing = required_columns - set(df.columns)
            if missing:
                raise ArtifactValidationError(
                    f"Artifact {relative_path} is missing required columns: {sorted(missing)}"
                )
        return df

    def load_parquet(
        self, relative_path: str, required_columns: Optional[Set[str]] = None
    ) -> pd.DataFrame:
        """Safely load and validate a Parquet artifact."""
        path = self._resolve_and_verify_path(relative_path)
        try:
            df = pd.read_parquet(path)
        except Exception as exc:
            raise ArtifactValidationError(
                f"Corrupt Parquet format in {relative_path}: {exc}"
            ) from exc

        if df.empty:
            raise ArtifactValidationError(f"Artifact {relative_path} is empty (0 rows)")

        if required_columns:
            missing = required_columns - set(df.columns)
            if missing:
                raise ArtifactValidationError(
                    f"Artifact {relative_path} is missing required columns: {sorted(missing)}"
                )
        return df

    # --------------------------------------------------------------------------
    # Specialized High-Level Loaders
    # --------------------------------------------------------------------------

    def load_regression_metrics(self) -> pd.DataFrame:
        """Load P06 ML delay prediction validation metrics."""
        df = self.load_csv(
            "artifacts/remediation/ml_validation/regression_metrics.csv",
            required_columns={"mae", "rmse"},
        )
        if "model" not in df.columns and "model_id" in df.columns:
            df["model"] = df["model_id"]
        return df

    def load_shap_global_importance(self) -> pd.DataFrame:
        """Load global SHAP feature importance rankings."""
        df = self.load_csv(
            "artifacts/remediation/ml_validation/shap_outputs/global_importance.csv",
            required_columns={"feature"},
        )
        if "mean_abs_shap" not in df.columns and "mean_abs_shap_minutes" in df.columns:
            df["mean_abs_shap"] = df["mean_abs_shap_minutes"]
        return df

    def load_shap_case_studies(self) -> List[Dict[str, Any]]:
        """Load local single-flight SHAP waterfall case studies."""
        data = self.load_json("artifacts/remediation/ml_validation/shap_outputs/shap_case_studies.json")
        if not isinstance(data, list):
            raise ArtifactValidationError("Expected a list of case studies in shap_case_studies.json")
        return data

    def load_solver_benchmarks(self) -> pd.DataFrame:
        """Load multi-algorithm comparative benchmark results."""
        return self.load_csv(
            "artifacts/remediation/benchmarks/solver_runs.csv",
            required_columns={"solver_variant", "objective_value", "total_wall_clock_ms", "reassignment_count"},
        )

    def load_cp_sat_formulations(self) -> Dict[str, Any]:
        """Load CP-SAT formulation comparison metrics (sparse interval vs dense grid)."""
        data = self.load_json("artifacts/remediation/cp_sat/formulation_comparison.json")
        if not isinstance(data, dict):
            raise ArtifactValidationError("Expected dict in formulation_comparison.json")
        return data

    def load_monte_carlo_statistical_summary(self) -> Dict[str, Any]:
        """Load descriptive summary metrics from the 500-scenario Monte Carlo evaluation."""
        data = self.load_json(
            "artifacts/remediation/monte_carlo/statistical_summary.json",
            required_keys={"n_evaluated", "mode_a_fixed_plan", "mode_b_recourse", "mode_c_oracle"},
        )
        if not isinstance(data, dict):
            raise ArtifactValidationError("Expected dict in statistical_summary.json")
        return data

    def load_monte_carlo_scenarios(self, mode: str) -> pd.DataFrame:
        """Load scenario-by-scenario results for a specific Monte Carlo mode ('fixed_plan', 'recourse', 'oracle')."""
        mode_file_map = {
            "fixed_plan": "artifacts/remediation/monte_carlo/fixed_plan_results.csv",
            "recourse": "artifacts/remediation/monte_carlo/recourse_results.csv",
            "oracle": "artifacts/remediation/monte_carlo/oracle_results.csv",
        }
        if mode not in mode_file_map:
            raise ValueError(f"Unknown Monte Carlo mode '{mode}'. Choose from: {list(mode_file_map.keys())}")
        df = self.load_csv(
            mode_file_map[mode],
            required_columns={"objective_value"},
        )
        if "scenario_id" not in df.columns:
            if "scenario_index" in df.columns:
                df["scenario_id"] = df["scenario_index"].apply(lambda x: f"SCEN_{int(x):03d}")
            elif "realization_id" in df.columns:
                df["scenario_id"] = df["realization_id"].astype(str)
        return df

    def load_stress_1500_results(self) -> pd.DataFrame:
        """Load mega-hub 1,500 flights scalability results."""
        return self.load_parquet(
            "artifacts/stress_1500x50/solver_results.parquet",
            required_columns={"solver", "solve_time_sec", "objective_value"},
        )
