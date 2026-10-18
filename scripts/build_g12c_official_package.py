import hashlib
import json
import os
import zipfile
from pathlib import Path

def get_file_hash_and_size(filepath):
    p = Path(filepath)
    if not p.exists():
        return None, 0
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest(), p.stat().st_size

def main():
    root_dir = Path("D:/Study/Code/Python/Aelous")
    evidence_dir = root_dir / "remediation_evidence" / "G12C_scientific_reconciliation"
    mc500_run_dir = root_dir / "artifacts" / "remediation" / "monte_carlo_mc500" / "mc500_20261012_173538_afa5db"

    manifest_data = {
        "manifest_name": "AEOLUS_G12C_SCIENTIFIC_RECONCILIATION_MANIFEST",
        "created_at": "2026-10-13T01:21:00+07:00",
        "milestone": "G12C",
        "verdict": "G12C_PASS",
        "git_commit": "c95caef53808a561b1a7d3a5a09399cc52f754f5",
        "git_branch": "remediation/g7-regression",
        "official_mc500_run_id": "mc500_20261012_173538_afa5db",
        "full_pytest_summary": {
            "pre_fix": {
                "passed": 2217,
                "failed": 4,
                "warnings": 4,
                "duration_seconds": 163.95,
                "log_file": "full_pytest_raw_pre_fix.log"
            },
            "post_fix": {
                "passed": 2221,
                "failed": 0,
                "warnings": 4,
                "duration_seconds": 154.01,
                "pass_rate_percent": 100.0,
                "log_file": "full_pytest_raw_post_fix.log"
            }
        },
        "evidence_reports": {},
        "audit_artifacts_and_logs": {},
        "reconciled_source_and_test_components": {},
        "immutable_mc500_references": {}
    }

    # 1. Evidence reports
    for i in range(1, 9):
        pattern = f"0{i}_*.md"
        matches = list(evidence_dir.glob(pattern))
        for m in matches:
            sha, size = get_file_hash_and_size(m)
            manifest_data["evidence_reports"][m.name] = {
                "sha256": sha,
                "size_bytes": size,
                "rel_path": str(m.relative_to(root_dir)).replace("\\", "/")
            }

    # 2. Audit artifacts & logs
    audit_files = [
        evidence_dir / "verified_mc500_raw_values.json",
        evidence_dir / "full_pytest_raw_pre_fix.log",
        evidence_dir / "full_pytest_raw_post_fix.log",
    ]
    for af in audit_files:
        if af.exists():
            sha, size = get_file_hash_and_size(af)
            manifest_data["audit_artifacts_and_logs"][af.name] = {
                "sha256": sha,
                "size_bytes": size,
                "rel_path": str(af.relative_to(root_dir)).replace("\\", "/")
            }

    # 3. Reconciled source & test components
    reconciled_files = [
        root_dir / "src" / "evaluation" / "final_evaluation_guard_v2.py",
        root_dir / "tests" / "benchmark" / "test_model_registry.py",
        root_dir / "tests" / "test_r27_certification_hardening.py",
        root_dir / "scripts" / "verify_g12c_mc500_raw.py",
    ]
    for rf in reconciled_files:
        sha, size = get_file_hash_and_size(rf)
        manifest_data["reconciled_source_and_test_components"][rf.name] = {
            "sha256": sha,
            "size_bytes": size,
            "rel_path": str(rf.relative_to(root_dir)).replace("\\", "/")
        }

    # 4. Immutable MC500 key references
    mc500_refs = [
        mc500_run_dir / "execution_ledger_entries.csv",
        mc500_run_dir / "execution_ledger_summary.json",
        mc500_run_dir / "gate_inventory.json",
        mc500_run_dir / "statistical_summary.json",
        mc500_run_dir / "failures.json",
        mc500_run_dir / "simulation_manifest.json",
    ]
    for mf in mc500_refs:
        sha, size = get_file_hash_and_size(mf)
        manifest_data["immutable_mc500_references"][mf.name] = {
            "sha256": sha,
            "size_bytes": size,
            "rel_path": str(mf.relative_to(root_dir)).replace("\\", "/")
        }

    manifest_path = evidence_dir / "EVIDENCE_MANIFEST.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)
    print(f"Wrote manifest: {manifest_path}")

    # Build ZIP package
    zip_path = root_dir / "AEOLUS_G12C_REVIEW_PACKAGE.zip"
    print(f"Building ZIP package: {zip_path} ...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add all files in evidence_dir
        for ef in sorted(evidence_dir.rglob("*")):
            if ef.is_file():
                arcname = "evidence/" + str(ef.relative_to(evidence_dir)).replace("\\", "/")
                zf.write(ef, arcname)

        # Add modified source and test files
        for rf in reconciled_files:
            arcname = "reconciled_code/" + str(rf.relative_to(root_dir)).replace("\\", "/")
            zf.write(rf, arcname)

        # Add core MC500 reference summaries
        for mf in [mc500_run_dir / "execution_ledger_summary.json", mc500_run_dir / "gate_inventory.json", mc500_run_dir / "statistical_summary.json", mc500_run_dir / "failures.json", mc500_run_dir / "simulation_manifest.json"]:
            if mf.exists():
                arcname = "mc500_summaries/" + mf.name
                zf.write(mf, arcname)

    zip_sha, zip_size = get_file_hash_and_size(zip_path)
    print(f"ZIP package created successfully.")
    print(f"Path: {zip_path}")
    print(f"Size: {zip_size:,} bytes")
    print(f"SHA-256: {zip_sha}")

if __name__ == "__main__":
    main()
