"""Temporal roles and bounded IO for V3; final labels are closed until freeze."""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
import hashlib

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds

from src.data.access_guard import assert_data_access_allowed
from src.features.binary_improvement import prepare_frame, source_columns
from src.models.binary_improvement_execution import digest


@dataclass(frozen=True)
class Roles:
    branch: str
    quarter: str
    train_end: pd.Timestamp
    calibration: tuple
    selection: tuple
    threshold: tuple
    score: tuple

    def ranges(self):
        return {"calibration": self.calibration, "selection": self.selection,
                "threshold": self.threshold, "score": self.score}


def roles_for(branch: str, quarter: str) -> Roles:
    if branch not in ("A", "B"):
        raise ValueError("Unknown branch")
    target = pd.Period(quarter, freq="Q")
    start = target.start_time.normalize()
    count = 3 if branch == "A" else 1
    earliest = start - pd.DateOffset(months=count * 3)
    bounds = [earliest + pd.DateOffset(months=count * i) for i in range(4)]
    parts = [(bounds[i], bounds[i + 1] - pd.Timedelta(days=1)) for i in range(3)]
    return Roles(branch, quarter, earliest - pd.Timedelta(days=1),
                 *parts, (start, target.end_time.normalize()))


def cache_key(payload):
    import json
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:24]


class BoundedData:
    def __init__(self, root: Path, v2_run: Path, *, smoke=False, cache_root: Path | None = None):
        self.root, self.v2_run, self.smoke = root, v2_run, smoke
        self.audit = {}
        self.q4_unlocked = False
        self.confirmation_unlocked = False
        self.cache = OrderedDict()
        self.cache_root = cache_root
        self.hashes = {}

    def unlock_q4(self, freeze_path: Path):
        import json
        freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
        if freeze.get("status") != "FROZEN_BEFORE_Q4" or not freeze.get("models"):
            raise PermissionError("A concrete pre-Q4 model/threshold freeze is required")
        for record in freeze["models"].values():
            path = (freeze_path.parent / record.get("path", "")).resolve()
            if (not path.is_relative_to(freeze_path.parent.resolve()) or not path.is_file()
                or digest(path) != record.get("sha256")):
                raise PermissionError("Frozen model checksum/path is invalid")
        self.q4_unlocked = True

    def read(self, task, start, end, *, purpose="development"):
        start, end = pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize()
        if start > end or start.year < 2016 or end.year >= 2024:
            raise PermissionError("V3 blocks 2024 before any filesystem/cache access")
        if end >= pd.Timestamp("2023-01-01"):
            if purpose != "confirmation" or not self.confirmation_unlocked:
                raise PermissionError("2023 requires a frozen Q4 decision")
        elif end >= pd.Timestamp("2022-10-01"):
            if purpose != "final" or not self.q4_unlocked:
                raise PermissionError("Q4/2022 labels are closed until model freeze")
        key = (task, str(start), str(end), purpose)
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key].copy(deep=False)
        cache_path = self.cache_root / (cache_key(key) + ".parquet") if self.cache_root else None
        if cache_path and cache_path.exists():
            result = pd.read_parquet(cache_path)
            self.cache[key] = result
            while len(self.cache) > 2:
                self.cache.popitem(last=False)
            return result.copy(deep=False)
        frames = []
        for year in range(start.year, end.year + 1):
            assert_data_access_allowed(year, "development", config_version="binary_improvement_v3")
            parent = self.v2_run / "cache" / task / f"{year}.parquet"
            lower, upper = max(start, pd.Timestamp(year, 1, 1)), min(end, pd.Timestamp(year, 12, 31))
            if parent.exists():
                data = ds.dataset(parent, format="parquet")
                frame = data.to_table(filter=(ds.field("__date") >= lower.to_pydatetime()) & (ds.field("__date") <= upper.to_pydatetime())).to_pandas()
                if parent not in self.hashes:
                    self.hashes[parent] = digest(parent)
                source = {"path": str(parent.relative_to(self.root)), "sha256": self.hashes[parent]}
            else:
                flow = "inbound_atl" if task == "arrival" else "outbound_atl"
                folder = self.root / "data/processed" / flow / f"year={year}"
                files = sorted(folder.glob("*.parquet"))
                if not files:
                    raise FileNotFoundError(folder)
                data = ds.dataset(files, format="parquet")
                field = data.schema.field("FL_DATE").type
                lo, hi = (lower.to_pydatetime(), upper.to_pydatetime()) if pa.types.is_timestamp(field) else (str(lower), str(upper))
                raw = data.to_table(columns=source_columns(task), filter=(ds.field("FL_DATE") >= lo) & (ds.field("FL_DATE") <= hi)).to_pandas()
                frame = prepare_frame(raw, task)
                source = {"files": [{"path": str(f.relative_to(self.root)), "sha256": digest(f)} for f in files]}
            if frame["__date"].lt(lower).any() or frame["__date"].gt(upper).any():
                raise ValueError("Row outside the requested temporal projection")
            self.audit[f"{task}_{year}"] = source
            frames.append(frame)
        result = pd.concat(frames, ignore_index=True).sort_values(["__date", "__key"]).reset_index(drop=True)
        if result["__key"].isna().any() or result["__key"].duplicated().any():
            raise ValueError("Missing/duplicate flight keys")
        if self.smoke and len(result) > 5000:
            groups = result["__date"].dt.to_period("M")
            result = result.groupby(groups, group_keys=False).sample(frac=min(1, 5000 / len(result)), random_state=202601).reset_index(drop=True)
        if cache_path:
            cache_path.parent.mkdir(exist_ok=True, parents=True)
            result.to_parquet(cache_path, index=False)
        self.cache[key] = result
        while len(self.cache) > 2:
            self.cache.popitem(last=False)
        return result.copy(deep=False)


def train_window(end, years):
    return max(pd.Timestamp("2016-01-01"), pd.Timestamp(end) - pd.DateOffset(years=int(years)) + pd.Timedelta(days=1)) if years else pd.Timestamp("2016-01-01")


def warmup_indices(frame, *, days=90, cap=None, seed=202601):
    eligible = frame.index[frame["__date"] >= frame["__date"].min() + pd.Timedelta(days=days)].to_numpy()
    if cap and len(eligible) > cap:
        # Deterministic exact-size proportional month sampling, no class rebalancing.
        rng = np.random.default_rng(seed)
        groups = frame.loc[eligible, "__date"].dt.to_period("M")
        pieces = []
        for _, indices in groups.groupby(groups).groups.items():
            quota = int(np.floor(len(indices) * cap / len(eligible)))
            pieces.extend(rng.choice(np.asarray(indices), quota, replace=False))
        remaining = np.setdiff1d(eligible, pieces)
        pieces.extend(rng.choice(remaining, cap - len(pieces), replace=False))
        eligible = np.sort(np.asarray(pieces, dtype=int))
    return eligible
