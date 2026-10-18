"""Adapter transforming raw prediction records to FlightPredictionView."""

from typing import Any, Dict

from dashboard.core.contracts import FlightPredictionView, ProvenanceType, RiskCategory
from dashboard.core.validation import ScientificValidator


def adapt_prediction_row_to_view(
    row: Dict[str, Any],
    provenance: ProvenanceType = ProvenanceType.PRECOMPUTED_PREDICTION,
) -> FlightPredictionView:
    """Convert a dictionary or DataFrame row to a validated FlightPredictionView.

    Enforces target leakage checks before instantiating the view model.
    """
    # 1. Target leakage check
    ScientificValidator.check_prediction_data_leakage(list(row.keys()))

    flight_id = str(row.get("flight_id") or row.get("FLIGHT_ID", ""))
    carrier = str(row.get("carrier") or row.get("OP_UNIQUE_CARRIER", "DL"))
    origin = str(row.get("origin") or row.get("ORIGIN", "ORD"))
    destination = str(row.get("destination") or row.get("DEST", "ATL"))

    # Scheduled arrival time in minutes from midnight
    sched_arr_time_min = int(
        row.get("sched_arr_time_min")
        or row.get("scheduled_arrival_min")
        or row.get("CRS_ARR_TIME_MIN", 480)
    )

    # Predicted delay
    pred_delay = float(
        row.get("predicted_arr_delay_min")
        or row.get("predicted_delay_min")
        or row.get("pred_delay", 0.0)
    )

    # Risk categorization
    if pred_delay >= 30.0:
        risk_cat = RiskCategory.HIGH
    elif pred_delay >= 15.0:
        risk_cat = RiskCategory.MODERATE
    else:
        risk_cat = RiskCategory.LOW

    # Optional uncertainty bounds
    lower_bound = row.get("lower_bound_delay_min") or row.get("lower_bound_min")
    upper_bound = row.get("upper_bound_delay_min") or row.get("upper_bound_min")
    confidence = row.get("confidence_score")

    return FlightPredictionView(
        flight_id=flight_id,
        carrier=carrier,
        origin=origin,
        destination=destination,
        sched_arr_time_min=sched_arr_time_min,
        predicted_arr_delay_min=pred_delay,
        lower_bound_delay_min=float(lower_bound) if lower_bound is not None else None,
        upper_bound_delay_min=float(upper_bound) if upper_bound is not None else None,
        confidence_score=float(confidence) if confidence is not None else None,
        risk_category=risk_cat,
        top_shap_features=row.get("top_shap_features", {}),
        provenance=provenance,
    )
