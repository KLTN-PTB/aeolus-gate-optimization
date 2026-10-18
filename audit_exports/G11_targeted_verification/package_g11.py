"""Packaging script for AEOLUS-G11 Verification Package."""

import hashlib
import json
import zipfile
from pathlib import Path

G11_DIR = Path("D:/Study/Code/Python/Aelous/audit_exports/G11_targeted_verification")


def compute_sha256(path: Path) -> tuple[int, str]:
    data = path.read_bytes()
    return len(data), hashlib.sha256(data).hexdigest()


def main():
    report_files = [
        "01_MODE_B2_INFORMATION_AUDIT.md",
        "02_MODE_B2_COUNTEREXAMPLE_TESTS.md",
        "03_HYBRID_BEST_SO_FAR_AUDIT.md",
        "04_WALL_CLOCK_BUDGET_AUDIT.md",
        "05_SOURCE_HASH_RECONCILIATION.md",
        "06_RAW_TEST_AND_COMMAND_LOG.md",
        "07_FINAL_TARGETED_VERDICT.md",
    ]

    script_files = [
        "test_counterexample_b2_leakage.py",
        "test_hybrid_monotonicity_micro.py",
        "verify_source_hashes.py",
    ]

    manifest = {
        "gate": "AEOLUS-G11",
        "description": "Targeted Causality, Hybrid Invariant & Snapshot Verification Package",
        "timestamp_utc": "2026-10-12T09:41:00Z",
        "auditor_role": "Independent Scientific Software Verification Engineer",
        "deliverables": {},
        "test_scripts": {},
    }

    for rf in report_files:
        p = G11_DIR / rf
        sz, h = compute_sha256(p)
        manifest["deliverables"][rf] = {"size_bytes": sz, "sha256": h}

    for sf in script_files:
        p = G11_DIR / sf
        sz, h = compute_sha256(p)
        manifest["test_scripts"][sf] = {"size_bytes": sz, "sha256": h}

    manifest_path = G11_DIR / "evidence_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    sz_man, h_man = compute_sha256(manifest_path)
    print(f"Created evidence_manifest.json: size={sz_man}, sha256={h_man}")

    # Build ZIP archive
    zip_path = G11_DIR / "AEOLUS_G11_TARGETED_PACKAGE.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rf in report_files:
            zf.write(G11_DIR / rf, arcname=f"G11_reports/{rf}")
        for sf in script_files:
            zf.write(G11_DIR / sf, arcname=f"scripts/{sf}")
        zf.write(manifest_path, arcname="evidence_manifest.json")

    sz_zip, h_zip = compute_sha256(zip_path)
    print(f"Created AEOLUS_G11_TARGETED_PACKAGE.zip: size={sz_zip}, sha256={h_zip}")


if __name__ == "__main__":
    main()
