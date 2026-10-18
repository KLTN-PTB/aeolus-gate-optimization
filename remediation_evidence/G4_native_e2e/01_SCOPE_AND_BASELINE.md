# AEOLUS-G4 — DELIVERABLE 01: SCOPE AND BASELINE AUDIT

## 1. Executive Mission & Objective

Gate **AEOLUS-G4: Verified Aircraft Turn Pairing & Native Real-Data End-to-End** resolves the fundamental operational and methodological limitations identified in historical Phase P07. 

The primary mission is to establish authenticated, reproducible end-to-end evidence connecting canonical Aeolus historical data, frozen machine learning model checkpoints, deterministic aircraft turn pairing, and operations research gate assignment solvers without silent synthetic fallback or unverified rotation assertions.

---

## 2. Historical Baseline & P07 Forensic Inventory

In the legacy implementation of Phase P07 (`scripts/run_native_dual_core_pipeline.py` and `artifacts/remediation/native_dual_core/`):
1. **Row-Index Pairing Fallacy:** Leg matching matched row $i$ of the inbound slice directly to row $i$ of the outbound slice (`inbound_df.iloc[i]` with `outbound_df.iloc[i]`), completely ignoring physical airframe continuity.
2. **Timestamp Mutation:** When row $i$'s scheduled departure occurred before or too close to inbound arrival, the script artificially forced feasibility by modifying the departure minute (`dep_clock_min = arr_clock_min + 75`), mutating real historical timetables.
3. **Synthetic Fallback Concealment:** If data files were missing or date queries were empty, the runner silently generated synthetic fixtures (`build_synthetic_canonical_data`) while logging ambiguous warnings, obscuring the absence of real data.
4. **Zero Verified Pairs in P07 Run:** In the certified P07 smoke run ($N = 60$ raw legs, 30 turns), exactly **0 verified pairs** were produced. All 30 turns were labeled as `SYNTHETIC_PAIR` because the script attempted to match `tail_in == tail_out` using `OP_CARRIER_FL_NUM` as a fallback, which never matched across differing flight numbers.
5. **Leg vs. Turn Conflation:** Documentation repeatedly conflated flight leg count with aircraft turn count, obscuring that a turn requires two legs ($N_{\text{legs}} = 2 \times N_{\text{turns}}$) when paired, or represents an individual leg when unpaired.

---

## 3. Scope of Remediation in Gate G4

Gate G4 enforces five foundational architectural upgrades:
1. **Task G4.1 — Canonical Time Audit & Datetime Construction (`src/data/canonical_time.py`):**
   - Implements strict, typed parsing for flight dates and scheduled event times.
   - Handles multi-format inputs: ISO timestamp strings (`2023-11-23 09:30:00`), ISO dates (`2023-11-23`), integer HHMM (`930`), string HHMM (`0930`), and float HHMM (`930.0`).
   - Normalizes 2400 midnight rollover (+1 day, 00:00) without negative dwell.
   - Reconciles airport IANA timezones (America/New_York for ATL) and calculates monotonic timeline minutes.
2. **Task G4.2 — Deterministic Verified Aircraft Pairing (`src/simulation/verified_pairing.py`):**
   - Requires verified matching airframe tail numbers (`tail_number`), hub airport connection at ATL, chronological ordering ($T_{\text{arr}} < T_{\text{dep}}$), and physical turnaround compliance ($T_{\text{turn}} \ge 45$m).
   - Enforces 1-to-1 cardinality with zero leg reuse.
   - Deterministic candidate tie-breaking independent of DataFrame row permutation.
   - Distinct, transparent classification: `VERIFIED_ROTATION`, `INFERRED_PAIR`, `SYNTHETIC_PAIR`, and `UNMATCHED`.
   - Zero leg loss: Unmatched legs are preserved as individual gate-occupying turns (`UNMATCHED_ARR`, `UNMATCHED_DEP`).
3. **Task G4.3 — Strict REAL_ONLY Data Loader (`src/data/real_data_loader.py`):**
   - Hard execution barrier between `REAL_ONLY` and `ALLOW_SYNTHETIC`.
   - In `REAL_ONLY`: Missing partition $\to$ explicit failure; empty date window $\to$ explicit failure; missing schema $\to$ explicit failure. Zero borrowing of adjacent dates, zero silent synthetic fallback.
4. **Task G4.4 — Cryptographically Verified Native Inference:**
   - Arrival delay generated from frozen P4 NGBoost Student-t checkpoint (`P4_ARRIVAL_SHA256 = e7e746...`).
   - Departure delay generated from frozen XGBoost regressor and tree preprocessor (`DEP_XGB_SHA256 = e483df...`).
   - Strict prediction cutoff at $T-2$h before scheduled operation. Zero cached dummy predictions in certified runs.
5. **Task G4.5 — Multi-Solver Real-Data Predict-Then-Optimize Execution:**
   - End-to-end execution on Thanksgiving Day 2023 ($N = 200$ real flight legs, 100 inbound + 100 outbound) across CP-SAT, Greedy, and Hybrid solvers.
   - Evaluated by the independent hard-constraint verifier outside the solver.

---

## 4. Preservation Invariants

| Invariant | Status | Enforcement Mechanism |
| :--- | :--- | :--- |
| **Checkpoints Untouched** | **PRESERVED** | Frozen weights in `artifacts/dual_core/models/` and `artifacts/probabilistic/` verified by SHA-256 hashes. |
| **Raw Datasets Untouched** | **PRESERVED** | Raw Aeolus CSV and PT archives in `data/raw/` untouched; zero in-place mutations. |
| **Zero 2024 Contamination** | **PRESERVED** | All G4 pilot runs restricted to historical year 2023. Year 2024 remains untouched holdout. |
| **P07 Certified Baseline Preserved** | **PRESERVED** | Original P07 artifacts in `artifacts/remediation/native_dual_core/` preserved; G4 runs saved to isolated subdirectories. |
| **Git Safety** | **PRESERVED** | Branch isolated on `remediation/g4-native-e2e`. Zero unapproved commits or pushes. |
