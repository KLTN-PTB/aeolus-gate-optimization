"""Versioned OOF Parquet and JSON writers for Week-4 experiments."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from src.models.contracts import OOF_SCHEMA_VERSION, Week4ContractViolation


OOF_COLUMNS = (
    "flight_key",
    "fold_id",
    "validation_year",
    "y_arr_cls",
    "p_arr_delay_15",
    "y_arr_cls_pred_0_5",
    "y_arr_reg",
    "predicted_arr_delay_min",
    "method_id",
    "model_version",
    "preprocessing_version",
    "feature_manifest_version",
    "config_version",
    "seed",
    "experiment_contract_version",
    "oof_schema_version",
)


def validate_oof_frame(frame: pd.DataFrame) -> None:
    """Validate the exact row-level OOF schema before any artifact is written."""

    if tuple(frame.columns) != OOF_COLUMNS:
        raise Week4ContractViolation("OOF columns do not match the versioned schema")
    if frame.empty:
        raise Week4ContractViolation("OOF batch must contain at least one row")
    if frame["flight_key"].isna().any() or not frame["flight_key"].astype(str).str.len().gt(0).all():
        raise Week4ContractViolation("OOF flight_key must be present")
    for column in ("y_arr_cls", "y_arr_cls_pred_0_5"):
        if not set(frame[column].astype(int)).issubset({0, 1}):
            raise Week4ContractViolation(f"OOF {column} must be binary")
    for column in ("p_arr_delay_15", "y_arr_reg", "predicted_arr_delay_min"):
        values = np.asarray(frame[column], dtype=float)
        if not np.isfinite(values).all():
            raise Week4ContractViolation(f"OOF {column} must be finite")
    probabilities = np.asarray(frame["p_arr_delay_15"], dtype=float)
    if bool(((probabilities < 0.0) | (probabilities > 1.0)).any()):
        raise Week4ContractViolation("OOF probabilities must lie in [0, 1]")
    if not (frame["oof_schema_version"] == OOF_SCHEMA_VERSION).all():
        raise Week4ContractViolation("OOF schema version mismatch")


class ParquetOOFSink:
    """Append fold-sized OOF batches without concatenating all validation rows."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._temporary_path = self.path.with_suffix(self.path.suffix + ".tmp")
        self._writer: pq.ParquetWriter | None = None
        self.rows_written = 0

    def __enter__(self) -> "ParquetOOFSink":
        if self.path.suffix != ".parquet":
            raise Week4ContractViolation("OOF artifact path must end in .parquet")
        if self.path.exists() or self._temporary_path.exists():
            raise FileExistsError(f"refusing to overwrite versioned OOF artifact: {self.path}")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        return self

    def append(self, frame: pd.DataFrame) -> None:
        validate_oof_frame(frame)
        table = pa.Table.from_pandas(frame, preserve_index=False)
        if self._writer is None:
            self._writer = pq.ParquetWriter(self._temporary_path, table.schema)
        self._writer.write_table(table)
        self.rows_written += len(frame)

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self._writer is not None:
            self._writer.close()
        if exc_type is None:
            if self.rows_written == 0:
                raise Week4ContractViolation("cannot publish an empty OOF artifact")
            self._temporary_path.replace(self.path)
        elif self._temporary_path.exists():
            self._temporary_path.unlink()


def write_json_artifact(path: Path, payload: dict[str, Any]) -> None:
    """Write a new versioned JSON artifact and refuse an accidental overwrite."""

    target = Path(path)
    temporary = target.with_suffix(target.suffix + ".tmp")
    if target.exists() or temporary.exists():
        raise FileExistsError(f"refusing to overwrite versioned JSON artifact: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(target)
