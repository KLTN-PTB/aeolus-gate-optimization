"""Explicitly illustrative schedules, never an automatic real-data fallback."""
import pandas as pd


def sample_schedule() -> pd.DataFrame:
    rows = []
    for i, hour in enumerate((6, 8, 10, 12, 14, 16, 18)):
        rows.extend([
            {"FL_DATE": "2026-07-01", "OP_CARRIER": "DL", "OP_CARRIER_FL_NUM": 100 + i * 2,
             "ORIGIN": "MCO", "DEST": "ATL", "CRS_DEP_TIME": hour * 100,
             "CRS_ARR_TIME": (hour + 1) * 100 + 30, "CRS_ELAPSED_TIME": 90, "TAIL_NUM": f"DEMO{i:03d}"},
            {"FL_DATE": "2026-07-01", "OP_CARRIER": "DL", "OP_CARRIER_FL_NUM": 101 + i * 2,
             "ORIGIN": "ATL", "DEST": "JFK", "CRS_DEP_TIME": (hour + 3) * 100,
             "CRS_ARR_TIME": (hour + 5) * 100, "CRS_ELAPSED_TIME": 120, "TAIL_NUM": f"DEMO{i:03d}"},
        ])
    return pd.DataFrame(rows)
