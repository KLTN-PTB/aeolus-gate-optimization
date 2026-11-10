"""Timezone normalization, timeline alignment, and temporal causality for Aeolus.

Protocol: Aeolus Dual Core Architecture Protocol V2
Phase: P6 Time Normalization & Arrival-Departure Pairing
Task: Timezone-aware timestamp conversion, DST handling, rollover reconciliation, and causality checks.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, time, timedelta, timezone
import re
from typing import Any, Final
from zoneinfo import ZoneInfo

from src.contracts.turn_contracts import LegDirection


class UnknownAirportTimezoneError(ValueError):
    """Raised when an airport code cannot be mapped to an authenticated IANA timezone."""


class DSTGapError(ValueError):
    """Raised when a specified local time does not exist due to DST spring-forward."""


class TemporalCausalityViolation(ValueError):
    """Raised when prediction or cutoff timestamps violate operational causality."""


# Comprehensive verified IANA timezone lookup for US domestic airports
# Covers ATL hub, all 147 airports in the CPSAT turnaround fixture, and common domestic airports
AIRPORT_IANA_TIMEZONES: Final[dict[str, str]] = {
    # Hub Airport
    "ATL": "America/New_York",
    # Eastern Time (America/New_York)
    "ABE": "America/New_York",
    "ABY": "America/New_York",
    "AGS": "America/New_York",
    "ALB": "America/New_York",
    "AVL": "America/New_York",
    "BDL": "America/New_York",
    "BOS": "America/New_York",
    "BQK": "America/New_York",
    "BTV": "America/New_York",
    "BUF": "America/New_York",
    "BWI": "America/New_York",
    "CAE": "America/New_York",
    "CHA": "America/New_York",
    "CHO": "America/New_York",
    "CHS": "America/New_York",
    "CLE": "America/New_York",
    "CLT": "America/New_York",
    "CMH": "America/New_York",
    "CRW": "America/New_York",
    "CSG": "America/New_York",
    "CVG": "America/New_York",
    "DAB": "America/New_York",
    "DAY": "America/New_York",
    "DCA": "America/New_York",
    "DTW": "America/New_York",
    "EWR": "America/New_York",
    "EYW": "America/New_York",
    "FAY": "America/New_York",
    "FLL": "America/New_York",
    "GNV": "America/New_York",
    "GRR": "America/New_York",
    "GSO": "America/New_York",
    "GSP": "America/New_York",
    "HPN": "America/New_York",
    "IAD": "America/New_York",
    "ILM": "America/New_York",
    "JAX": "America/New_York",
    "JFK": "America/New_York",
    "LEX": "America/New_York",
    "LGA": "America/New_York",
    "MCO": "America/New_York",
    "MDT": "America/New_York",
    "MIA": "America/New_York",
    "MLB": "America/New_York",
    "MYR": "America/New_York",
    "OAJ": "America/New_York",
    "ORF": "America/New_York",
    "PBI": "America/New_York",
    "PHL": "America/New_York",
    "PIT": "America/New_York",
    "PVD": "America/New_York",
    "PWM": "America/New_York",
    "RDU": "America/New_York",
    "RIC": "America/New_York",
    "ROA": "America/New_York",
    "ROC": "America/New_York",
    "RSW": "America/New_York",
    "SAV": "America/New_York",
    "SDF": "America/New_York",
    "SRQ": "America/New_York",
    "SYR": "America/New_York",
    "TLH": "America/New_York",
    "TPA": "America/New_York",
    "TRI": "America/New_York",
    "TTN": "America/New_York",
    "TYS": "America/New_York",
    "VLD": "America/New_York",
    # Indiana (Eastern Time)
    "IND": "America/Indiana/Indianapolis",
    "FWA": "America/Indiana/Indianapolis",
    "SBN": "America/Indiana/Indianapolis",
    # Central Time (America/Chicago)
    "AEX": "America/Chicago",
    "ATW": "America/Chicago",
    "AUS": "America/Chicago",
    "BHM": "America/Chicago",
    "BMI": "America/Chicago",
    "BNA": "America/Chicago",
    "BTR": "America/Chicago",
    "CID": "America/Chicago",
    "DAL": "America/Chicago",
    "DFW": "America/Chicago",
    "DHN": "America/Chicago",
    "DSM": "America/Chicago",
    "ECP": "America/Chicago",
    "EVV": "America/Chicago",
    "FSD": "America/Chicago",
    "GPT": "America/Chicago",
    "GRB": "America/Chicago",
    "GTR": "America/Chicago",
    "HOU": "America/Chicago",
    "HSV": "America/Chicago",
    "IAH": "America/Chicago",
    "ICT": "America/Chicago",
    "JAN": "America/Chicago",
    "LFT": "America/Chicago",
    "LIT": "America/Chicago",
    "MCI": "America/Chicago",
    "MDW": "America/Chicago",
    "MEM": "America/Chicago",
    "MGM": "America/Chicago",
    "MKE": "America/Chicago",
    "MLI": "America/Chicago",
    "MLU": "America/Chicago",
    "MOB": "America/Chicago",
    "MSN": "America/Chicago",
    "MSP": "America/Chicago",
    "MSY": "America/Chicago",
    "OKC": "America/Chicago",
    "OMA": "America/Chicago",
    "ORD": "America/Chicago",
    "PNS": "America/Chicago",
    "SAT": "America/Chicago",
    "SGF": "America/Chicago",
    "SHV": "America/Chicago",
    "STL": "America/Chicago",
    "TUL": "America/Chicago",
    "VPS": "America/Chicago",
    "XNA": "America/Chicago",
    # Mountain Time (America/Denver)
    "ABQ": "America/Denver",
    "ASE": "America/Denver",
    "BOI": "America/Boise",
    "BZN": "America/Denver",
    "COS": "America/Denver",
    "DEN": "America/Denver",
    "EGE": "America/Denver",
    "ELP": "America/Denver",
    "HDN": "America/Denver",
    "JAC": "America/Denver",
    "MTJ": "America/Denver",
    "SLC": "America/Denver",
    # Arizona (Mountain Standard Time, No DST)
    "PHX": "America/Phoenix",
    "TUS": "America/Phoenix",
    "FLG": "America/Phoenix",
    # Pacific Time (America/Los_Angeles)
    "BUR": "America/Los_Angeles",
    "GEG": "America/Los_Angeles",
    "LAS": "America/Los_Angeles",
    "LAX": "America/Los_Angeles",
    "OAK": "America/Los_Angeles",
    "ONT": "America/Los_Angeles",
    "PDX": "America/Los_Angeles",
    "PSP": "America/Los_Angeles",
    "SAN": "America/Los_Angeles",
    "SEA": "America/Los_Angeles",
    "SFO": "America/Los_Angeles",
    "SJC": "America/Los_Angeles",
    "SMF": "America/Los_Angeles",
    "SNA": "America/Los_Angeles",
    # Alaska & Hawaii
    "ANC": "America/Anchorage",
    "FAI": "America/Anchorage",
    "JNU": "America/Anchorage",
    "HNL": "Pacific/Honolulu",
    "OGG": "Pacific/Honolulu",
    "KOA": "Pacific/Honolulu",
    # Caribbean / Atlantic (No DST)
    "SJU": "America/Puerto_Rico",
    "STT": "America/Port_of_Spain",
}


def get_airport_timezone(airport_code: str) -> str:
    """Returns the IANA timezone identifier for an airport. Fails closed if unrecognized."""
    code = airport_code.strip().upper()
    if code not in AIRPORT_IANA_TIMEZONES:
        raise UnknownAirportTimezoneError(
            f"Unrecognized airport code '{airport_code}'. Cannot assume a default timezone."
        )
    return AIRPORT_IANA_TIMEZONES[code]


def parse_hhmm_time(val: Any) -> tuple[int, int]:
    """Parses various HHMM formats (int 1835, str '18:35', str '1835', float 1835.0) into (hour, minute)."""
    if val is None:
        raise ValueError("Cannot parse None as HHMM time")

    if isinstance(val, (int, float)):
        int_val = int(round(val))
        if int_val < 0 or int_val > 2400:
            raise ValueError(f"HHMM numeric value {int_val} out of bounds [0, 2400]")
        hour = int_val // 100
        minute = int_val % 100
        if hour == 24 and minute == 0:
            return (0, 0)
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            raise ValueError(f"Invalid hour ({hour}) or minute ({minute}) from {int_val}")
        return (hour, minute)

    s = str(val).strip()
    if ":" in s:
        parts = s.split(":")
        hour = int(parts[0])
        minute = int(parts[1])
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            raise ValueError(f"Invalid time format '{s}'")
        return (hour, minute)

    if s.isdigit():
        int_val = int(s)
        return parse_hhmm_time(int_val)

    # ISO or space timestamp
    m = re.search(r"(\d{2}):(\d{2})", s)
    if m:
        return (int(m.group(1)), int(m.group(2)))

    raise ValueError(f"Unsupported time representation: '{val}'")


def normalize_local_to_utc(
    dt_naive: datetime,
    timezone_str: str,
    *,
    fold: int = 0,
    allow_gap: bool = False,
) -> tuple[datetime, dict[str, Any]]:
    """Converts a naive local datetime in a specified IANA timezone to timezone-aware UTC.

    Performs strict validation for:
    1. DST Spring-Forward Gap: Nonexistent local clock time.
    2. DST Fall-Back Fold: Ambiguous local clock time.
    """
    tz = ZoneInfo(timezone_str)
    dt_local = dt_naive.replace(tzinfo=tz, fold=fold)

    # Check for DST gap (spring-forward nonexistent time)
    dt_utc = dt_local.astimezone(timezone.utc)
    dt_roundtrip = dt_utc.astimezone(tz)

    is_gap = (dt_roundtrip.hour, dt_roundtrip.minute) != (dt_naive.hour, dt_naive.minute)
    if is_gap and not allow_gap:
        raise DSTGapError(
            f"Local time {dt_naive} does not exist in timezone '{timezone_str}' due to DST spring-forward gap."
        )

    # Check for DST fold (fall-back ambiguous time)
    dt_fold0 = dt_naive.replace(tzinfo=tz, fold=0).astimezone(timezone.utc)
    dt_fold1 = dt_naive.replace(tzinfo=tz, fold=1).astimezone(timezone.utc)
    is_ambiguous = dt_fold0 != dt_fold1

    flags = {
        "is_dst_gap": is_gap,
        "is_dst_ambiguous": is_ambiguous,
        "resolved_fold": fold,
        "timezone_str": timezone_str,
    }
    return dt_utc, flags


def calculate_normalized_timeline_min(
    dt_utc: datetime,
    reference_epoch_utc: datetime,
) -> int:
    """Calculates integer elapsed minutes from an explicit reference UTC epoch."""
    if dt_utc.tzinfo is None or reference_epoch_utc.tzinfo is None:
        raise ValueError("Both dt_utc and reference_epoch_utc must be timezone-aware")
    delta_sec = (dt_utc - reference_epoch_utc).total_seconds()
    return int(round(delta_sec / 60.0))


def reconcile_overnight_flight(
    dep_local_dt: datetime,
    origin_tz_str: str,
    dest_tz_str: str,
    scheduled_elapsed_min: float | None,
    arr_time_val: Any | None = None,
) -> dict[str, Any]:
    """Reconciles scheduled arrival time and detects day rollover for overnight flights.

    If scheduled_elapsed_min is available, arrival UTC is computed causally:
        arr_utc = dep_utc + elapsed_time
    Then mapped to destination local timezone.
    If arr_time_val (wall clock) is provided, checks consistency with elapsed duration.
    """
    dep_utc, dep_flags = normalize_local_to_utc(dep_local_dt, origin_tz_str)
    dest_tz = ZoneInfo(dest_tz_str)

    res: dict[str, Any] = {
        "dep_local": dep_local_dt.replace(tzinfo=ZoneInfo(origin_tz_str)),
        "dep_utc": dep_utc,
        "origin_timezone": origin_tz_str,
        "dest_timezone": dest_tz_str,
        "is_overnight": False,
        "review_required": False,
        "reconciliation_notes": [],
    }

    if scheduled_elapsed_min is not None and scheduled_elapsed_min > 0:
        arr_utc = dep_utc + timedelta(minutes=float(scheduled_elapsed_min))
        arr_local = arr_utc.astimezone(dest_tz)
        res["arr_utc"] = arr_utc
        res["arr_local"] = arr_local
        res["is_overnight"] = arr_local.date() > dep_local_dt.date()

        # Cross-check with raw arrival clock if provided
        if arr_time_val is not None:
            try:
                arr_h, arr_m = parse_hhmm_time(arr_time_val)
                raw_clock_minutes = arr_h * 60 + arr_m
                computed_clock_minutes = arr_local.hour * 60 + arr_local.minute
                diff_min = abs(raw_clock_minutes - computed_clock_minutes)
                # Allow small differences (e.g., taxi buffer / block-time adjustments <= 30m)
                if diff_min > 30 and (1440 - diff_min) > 30:
                    res["review_required"] = True
                    res["reconciliation_notes"].append(
                        f"Discrepancy of {diff_min}m between CRS_ELAPSED_TIME and raw CRS_ARR_TIME clock."
                    )
            except Exception as e:
                res["review_required"] = True
                res["reconciliation_notes"].append(f"Failed parsing raw CRS_ARR_TIME: {e}")
    else:
        # Without elapsed duration, arrival date is unverified
        res["review_required"] = True
        res["reconciliation_notes"].append(
            "Missing CRS_ELAPSED_TIME; arrival timestamp cannot be independently proved."
        )

    return res


def validate_temporal_causality(
    *,
    prediction_generated_at_utc: datetime | None,
    planning_snapshot_at_utc: datetime | None,
    model_prediction_cutoff_utc: datetime | None,
    scheduled_event_utc: datetime | None,
) -> tuple[bool, list[str]]:
    """Validates operational temporal causality.

    Invariants:
    1. A prediction generated AFTER the planning snapshot cannot be used as prior knowledge.
       (prediction_generated_at <= planning_snapshot_at)
    2. Prediction cutoff must precede or equal the scheduled operational event.
       (model_prediction_cutoff <= scheduled_event)
    """
    violations: list[str] = []

    if prediction_generated_at_utc is not None and planning_snapshot_at_utc is not None:
        if prediction_generated_at_utc > planning_snapshot_at_utc:
            violations.append(
                f"PREDICTION_POSTDATES_PLANNING_SNAPSHOT: prediction generated at {prediction_generated_at_utc.isoformat()} "
                f"after planning snapshot at {planning_snapshot_at_utc.isoformat()}."
            )

    if model_prediction_cutoff_utc is not None and scheduled_event_utc is not None:
        if model_prediction_cutoff_utc > scheduled_event_utc:
            violations.append(
                f"CUTOFF_POSTDATES_SCHEDULED_EVENT: cutoff {model_prediction_cutoff_utc.isoformat()} "
                f"is after scheduled event {scheduled_event_utc.isoformat()}."
            )

    is_valid = len(violations) == 0
    return is_valid, violations
