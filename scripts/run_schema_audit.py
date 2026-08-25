"""Run the read-only Aeolus Tabular schema audit one year at a time.

This is an execution helper for the Week-2 schema audit.  It never writes into
``data/raw``; year summaries are written by ``SchemaAuditor`` under artifacts.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.schema_audit import SchemaAuditor


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunk-size", type=int, default=250_000)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.chunk_size <= 0:
        parser.error("--chunk-size must be positive")

    auditor = SchemaAuditor()
    reference: Path | None = None
    for year in range(2016, 2025):
        summary = auditor.audit_year(
            year,
            chunk_size=args.chunk_size,
            reference_schema=reference,
            resume=args.resume,
        )
        print(
            f"COMPLETE year={year} rows={summary['row_count']} "
            f"runtime_seconds={summary.get('runtime_seconds')} resumed={summary['resumed']}",
            flush=True,
        )
        reference = auditor.manifest_path(year)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
