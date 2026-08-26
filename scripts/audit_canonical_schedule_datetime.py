"""Audit canonical schedule date/time representations for development years."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.canonical_schedule_datetime_audit import audit_development_years
from src.data.flight_chain_reconstruction import (
    assert_output_path_safe,
    assert_project_venv,
    assert_raw_inventory_unchanged,
    snapshot_raw_inventory,
)


DEFAULT_OUTPUT = Path(
    "artifacts/manifests/canonical_schedule_datetime_representation_audit_v1.json"
)


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


def parse_development_years(value: str) -> list[int]:
    """Parse deterministic comma/range syntax and reject non-development years."""
    years: set[int] = set()
    for token in (part.strip() for part in value.split(",")):
        if not token:
            raise ValueError("Empty year token")
        if "-" in token:
            parts = token.split("-")
            if len(parts) != 2:
                raise ValueError(f"Invalid year range: {token}")
            start, end = (int(part) for part in parts)
            if start > end:
                raise ValueError(f"Year range must be ascending: {token}")
            years.update(range(start, end + 1))
        else:
            years.add(int(token))
    if not years:
        raise ValueError("At least one audit year is required")
    unsupported = sorted(year for year in years if year not in range(2016, 2024))
    if unsupported:
        raise ValueError(
            "Audit is restricted to development years 2016-2023; "
            f"unsupported={unsupported}"
        )
    return sorted(years)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit canonical FL_DATE/CRS schedule representations without "
            "constructing Flight Chains or changing production normalization."
        )
    )
    parser.add_argument("--years", default="2016-2023")
    parser.add_argument("--batch-size", type=_positive_int, default=100_000)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        years = parse_development_years(args.years)
    except ValueError as error:
        parser.error(str(error))

    assert_project_venv(ROOT)
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output = assert_output_path_safe(output, project_root=ROOT)
    raw_before = snapshot_raw_inventory(ROOT)
    manifest = audit_development_years(ROOT, years, batch_size=args.batch_size)
    raw_after = snapshot_raw_inventory(ROOT)
    assert_raw_inventory_unchanged(raw_before, raw_after)
    manifest.update(
        {
            "raw_chain_used": False,
            "raw_pt_loaded": False,
            "chains_constructed": False,
            "production_normalization_modified": False,
            "final_holdout_2024_accessed": False,
            "raw_integrity": {
                "file_count": len(raw_before),
                "path_size_mtime_unchanged": True,
            },
        }
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(output)
    print(
        "CANONICAL_DATETIME_AUDIT: COMPLETE "
        f"years={years} rows={manifest['total_rows']} output={output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
