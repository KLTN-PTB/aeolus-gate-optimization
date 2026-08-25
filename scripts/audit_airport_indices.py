"""Streaming cross-year audit of airport-code to index mappings.

This schema-only helper retains only unique airport/index pairs and never writes
to raw data.  It is not a feature-engineering or model-development workflow.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from src.data.load_aeolus import resolve_tabular_csv


def _mapping_audit(code_column: str, index_column: str, chunk_size: int = 250_000) -> dict:
    per_year: dict[str, dict[str, set[str]]] = {}
    global_mapping: dict[str, set[str]] = defaultdict(set)
    for year in range(2016, 2025):
        source = resolve_tabular_csv(year, purpose="schema_audit")
        mapping: dict[str, set[str]] = defaultdict(set)
        for chunk in pd.read_csv(source, usecols=[code_column, index_column], chunksize=chunk_size, low_memory=False):
            pairs = chunk.dropna().astype("string")
            pairs[index_column] = pairs[index_column].str.strip()
            pairs[code_column] = pairs[code_column].str.strip()
            pairs = pairs[(pairs[code_column] != "") & (pairs[index_column] != "")]
            for code, index in pairs.drop_duplicates().itertuples(index=False, name=None):
                mapping[str(code)].add(str(index))
                global_mapping[str(code)].add(str(index))
        per_year[str(year)] = {
            code: sorted(values) for code, values in sorted(mapping.items())
        }
    within_year_conflicts = {
        year: {code: sorted(values) for code, values in mapping.items() if len(values) > 1}
        for year, mapping in per_year.items()
    }
    within_year_conflicts = {year: entries for year, entries in within_year_conflicts.items() if entries}
    cross_year_conflicts = {code: sorted(values) for code, values in global_mapping.items() if len(values) > 1}
    result = "STABLE" if not within_year_conflicts and not cross_year_conflicts else "UNSTABLE"
    return {
        "code_column": code_column,
        "index_column": index_column,
        "years": list(range(2016, 2025)),
        "unique_codes_by_year": {year: len(mapping) for year, mapping in per_year.items()},
        "within_year_conflicts": within_year_conflicts,
        "cross_year_conflicts": cross_year_conflicts,
        "result": result,
        "mapping_by_year": per_year,
    }


def main() -> int:
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "audit_type": "schema_only_cross_year_airport_index_mapping",
        "origin": _mapping_audit("ORIGIN", "ORIGIN_INDEX"),
        "destination": _mapping_audit("DEST", "DEST_INDEX"),
    }
    output = PROJECT_ROOT / "artifacts" / "manifests" / "airport_index_mapping_audit.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
