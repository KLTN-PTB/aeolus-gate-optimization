import pandas as pd
import pytest


@pytest.fixture
def raw_table():
    return pd.DataFrame([
        {"FL_DATE": "2026-07-01", "OP_CARRIER": "DL", "OP_CARRIER_FL_NUM": 101,
         "ORIGIN": "MCO", "DEST": "ATL", "CRS_DEP_TIME": 800, "CRS_ARR_TIME": 930,
         "CRS_ELAPSED_TIME": 90, "TAIL_NUM": "N101", "ARR_DELAY": 500.0},
        {"FL_DATE": "2026-07-01", "OP_CARRIER": "DL", "OP_CARRIER_FL_NUM": 102,
         "ORIGIN": "ATL", "DEST": "JFK", "CRS_DEP_TIME": 1100, "CRS_ARR_TIME": 1300,
         "CRS_ELAPSED_TIME": 120, "TAIL_NUM": "N101", "DEP_DELAY": -20.0},
        {"FL_DATE": "2026-07-01", "OP_CARRIER": "DL", "OP_CARRIER_FL_NUM": 103,
         "ORIGIN": "MCO", "DEST": "ATL", "CRS_DEP_TIME": 1000, "CRS_ARR_TIME": 1130,
         "CRS_ELAPSED_TIME": 90, "TAIL_NUM": None},
        {"FL_DATE": "2026-07-01", "OP_CARRIER": "DL", "OP_CARRIER_FL_NUM": 104,
         "ORIGIN": "ATL", "DEST": "MCO", "CRS_DEP_TIME": 1400, "CRS_ARR_TIME": 1530,
         "CRS_ELAPSED_TIME": 90, "TAIL_NUM": None},
    ])
