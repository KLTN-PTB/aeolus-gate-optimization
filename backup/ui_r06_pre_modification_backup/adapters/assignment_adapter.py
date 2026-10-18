"""Adapter transforming GateAssignment domain objects to GateTimelineView."""

from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

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

    upper_gate = gate_id.upper().strip()
    clean_gate = upper_gate.replace("GATE_", "")

    # 1. Determine resource_type & remote flag
    raw_res_type = d.get("resource_type")
    if raw_res_type is not None:
        resource_type = getattr(raw_res_type, "value", str(raw_res_type))
    elif getattr(assign_obj_or_dict, "resource_type", None) is not None:
        resource_type = getattr(assign_obj_or_dict.resource_type, "value", str(assign_obj_or_dict.resource_type))
    elif "APRON" in upper_gate or "OVERFLOW" in upper_gate:
        resource_type = "UNBOUNDED_OVERFLOW_APRON"
    elif "REMOTE" in upper_gate:
        resource_type = "FINITE_REMOTE_STAND"
    else:
        resource_type = "CONTACT_GATE"

    is_remote = bool(
        d.get("is_remote")
        or "REMOTE" in upper_gate
        or "APRON" in upper_gate
        or "OVERFLOW" in upper_gate
        or resource_type in ("FINITE_REMOTE_STAND", "UNBOUNDED_OVERFLOW_APRON")
    )

    # 2. Extract concourse from gate_id (TASK R05-A / ISSUE-R00-07)
    # Strictly prevent APRON / OVERFLOW from being misclassified as Concourse A
    if clean_gate.startswith("REMOTE") or clean_gate.startswith("STAND"):
        concourse = "REMOTE"
    elif clean_gate.startswith("APRON") or clean_gate.startswith("OVERFLOW") or clean_gate.startswith("OVF") or resource_type == "UNBOUNDED_OVERFLOW_APRON":
        concourse = "OVERFLOW"
    elif d.get("concourse") and str(d["concourse"]).upper() not in ("", "NONE", "UNKNOWN"):
        concourse = str(d["concourse"])
    elif clean_gate.startswith("T"):
        concourse = "T"
    elif clean_gate.startswith("A"):
        concourse = "A"
    elif clean_gate.startswith("G_") or clean_gate.startswith("G"):
        digits = "".join([ch for ch in clean_gate if ch.isdigit()])
        if digits:
            try:
                num = int(digits)
                concourse = "T" if num <= 10 else "A"
            except ValueError:
                concourse = "T"
        else:
            concourse = "UNKNOWN_GROUP"
    else:
        concourse = "UNKNOWN_GROUP"

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


def check_intervals_overlap(
    interval_a: Tuple[int, int],
    interval_b: Tuple[int, int],
) -> bool:
    """Determine whether two half-open intervals [s1, e1) and [s2, e2) overlap.

    Adjacent intervals [a, b) and [b, c) do NOT overlap.
    """
    s1, e1 = interval_a
    s2, e2 = interval_b
    return s1 < e2 and s2 < e1


def filter_assignments(
    assignments: Sequence[GateTimelineView],
    concourse_filter: Optional[Sequence[str]] = None,
    carrier_filter: Optional[str] = None,
    resource_type_filter: Optional[str] = None,
    search_query: Optional[str] = None,
    time_window: Optional[Tuple[int, int]] = None,
) -> List[GateTimelineView]:
    """Filter assignments by intersecting all active criteria (Task R05-B).

    - concourse_filter: None means all; [] means none; ['T'] means only T.
    - carrier_filter: None or 'ALL' means all; 'DL' means only DL.
    - resource_type_filter: None or 'ALL' means all; specific type means only matching.
    - search_query: None or '' means all; string means case-insensitive substring match.
    - time_window: (w_start, w_end) checks interval intersection [start, release) overlapping with [w_start, w_end).
    """
    res = list(assignments)

    if concourse_filter is not None:
        c_set = set(concourse_filter)
        res = [a for a in res if a.concourse in c_set]

    if carrier_filter is not None and carrier_filter.upper() != "ALL":
        res = [a for a in res if a.carrier.upper() == carrier_filter.upper()]

    if resource_type_filter is not None and resource_type_filter.upper() != "ALL":
        res = [a for a in res if a.resource_type.upper() == resource_type_filter.upper()]

    if search_query is not None and search_query.strip():
        q = search_query.strip().upper()
        res = [a for a in res if q in a.flight_id.upper()]

    if time_window is not None:
        w_start, w_end = time_window
        res = [
            a for a in res
            if a.start_min < w_end and a.actual_gate_release_min > w_start
        ]

    return res


def detect_gate_conflicts(
    assignments: Sequence[GateTimelineView],
    gate_capacities: Optional[Dict[str, int]] = None,
) -> Dict[str, List[str]]:
    """Detect capacity and overlapping conflicts per gate for half-open intervals [start, release)."""
    by_gate: Dict[str, List[GateTimelineView]] = {}
    for a in assignments:
        by_gate.setdefault(a.gate_id, []).append(a)

    conflicts: Dict[str, List[str]] = {}
    for gid, asns in by_gate.items():
        cap = gate_capacities.get(gid, 1) if gate_capacities else 1
        if cap == 1:
            for i in range(len(asns)):
                for j in range(i + 1, len(asns)):
                    a1, a2 = asns[i], asns[j]
                    if check_intervals_overlap(a1.total_blocked_interval, a2.total_blocked_interval):
                        conflicts.setdefault(gid, []).append(f"{a1.flight_id} vs {a2.flight_id}")
        else:
            # Pooled capacity K (finite remote stand): check maximum simultaneous occupancy
            events = []
            for a in asns:
                events.append((a.start_min, 1, a.flight_id))
                events.append((a.actual_gate_release_min, -1, a.flight_id))
            # Sort events: departures (-1) before arrivals (+1) at same timestamp for half-open intervals
            events.sort(key=lambda x: (x[0], x[1]))
            concurrent = 0
            for t, delta, fid in events:
                concurrent += delta
                if concurrent > cap:
                    conflicts.setdefault(gid, []).append(f"Capacity exceeded ({concurrent} > {cap}) at t={t}")
                    break
    return conflicts
