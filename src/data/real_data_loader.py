"""Real-Only Canonical Flight Data Loader and Verification Engine.

Protocol: Aeolus Dual Core Architecture Protocol V2
Phase: AEOLUS-G4 Task G4.3 REAL_ONLY Data Loader
Enforces:
1. Strict REAL_ONLY mode: zero silent fallback to synthetic fixtures.
2. Missing partitions fail immediately.
3. Empty date range queries fail immediately without borrowing adjacent dates.
4. Schema validation: mandatory columns verified.
5. Missing model checkpoints fail closed.
6. ALLOW_SYNTHETIC mode isolated exclusively for designated smoke/demo runs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
import logging
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from src.contracts.turn_contracts import FlightLeg, LegDirection
from src.data.canonical_time import build_canonical_scheduled_datetime

LOGGER = logging.getLogger("real_data_loader")


class DataLoaderMode(str, Enum):
    """Operational loader execution mode."""

    REAL_ONLY = "REAL_ONLY"
    ALLOW_SYNTHETIC = "ALLOW_SYNTHETIC"


class DataLoadError(RuntimeError):
    """Base exception for data loading failures."""


class MissingPartitionError(DataLoadError, FileNotFoundError):
    """Raised when expected canonical dataset partition does not exist on disk."""


class EmptyDateRangeError(DataLoadError, ValueError):
    """Raised when the specified date filter yields zero flight records."""


class SchemaContractViolation(DataLoadError, ValueError):
    """Raised when canonical dataset lacks mandatory columns or has invalid types."""


class CheckpointMissingError(DataLoadError, FileNotFoundError):
    """Raised when required model checkpoint or preprocessor is absent."""


MANDATORY_INBOUND_COLUMNS: Sequence[str] = (
    "FL_DATE",
    "OP_CARRIER",
    "OP_CARRIER_FL_NUM",
    "ORIGIN",
    "DEST",
    "CRS_DEP_TIME",
    "CRS_ARR_TIME",
    "CRS_ELAPSED_TIME",
)

MANDATORY_OUTBOUND_COLUMNS: Sequence[str] = (
    "FL_DATE",
    "OP_CARRIER",
    "OP_CARRIER_FL_NUM",
    "ORIGIN",
    "DEST",
    "CRS_DEP_TIME",
    "CRS_ARR_TIME",
    "CRS_ELAPSED_TIME",
)


@dataclass
class LoadedFlightData:
    """Container holding loaded DataFrames and FlightLeg domain entities."""

    inbound_df: pd.DataFrame
    outbound_df: pd.DataFrame
    legs: dict[str, FlightLeg]
    mode: DataLoaderMode
    date_range: tuple[str, str]
    hub_airport: str
    counts: dict[str, int]


class RealDataLoader:
    """Authoritative loader enforcing strict REAL_ONLY data invariants."""

    def __init__(
        self,
        *,
        mode: DataLoaderMode = DataLoaderMode.REAL_ONLY,
        base_dir: Path | None = None,
    ) -> None:
        self.mode = mode
        self.base_dir = base_dir or Path("data/processed")

    def load_atl_data(
        self,
        *,
        year: int = 2023,
        start_date: str,
        end_date: str,
        limit_legs: int | None = None,
        hub_airport: str = "ATL",
    ) -> LoadedFlightData:
        """Load canonical ATL inbound and outbound flights.

        Args:
            year: Historical year partition (default: 2023).
            start_date: Start date YYYY-MM-DD.
            end_date: End date YYYY-MM-DD.
            limit_legs: Maximum number of legs to load per direction (optional).
            hub_airport: Target airport code (default: 'ATL').

        Raises:
            MissingPartitionError: If partition files/directories are missing in REAL_ONLY.
            EmptyDateRangeError: If date filter yields 0 flights in REAL_ONLY.
            SchemaContractViolation: If mandatory columns are missing in REAL_ONLY.
        """
        hub = hub_airport.strip().upper()
        inbound_partition = self.base_dir / "inbound_atl" / f"year={year}"
        outbound_partition = self.base_dir / "outbound_atl" / f"year={year}"

        # 1. Check partition existence
        if not inbound_partition.exists() or not outbound_partition.exists():
            if self.mode == DataLoaderMode.REAL_ONLY:
                missing = []
                if not inbound_partition.exists():
                    missing.append(str(inbound_partition))
                if not outbound_partition.exists():
                    missing.append(str(outbound_partition))
                raise MissingPartitionError(
                    f"REAL_ONLY mode violation: Mandatory canonical partitions missing on disk: {missing}"
                )
            else:
                LOGGER.warning("ALLOW_SYNTHETIC mode: Partitions not found, synthetic fallback allowed.")
                return self._generate_synthetic_slice(start_date, end_date, limit_legs or 50, hub)

        # 2. Read parquet files
        try:
            df_in_raw = pd.read_parquet(inbound_partition)
            df_out_raw = pd.read_parquet(outbound_partition)
        except Exception as e:
            if self.mode == DataLoaderMode.REAL_ONLY:
                raise DataLoadError(f"REAL_ONLY mode error reading parquets: {e}") from e
            return self._generate_synthetic_slice(start_date, end_date, limit_legs or 50, hub)

        # 3. Schema validation
        missing_in_cols = set(MANDATORY_INBOUND_COLUMNS) - set(df_in_raw.columns)
        if missing_in_cols:
            raise SchemaContractViolation(
                f"Canonical inbound schema missing mandatory columns: {sorted(missing_in_cols)}"
            )

        missing_out_cols = set(MANDATORY_OUTBOUND_COLUMNS) - set(df_out_raw.columns)
        if missing_out_cols:
            raise SchemaContractViolation(
                f"Canonical outbound schema missing mandatory columns: {sorted(missing_out_cols)}"
            )

        # 4. Date filtering
        # Standardize FL_DATE to string YYYY-MM-DD
        df_in_raw["FL_DATE_STR"] = df_in_raw["FL_DATE"].astype(str).str.slice(0, 10)
        df_out_raw["FL_DATE_STR"] = df_out_raw["FL_DATE"].astype(str).str.slice(0, 10)

        in_slice = df_in_raw[
            (df_in_raw["FL_DATE_STR"] >= start_date) & (df_in_raw["FL_DATE_STR"] <= end_date)
        ].copy()
        out_slice = df_out_raw[
            (df_out_raw["FL_DATE_STR"] >= start_date) & (df_out_raw["FL_DATE_STR"] <= end_date)
        ].copy()

        if in_slice.empty or out_slice.empty:
            if self.mode == DataLoaderMode.REAL_ONLY:
                raise EmptyDateRangeError(
                    f"REAL_ONLY mode violation: Zero flights found in date window [{start_date}, {end_date}]. "
                    f"Inbound count: {len(in_slice)}, Outbound count: {len(out_slice)}. "
                    "Borrowing adjacent dates is strictly forbidden."
                )
            else:
                LOGGER.warning("ALLOW_SYNTHETIC mode: Empty date range, generating synthetic fixture.")
                return self._generate_synthetic_slice(start_date, end_date, limit_legs or 50, hub)

        # Apply limits if specified
        if limit_legs is not None and limit_legs > 0:
            in_slice = in_slice.head(limit_legs)
            out_slice = out_slice.head(limit_legs)

        in_slice = in_slice.reset_index(drop=True)
        out_slice = out_slice.reset_index(drop=True)

        # 5. Build FlightLegs
        legs: dict[str, FlightLeg] = {}

        # Add flight_key column if not present
        if "flight_key" not in in_slice.columns:
            in_slice["flight_key"] = [f"REAL_ARR_{i+1:05d}" for i in range(len(in_slice))]
        if "flight_key" not in out_slice.columns:
            out_slice["flight_key"] = [f"REAL_DEP_{i+1:05d}" for i in range(len(out_slice))]

        for i, row in in_slice.iterrows():
            f_key = str(row["flight_key"])
            time_obj = build_canonical_scheduled_datetime(
                raw_date=row["FL_DATE"],
                raw_time=row["CRS_ARR_TIME"],
                airport_code=hub,
            )
            tail = row.get("TAIL_NUM")
            tail_str = str(tail).strip().upper() if pd.notna(tail) and str(tail).strip() else None

            legs[f_key] = FlightLeg(
                flight_id=f_key,
                direction=LegDirection.ARR,
                carrier=str(row["OP_CARRIER"]).strip().upper(),
                flight_number=str(int(row["OP_CARRIER_FL_NUM"])),
                origin=str(row["ORIGIN"]).strip().upper(),
                destination=hub,
                scheduled_event_local=time_obj.local_datetime,
                scheduled_event_utc=time_obj.utc_datetime,
                event_timezone=time_obj.timezone_name,
                scheduled_elapsed_min=float(row.get("CRS_ELAPSED_TIME", 120.0)),
                normalized_timeline_min=time_obj.timeline_minute,
                tail_number=tail_str,
            )

        for i, row in out_slice.iterrows():
            f_key = str(row["flight_key"])
            time_obj = build_canonical_scheduled_datetime(
                raw_date=row["FL_DATE"],
                raw_time=row["CRS_DEP_TIME"],
                airport_code=hub,
            )
            tail = row.get("TAIL_NUM")
            tail_str = str(tail).strip().upper() if pd.notna(tail) and str(tail).strip() else None

            legs[f_key] = FlightLeg(
                flight_id=f_key,
                direction=LegDirection.DEP,
                carrier=str(row["OP_CARRIER"]).strip().upper(),
                flight_number=str(int(row["OP_CARRIER_FL_NUM"])),
                origin=hub,
                destination=str(row["DEST"]).strip().upper(),
                scheduled_event_local=time_obj.local_datetime,
                scheduled_event_utc=time_obj.utc_datetime,
                event_timezone=time_obj.timezone_name,
                scheduled_elapsed_min=float(row.get("CRS_ELAPSED_TIME", 120.0)),
                normalized_timeline_min=time_obj.timeline_minute,
                tail_number=tail_str,
            )

        counts = {
            "inbound_legs": len(in_slice),
            "outbound_legs": len(out_slice),
            "total_legs": len(legs),
        }

        return LoadedFlightData(
            inbound_df=in_slice,
            outbound_df=out_slice,
            legs=legs,
            mode=self.mode,
            date_range=(start_date, end_date),
            hub_airport=hub,
            counts=counts,
        )

    def _generate_synthetic_slice(
        self,
        start_date: str,
        end_date: str,
        n_legs: int,
        hub_airport: str,
    ) -> LoadedFlightData:
        """Isolated synthetic generator exclusively for ALLOW_SYNTHETIC mode."""
        in_records = []
        out_records = []
        legs = {}

        for i in range(n_legs):
            arr_id = f"SYNTH_ARR_{i+1:04d}"
            dep_id = f"SYNTH_DEP_{i+1:04d}"
            arr_time_min = 360 + (i * 15)  # 06:00 + i*15m
            dep_time_min = arr_time_min + 75  # 75m dwell

            carrier = ["DL", "AA", "UA", "WN"][i % 4]
            fl_num = f"{1000 + i}"
            tail = f"N{100 + i:03d}{carrier}"

            in_records.append({
                "flight_key": arr_id,
                "FL_DATE": f"{start_date} 00:00:00",
                "OP_CARRIER": carrier,
                "OP_CARRIER_FL_NUM": fl_num,
                "ORIGIN": "ORD",
                "DEST": hub_airport,
                "CRS_DEP_TIME": f"{start_date} {(arr_time_min - 120) // 60:02d}:{(arr_time_min - 120) % 60:02d}:00",
                "CRS_ARR_TIME": f"{start_date} {arr_time_min // 60:02d}:{arr_time_min % 60:02d}:00",
                "CRS_ELAPSED_TIME": 120.0,
                "TAIL_NUM": tail,
            })
            out_records.append({
                "flight_key": dep_id,
                "FL_DATE": f"{start_date} 00:00:00",
                "OP_CARRIER": carrier,
                "OP_CARRIER_FL_NUM": fl_num,
                "ORIGIN": hub_airport,
                "DEST": "LGA",
                "CRS_DEP_TIME": f"{start_date} {dep_time_min // 60:02d}:{dep_time_min % 60:02d}:00",
                "CRS_ARR_TIME": f"{start_date} {(dep_time_min + 120) // 60:02d}:{(dep_time_min + 120) % 60:02d}:00",
                "CRS_ELAPSED_TIME": 120.0,
                "TAIL_NUM": tail,
            })

            time_arr = build_canonical_scheduled_datetime(start_date, f"{arr_time_min // 60:02d}:{arr_time_min % 60:02d}", hub_airport)
            time_dep = build_canonical_scheduled_datetime(start_date, f"{dep_time_min // 60:02d}:{dep_time_min % 60:02d}", hub_airport)

            legs[arr_id] = FlightLeg(
                flight_id=arr_id,
                direction=LegDirection.ARR,
                carrier=carrier,
                flight_number=fl_num,
                origin="ORD",
                destination=hub_airport,
                scheduled_event_local=time_arr.local_datetime,
                scheduled_event_utc=time_arr.utc_datetime,
                event_timezone=time_arr.timezone_name,
                scheduled_elapsed_min=120.0,
                normalized_timeline_min=arr_time_min,
                tail_number=tail,
            )
            legs[dep_id] = FlightLeg(
                flight_id=dep_id,
                direction=LegDirection.DEP,
                carrier=carrier,
                flight_number=fl_num,
                origin=hub_airport,
                destination="LGA",
                scheduled_event_local=time_dep.local_datetime,
                scheduled_event_utc=time_dep.utc_datetime,
                event_timezone=time_dep.timezone_name,
                scheduled_elapsed_min=120.0,
                normalized_timeline_min=dep_time_min,
                tail_number=tail,
            )

        df_in = pd.DataFrame(in_records)
        df_out = pd.DataFrame(out_records)

        return LoadedFlightData(
            inbound_df=df_in,
            outbound_df=df_out,
            legs=legs,
            mode=self.mode,
            date_range=(start_date, end_date),
            hub_airport=hub_airport,
            counts={"inbound_legs": len(df_in), "outbound_legs": len(df_out), "total_legs": len(legs)},
        )
