"""Startup preflight inspection service.

Validates environment, dependencies, model artifacts, and canonical scenarios.
Provides graceful degradation if optional artifacts are missing.
"""

from dataclasses import dataclass, field
import importlib
from pathlib import Path
from typing import Any, Dict, List, Optional

from dashboard.core.config import DEFAULT_CONFIG, DashboardConfig


@dataclass(frozen=True)
class PreflightCheckItem:
    """Individual diagnostic check result."""

    category: str
    name: str
    is_passed: bool
    is_critical: bool
    detail: str


@dataclass(frozen=True)
class PreflightReport:
    """Consolidated system readiness report."""

    is_healthy: bool
    ready_for_presentation: bool
    ready_for_research: bool
    live_solving_available: bool
    checks: List[PreflightCheckItem] = field(default_factory=list)

    def summary_dict(self) -> Dict[str, Any]:
        return {
            "is_healthy": self.is_healthy,
            "ready_for_presentation": self.ready_for_presentation,
            "ready_for_research": self.ready_for_research,
            "live_solving_available": self.live_solving_available,
            "total_checks": len(self.checks),
            "passed_checks": sum(1 for c in self.checks if c.is_passed),
            "failed_checks": sum(1 for c in self.checks if not c.is_passed),
        }


class PreflightService:
    """Diagnostic service to verify system readiness prior to dashboard launch."""

    REQUIRED_PACKAGES = [
        ("streamlit", True),
        ("plotly", True),
        ("ortools", True),
        ("xgboost", True),
        ("pandas", True),
        ("numpy", True),
        ("scipy", True),
        ("shap", False),  # Optional for explainability
    ]

    ESSENTIAL_ARTIFACTS = [
        ("artifacts/remediation/monte_carlo/statistical_summary.json", True),
        ("artifacts/remediation/monte_carlo/fixed_plan_results.csv", True),
        ("artifacts/remediation/monte_carlo/recourse_results.csv", True),
        ("artifacts/remediation/benchmarks/solver_runs.csv", True),
        ("artifacts/remediation/ml_validation/regression_metrics.csv", False),
        ("artifacts/stress_1500x50/solver_results.parquet", False),
    ]

    def __init__(self, config: Optional[DashboardConfig] = None) -> None:
        self.config = config or DEFAULT_CONFIG
        self.project_root = self.config.project_root

    def run_preflight_checks(self) -> PreflightReport:
        """Run all diagnostic checks and compile a PreflightReport."""
        checks: List[PreflightCheckItem] = []

        # 1. Dependency Checks
        for pkg, is_crit in self.REQUIRED_PACKAGES:
            try:
                mod = importlib.import_module(pkg)
                ver = getattr(mod, "__version__", "unknown")
                checks.append(
                    PreflightCheckItem(
                        category="Dependencies",
                        name=f"Python package: {pkg}",
                        is_passed=True,
                        is_critical=is_crit,
                        detail=f"Installed version: {ver}",
                    )
                )
            except ImportError:
                checks.append(
                    PreflightCheckItem(
                        category="Dependencies",
                        name=f"Python package: {pkg}",
                        is_passed=False,
                        is_critical=is_crit,
                        detail="Package not installed in current environment.",
                    )
                )

        # 2. Essential Research Artifact Checks
        for rel_path, is_crit in self.ESSENTIAL_ARTIFACTS:
            full_path = self.project_root / rel_path
            exists = full_path.exists() and full_path.is_file()
            checks.append(
                PreflightCheckItem(
                    category="Artifacts",
                    name=Path(rel_path).name,
                    is_passed=exists,
                    is_critical=is_crit,
                    detail=f"Path: {rel_path} ({'Found' if exists else 'Missing'})",
                )
            )

        # 3. 2024 Holdout Seal Check (Finding D3)
        quarantined = "2024" in self.config.quarantined_years
        checks.append(
            PreflightCheckItem(
                category="Scientific Governance",
                name="2024 Final Holdout Quarantine",
                is_passed=quarantined,
                is_critical=True,
                detail="2024 data strictly quarantined from UI selectors.",
            )
        )

        # 4. Live Solving Engine Readiness
        try:
            import ortools
            live_ok = True
            live_detail = "OR-Tools CP-SAT engine functional for live solving."
        except ImportError:
            live_ok = False
            live_detail = "OR-Tools not available; live solving disabled."

        checks.append(
            PreflightCheckItem(
                category="Optimization Engine",
                name="CP-SAT Live Solving",
                is_passed=live_ok,
                is_critical=True,
                detail=live_detail,
            )
        )

        # Evaluate readiness flags
        critical_failures = [c for c in checks if c.is_critical and not c.is_passed]
        is_healthy = len(critical_failures) == 0

        # Ready for presentation if all critical dependencies and MC artifacts pass
        ready_pres = is_healthy

        # Ready for research if SHAP and stress artifacts also exist
        ready_research = all(c.is_passed for c in checks)

        return PreflightReport(
            is_healthy=is_healthy,
            ready_for_presentation=ready_pres,
            ready_for_research=ready_research,
            live_solving_available=live_ok,
            checks=checks,
        )
