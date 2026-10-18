"""Scenario registry and data loader service with 2024 holdout isolation."""

import hashlib
import json
import math
from typing import Dict, List, Optional, Sequence, Tuple

from dashboard.core.config import DEFAULT_CONFIG, DashboardConfig
from dashboard.core.contracts import ProvenanceType, ScenarioContext, ScenarioDataIdentity
from src.optimization.domain import Flight, Gate
from src.simulation.scalability_scenario import (
    generate_scalability_scenario,
    scenario_to_flights,
    scenario_to_gates,
)


def compute_canonical_scenario_digest(
    flights: Sequence[Flight],
    gates: Sequence[Gate],
    scenario_id: str,
    generator_seed: Optional[int] = None,
) -> str:
    """Compute a deterministic, permutation-invariant SHA-256 fingerprint for a scenario dataset (Task R02-A).

    Serializes sorted flights and gates with arrival/departure windows, turnaround requirements,
    concourse assignments, gate capacities, and generator parameters.
    """
    serialized_flights = []
    for fl in sorted(flights, key=lambda f: str(f.flight_id)):
        fl_dict = {
            "flight_id": str(fl.flight_id),
            "carrier": str(fl.carrier or ""),
            "aircraft_type": str(fl.aircraft_type or ""),
            "scheduled_arrival_min": int(fl.scheduled_arrival_min),
            "scheduled_departure_min": int(fl.scheduled_departure_min),
            "predicted_arrival_min": int(fl.predicted_arrival_min),
            "simulated_departure_min": int(fl.simulated_departure_min),
            "min_turnaround_min": int(fl.min_turnaround_min),
            "buffer_min": int(fl.buffer_min),
            "nominal_gate_id": str(fl.nominal_gate_id or ""),
        }
        serialized_flights.append(fl_dict)

    serialized_gates = []
    for gt in sorted(gates, key=lambda g: str(g.gate_id)):
        res_t = gt.resource_type.value if hasattr(gt.resource_type, "value") else str(gt.resource_type or "")
        cap = float(gt.capacity) if math.isfinite(gt.capacity) else "unbounded"
        gt_dict = {
            "gate_id": str(gt.gate_id),
            "gate_index": int(gt.gate_index),
            "is_overflow": bool(gt.is_overflow),
            "resource_type": res_t,
            "capacity": cap,
            "allowed_carriers": sorted(list(gt.allowed_carriers)) if gt.allowed_carriers is not None else None,
            "allowed_aircraft_types": sorted(list(gt.allowed_aircraft_types)) if gt.allowed_aircraft_types is not None else None,
        }
        serialized_gates.append(gt_dict)

    payload = {
        "scenario_id": str(scenario_id),
        "generator_seed": generator_seed,
        "flight_count": len(serialized_flights),
        "gate_count": len(serialized_gates),
        "flights": serialized_flights,
        "gates": serialized_gates,
        "schema_version": "2.0",
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class ScenarioService:
    """Manages operational scenarios, flight generation, and dataset boundaries."""

    _cached_scenarios: Dict[str, Tuple[List[Flight], List[Gate]]] = {}
    _cached_digests: Dict[str, str] = {}

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

                digest = self.compute_scenario_hash(scenario_id)
                gate_count = 25 if "120" in scenario_id else 15

                return ScenarioContext(
                    scenario_id=scen_meta["id"],
                    hub_iata=scen_meta["hub"],
                    flight_count=int(scen_meta["flights"]),
                    gate_count=gate_count,
                    remote_capacity=1,
                    scenario_hash=digest,
                    scenario_digest=digest,
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

        if scenario_id in self._cached_scenarios:
            cached_flights, cached_gates = self._cached_scenarios[scenario_id]
            return list(cached_flights), list(cached_gates)

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
            digest = compute_canonical_scenario_digest(flights, all_gates, scenario_id, generator_seed=42)
            self._cached_scenarios[scenario_id] = (flights, all_gates)
            self._cached_digests[scenario_id] = digest
            return list(flights), list(all_gates)

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
            digest = compute_canonical_scenario_digest(flights, all_gates, scenario_id, generator_seed=202602)
            self._cached_scenarios[scenario_id] = (flights, all_gates)
            self._cached_digests[scenario_id] = digest
            return list(flights), list(all_gates)

        raise ValueError(f"Scenario not implemented in registry: {scenario_id}")

    def compute_scenario_hash(
        self,
        scenario_id: str,
        flights: Optional[Sequence[Flight]] = None,
        gates: Optional[Sequence[Gate]] = None,
        generator_seed: Optional[int] = None,
    ) -> str:
        """Deterministic fingerprint of scenario parameters (Task R02-A / ISSUE-R00-06)."""
        if flights is not None and gates is not None:
            return compute_canonical_scenario_digest(flights, gates, scenario_id, generator_seed)
        if scenario_id in self._cached_digests:
            return self._cached_digests[scenario_id]
        fls, gts = self.load_scenario(scenario_id)
        return self._cached_digests.get(
            scenario_id,
            compute_canonical_scenario_digest(fls, gts, scenario_id, generator_seed),
        )

    def get_scenario_identity(self, scenario_id: str) -> ScenarioDataIdentity:
        """Fetch authoritative dataset identity contract (Task R02-B)."""
        flights, gates = self.load_scenario(scenario_id)
        digest = self.compute_scenario_hash(scenario_id)
        seed = 42 if "120" in scenario_id else (202602 if "PEAK_01" in scenario_id else None)
        return ScenarioDataIdentity(
            scenario_id=scenario_id,
            scenario_digest=digest,
            flight_count=len(flights),
            gate_count=len(gates),
            remote_capacity=1,
            hub_iata="ATL",
            dataset_version="BTS_2023_V1",
            generator_seed=seed,
            schema_version="2.0",
        )

