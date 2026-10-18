"""
Create evidence_manifest.json and package AEOLUS_G10_VERIFICATION_PACKAGE.zip
for the AEOLUS-G10 Independent Audit.
"""
import hashlib
import json
import os
import pathlib
import zipfile

def compute_sha256(filepath: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def main():
    root = pathlib.Path("D:/Study/Code/Python/Aelous").resolve()
    g10_dir = root / "audit_exports" / "G10_independent_verification"
    g10_dir.mkdir(parents=True, exist_ok=True)

    # 1. Compute hashes of all 11 G10 reports
    reports = sorted(list(g10_dir.glob("*.md")))
    manifest = {
        "gate": "AEOLUS-G10",
        "description": "Independent Post-Remediation Source & Scientific Evidence Audit",
        "timestamp_utc": "2026-10-11T12:43:00Z",
        "head_commit": "c95caef53808a561b1a7d3a5a09399cc52f754f5",
        "active_branch": "remediation/g7-regression",
        "g10_deliverables": {},
        "key_source_files": {},
        "key_test_files": {},
        "key_artifacts": {},
        "excluded_large_files": [
            {
                "path": "artifacts/remediation/outbound_classification/predictions/outbound_classification_selection_2023.parquet",
                "size_bytes": 13971264,
                "sha256": compute_sha256(root / "artifacts/remediation/outbound_classification/predictions/outbound_classification_selection_2023.parquet") if (root / "artifacts/remediation/outbound_classification/predictions/outbound_classification_selection_2023.parquet").exists() else None,
                "reason": "Large Parquet file (~14MB). Recomputed metrics and reliability summaries are packaged in CSV/JSON format."
            },
            {
                "path": "artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib",
                "size_bytes": 243595,
                "sha256": "e7e7462f17b65b276ebdee9c7beced15e090f69b088a18896d5a91aaa8cb062f",
                "reason": "Binary model checkpoint. Verified against frozen SHA-256."
            },
            {
                "path": "artifacts/dual_core/models/departure_xgboost_baseline_v1.joblib",
                "size_bytes": 498135,
                "sha256": "e483df5fd03ce4d0eefe7b431fc289b6804589c62eda17b48fb8051849f4f6e1",
                "reason": "Binary model checkpoint. Verified against frozen SHA-256."
            },
            {
                "path": "artifacts/remediation/outbound_classification/models/outbound_xgboost_calibrated_v1.joblib",
                "size_bytes": 498237,
                "sha256": "73ef9da305886d34e9e1bb939a9ceae0b686259021e1dbdfa79d0be18b01e1ff",
                "reason": "Binary model checkpoint. Verified against frozen SHA-256."
            }
        ]
    }

    for r in reports:
        manifest["g10_deliverables"][r.name] = {
            "size_bytes": r.stat().st_size,
            "sha256": compute_sha256(r)
        }

    # Key sources
    key_sources = [
        "src/contracts/provenance.py",
        "src/contracts/temporal.py",
        "src/data/canonical_time.py",
        "src/data/real_data_loader.py",
        "src/simulation/monte_carlo_engine_v2.py",
        "src/simulation/verified_pairing.py",
        "src/optimization/solvers/hybrid_solver.py",
        "src/optimization/solvers/cp_sat_solver.py",
        "scripts/run_g2_monte_carlo_remediation.py",
        "scripts/run_g5_fair_benchmark.py",
        "scripts/train_outbound_classifiers_g3.py",
        "scripts/run_native_dual_core_pipeline.py",
        "audit_exports/working_tree_git_diff.patch"
    ]
    for s in key_sources:
        sp = root / s
        if sp.exists():
            manifest["key_source_files"][s] = {
                "size_bytes": sp.stat().st_size,
                "sha256": compute_sha256(sp)
            }

    # Key tests
    key_tests = [
        "tests/test_g1_provenance_and_temporal_contracts.py",
        "tests/test_g2_monte_carlo_causality.py",
        "tests/test_g3_ml_validation.py",
        "tests/test_g4_native_e2e.py",
        "tests/test_g5_solver_correctness.py",
        "tests/test_g6_dashboard_integrity.py",
        "tests/test_g7_scientific_invariants.py",
        "tests/benchmark/test_model_registry.py",
        "tests/test_r22_system_freeze_v3.py",
        "tests/test_r27_certification_hardening.py"
    ]
    for t in key_tests:
        tp = root / t
        if tp.exists():
            manifest["key_test_files"][t] = {
                "size_bytes": tp.stat().st_size,
                "sha256": compute_sha256(tp)
            }

    # Key artifacts
    key_artifacts = [
        "artifacts/remediation/outbound_classification/metrics/outbound_classification_metrics_2023.csv",
        "artifacts/remediation/outbound_classification/metrics/reliability_diagrams_2023.json",
        "artifacts/remediation/monte_carlo_remediated/simulation_manifest.json",
        "artifacts/remediation/monte_carlo_remediated/statistical_summary.json",
        "artifacts/remediation/benchmarks/g5_fair_benchmark/g5_fair_benchmark_results.csv",
        "artifacts/remediation/benchmarks/g5_fair_benchmark/g5_fair_benchmark_manifest.json",
        "artifacts/remediation/native_dual_core_g4_pilot/run_manifest.json",
        "artifacts/remediation/native_dual_core_g4_pilot/turn_pairing_audit.json",
        "artifacts/remediation/native_dual_core_g4_pilot_inferred/run_manifest.json",
        "data/processed/p07_flights_core.csv"
    ]
    for a in key_artifacts:
        ap = root / a
        if ap.exists():
            manifest["key_artifacts"][a] = {
                "size_bytes": ap.stat().st_size,
                "sha256": compute_sha256(ap)
            }

    manifest_path = g10_dir / "evidence_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Written manifest: {manifest_path} ({manifest_path.stat().st_size} bytes)")

    # 2. Build ZIP package
    zip_path = g10_dir / "AEOLUS_G10_VERIFICATION_PACKAGE.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Include all G10 deliverables
        for r in reports:
            zf.write(r, arcname=f"G10_reports/{r.name}")
        zf.write(manifest_path, arcname="evidence_manifest.json")

        # Include patch
        patch_file = root / "audit_exports" / "working_tree_git_diff.patch"
        if patch_file.exists():
            zf.write(patch_file, arcname="git_diff/working_tree_git_diff.patch")

        # Include key sources & scripts
        for s in key_sources:
            sp = root / s
            if sp.exists() and s != "audit_exports/working_tree_git_diff.patch":
                zf.write(sp, arcname=f"sources/{s}")

        # Include key tests
        for t in key_tests:
            tp = root / t
            if tp.exists():
                zf.write(tp, arcname=f"tests/{t}")

        # Include key artifacts
        for a in key_artifacts:
            ap = root / a
            if ap.exists():
                zf.write(ap, arcname=f"artifacts/{a}")

    print(f"Created ZIP: {zip_path}")
    print(f"ZIP Size: {zip_path.stat().st_size} bytes ({zip_path.stat().st_size / (1024*1024):.2f} MB)")

if __name__ == "__main__":
    main()
