"""Label-free features for strictly validated upload schedules."""
import pandas as pd

from src.features.tabular_features import (APPROVED_PREDICTOR_COLUMNS_V1_1,
    _categorical, _flight_number, _numeric_without_silent_coercion,
    _validate_calendar_source, ArrivalFeatureContractViolation)
from src.features.departure_features import _build_feature_matrix
from web_dashboard.schedule_validation import validate_schedule


def prepare_schedule_inference(raw, task):
    if task not in ("arrival", "departure"):
        raise ValueError("Unknown inference task")
    frame = raw.copy().reset_index(drop=True)
    if frame.flight_key.isna().any() or frame.flight_key.duplicated().any():
        raise ValueError("Inference requires unique nonmissing flight keys")
    population = "DEST" if task == "arrival" else "ORIGIN"
    if not frame[population].eq("ATL").all():
        raise ValueError("Inference population differs from task")
    dates = pd.to_datetime(frame.FL_DATE, errors="raise").dt.normalize()
    departures, arrivals = [], []
    for row, day in zip(frame.to_dict("records"), dates):
        dep, arr = validate_schedule(day.date(), row["CRS_DEP_TIME"], row["CRS_ARR_TIME"],
            row["CRS_ELAPSED_TIME"], row["ORIGIN"], row["DEST"])
        departures.append(dep.local_datetime.replace(tzinfo=None))
        arrivals.append(arr.replace(tzinfo=None))
    departure = pd.Series(pd.to_datetime(departures), index=frame.index)
    arrival = pd.Series(pd.to_datetime(arrivals), index=frame.index)
    for name, values in (("MONTH", dates.dt.month), ("DAY_OF_MONTH", dates.dt.day), ("DAY_OF_WEEK", dates.dt.dayofweek+1)):
        if name not in frame:
            frame[name] = values
        _validate_calendar_source(frame, name, values)
    if task == "departure":
        result = _build_feature_matrix(frame, dates, departure)
    else:
        result = pd.DataFrame(index=frame.index)
        result["CRS_ELAPSED_TIME"] = _numeric_without_silent_coercion(frame.CRS_ELAPSED_TIME,
            field="CRS_ELAPSED_TIME", error_type=ArrivalFeatureContractViolation)
        for name, values in (("calendar_year", dates.dt.year), ("calendar_month", dates.dt.month),
                             ("calendar_day_of_month", dates.dt.day), ("calendar_day_of_week", dates.dt.dayofweek+1)):
            result[name] = values.astype("int64")
        result["is_weekend"] = result.calendar_day_of_week.isin([6, 7]).astype("int8")
        result["scheduled_departure_hour"] = departure.dt.hour.astype("int64")
        result["scheduled_departure_minute"] = departure.dt.minute.astype("int64")
        result["OP_CARRIER"] = _categorical(frame.OP_CARRIER, field="OP_CARRIER")
        result["ORIGIN"] = _categorical(frame.ORIGIN, field="ORIGIN")
        result["OP_CARRIER_FL_NUM"] = _flight_number(frame.OP_CARRIER_FL_NUM)
    result["scheduled_arrival_hour"] = arrival.dt.hour.astype("int16")
    result["scheduled_arrival_minute"] = arrival.dt.minute.astype("int16")
    if task == "arrival":
        result = result.loc[:, list(APPROVED_PREDICTOR_COLUMNS_V1_1)]
    result["__date"] = dates
    result["__year"] = dates.dt.year
    result["__key"] = frame.flight_key.astype(str)
    return result
