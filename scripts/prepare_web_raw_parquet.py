"""Convert BTS 71-field .asc to raw schedule Parquet for the web dashboard.

Only schedule columns (and optional historical evaluation labels) are copied.
No ML prediction, actual-time filtering, pairing, or gate assignment happens here.
FL_DATE is departure date at origin; selecting a date here is NOT selecting ATL
arrival-local service date. Include adjacent departure dates for overnight legs.
"""
import argparse
import csv
from datetime import date
from pathlib import Path

import pandas as pd


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=root / "data/raw/ontime.td.202607.asc")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--start-date", type=date.fromisoformat, required=True)
    parser.add_argument("--end-date", type=date.fromisoformat, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Không ghi đè file đã tồn tại: {args.output}")
    if args.start_date > args.end_date:
        raise ValueError("Ngày bắt đầu phải trước hoặc bằng ngày kết thúc.")
    rows = []
    with args.source.open(encoding="utf-8-sig", newline="") as stream:
        for line, fields in enumerate(csv.reader(stream, delimiter="|"), start=1):
            if len(fields) != 71:
                raise ValueError(f"Dòng {line} không có đúng 71 trường BTS.")
            if fields[6] != "ATL" and fields[7] != "ATL":
                continue
            flight_date = date.fromisoformat(f"{fields[8][:4]}-{fields[8][4:6]}-{fields[8][6:8]}")
            if not args.start_date <= flight_date <= args.end_date:
                continue
            rows.append({"FL_DATE": flight_date.isoformat(), "OP_CARRIER": fields[4],
                "OP_CARRIER_FL_NUM": int(fields[5]), "ORIGIN": fields[6], "DEST": fields[7],
                "CRS_DEP_TIME": fields[11], "CRS_ARR_TIME": fields[14],
                "CRS_ELAPSED_TIME": float(fields[18]) if fields[18] else None,
                "TAIL_NUM": fields[25] or None,
                "DEP_DELAY": float(fields[20]) if fields[20] else None,
                "ARR_DELAY": float(fields[21]) if fields[21] else None})
    if not rows:
        raise ValueError("Không có lượt bay trong phạm vi ngày nguồn.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(args.output, index=False)
    print(f"Created {args.output} ({len(rows)} raw records). No predictions or actual-time eligibility filtering.")


if __name__ == "__main__":
    main()
