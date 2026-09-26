"""Synthetic Airport Environment Simulator.

Generates airport gate topology, gate compatibility rules, contact/remote status,
and assigns synthetic aircraft types for simulation experiments.
"""

from __future__ import annotations

import logging
import random
from pathlib import Path
from typing import Any, Optional

import yaml

from src.optimization.contracts import Gate

logger = logging.getLogger(__name__)

AIRCRAFT_TYPES = ["A319", "A320", "A321", "B737", "B738", "B739", "WIDEBODY"]


def generate_gates(
    n_gates: int,
    seed: int,
    wide_capable_ratio: float = 0.2,
    contact_ratio: float = 0.7,
) -> list[Gate]:
    """Generate synthetic airport gates with deterministic topology and compatibility."""
    rng = random.Random(seed)
    gates: list[Gate] = []

    for k in range(n_gates):
        is_wide_capable = rng.random() < wide_capable_ratio
        compatible = AIRCRAFT_TYPES if is_wide_capable else AIRCRAFT_TYPES[:-1]
        is_contact = rng.random() < contact_ratio

        adjacent: list[str] = []
        if k > 0:
            adjacent.append(f"G{k:02d}")
        if k < n_gates - 1:
            adjacent.append(f"G{k+2:02d}")

        gate = Gate(
            gate_id=f"G{k+1:02d}",
            compatible_types=compatible,
            is_contact_gate=is_contact,
            available_from_min=0,
            available_to_min=1440,
            adjacent_gates=adjacent,
        )
        gates.append(gate)

    wide_count = sum(1 for g in gates if "WIDEBODY" in g.compatible_types)
    contact_count = sum(1 for g in gates if g.is_contact_gate)
    logger.info(
        "Generated %d gates (Widebody capable: %d/%.1f%%, Contact: %d/%.1f%%)",
        n_gates,
        wide_count,
        (wide_count / n_gates) * 100.0 if n_gates > 0 else 0,
        contact_count,
        (contact_count / n_gates) * 100.0 if n_gates > 0 else 0,
    )
    return gates


def assign_aircraft_type(rng: random.Random, widebody_share: float = 0.08) -> str:
    """Assign an aircraft type randomly given a widebody share probability."""
    if rng.random() < widebody_share:
        return "WIDEBODY"
    return rng.choice(AIRCRAFT_TYPES[:-1])


def load_simulation_config(config_path: Path | str) -> dict[str, Any]:
    """Load configuration YAML for week 7 airport simulation."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Simulation config not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}
