"""Strict upload schedule validation, independent of frozen research parsers."""
from datetime import datetime, time, timedelta
from numbers import Real
import re

import pandas as pd

from src.data.canonical_time import parse_canonical_scheduled_time
from src.data.time_normalization import normalize_local_to_utc
from web_dashboard.timezones import airport_zone, departure_timestamp


def _timestamp(value):
    if isinstance(value, time) and (value.second or value.microsecond):
        raise ValueError("Timestamp lịch bay phải chính xác đến phút.")
    if isinstance(value, datetime):
        parsed = pd.Timestamp(value)
    elif isinstance(value, str) and re.match(r"^\d{4}-\d{2}-\d{2}", value.strip()):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})?", value.strip()):
            raise ValueError("Timestamp lịch bay không hợp lệ.")
        parsed = pd.Timestamp(value.strip())
    else:
        if isinstance(value, Real) and (not pd.notna(value) or value != int(value)):
            raise ValueError("Giờ HHMM phải là số nguyên hợp lệ, không tự làm tròn.")
        if isinstance(value, str) and not re.fullmatch(r"(?:\d{1,4}|\d{1,2}:\d{2})", value.strip()):
            raise ValueError("Định dạng giờ lịch bay không hợp lệ.")
        parse_canonical_scheduled_time(value)
        return None
    if pd.isna(parsed) or parsed.second or parsed.microsecond or parsed.nanosecond:
        raise ValueError("Timestamp lịch bay phải chính xác đến phút.")
    return parsed


def validate_schedule(flight_date, departure, arrival, elapsed, origin, destination):
    if not 0 < float(elapsed) <= 1440:
        raise ValueError("CRS_ELAPSED_TIME phải nằm trong (0, 1440] phút.")
    dep_source, arr_source = _timestamp(departure), _timestamp(arrival)
    # A full timestamp may explicitly describe FL_DATE+1 midnight (2400).
    dep_clock = departure
    if dep_source is not None and dep_source.date() == flight_date + timedelta(days=1) and dep_source.hour == dep_source.minute == 0:
        dep_clock = 2400
    dep = departure_timestamp(flight_date, dep_clock, origin)
    _, flags = normalize_local_to_utc(dep.local_datetime.replace(tzinfo=None), airport_zone(origin).key)
    if flags["is_dst_ambiguous"]:
        raise ValueError("Giờ khởi hành mơ hồ do đổi DST; cần làm rõ nguồn thời gian trước khi nạp.")
    arr_utc = dep.utc_datetime + timedelta(minutes=float(elapsed))
    arr = arr_utc.astimezone(airport_zone(destination))
    for source, expected, name in ((dep_source, dep.local_datetime, "CRS_DEP_TIME"), (arr_source, arr, "CRS_ARR_TIME")):
        if source is not None:
            if source.replace(tzinfo=None) != expected.replace(tzinfo=None):
                raise ValueError(f"Ngày/giờ trong {name} mâu thuẫn với lịch bay.")
            if source.tzinfo is not None and source.utcoffset() != expected.utcoffset():
                raise ValueError(f"UTC offset trong {name} mâu thuẫn với múi giờ sân bay.")
    h, m, _ = parse_canonical_scheduled_time(arrival)
    if (arr.hour, arr.minute) != (h, m):
        raise ValueError("Giờ đến không khớp giờ đi + thời lượng + múi giờ; không tự đoán ngày đến.")
    return dep, arr
