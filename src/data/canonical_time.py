"""Canonical Time Parsing, Datetime Normalization, and Timezone Utilities.

Protocol: Aeolus Dual Core Architecture Protocol V2
Phase: AEOLUS-G4 Canonical Time Audit & Datetime Construction
Task G4.1: Strictly validated scheduled datetime construction, midnight rollover,
and timezone reconciliation without heuristic string parsing or silent failure.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
import math
import re
from typing import Any, Final
from zoneinfo import ZoneInfo

from src.data.time_normalization import (
    AIRPORT_IANA_TIMEZONES,
    get_airport_timezone,
    normalize_local_to_utc,
    parse_hhmm_time,
)


class CanonicalTimeError(ValueError):
    """Base exception for canonical time audit and parsing violations."""


class InvalidDatetimeError(CanonicalTimeError):
    """Raised when date or time components cannot be parsed into valid timestamps."""


class AmbiguousMidnightError(CanonicalTimeError):
    """Raised when midnight timestamp cannot be proven without ambiguous interpretation."""


class MidnightRolloverError(CanonicalTimeError):
    """Raised when midnight rollover logic encounters inconsistent date offsets."""


@dataclass(frozen=True)
class ScheduledEventTimestamp:
    """Immutable audit record representing a verified scheduled flight event timestamp."""

    local_datetime: datetime
    utc_datetime: datetime
    timezone_name: str
    timeline_minute: int  # Minutes from 00:00 of reference flight date
    is_next_day_rollover: bool
    source_format: str


def parse_canonical_scheduled_time(
    raw_time: Any,
) -> tuple[int, int, bool]:
    """Parse raw scheduled time representation into (hour, minute, is_2400_rollover).

    Supports:
    - ISO datetime strings: '2023-01-01 07:05:00', '2023-01-01T07:05:00'
    - HH:MM strings: '07:05', '7:05', '00:00', '24:00'
    - HHMM numeric/string representations: 705, '0705', 705.0, 2400, '2400'
    - Python datetime or time objects

    Returns:
        Tuple of (hour, minute, is_next_day_rollover).
        Hour is normalized to [0, 23]. If raw input was 2400 or 24:00,
        returns (0, 0, True).
    """
    if raw_time is None:
        raise InvalidDatetimeError("Raw scheduled time value is None")

    if isinstance(raw_time, datetime):
        return (raw_time.hour, raw_time.minute, False)

    if isinstance(raw_time, time):
        return (raw_time.hour, raw_time.minute, False)

    # If numeric (int or float)
    if isinstance(raw_time, (int, float)):
        if isinstance(raw_time, float) and (math.isnan(raw_time) or not math.isfinite(raw_time)):
            raise InvalidDatetimeError(f"Non-finite numeric time value: {raw_time}")
        int_val = int(round(raw_time))
        if int_val < 0 or int_val > 2400:
            raise InvalidDatetimeError(f"Numeric HHMM value out of bounds [0, 2400]: {int_val}")
        hour = int_val // 100
        minute = int_val % 100
        if hour == 24 and minute == 0:
            return (0, 0, True)
        if hour > 23 or minute > 59:
            raise InvalidDatetimeError(f"Invalid hour ({hour}) or minute ({minute}) from {int_val}")
        return (hour, minute, False)

    s = str(raw_time).strip()
    if not s or s.lower() == "nan" or s.lower() == "none":
        raise InvalidDatetimeError("Empty or NaN scheduled time string")

    # Match full ISO timestamp pattern (e.g. '2023-01-01 07:05:00' or '2023-01-01T07:05:00')
    iso_match = re.match(r"^\d{4}-\d{2}-\d{2}[ T](\d{2}):(\d{2})(?::(\d{2}))?", s)
    if iso_match:
        h = int(iso_match.group(1))
        m = int(iso_match.group(2))
        if h == 24 and m == 0:
            return (0, 0, True)
        if h > 23 or m > 59:
            raise InvalidDatetimeError(f"Invalid time components in ISO string '{s}': {h}:{m}")
        return (h, m, False)

    # Match HH:MM
    if ":" in s:
        parts = s.split(":")
        try:
            h = int(parts[0])
            m = int(parts[1])
        except ValueError as e:
            raise InvalidDatetimeError(f"Non-integer components in time string '{s}'") from e
        if h == 24 and m == 0:
            return (0, 0, True)
        if h < 0 or h > 23 or m < 0 or m > 59:
            raise InvalidDatetimeError(f"Time out of range '{s}': hour={h}, minute={m}")
        return (h, m, False)

    # Match clean digit strings like '705' or '0705' or '2400'
    if s.isdigit():
        int_val = int(s)
        return parse_canonical_scheduled_time(int_val)

    raise InvalidDatetimeError(f"Unsupported scheduled time format: '{raw_time}'")


def parse_canonical_flight_date(
    raw_date: Any,
) -> date:
    """Parse raw flight date into Python date.

    Supports:
    - 'YYYY-MM-DD' or 'YYYY-MM-DD 00:00:00'
    - date or datetime instances
    """
    if raw_date is None:
        raise InvalidDatetimeError("Raw flight date value is None")

    if isinstance(raw_date, datetime):
        return raw_date.date()

    if isinstance(raw_date, date):
        return raw_date

    s = str(raw_date).strip()
    if not s or s.lower() == "nan" or s.lower() == "none":
        raise InvalidDatetimeError("Empty or NaN flight date string")

    # Extract first 10 characters (YYYY-MM-DD)
    date_part = s[:10]
    try:
        parsed = date.fromisoformat(date_part)
        return parsed
    except ValueError as e:
        raise InvalidDatetimeError(f"Cannot parse flight date '{raw_date}'") from e


def build_canonical_scheduled_datetime(
    raw_date: Any,
    raw_time: Any,
    airport_code: str,
    *,
    day_offset: int = 0,
) -> ScheduledEventTimestamp:
    """Build a fully validated, timezone-aware scheduled event timestamp.

    Enforces:
    1. Strict date parsing.
    2. Accurate HHMM / ISO time normalization.
    3. 2400 midnight rollover handling (+1 day).
    4. Authenticated IANA airport timezone lookup.
    5. Naive local to timezone-aware UTC conversion.
    6. Monotonic timeline minute calculation relative to service flight date.

    Args:
        raw_date: Flight service date (FL_DATE).
        raw_time: Scheduled clock time (CRS_DEP_TIME or CRS_ARR_TIME).
        airport_code: 3-letter IATA airport code (e.g. 'ATL', 'ORD').
        day_offset: Optional additional day offset for multi-day flights.

    Returns:
        ScheduledEventTimestamp with verified local and UTC timestamps.
    """
    service_date = parse_canonical_flight_date(raw_date)
    hour, minute, is_rollover = parse_canonical_scheduled_time(raw_time)

    total_day_offset = day_offset + (1 if is_rollover else 0)
    event_date = service_date + timedelta(days=total_day_offset)

    tz_str = get_airport_timezone(airport_code)
    tz = ZoneInfo(tz_str)

    dt_naive = datetime(
        event_date.year,
        event_date.month,
        event_date.day,
        hour,
        minute,
        0,
    )

    dt_utc, tz_flags = normalize_local_to_utc(dt_naive, tz_str)
    dt_local = dt_naive.replace(tzinfo=tz)

    # Timeline minute from 00:00 of service_date
    service_midnight_local = datetime(
        service_date.year, service_date.month, service_date.day, 0, 0, 0, tzinfo=tz
    )
    timeline_minute = int(round((dt_local - service_midnight_local).total_seconds() / 60.0))

    return ScheduledEventTimestamp(
        local_datetime=dt_local,
        utc_datetime=dt_utc,
        timezone_name=tz_str,
        timeline_minute=timeline_minute,
        is_next_day_rollover=total_day_offset > 0,
        source_format=f"date={service_date.isoformat()}, time={hour:02d}:{minute:02d}, tz={tz_str}",
    )
