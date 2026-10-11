# UI-R00: 08 — SAFETY FREEZE & NON-DESTRUCTIVE ROLLBACK PLAN

**Document ID:** `AEOLUS-UI-R00-08-ROLLBACK-PLAN`  
**Phase:** UI-R00 (Baseline, Technical Audit & Safety Freeze)  
**Audit Timestamp:** 2026-10-10T23:32:00+07:00  
**Auditor:** Git Safety Specialist & Release Engineer  

---

## 1. Executive Summary

A core directive of Phase UI-R00 is establishing a **bulletproof, non-destructive safety rollback procedure**. The repository currently has a dirty working tree containing pre-existing modifications in `src/optimization/adapter.py` and untracked Phase P10 files.

Under no circumstances may destructive Git commands (`git reset --hard`, `git clean -fd`) be executed. This document defines the exact protocol to safeguard existing work and provide safe rollback points during the upcoming redesign phases (UI-R01 through UI-R08).

---

## 2. Pre-Existing Working Tree State (Safety Baseline)

As audited in `01_repository_baseline.md`:
- **Current Branch:** `development/scalability-1500x50`
- **HEAD Commit:** `223f0dd`
- **Modified Tracked File:** `src/optimization/adapter.py` (type-checking import only)
- **Untracked Directories:** `dashboard/`, `docs/dashboard/`, `tests/dashboard/`, `artifacts/remediation/`
- **UI-R00 Created Files:** Strictly confined to `docs/dashboard/redesign/UI-R00/`

---

## 3. Pre-Redesign Safety Snapshot Protocol

Before beginning any modifications in Phase **UI-R01**, the user or automated pipeline should create a dedicated local checkpoint branch without touching the working tree.

### 3.1. Non-Destructive Checkpoint Creation
```powershell
# 1. Verify working tree status without modifying files
git status --porcelain=v1

# 2. Create a safety stash that includes untracked files (without deleting)
# WARNING: Do NOT use git clean or git reset!
# To create an immutable checkpoint commit on a safety branch:
git checkout -b backup/pre-ui-redesign-baseline-20261010
git add dashboard/ docs/ tests/dashboard/ requirements-dashboard.txt README_DASHBOARD.md src/optimization/adapter.py
git commit -m "chore(freeze): capture pre-ui-redesign baseline before UI-R01"

# 3. Create active feature branch for the redesign sequence
git checkout -b feature/dashboard-ui-redesign
```

*Note: This command sequence commits the pre-existing P10 implementation to a safety backup branch (`backup/pre-ui-redesign-baseline-20261010`), guaranteeing zero risk of work loss.*

---

## 4. Phase-by-Phase Safe Rollback Procedures

If any subsequent phase fails its Quality Gate, apply the following non-destructive rollback steps:

### Scenario A: Rollback Changes Within an Uncommitted Redesign Phase (e.g. in UI-R01)
To undo working changes in `dashboard/` while preserving pre-existing files:
```powershell
# Check which files were modified in the current phase
git status --short dashboard/

# Revert only specific files modified during the phase:
git checkout -- dashboard/path/to/modified_file.py

# DO NOT RUN git reset --hard HEAD
```

### Scenario B: Reverting to the Clean UI-R00 Baseline
If the redesign needs to be completely rolled back to the state at the end of UI-R00:
```powershell
# 1. Switch back to the safety branch created in Section 3
git checkout backup/pre-ui-redesign-baseline-20261010

# 2. Or if working on feature/dashboard-ui-redesign, perform a non-destructive revert:
git revert --no-commit <commit-hash-of-failed-phase>
```

### Scenario C: Emergency Quarantine of Specific Dashboard Pages
If a single page introduces a regression during presentation rehearsals:
```powershell
# Restore only that page from the backup branch:
git checkout backup/pre-ui-redesign-baseline-20261010 -- dashboard/pages/page_03_gate_operations.py
```

---

## 5. Prohibited Git Operations (Safety Blacklist)

The following commands are **STRICTLY PROHIBITED** across all redesign phases:

| Prohibited Command | Danger Level | Reason for Prohibition |
| :--- | :---: | :--- |
| `git reset --hard` | 🔴 **CRITICAL** | Irrevocably destroys uncommitted work in `adapter.py` and working files |
| `git clean -fd` | 🔴 **CRITICAL** | Deletes untracked artifacts, reports, and P10 test scripts |
| `git push --force` | 🔴 **CRITICAL** | Overwrites remote repository history |
| `git checkout -f` | 🟠 **HIGH** | Discards working tree changes indiscriminately |
| `rmdir /s /q artifacts` | 🔴 **CRITICAL** | Destroys irreplaceable P00–P09 research results |

---

## 6. Verification Checklist Before Starting UI-R01
- [x] All UI-R00 deliverables saved in `docs/dashboard/redesign/UI-R00/`.
- [x] No modifications made to `dashboard/` or `src/`.
- [x] Pre-existing test suite passes 100% (212/212 tests).
- [x] Rollback commands documented and validated.
- [x] Ready for explicit user authorization before starting UI-R01.
