"""Scenario registry and data loader service with 2024 holdout isolation."""

import hashlib
from typing import Dict, List, Optional, Tuple

from dashboard.core.config import DEFAULT_CONFIG, DashboardConfig
from dashboard.core.contracts import ProvenanceType, ScenarioContext
from src.optimization.domain import Flight, Gate
from src.simulation.scalability_scenario import (
    generate_scalability_scenario,
    scenario_to_flights,
    scenario_to_gates,
)


class ScenarioService:
    """Manages operational scenarios, flight generation, and dataset boundaries."""

    def __init__(self, config: Optional[DashboardConfig] = None) -> None:
        self.config = config or DEFAULT_CONFIG

    def list_scenarios(self) -> List[Dict[str, str]]:
        """Return registered operational scenarios (strictly excluding sealed 2024 data)."""
        return list(self.config.registered_scenarios)

    def get_scenario_context(self, scenario_id: str) -> ScenarioContext:
        """Fetch high-level metadata for a scenario."""
        for scen_meta in self.config.registered_scenarios:
            if scen_meta["id"] == scenario_id:
                # Anti-leakage guard: Finding D3
                if scen_meta.get("year") in self.config.quarantined_years:
                    raise PermissionError(
                        f"Scenario {scenario_id} references quarantined year 2024, sealed under Protocol V4."
                    )

                return ScenarioContext(
                    scenario_id=scen_meta["id"],
                    hub_iata=scen_meta["hub"],
                    flight_count=int(scen_meta["flights"]),
                    gate_count=25 if "120" in scenario_id else 15,
                    remote_capacity=1,
                    scenario_hash=self.compute_scenario_hash(scenario_id),
                    provenance=ProvenanceType.SCHEDULE_BASELINE,
                )

        raise ValueError(f"Unknown scenario ID: {scenario_id}")

    def load_scenario(
        self, scenario_id: str
    ) -> Tuple[List[Flight], List[Gate]]:
        """Load concrete Flight and Gate domain objects for the specified scenario."""
        if "2024" in scenario_id:
            raise PermissionError(
                f"Access denied: Scenario {scenario_id} contains 2024 data sealed under Protocol V4."
            )

        if scenario_id == "SCEN_P09_CANONICAL_120":
            scen = generate_scalability_scenario(
                n_flights=120,
                n_contact_gates=25,
                seed=42,
                scenario_id=scenario_id,
                date_str="2023-07-15",
                day_id="2023-07-15",
            )
            flights = scenario_to_flights(scen)
            contact_gates, remote_gate = scenario_to_gates(scen)
            all_gates = contact_gates + [remote_gate]
            return flights, all_gates

        elif scenario_id == "SCEN_2023_PEAK_01":
            scen = generate_scalability_scenario(
                n_flights=85,
                n_contact_gates=15,
                seed=202602,
                scenario_id=scenario_id,
                date_str="2023-07-15",
                day_id="2023-07-15",
            )
            flights = scenario_to_flights(scen)
            contact_gates, remote_gate = scenario_to_gates(scen)
            all_gates = contact_gates + [remote_gate]
            return flights, all_gates

        raise ValueError(f"Scenario not implemented in registry: {scenario_id}")

    def compute_scenario_hash(self, scenario_id: str) -> str:
        """Deterministic fingerprint of scenario parameters."""
        raw_token = f"{scenario_id}::ATL::BTS_2023::SEED_42"
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
