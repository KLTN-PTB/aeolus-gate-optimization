"""Adapter transforming GateAssignment domain objects to GateTimelineView."""

from typing import Any, Dict, Optional

from dashboard.core.contracts import GateTimelineView, ProvenanceType
from src.optimization.domain import Flight, GateAssignment


def adapt_assignment_to_view(
    assign_obj_or_dict: Any,
    has_conflict: bool = False,
    buffer_min: int = 15,
    flight: Optional[Flight] = None,
    scenario_id: str = "SCEN_P09_CANONICAL_120",
    prediction_source: str = "NATIVE_DUAL_CORE",
    provenance: ProvenanceType = ProvenanceType.PRECOMPUTED_PREDICTION,
) -> GateTimelineView:
    """Convert a GateAssignment domain dataclass or dictionary to GateTimelineView.

    Guarantees buffer is present exactly once, never omitted and never double-counted.
    """
    if isinstance(assign_obj_or_dict, dict):
        d = assign_obj_or_dict
        is_domain_obj = False
    else:
        d = {k: getattr(assign_obj_or_dict, k) for k in dir(assign_obj_or_dict) if not k.startswith("_")}
        is_domain_obj = isinstance(assign_obj_or_dict, GateAssignment)

    flight_id = str(d.get("flight_id", ""))
    gate_id = str(d.get("gate_id", ""))
    raw_start = int(d.get("occupancy_start_min", d.get("start_min", 0)))
    raw_end = int(d.get("occupancy_end_min", d.get("end_min", 0)))

    # Determine physical gate-out vs release
    if flight is not None:
        start_min = int(flight.gate_in_min)
        gate_out_min = int(flight.gate_out_min)
        gate_release_min = int(flight.gate_release_min)
        carrier = flight.carrier
        flight_number = flight.flight_number
        nominal_gate_id = flight.nominal_gate_id
        is_reassigned = bool(nominal_gate_id and nominal_gate_id != gate_id)
    else:
        start_min = raw_start
        carrier = str(d.get("carrier", "DL"))
        flight_number = str(d.get("flight_number", flight_id))
        nominal_gate_id = d.get("nominal_gate_id")
        is_reassigned = bool(d.get("is_reassigned", d.get("is_reassignment", False)))
        if nominal_gate_id and nominal_gate_id != gate_id:
            is_reassigned = True

        if is_domain_obj or d.get("end_already_has_buffer", False):
            # Domain GateAssignment: occupancy_end_min already includes buffer
            gate_release_min = raw_end
            gate_out_min = max(start_min, gate_release_min - buffer_min)
        elif "gate_out_min" in d:
            gate_out_min = int(d["gate_out_min"])
            gate_release_min = int(d.get("gate_release_min", gate_out_min + buffer_min))
        else:
            # Legacy/Dict mode: raw_end is physical end, buffer is added to release
            gate_out_min = raw_end
            gate_release_min = gate_out_min + buffer_min

    is_remote = bool(d.get("is_remote", "REMOTE" in gate_id.upper() or "APRON" in gate_id.upper()))
    resource_type = str(d.get("resource_type", "FINITE_REMOTE_STAND" if is_remote else "CONTACT_GATE"))

    # Extract concourse from gate_id (e.g., "GATE_A01" -> "A", "T02" -> "T", "G_05" -> "T", "REMOTE_OVERFLOW" -> "REMOTE")
    clean_gate = gate_id.replace("GATE_", "")
    if clean_gate.startswith("REMOTE"):
        concourse = "REMOTE"
    elif clean_gate.startswith("T"):
        concourse = "T"
    elif clean_gate.startswith("A"):
        concourse = "A"
    elif clean_gate.startswith("G_"):
        try:
            num = int(clean_gate.split("_")[1])
            concourse = "T" if num <= 10 else "A"
        except (ValueError, IndexError):
            concourse = "T"
    else:
        concourse = clean_gate[:1]

    assignment_id = f"ASN_{flight_id}_{gate_id}_{start_min}"

    return GateTimelineView(
        assignment_id=assignment_id,
        flight_id=flight_id,
        gate_id=gate_id,
        concourse=concourse,
        start_min=start_min,
        end_min=gate_out_min,
        buffer_min=buffer_min,
        is_reassigned=is_reassigned,
        is_remote=is_remote,
        has_conflict=has_conflict,
        provenance=provenance,
        carrier=carrier,
        flight_number=flight_number,
        nominal_gate_id=nominal_gate_id,
        resource_type=resource_type,
        scenario_id=scenario_id,
        prediction_source=prediction_source,
        gate_out_min=gate_out_min,
        gate_release_min=gate_release_min,
    )
