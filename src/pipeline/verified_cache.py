"""Versioned, atomic training caches; old/unverifiable runs fail closed."""
import hashlib
import json
import os
from pathlib import Path
import uuid

import joblib
import pandas as pd


class CacheValidationError(ValueError):
    pass


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


class VerifiedCache:
    def __init__(self, root, output, contract):
        self.root, self.output, self.contract = Path(root), Path(output), contract
        self._sources = {}

    def fail(self, path, reason):
        raise CacheValidationError(f"Cache {path}: {reason}. Create a new run; existing artifacts were preserved.")

    def sources(self, task, year):
        folder = self.root / "data/processed" / ("inbound_atl" if task == "arrival" else "outbound_atl") / f"year={year}"
        files = sorted(folder.glob("*.parquet"))
        if not files:
            self.fail(folder, "source partition missing")
        result = []
        for path in files:
            stat = path.stat()
            signature = (stat.st_size, stat.st_mtime_ns)
            saved = self._sources.get(path)
            if saved is None or saved[0] != signature:
                saved = (signature, digest(path))
                self._sources[path] = saved
            result.append({"path": path.relative_to(self.root).as_posix(), "sha256": saved[1]})
        return result

    def context(self, task, year, **extra):
        return {"task": task, "year": year, "contract": self.contract, **extra}

    @staticmethod
    def sidecar(path):
        return path.with_suffix(path.suffix + ".manifest.json")

    def metadata(self, path, context=None):
        try:
            meta = json.loads(self.sidecar(path).read_text(encoding="utf-8"))
            saved_context = meta["context"]
            if (not isinstance(saved_context, dict) or saved_context.get("task") not in ("arrival", "departure")
                    or saved_context.get("year") not in range(2016, 2024)
                    or not isinstance(saved_context.get("sources_by_year"), list)
                    or not saved_context["sources_by_year"]):
                self.fail(path, "invalid cache dependency manifest")
            if meta["version"] != 1 or (context is not None and meta["context"] != context):
                self.fail(path, "contract/dependencies changed")
            if digest(path) != meta["sha256"]:
                self.fail(path, "payload checksum mismatch")
            return meta
        except (OSError, KeyError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
            self.fail(path, f"missing or invalid manifest/payload ({exc})")

    def load(self, path, context):
        meta = self.metadata(path, context)
        try:
            value = (pd.read_parquet(path) if path.suffix == ".parquet" else
                     json.loads(path.read_text(encoding="utf-8")) if path.suffix == ".json" else joblib.load(path))
            if isinstance(value, pd.DataFrame):
                if meta["schema"] != {str(k): str(v) for k, v in value.dtypes.items()} or meta["rows"] != len(value):
                    self.fail(path, "data schema/row count mismatch")
            return value
        except CacheValidationError:
            raise
        except Exception as exc:
            self.fail(path, f"cannot deserialize cache ({exc})")

    def save(self, path, value, context):
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
        side = self.sidecar(path)
        side_temp = temp.with_suffix(".json.tmp")
        try:
            if isinstance(value, pd.DataFrame):
                value.to_parquet(temp, index=False)
            elif path.suffix == ".json":
                temp.write_text(json.dumps(value, allow_nan=False), encoding="utf-8")
            else:
                joblib.dump(value, temp)
            meta = {"version": 1, "context": context, "sha256": digest(temp)}
            if isinstance(value, pd.DataFrame):
                meta.update(rows=len(value), schema={str(k): str(v) for k, v in value.dtypes.items()})
            side_temp.write_text(json.dumps(meta, sort_keys=True), encoding="utf-8")
            os.replace(temp, path)
            os.replace(side_temp, side)
        finally:
            temp.unlink(missing_ok=True)
            side_temp.unlink(missing_ok=True)

    def preflight(self):
        for folder in ("data_cache", "matrix_cache", "oof", "hpo"):
            for path in (self.output / folder).glob("*"):
                if path.name.endswith(".manifest.json"):
                    if not path.with_name(path.name.removesuffix(".manifest.json")).exists():
                        self.fail(path, "manifest has no payload")
                    continue
                if path.suffix not in (".parquet", ".joblib", ".json", ".sqlite3"):
                    if path.name.endswith(".tmp"):
                        self.fail(path, "incomplete cache write")
                    if path.name.endswith(".manifest.json") and not path.with_name(path.name.removesuffix(".manifest.json")).exists():
                        self.fail(path, "manifest has no payload")
                    continue
                meta = self.metadata(path)
                context = meta["context"]
                if context.get("contract") != self.contract:
                    self.fail(path, "training contract changed")
                # Evaluation-year source bytes stay closed until evaluate().
                for partition in context.get("sources_by_year", []):
                    year = partition["year"]
                    if year > 2022:
                        continue
                    if self.sources(context["task"], year) != partition["files"]:
                        self.fail(path, "source data changed")
                    if "data_sha256" in partition:
                        dependency = self.output / "data_cache" / f"{context['task']}_{year}.parquet"
                        if self.metadata(dependency)["sha256"] != partition["data_sha256"]:
                            self.fail(path, "matrix input cache changed")

    def seal(self, path, context):
        """Seal a closed external artifact such as an Optuna SQLite study."""
        side = self.sidecar(path)
        temp = side.with_name(side.name + ".tmp")
        temp.write_text(json.dumps({"version": 1, "context": context, "sha256": digest(path)}, sort_keys=True), encoding="utf-8")
        os.replace(temp, side)
