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
        "data/simulation",
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
            "provenance": "SCALABILITY_GENERATOR_BTS_2023_DERIVED",
            "legacy_provenance": "BTS_OTP_2023_CURATED",
            "data_origin": "REAL_DERIVED",
            "scenario_generation": "SCALABILITY_GENERATOR",
            "pairing_source": "UNPAIRED",
            "prediction_source": "NONE",
            "is_synthetic": "True",
        },
        {
            "id": "SCEN_2026_07_01_1500_MOVEMENTS_150_GATES",
            "name": "ATL 01/07/2026 — 750 đến + 750 đi, 150 cổng",
            "hub": "ATL", "year": "2026", "service_date": "2026-07-01",
            "flights": "1500", "optimization_flights": "750",
            "arrival_count": "750", "departure_count": "750", "gates": "150",
            "artifact_path": "data/simulation/SCEN_2026_07_01_1500_MOVEMENTS_150_GATES.parquet",
            "movements_path": "data/simulation/SCEN_2026_07_01_1500_MOVEMENTS_150_GATES_movements.parquet",
            "gates_path": "data/simulation/SCEN_2026_07_01_1500_MOVEMENTS_150_GATES_gates.json",
            "manifest_path": "data/simulation/SCEN_2026_07_01_1500_MOVEMENTS_150_GATES_manifest.json",
            "max_live_solving_flights": "750", "remote_capacity": "0", "allow_overflow": "False",
            "cp_sat_use_warm_start": "True",
            "provenance": "BTS_20260701_HISTORICAL_REPLAY",
            "time_basis": "HISTORICAL_REPLAY", "information_regime": "RETROSPECTIVE",
            "data_origin": "REAL_DERIVED", "scenario_generation": "HISTORICAL_REPLAY",
            "pairing_source": "INFERRED", "prediction_source": "NONE", "is_synthetic": "True",
        },
        {
            "id": "SCEN_2023_PEAK_01",
            "name": "Atlanta Concourse T Stress (85 Chuyến, 15 Cổng)",
            "hub": "ATL",
            "year": "2023",
            "flights": "85",
            "gates": "15+1",
            "provenance": "SCALABILITY_GENERATOR_BTS_2023_DERIVED",
            "legacy_provenance": "BTS_OTP_2023_CURATED",
            "data_origin": "REAL_DERIVED",
            "scenario_generation": "SCALABILITY_GENERATOR",
            "pairing_source": "UNPAIRED",
            "prediction_source": "NONE",
            "is_synthetic": "True",
        },
        {
            "id": "SCEN_P07_DUAL_CORE_30",
            "name": "Atlanta Dual-Core Turnaround (30 Turns / 60 Chuyến, 15 Cổng)",
            "hub": "ATL",
            "year": "2023",
            "flights": "60",
            "gates": "15+1",
            "provenance": "NATIVE_DUAL_CORE_SYNTHESIS",
            "legacy_provenance": "NATIVE_DUAL_CORE_SYNTHESIS",
            "data_origin": "REAL_DERIVED",
            "scenario_generation": "PARAMETRIC_SIMULATION",
            "pairing_source": "SYNTHETIC_PAIR",
            "prediction_source": "NATIVE_INFERENCE",
            "is_synthetic": "True",
        },
        {
            "id": "SCEN_2023_STRESS_1500_50",
            "name": "Atlanta Stress (1.500 Chuyến, 50 Cổng)",
            "hub": "ATL",
            "year": "2023",
            "flights": "1500",
            "gates": "50+1",
            "artifact_path": "data/simulation/SCEN_2023_STRESS_1500_50.parquet",
            "max_live_solving_flights": "1500",
            "provenance": "PRECOMPUTED_PARQUET_STRESS_SCENARIO",
            "data_origin": "UNKNOWN",
            "scenario_generation": "UNKNOWN",
            "pairing_source": "UNPAIRED",
            "prediction_source": "PRECOMPUTED",
            "is_synthetic": "True",
        },
    )

    def live_solving_limit(self, scenario_id: str) -> int:
        """Apply explicit execution limits for registered large scenarios."""
        for scenario in self.registered_scenarios:
            if scenario["id"] == scenario_id:
                return int(scenario.get("max_live_solving_flights", self.max_live_solving_flights))
        return self.max_live_solving_flights

    def scenario_metadata(self, scenario_id: str) -> Dict[str, str]:
        return next((s for s in self.registered_scenarios if s["id"] == scenario_id), {})

    def allows_overflow(self, scenario_id: str) -> bool:
        return self.scenario_metadata(scenario_id).get("allow_overflow", "True").lower() == "true"


    def is_path_allowlisted(self, target_path: Path | str) -> bool:
        """Verify that a path is strictly inside the project root and within allowlisted directories."""
        try:
            p = Path(target_path)
            resolved = p.resolve() if p.is_absolute() else (self.project_root / p).resolve()
            rel = resolved.relative_to(self.project_root)
        except (ValueError, RuntimeError):
            return False

        # Must not contain path traversal components in relative representation
        if ".." in rel.parts:
            return False

        # Canonical containment check: path must equal or be child of an allowlisted directory
        for allowed in self.allowed_artifact_dirs:
            allowed_path = (self.project_root / allowed).resolve()
            if resolved == allowed_path or allowed_path in resolved.parents:
                return True
        return False

    def is_model_dir_allowlisted(self, model_path: Path | str) -> bool:
        """Verify that a model directory is within allowlisted model locations."""
        try:
            p = Path(model_path)
            resolved = p.resolve() if p.is_absolute() else (self.project_root / p).resolve()
            rel = resolved.relative_to(self.project_root)
        except (ValueError, RuntimeError):
            return False

        if ".." in rel.parts:
            return False

        for allowed in self.allowed_model_dirs:
            allowed_path = (self.project_root / allowed).resolve()
            if resolved == allowed_path or allowed_path in resolved.parents:
                return True
        return False


# Global default configuration instance
DEFAULT_CONFIG = DashboardConfig()
