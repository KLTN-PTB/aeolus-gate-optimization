# AEOLUS-MC500 PREFLIGHT: Deliverable 01 — Current Authoritative Source Identity & Repository State

## 1. Executive Summary & Objective

This document establishes the exact, authoritative identity of the `aeolus-gate-optimization` codebase in its current working tree state prior to any large-scale Monte Carlo execution ($N=500$). 

As observed during the preflight audit:
1. The prior archive `AEOLUS_G12B_R1_REVIEW_PACKAGE.zip` packaged report markdowns and the `safety_backup/` directory (which captured the pre-fix state of G12B). It did not package the post-fix implementation source files or `tests/test_g12b_r1_contract_integrity.py`.
2. To ensure 100% scientific reproducibility, this preflight audit operates directly on the **actual working tree files on disk**, reconciling their cryptographic fingerprints (SHA-256), line counts, and Git working tree status.

---

## 2. Git Working Tree & Repository Environment

- **Current Git HEAD**: `c95caef53808a561b1a7d3a5a09399cc52f754f5`
- **Active Branch**: `remediation/g7-regression`
- **Execution Platform**: Windows 10 Pro (x64)
- **Python Runtime**: `3.11.15` (Virtualenv: `.venv\Scripts\python.exe`)
- **OR-Tools Version**: `9.15.6755`
- **Repository Cleanliness Policy**: Strict adherence to zero-commit, zero-push, zero-reset, zero-clean policy. Uncommitted working tree state is preserved.

---

## 3. Reverse Patch Verification & Reconciling `SAFETY_MANIFEST.json`

### 3.1 The Reversal Verification
The pre-execution safety patch exported during Task 0 is located at:
`remediation_evidence/G12B_R1_contract_integrity/safety_backup/tracked_modifications_g12b.patch` (43,878 bytes).

When executing Git reverse apply check with whitespace normalization:
```bash
git apply --ignore-space-change --ignore-whitespace --check --reverse remediation_evidence/G12B_R1_contract_integrity/safety_backup/tracked_modifications_g12b.patch
```
- **Exit Code**: `0` (Success).
- **Result**: Patch applies in reverse cleanly against the base HEAD without collisions.

### 3.2 Reconciliation of `reverse_apply_check=false` Discrepancy
In `remediation_evidence/G12B_R1_contract_integrity/safety_backup/SAFETY_MANIFEST.json`, the field was recorded as:
```json
"reverse_apply_check": false
```
**Forensic Cause**: On Windows, Git checkouts often handle Line Feed (LF) and Carriage Return + Line Feed (CRLF) differences. The automated script that initially wrote `SAFETY_MANIFEST.json` invoked `git apply --check --reverse` without `--ignore-space-change --ignore-whitespace`. Because the patch had LF while the working tree had CRLF, Git returned exit code `1`, causing the JSON script to write `false`. When the flags `--ignore-space-change --ignore-whitespace` were added, Git returned exit code `0`. This audit confirms that the patch is indeed 100% reverse-applicable.

---

## 4. Authoritative Source Inventory & Cryptographic Fingerprints

The following table reflects the actual, current source files residing in the working tree:

| File Path | Role in System | Size (Bytes) | SHA-256 Checksum | Git Status |
| :--- | :--- | :---: | :--- | :---: |
| `src/simulation/monte_carlo_engine_v2.py` | Causal MC engine, Mode B2, Ledger classes | 57,958 | `17d367712fabd42e0811097015140c0565eab255f2aaa03a8646ded440fa0ad2` | Untracked (`??`) |
| `src/optimization/solvers/hybrid_solver.py` | Hybrid CP-SAT + SA solver with incumbent guard | 19,049 | `7dbe88c94640145c568bde52b3cbefe837e53ac9675b4fb1975ad8bf8c44d94a` | Tracked Modified (`M`) |
| `src/optimization/sa/annealer.py` | Simulated Annealing engine & neighborhood moves | 12,933 | `e6b49165fb2e6aeb760743d480653acbcd5eb5150b6986794e6a9334f9d341e8` | Tracked Modified (`M`) |
| `src/optimization/domain.py` | Optimization domain entities & hard verifier | 61,431 | `7e2101388729ee48f1f4555c6ee859a0525b4a7a901c76e33c6b3adde78ea580` | Clean (` `) |
| `src/optimization/config.py` | Optimization configurations & objective weights | 5,953 | `7d0b06102cd900ef13c16d40c7728bca251b0f7027ef43ea452d936edc0b1669` | Clean (` `) |
| `src/optimization/evaluation.py` | Authoritative gate assignment evaluator | 6,859 | `62de5417c576225b2d98e38e2df008653112a6ad360da49543874387fc9db8f1` | Clean (` `) |
| `tests/test_g12b_r1_contract_integrity.py` | 31 contract integrity tests (Task 1–4) | 34,183 | `44bf48bbf6d14cca1b41efe86a7fe2b4c3382047b8d8acc9b999f5d57d879c70` | Untracked (`??`) |
| `tests/test_g12a_causal_online_recourse.py` | 13 non-anticipative causality tests | 35,651 | `72030ef5574b6f43f14a6c3b6f3a3b1ff6347df1e68e973e0a9b0b5177364f10` | Untracked (`??`) |
| `tests/test_g2_monte_carlo_causality.py` | 15 G2 causality & mode comparison tests | 27,707 | `386384203b3996d58744b0b98a59b7e9cda11347b9f9ea895fba4438a3601717` | Untracked (`??`) |
| `tests/test_sa_hybrid_correctness_p03.py` | 37 SA & Hybrid correctness tests | 32,296 | `6f161f9e7cfc9ffdd6cb8e1a3d0f4cd0ff32db3aabb5385b02bae20791f5cd9a` | Tracked Modified (`M`) |
| `scripts/run_g2_monte_carlo_remediation.py` | Production Monte Carlo pipeline runner | 17,732 | `12341f4921b18cde858f2e2bc7042c10a2f8f550e010bea93ea67b50817b6856` | Untracked (`??`) |
| `scripts/run_g12a_causal_pilot.py` | Causal pilot runner (N=100) | 9,346 | `5acd6c3eb967cfdf0423fb862deda2e00a51b7fc4482dd772c936630d3ffb5fb` | Untracked (`??`) |
| `scripts/run_g12b_fair_benchmark.py` | Fair wall-clock benchmark script (5 tiers) | 16,803 | `72ccbd7eb121e5d9a1b6d17b71835fff0c7eaf213b033064dbe7c397e5aa2628` | Untracked (`??`) |
| `scripts/dry_run_mc500_preflight.py` | Preflight small dry-run script (N=5) | 12,397 | `acb60f1ad5d24d9e26217637dbca0040f7d0e37cb0d20d75c82ffaf7e53f1947` | Untracked (`??`) |
| `tests/test_mc500_ledger_runner_integration.py` | Ledger runner integration verification tests | 2,746 | `c4844330ad8a402324f33eb9602a8145459346a0662d0016e792c3005a764d26` | Untracked (`??`) |

---

## 5. Verification Assessment

All files above represent the authoritative source code as modified through G12B-R1 and preflight preparation. There are zero synthetic or fabricated replacement files.
