"""Adapter transforming raw prediction records to FlightPredictionView."""

from typing import Any, Dict, Optional, Sequence

from dashboard.core.contracts import FlightPredictionView, ProvenanceType, RiskCategory
from dashboard.core.validation import ScientificValidator


def adapt_prediction_row_to_view(
    row: Dict[str, Any],
    flight_manifest: Optional[Dict[str, Any]] = None,
    scenario_id: Optional[str] = None,
    provenance: ProvenanceType = ProvenanceType.PRECOMPUTED_PREDICTION,
) -> FlightPredictionView:
    """Convert a dictionary or DataFrame row to a validated FlightPredictionView.

    Enforces target leakage checks before instantiating the view model.
    Never silently invents or hardcodes dummy metadata (DL, ORD, ATL, 480).
    """
    # 1. Target leakage check
    ScientificValidator.check_prediction_data_leakage(list(row.keys()))

    # Cross-scenario isolation guard (R01-T03)
    row_scenario = row.get("scenario_id")
    if scenario_id and row_scenario and row_scenario != scenario_id:
        raise ValueError(
            f"Cross-scenario mismatch: row scenario '{row_scenario}' does not match active scenario '{scenario_id}'"
        )

    flight_id = str(row.get("flight_id") or row.get("FLIGHT_ID") or "")
    if not flight_id:
        raise ValueError("flight_id cannot be empty")

    # Resolve metadata from flight_manifest if provided and matched
    manifest_match = None
    if flight_manifest is not None:
        manifest_match = flight_manifest.get(flight_id)

    # Carrier resolution
    carrier_raw = (
        row.get("carrier")
        or row.get("OP_UNIQUE_CARRIER")
        or (getattr(manifest_match, "carrier", None) if manifest_match else None)
        or (manifest_match.get("carrier") if isinstance(manifest_match, dict) else None)
    )
    carrier = str(carrier_raw) if carrier_raw is not None and str(carrier_raw).strip() else "N/A"

    # Origin resolution
    origin_raw = (
        row.get("origin")
        or row.get("ORIGIN")
        or (getattr(manifest_match, "origin", None) if manifest_match else None)
        or (manifest_match.get("origin") if isinstance(manifest_match, dict) else None)
    )
    origin = str(origin_raw) if origin_raw is not None and str(origin_raw).strip() else "N/A"

    # Destination resolution
    dest_raw = (
        row.get("destination")
        or row.get("DEST")
        or (getattr(manifest_match, "destination", None) if manifest_match else None)
        or (manifest_match.get("destination") if isinstance(manifest_match, dict) else None)
    )
    destination = str(dest_raw) if dest_raw is not None and str(dest_raw).strip() else "N/A"

    # Scheduled arrival time resolution (minutes from midnight)
    sched_time_raw = (
        row.get("sched_arr_time_min")
        or row.get("scheduled_arrival_min")
        or row.get("CRS_ARR_TIME_MIN")
        or (getattr(manifest_match, "scheduled_arrival_min", None) if manifest_match else None)
        or (manifest_match.get("scheduled_arrival_min") if isinstance(manifest_match, dict) else None)
    )
    sched_arr_time_min: Optional[int] = None
    if sched_time_raw is not None:
        try:
            sched_arr_time_min = int(sched_time_raw)
        except (ValueError, TypeError):
            sched_arr_time_min = None

    # Predicted delay resolution (preserving real 0.0 values without falsy suppression)
    pred_delay = None
    for k in ["predicted_arr_delay_min", "predicted_delay_min", "pred_delay"]:
        if k in row and row[k] is not None:
            try:
                pred_delay = float(row[k])
                break
            except (ValueError, TypeError):
                pass
    if pred_delay is None:
        pred_delay = 0.0

    # Risk categorization
    if pred_delay >= 30.0:
        risk_cat = RiskCategory.HIGH
    elif pred_delay >= 15.0:
        risk_cat = RiskCategory.MODERATE
    else:
        risk_cat = RiskCategory.LOW

    # Optional uncertainty bounds
    lower_bound = row.get("lower_bound_delay_min") if "lower_bound_delay_min" in row else row.get("lower_bound_min")
    upper_bound = row.get("upper_bound_delay_min") if "upper_bound_delay_min" in row else row.get("upper_bound_min")
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
