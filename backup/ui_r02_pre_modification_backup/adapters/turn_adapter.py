"""Adapter transforming SimulationTurnResult domain objects to AircraftTurnView."""

from typing import Any, Dict

from dashboard.core.contracts import AircraftTurnView, ProvenanceType, RiskCategory


def adapt_turn_to_view(
    turn_obj_or_dict: Any,
    provenance: ProvenanceType = ProvenanceType.PRECOMPUTED_PREDICTION,
) -> AircraftTurnView:
    """Convert a SimulationTurnResult dataclass or dictionary to AircraftTurnView."""
    if isinstance(turn_obj_or_dict, dict):
        d = turn_obj_or_dict
    else:
        # Dataclass instance
        d = {k: getattr(turn_obj_or_dict, k) for k in dir(turn_obj_or_dict) if not k.startswith("_")}

    turn_id = str(d.get("turn_id", ""))
    inbound_id = str(d.get("inbound_flight_id", ""))
    outbound_id = str(d.get("outbound_flight_id", ""))
    tail_num = str(d.get("tail_number", "N_UNKNOWN"))
    ac_type = str(d.get("aircraft_type", "B738"))

    sched_window = int(d.get("sched_turn_window_min", 75))
    min_turn = int(d.get("min_turn_time_min", 45))
    sched_slack = int(d.get("sched_slack_min", sched_window - min_turn))

    absorbed = float(d.get("inbound_delay_absorbed_min", 0.0))
    rem_slack = float(d.get("remaining_slack_min", max(0.0, sched_slack - absorbed)))
    prop_delay = float(d.get("propagated_outbound_delay_min", 0.0))

    # Risk mapping
    risk_raw = str(d.get("slack_risk_index", "LOW")).upper()
    if "HIGH" in risk_raw or rem_slack < 5.0:
        risk_cat = RiskCategory.HIGH
    elif "MED" in risk_raw or rem_slack < 20.0:
        risk_cat = RiskCategory.MODERATE
    else:
        risk_cat = RiskCategory.LOW

    occ_start = int(d.get("gate_occupancy_start_min", 480))
    occ_end = int(d.get("gate_occupancy_end_min", occ_start + sched_window))

    return AircraftTurnView(
        turn_id=turn_id,
        inbound_flight_id=inbound_id,
        outbound_flight_id=outbound_id,
        tail_number=tail_num,
        aircraft_type=ac_type,
        sched_turn_window_min=sched_window,
        min_turn_time_min=min_turn,
        sched_slack_min=sched_slack,
        inbound_delay_absorbed_min=absorbed,
        remaining_slack_min=rem_slack,
        propagated_outbound_delay_min=prop_delay,
        slack_risk_index=risk_cat,
        gate_occupancy_start_min=occ_start,
        gate_occupancy_end_min=occ_end,
        buffer_min=int(d.get("buffer_min", 15)),
        provenance=provenance,
    )
