"""AEOLUS-G11: Source Hash Reconciliation Script.

Compares SHA-256 and size across:
1. Actual disk filesystem
2. G10 evidence_manifest.json
3. G10 AEOLUS_G10_VERIFICATION_PACKAGE.zip
4. G10 01_SOURCE_SNAPSHOT.md text table
"""

import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
G10_DIR = ROOT_DIR / "audit_exports" / "G10_independent_verification"


def compute_file_sha256(filepath: Path) -> tuple[int, str]:
    if not filepath.exists():
        return 0, "MISSING_ON_DISK"
    data = filepath.read_bytes()
    return len(data), hashlib.sha256(data).hexdigest()


def parse_snapshot_md_table(md_path: Path) -> dict[str, dict[str, str]]:
    content = md_path.read_text(encoding="utf-8")
    table_pattern = re.compile(
        r"\|\s*\d+\s*\|\s*`([^`]+)`\s*\|(?:[^|]*\|)?\s*([^|]+)\|\s*`?([a-f0-9]{64})`?\s*\|",
        re.MULTILINE,
    )
    entries = {}
    for match in table_pattern.finditer(content):
        file_path = match.group(1).strip()
        size_str = match.group(2).strip()
        sha256_hash = match.group(3).strip()
        entries[file_path] = {
            "reported_size": size_str,
            "reported_sha256": sha256_hash,
        }
    return entries


def main():
    manifest_path = G10_DIR / "evidence_manifest.json"
    zip_path = G10_DIR / "AEOLUS_G10_VERIFICATION_PACKAGE.zip"
    snapshot_path = G10_DIR / "01_SOURCE_SNAPSHOT.md"

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest_data = json.load(f)

    snapshot_entries = parse_snapshot_md_table(snapshot_path)

    zip_entries = {}
    if zip_path.exists():
        with zipfile.ZipFile(zip_path, "r") as zf:
            for info in zf.infolist():
                data = zf.read(info.filename)
                # Map info.filename by removing known prefixes like 'sources/', 'tests/', 'artifacts/', 'git_diff/', 'G10_reports/'
                clean_name = info.filename
                for prefix in ("sources/", "tests/", "artifacts/", "git_diff/", "G10_reports/"):
                    if clean_name.startswith(prefix):
                        clean_name = clean_name[len(prefix):]
                        break
                zip_entries[clean_name] = {
                    "size_bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "orig_zip_path": info.filename,
                }

    print("=" * 110)
    print(f"{'FILE PATH':<50} | {'DISK MATCH MANIFEST?':<22} | {'DISK MATCH ZIP?':<16} | {'DISK MATCH SNAPSHOT MD?'}")
    print("=" * 110)

    # All files to audit: union of snapshot and manifest
    all_files = sorted(set(list(snapshot_entries.keys()) + list(manifest_data.get("key_source_files", {}).keys())))

    reconciliation_results = []

    for rel_path in all_files:
        disk_file = ROOT_DIR / rel_path
        disk_size, disk_hash = compute_file_sha256(disk_file)

        manifest_info = manifest_data.get("key_source_files", {}).get(rel_path, {})
        manifest_hash = manifest_info.get("sha256", "NOT_IN_MANIFEST")
        manifest_size = manifest_info.get("size_bytes", -1)

        zip_info = zip_entries.get(rel_path, {})
        zip_hash = zip_info.get("sha256", "NOT_IN_ZIP")

        snap_info = snapshot_entries.get(rel_path, {})
        snap_hash = snap_info.get("reported_sha256", "NOT_IN_SNAPSHOT")
        snap_size_str = snap_info.get("reported_size", "")

        match_manifest = (disk_hash == manifest_hash)
        match_zip = (disk_hash == zip_hash)
        match_snap = (disk_hash == snap_hash)

        reconciliation_results.append({
            "path": rel_path,
            "disk_size": disk_size,
            "disk_hash": disk_hash,
            "manifest_size": manifest_size,
            "manifest_hash": manifest_hash,
            "zip_hash": zip_hash,
            "snap_hash": snap_hash,
            "snap_size_str": snap_size_str,
            "match_manifest": match_manifest,
            "match_zip": match_zip,
            "match_snap": match_snap,
        })

        print(f"{rel_path:<50} | {str(match_manifest):<22} | {str(match_zip):<16} | {str(match_snap)}")

    print("=" * 110)
    print("\nDETAILED MISMATCH SUMMARY FOR 01_SOURCE_SNAPSHOT.md:")
    snap_mismatches = [r for r in reconciliation_results if not r["match_snap"]]
    print(f"Total files audited: {len(reconciliation_results)}")
    print(f"Files where Disk matches Manifest: {sum(1 for r in reconciliation_results if r['match_manifest'])} / {len(reconciliation_results)}")
    print(f"Files where Disk matches ZIP:      {sum(1 for r in reconciliation_results if r['match_zip'])} / {len(reconciliation_results)}")
    print(f"Files where Disk matches 01_SOURCE_SNAPSHOT.md: {sum(1 for r in reconciliation_results if r['match_snap'])} / {len(reconciliation_results)}")
    print(f"Number of mismatches in 01_SOURCE_SNAPSHOT.md table: {len(snap_mismatches)}")

    for m in snap_mismatches:
        print(f"\nFile: {m['path']}")
        print(f"  Actual Disk:      size={m['disk_size']:>6d} bytes, sha256={m['disk_hash']}")
        print(f"  Manifest:         size={m['manifest_size']:>6d} bytes, sha256={m['manifest_hash']}")
        print(f"  ZIP:              sha256={m['zip_hash']}")
        print(f"  01_SNAPSHOT.md:   size={m['snap_size_str']:>10s}, sha256={m['snap_hash']}")


if __name__ == "__main__":
    main()
