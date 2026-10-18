# AEOLUS-G12B: BASELINE AUDIT, SAFETY BACKUP & SOURCE IDENTITY RECONCILIATION

**Date:** 2026-10-12  
**Auditor:** Senior Operations Research Engineer, Principal Python Software Engineer  
**Scope:** Phase 0 Safety Preservation, Checksum Reconciliation, and Non-Negotiable Safety Rules  

---

## 1. Environment & Git State at Gate Initiation

- **Git HEAD:** `c95caef53808a561b1a7d3a5a09399cc52f754f5`
- **Active Branch:** `remediation/g7-regression`
- **Tracked Modifications:** 9 files in `git status` (8 textually modified files + `src/contracts/__init__.py` stat cache parity).
- **Working Tree Patch:** Preserved in clean UTF-8 at `remediation_evidence/G12B_hybrid_and_contract_closure/safety_backup/tracked_modifications.patch` (30,957 bytes).
- **Reverse Apply Verification:** `git apply --check --reverse` executed with `returncode = 0`.

---

## 2. Reconciliation of G12A-R1 Source Hashes and File Counts

### 2.1 Authoritative Snapshot Hashes
The authoritative working tree state at G12B initiation has been cryptographically confirmed:
- `src/simulation/monte_carlo_engine_v2.py`:
  - Size: 40,853 bytes
  - SHA-256: `ceb403130e68fb2f53d0fa53af377e2d592dce7151c3c684032591e044c48fa0`
  - *Note:* The file on disk and the file inside `AEOLUS_G12A_R1_REVIEW_PACKAGE.zip` are bitwise identical (`ceb40313...`). The intermediate hash (`2ba5f98c...`) previously printed in terminal output was captured prior to the final whitespace formatting step.
- `tests/test_g12a_causal_online_recourse.py`:
  - Size: 35,649 bytes
  - SHA-256: `52d0258aa89e028cf8b6ed3f295bc429227c9e780c29ba93a1aef2744d2e69a9`
- `scripts/run_g12a_causal_pilot.py`:
  - Size: 9,346 bytes
  - SHA-256: `5acd6c3eb967cfdf0423fb862deda2e00a51b7fc4482dd772c936630d3ffb5fb`

### 2.2 Reconciling Manifest (43 files) vs Review ZIP (26 files)
- In G12A-R1, `08_EVIDENCE_MANIFEST.json` scanned the entire recursive directory tree of `remediation_evidence/G12A_R1_final_reconciliation/`, which included 29 files in the internal `safety_backup/` sub-directories (`tracked_snapshots/` and `untracked_sources/`), plus reports and source files, totaling 43 entries.
- The review bundle `AEOLUS_G12A_R1_REVIEW_PACKAGE.zip` contained the 26 essential deliverable files (3 core sources, 8 dependencies, 4 pilot artifacts, 8 reports, and 3 audit artifacts), intentionally avoiding redundant duplication of the internal snapshot tree.
- **Verification Result:** Zero files were lost. All working tree files and historical evidence are intact.

---

## 3. Safety Backup Structure

The backup is maintained under `remediation_evidence/G12B_hybrid_and_contract_closure/safety_backup/`:
1. `tracked_modifications.patch`: Unified diff of all tracked changes (UTF-8, 30,957 bytes).
2. `tracked_snapshots/`: Working-tree copies of all 9 tracked files.
3. `untracked_sources/`: Working-tree copies of all 20 essential untracked source, test, and script files.
4. `BACKUP_MANIFEST.json`: Cryptographic manifest of the 31 files in the backup directory.
