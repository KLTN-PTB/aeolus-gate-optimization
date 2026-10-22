"""Read-only status for a local V3 run; never creates/updates a study."""
import argparse
import json
from pathlib import Path
import sqlite3


def status(run):
    result = {"run": str(run), "progress": None, "studies": {}}
    path = run / "progress.json"
    if path.exists():
        result["progress"] = json.loads(path.read_text(encoding="utf-8"))
    for path in sorted(run.glob("*.sqlite3")):
        try:
            with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=2) as connection:
                result["studies"][path.stem] = dict(connection.execute("SELECT state, COUNT(*) FROM trials GROUP BY state"))
        except sqlite3.OperationalError as exc:
            result["studies"][path.stem] = {"initializing_or_busy": str(exc)}
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    print(json.dumps(status(args.run), indent=2))
