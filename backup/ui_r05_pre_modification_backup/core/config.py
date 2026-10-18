"""Dashboard configuration, allowlists, and execution boundaries.

All paths are resolved relative to project root dynamically without hardcoded drive letters.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set, Tuple


@dataclass(frozen=True)
class DashboardConfig:
    """Immutable dashboard system configuration and security boundaries."""

    # Project root discovery (resolves 2 levels up from dashboard/core/)
    project_root: Path = field(
        default_factory=lambda: Path(__file__).resolve().parent.parent.parent
    )

    # Allowed artifact directories (path traversal protection)
    allowed_artifact_dirs: Tuple[str, ...] = (
        "artifacts/remediation",
        "artifacts/stress_1500x50",
        "artifacts/models",
        "artifacts/simulation",
        "data/processed",
        "docs/dashboard_discovery/samples",
    )

    # Allowed model checkpoint directories (only verified checkpoints can be loaded)
    allowed_model_dirs: Tuple[str, ...] = (
        "artifacts/models/inbound_arrival",
        "artifacts/models/outbound_departure",
        "models",
    )

    # Live solving execution limits
    max_live_solving_flights: int = 150
    default_cp_sat_time_limit_sec: float = 30.0
    default_cp_sat_num_workers: int = 4

    # Default optimization weights (P09 locked)
    default_w_pref: float = 10.0
    default_w_remote: float = 200.0
    default_w_conflict: float = 1000.0
    default_buffer_time_min: int = 15
    default_finite_remote_capacity: int = 1
    default_allow_unbounded_overflow: bool = True

    # Quarantined data years (Anti-leakage rule from Finding D3)
    quarantined_years: Tuple[str, ...] = ("2024",)

    # Registered demo scenarios
    registered_scenarios: Tuple[Dict[str, str], ...] = (
        {
            "id": "SCEN_P09_CANONICAL_120",
            "name": "Atlanta Peak Morning (120 Chuyến, 25 Cổng)",
            "hub": "ATL",
            "year": "2023",
            "flights": "120",
            "gates": "25+1",
            "provenance": "BTS_OTP_2023_CURATED",
        },
        {
            "id": "SCEN_2023_PEAK_01",
            "name": "Atlanta Concourse T Stress (85 Chuyến, 15 Cổng)",
            "hub": "ATL",
            "year": "2023",
            "flights": "85",
            "gates": "15+1",
            "provenance": "BTS_OTP_2023_CURATED",
        },
        {
            "id": "SCEN_P07_DUAL_CORE_30",
            "name": "Atlanta Dual-Core Turnaround (30 Turns / 60 Chuyến, 15 Cổng)",
            "hub": "ATL",
            "year": "2023",
            "flights": "60",
            "gates": "15+1",
            "provenance": "NATIVE_DUAL_CORE_SYNTHESIS",
        },
    )

    def is_path_allowlisted(self, target_path: Path | str) -> bool:
        """Verify that a path is strictly inside the project root and within allowlisted directories."""
        resolved = Path(target_path).resolve()
        # Must be within project root
        try:
            rel = resolved.relative_to(self.project_root)
        except ValueError:
            return False

        # Must not contain path traversal components
        if ".." in rel.parts:
            return False

        rel_posix = rel.as_posix()
        return any(
            rel_posix.startswith(allowed) or rel_posix == allowed
            for allowed in self.allowed_artifact_dirs
        )

    def is_model_dir_allowlisted(self, model_path: Path | str) -> bool:
        """Verify that a model directory is within allowlisted model locations."""
        resolved = Path(model_path).resolve()
        try:
            rel = resolved.relative_to(self.project_root)
        except ValueError:
            return False
        rel_posix = rel.as_posix()
        return any(
            rel_posix.startswith(allowed) or rel_posix == allowed
            for allowed in self.allowed_model_dirs
        )


# Global default configuration instance
DEFAULT_CONFIG = DashboardConfig()
