"""Untrusted BTS/project Parquet -> audited schedule-only ATL records.

Actual outcomes are retained ONLY in optional evaluation columns, never features,
pairing, date selection, or eligibility. No silent row loss or timestamp guessing.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
from numbers import Real
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from web_dashboard.schedule_validation import validate_schedule

REQUIRED = ("FL_DATE", "OP_CARRIER", "OP_CARRIER_FL_NUM", "ORIGIN", "DEST",
            "CRS_DEP_TIME", "CRS_ARR_TIME", "CRS_ELAPSED_TIME")
ALIASES = {
    "FlightDate": "FL_DATE", "Operating_Airline": "OP_CARRIER",
    "Reporting_Airline": "OP_CARRIER", "Flight_Number_Operating_Airline": "OP_CARRIER_FL_NUM",
    "Flight_Number_Reporting_Airline": "OP_CARRIER_FL_NUM", "Origin": "ORIGIN", "Dest": "DEST",
    "CRSDepTime": "CRS_DEP_TIME", "CRSArrTime": "CRS_ARR_TIME", "CRSElapsedTime": "CRS_ELAPSED_TIME",
    "Tail_Number": "TAIL_NUM", "ArrDelay": "ARR_DELAY", "DepDelay": "DEP_DELAY",
}
OUTCOMES = ("ARR_DELAY", "DEP_DELAY")
NORMALIZATION_VERSION = "bts_upload_schedule_v2"


class InputError(ValueError):
    pass


def _rename(frame: pd.DataFrame) -> pd.DataFrame:
    # Operating carrier has priority over reporting carrier, but never over an
    # explicit canonical field. This avoids creating duplicate Pandas columns.
    renames: dict[str, str] = {}
    claimed = set(frame.columns)
    for old, new in ALIASES.items():
        if old in frame.columns and new not in claimed:
            renames[old] = new
            claimed.add(new)
    return frame.rename(columns=renames)


def normalize_files(paths: list[Path], *, offline_evaluation: bool = False) -> tuple[pd.DataFrame, dict]:
    # Research-only entry point. Upload callers retain the sealed-year rejection.
    if offline_evaluation:
        from src.data.access_guard import assert_data_access_allowed
        assert_data_access_allowed(2024, 'final_evaluation')
    records, errors, sources = [], [], []
    total_rows = ignored_rows = 0
    seen: set[str] = set()
    for source_index, path in enumerate(paths):
        try:
            # Explicit ownership closes the Windows handle even if Arrow fails
            # while constructing the reader for a corrupt file.
            with path.open("rb") as stream:
                parquet = pq.ParquetFile(stream)
                if parquet.metadata.num_rows > 5_000_000:
                    raise InputError("File vượt 5 triệu dòng; hãy tách thành file nhỏ hơn.")
                if sum(parquet.metadata.row_group(i).total_byte_size
                       for i in range(parquet.metadata.num_row_groups)) > 2 * 1024 ** 3:
                    raise InputError("Dữ liệu giải nén vượt 2 GB; hãy tách file.")
                columns = parquet.schema_arrow.names
                if len(set(columns)) != len(columns):
                    raise InputError("Tên cột bị trùng.")
                if {"predicted_arrival_min", "predicted_delay_min", "gate_occupancy_start_min"} & set(columns):
                    raise InputError("Đây là dữ liệu dự báo/kịch bản đã xử lý, không phải raw lịch bay.")
                needed = set(REQUIRED) | set(ALIASES) | {"TAIL_NUM", *OUTCOMES, "MONTH", "DAY_OF_MONTH", "DAY_OF_WEEK"}
                frame = _rename(parquet.read(columns=[c for c in columns if c in needed]).to_pandas())
        except InputError:
            raise
        except Exception as exc:
            raise InputError(f"Không đọc được Parquet hợp lệ: {exc}") from exc
        missing = set(REQUIRED) - set(frame.columns)
        if missing:
            raise InputError(f"Thiếu cột bắt buộc: {', '.join(sorted(missing))}.")
        total_rows += len(frame)
        for col in ("ORIGIN", "DEST", "OP_CARRIER"):
            frame[col] = frame[col].astype("string").str.strip().str.upper()
        relevant = (frame.ORIGIN.eq("ATL") | frame.DEST.eq("ATL")).fillna(False)
        ignored_rows += int((~relevant).sum())
        sources.append({"source_index": source_index, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "rows": len(frame), "columns": columns})
        for index, row in frame.loc[relevant].iterrows():
            try:
                # Keep HHMM semantics: integers are NOT Unix timestamp nanoseconds.
                raw_date = str(row.FL_DATE).strip()
                if len(raw_date) == 8 and raw_date.isdigit():
                    raw_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
                flight_date = pd.Timestamp(raw_date).date()
                if pd.isna(flight_date):
                    raise InputError("Ngày bay không hợp lệ.")
                if flight_date.year == 2024 and not offline_evaluation:
                    raise InputError("Dữ liệu năm 2024 đang được cách ly; không được nạp cho demo.")
                for name, expected in (("MONTH", flight_date.month), ("DAY_OF_MONTH", flight_date.day),
                                       ("DAY_OF_WEEK", flight_date.isoweekday())):
                    if name in row and pd.notna(row[name]) and float(row[name]) != expected:
                        raise InputError(f"{name} mâu thuẫn với lịch suy ra từ FL_DATE.")
                origin, destination, carrier = str(row.ORIGIN), str(row.DEST), str(row.OP_CARRIER)
                if origin == destination or not all(len(a) == 3 and a.isalpha() for a in (origin, destination)):
                    raise InputError("Mã sân bay không hợp lệ hoặc chặng bay trùng điểm đầu/cuối.")
                if carrier in ("", "<NA>", "NAN", "NONE"):
                    raise InputError("Thiếu hãng khai thác.")
                number = float(row.OP_CARRIER_FL_NUM)
                elapsed = float(row.CRS_ELAPSED_TIME)
                if not np.isfinite(number) or number <= 0 or not number.is_integer():
                    raise InputError("Số hiệu chuyến bay phải là số nguyên dương.")
                if not np.isfinite(elapsed) or not 0 < elapsed <= 1440:
                    raise InputError("CRS_ELAPSED_TIME phải nằm trong (0, 1440] phút.")
                for value in (row.CRS_DEP_TIME, row.CRS_ARR_TIME):
                    if isinstance(value, Real) and (not np.isfinite(value) or value != int(value)):
                        raise InputError("Giờ HHMM phải là số nguyên hợp lệ, không tự làm tròn.")
                dep, arr_local = validate_schedule(flight_date, row.CRS_DEP_TIME, row.CRS_ARR_TIME,
                                                 elapsed, origin, destination)
                direction = "ARR" if destination == "ATL" else "DEP"
                event = arr_local if direction == "ARR" else dep.local_datetime
                identity = f"{flight_date}|{carrier}|{int(number)}|{origin}|{destination}|{dep.utc_datetime.isoformat()}"
                key = hashlib.sha256(identity.encode()).hexdigest()[:24]
                if key in seen:
                    raise InputError("Chuyến bị trùng định danh lịch bay giữa các dòng/file.")
                seen.add(key)
                tail = row.get("TAIL_NUM")
                tail = str(tail).strip().upper() if pd.notna(tail) else None
                if tail in ("", "<NA>", "NAN", "NONE", "NULL", "N/A", "UNK", "UNKNOWN"):
                    tail = None
                record = {
                    "flight_key": key, "FL_DATE": flight_date.isoformat(), "OP_CARRIER": carrier,
                    "OP_CARRIER_FL_NUM": int(number), "ORIGIN": origin, "DEST": destination,
                    "CRS_DEP_TIME": dep.local_datetime.replace(tzinfo=None).isoformat(sep=" "),
                    "CRS_ARR_TIME": arr_local.replace(tzinfo=None).isoformat(sep=" "),
                    "CRS_ELAPSED_TIME": elapsed, "MONTH": flight_date.month,
                    "DAY_OF_MONTH": flight_date.day, "DAY_OF_WEEK": flight_date.isoweekday(),
                    "TAIL_NUM": tail, "direction": direction,
                    "service_date": event.date().isoformat(), "scheduled_event_local": event.isoformat(),
                    "scheduled_event_utc": event.astimezone(timezone.utc).isoformat(),
                    "prediction_cutoff_utc": (dep.utc_datetime - timedelta(hours=2)).isoformat(),
                    "source_index": source_index, "source_row": int(index) + 1,
                }
                for outcome in OUTCOMES:
                    value = pd.to_numeric(row.get(outcome), errors="coerce")
                    record[outcome] = float(value) if pd.notna(value) and np.isfinite(value) else None
                records.append(record)
            except Exception as exc:
                errors.append({"source_index": source_index, "row": int(index) + 1, "message": str(exc)})
    result = pd.DataFrame(records)
    dates = []
    if not result.empty:
        for day, group in result.groupby("service_date", sort=True):
            dates.append({"date": day, "arrivals": int(group.direction.eq("ARR").sum()),
                          "departures": int(group.direction.eq("DEP").sum()), "total": len(group)})
    report = {
        "normalization_version": NORMALIZATION_VERSION, "input_rows": total_rows,
        "non_atl_rows": ignored_rows, "valid_rows": len(records), "invalid_rows": len(errors),
        "errors": errors[:100], "dates": dates, "sources": sources,
        "can_run": bool(records) and not errors,
        "preview": result.drop(columns=list(OUTCOMES), errors="ignore").head(8).to_dict("records"),
        "warnings": ["Chỉ lịch bay liên quan ATL được giữ; dữ liệu thực tế không đi vào mô hình.",
                     "Số đuôi trong raw là bằng chứng lịch sử/giả định kế hoạch, không chứng minh đã biết tại thời điểm dự báo."],
    }
    if offline_evaluation:
        report['evaluation_regime'] = 'POST_HOLDOUT_REEVALUATION_NOT_NEW_INDEPENDENT_TEST'
        return result, report
    return result, dataset_eligibility(report)


def dataset_eligibility(report: dict) -> dict:
    """Upgrade saved reports as well as new uploads without a DB migration."""
    report = {**report, "dates": [dict(day) for day in report.get("dates", [])]}
    for day in report["dates"]:
        day["eligible"] = datetime.fromisoformat(day["date"]).year != 2024
        day["blocked_reason"] = None if day["eligible"] else "Ngày vận hành năm 2024 được cách ly theo chính sách holdout."
    report["can_run"] = bool(report.get("valid_rows")) and not report.get("invalid_rows", 0) and any(d["eligible"] for d in report["dates"])
    return report


def validate_run_dates(frame: pd.DataFrame, service_date: str) -> None:
    """Defense at the worker boundary, including datasets saved before v2."""
    if datetime.fromisoformat(service_date).year == 2024:
        raise InputError("Ngày vận hành năm 2024 được cách ly.")
    selected = frame.loc[frame.service_date.eq(service_date)]
    if selected.empty:
        raise InputError("Ngày đã chọn không có lượt bay ATL.")
    if pd.to_datetime(selected.FL_DATE).dt.year.eq(2024).any():
        raise InputError("Dữ liệu nguồn năm 2024 được cách ly.")
