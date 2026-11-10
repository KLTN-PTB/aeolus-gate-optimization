"""Upload-only extension; NEVER mutate the frozen research timezone map.

Mappings checked against the OpenFlights primary airport dataset on 2026-10-18:
https://raw.githubusercontent.com/jpatokal/openflights/master/data/airports.dat
"""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from src.data.canonical_time import ScheduledEventTimestamp, build_canonical_scheduled_datetime, parse_canonical_scheduled_time
from src.data.time_normalization import get_airport_timezone, normalize_local_to_utc

EXTRA_TIMEZONES = {
    "BGR": "America/New_York", "TVC": "America/New_York", "HHH": "America/New_York",
    "RNO": "America/Los_Angeles", "RAP": "America/Denver", "FAR": "America/Chicago",
    # STX checked against the same primary airport dataset on 2026-10-22.
    "STX": "America/St_Thomas",
}


def airport_zone(code: str) -> ZoneInfo:
    return ZoneInfo(EXTRA_TIMEZONES[code] if code in EXTRA_TIMEZONES else get_airport_timezone(code))


def departure_timestamp(flight_date, raw_time, origin):
    if origin not in EXTRA_TIMEZONES:
        return build_canonical_scheduled_datetime(flight_date, raw_time, origin)
    hour, minute, rollover = parse_canonical_scheduled_time(raw_time)
    day = flight_date + timedelta(days=int(rollover))
    naive = datetime.combine(day, time(hour, minute))
    zone = airport_zone(origin)
    utc, _ = normalize_local_to_utc(naive, zone.key)
    return ScheduledEventTimestamp(local_datetime=utc.astimezone(zone), utc_datetime=utc,
        timezone_name=zone.key, timeline_minute=int(rollover) * 1440 + hour * 60 + minute,
        is_next_day_rollover=rollover, source_format="UPLOAD_HHMM_OR_TIMESTAMP")
