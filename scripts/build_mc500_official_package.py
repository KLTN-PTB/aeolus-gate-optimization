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
    evidence_dir = root_dir / "remediation_evidence" / "MC500_official_experiment"
    run_dir = root_dir / "artifacts" / "remediation" / "monte_carlo_mc500" / "mc500_20261012_173538_afa5db"

    # Files to include in manifest
    manifest_data = {
        "manifest_name": "AEOLUS_MC500_FINAL_EVIDENCE_MANIFEST",
        "created_at": "2026-10-13T00:44:00+07:00",
        "run_id": "mc500_20261012_173538_afa5db",
        "git_commit": "c95caef53808a561b1a7d3a5a09399cc52f754f5",
        "git_branch": "remediation/g7-regression",
        "verdict": "MC500_EXPERIMENT_COMPLETE_VERIFIED",
        "evidence_reports": {},
        "production_artifacts": {},
        "provenance_and_audit_files": {},
        "source_code_components": {}
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

    # 2. Provenance and audit files
    audit_files = [
        evidence_dir / "detailed_statistical_metrics.json",
        evidence_dir / "preflight_pytest_log.txt",
        evidence_dir / "SOURCE_AND_TOPOLOGY_MANIFEST.json",
        evidence_dir / "working_tree_pre_n500.patch",
    ]
    for af in audit_files:
        if af.exists():
            sha, size = get_file_hash_and_size(af)
            manifest_data["provenance_and_audit_files"][af.name] = {
                "sha256": sha,
                "size_bytes": size,
                "rel_path": str(af.relative_to(root_dir)).replace("\\", "/")
            }

    # 3. Production run artifacts
    for rf in sorted(run_dir.glob("*")):
        if rf.is_file():
            sha, size = get_file_hash_and_size(rf)
            manifest_data["production_artifacts"][rf.name] = {
                "sha256": sha,
                "size_bytes": size,
                "rel_path": str(rf.relative_to(root_dir)).replace("\\", "/")
            }

    # 4. Source code components
    source_files = [
        root_dir / "scripts" / "run_g2_monte_carlo_remediation.py",
        root_dir / "src" / "simulation" / "monte_carlo_engine_v2.py",
        root_dir / "src" / "simulation" / "scalability_scenario.py",
        root_dir / "src" / "evaluation" / "downstream_comparison_v2.py",
    ]
    for sf in source_files:
        sha, size = get_file_hash_and_size(sf)
        manifest_data["source_code_components"][sf.name] = {
            "sha256": sha,
            "size_bytes": size,
            "rel_path": str(sf.relative_to(root_dir)).replace("\\", "/")
        }

    manifest_path = evidence_dir / "FINAL_EVIDENCE_MANIFEST.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)
    print(f"Wrote manifest: {manifest_path}")

    # Build ZIP package
    zip_path = root_dir / "AEOLUS_MC500_OFFICIAL_REVIEW_PACKAGE.zip"
    print(f"Building ZIP package: {zip_path} ...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add all files in evidence_dir
        for ef in sorted(evidence_dir.rglob("*")):
            if ef.is_file():
                arcname = "evidence/" + str(ef.relative_to(evidence_dir)).replace("\\", "/")
                zf.write(ef, arcname)

        # Add all files in run_dir
        for rf in sorted(run_dir.rglob("*")):
            if rf.is_file():
                arcname = "production_run_artifacts/" + str(rf.relative_to(run_dir)).replace("\\", "/")
                zf.write(rf, arcname)

        # Add source files
        for sf in source_files:
            arcname = "source/" + str(sf.relative_to(root_dir)).replace("\\", "/")
            zf.write(sf, arcname)

    zip_sha, zip_size = get_file_hash_and_size(zip_path)
    print(f"ZIP package created successfully.")
    print(f"Path: {zip_path}")
    print(f"Size: {zip_size:,} bytes")
    print(f"SHA-256: {zip_sha}")

if __name__ == "__main__":
    main()
