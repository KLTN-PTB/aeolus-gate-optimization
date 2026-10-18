# SAFETY BACKUP EXCLUSION LIST

**Date:** 2026-10-12  
**Backup Directory:** `remediation_evidence/G12A_R1_final_reconciliation/safety_backup/`  

---

## 1. Excluded Categories & Technical Rationale

| Category | Specific Paths / Patterns | Technical Rationale for Exclusion |
| :--- | :--- | :--- |
| **Python Virtual Environment** | `.venv/` | Ephemeral build binaries and site-packages. Can be cleanly reproduced via `requirements.txt` or `pyproject.toml`. |
| **Raw Datasets (Multi-GB)** | `data/raw/`, `data/processed/*.parquet` | High-volume read-only datasets protected under immutable provenance contracts. Adding multi-GB files to git/evidence directories introduces storage bloat and risks corruption. |
| **Frozen ML Model Checkpoints** | `artifacts/models/*.pkl`, `artifacts/checkpoints/` | Pre-trained historical binaries from P07/P08/G3, verified via immutable SHA-256 manifests. |
| **Large Simulation Cache Archives** | `artifacts/remediation/monte_carlo/` (P09 frozen), `artifacts/remediation/monte_carlo_remediated/` (G2 frozen) | Frozen baseline evaluation runs preserved in read-only state. |
| **Bytecode & Compiler Cache** | `**/__pycache__/`, `**/*.pyc`, `.pytest_cache/` | Non-deterministic ephemeral compiler artifacts. |
| **Temporary Scratch & Logs** | `.system_generated/`, `scratch/` | Agent session execution logs and scratch files. |

---

## 2. Invariant Safety Statement

All essential code, contracts, tests, runners, and configuration files created or modified across gates G1 through G12A have been safely preserved in:
- `tracked_snapshots/` (Complete working-tree copies of all 9 tracked modified files)
- `untracked_sources/` (Complete working-tree copies of all 20 essential untracked source, test, and runner files)
- `tracked_modifications.patch` (Clean UTF-8 unified git diff verified to apply forward to pristine HEAD with returncode 0)
- `BACKUP_MANIFEST.json` (Cryptographic SHA-256 manifest of the entire safety backup package)
