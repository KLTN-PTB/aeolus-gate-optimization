# AEOLUS-G4 — DELIVERABLE 02: TECHNICAL IMPLEMENTATION REPORT

## 1. Architectural Overview & Component Pipeline

Gate G4 implements an authenticated, modular data-and-inference architecture that connects canonical historical flight records to downstream operations research gate assignment solvers:

```
+---------------------------------------------------------------------------------------------------+
|                                 AEOLUS-G4 INTEGRATION ARCHITECTURE                                 |
+---------------------------------------------------------------------------------------------------+
|                                                                                                   |
|   1. Canonical Real Data (data/processed/inbound_atl, outbound_atl)                               |
|          |                                                                                        |
|          v                                                                                        |
|   2. RealDataLoader (src/data/real_data_loader.py)                                                |
|      - Mode: REAL_ONLY vs. ALLOW_SYNTHETIC                                                        |
|      - Schema verification (MANDATORY_INBOUND/OUTBOUND_COLUMNS)                                   |
|      - Date slice query (start_date, end_date)                                                    |
|          |                                                                                        |
|          v                                                                                        |
|   3. Canonical Time Audit (src/data/canonical_time.py)                                            |
|      - Typed parsing: ISO strings, HH:MM, HHMM numeric, 2400 rollover                         |
|      - IANA timezone normalization (America/New_York) -> UTC & timeline minutes                   |
|          |                                                                                        |
|          +-----------------------------------+-----------------------------------+                |
|          |                                                                       |                |
|          v                                                                       v                |
|   4A. Native Arrival ML Inference                     4B. Native Departure ML Inference           |
|       - Model: b5_ngboost_student_t (P4)                  - Model: departure_certified_point_v1   |
|       - Checkpoint: model_weights_frozen_v1.joblib        - Checkpoint: departure_xgboost_v1      |
|       - Cutoff: CRS_DEP_TIME - 2 hours                    - Preprocessor: departure_tree_prep_v1  |
|       - Predicts: mu, sigma, df (Student-t)               - Cutoff: CRS_DEP_TIME - 2 hours        |
|          |                                                                       |                |
|          +-----------------------------------+-----------------------------------+                |
|                                              |                                                    |
|                                              v                                                    |
|   5. Deterministic Aircraft Pairing (src/simulation/verified_pairing.py)                          |
|      - Strict Tail Matching (inbound.tail == outbound.tail)                                       |
|      - Hub Airport Verification (inbound.dest == ATL, outbound.origin == ATL)                     |
|      - Chronological Dwell: T_arr < T_dep, 45m <= Dwell <= 720m                                   |
|      - 1-to-1 Cardinality (Zero leg reuse)                                                        |
|      - Permutation Invariant (Lexicographical tie-breaking)                                       |
|      - Output: VERIFIED_PAIR / INFERRED_PAIR / UNMATCHED_ARR / UNMATCHED_DEP                      |
|                                              |                                                    |
|                                              v                                                    |
|   6. DualTurnEngine & RBAC Adapter (src/simulation/dual_prediction_turn.py, adapter.py)           |
|      - Synthesizes DualAircraftTurn & Flight domain entities                                      |
|      - Gate-in = Simulated Arrival; Gate-out = max(D_ml, D_min); Buffer added once                |
|                                              |                                                    |
|                                              v                                                    |
|   7. Multi-Solver Execution & Independent Verification (CPSat, Greedy, Hybrid)                    |
|      - Solves gate allocation over 20-50 contact gates + overflow stands                          |
|      - verify_hard_constraints_independently confirms 0 overlaps / 0 capacity violations          |
|                                              |                                                    |
|                                              v                                                    |
|   8. Comprehensive Artifact Export (run_manifest.json, predictions, turn_audit, optimization)     |
|                                                                                                   |
+---------------------------------------------------------------------------------------------------+
```

---

## 2. Technical Implementation by Task

### 2.1. Task G4.1: Canonical Datetime Normalization (`src/data/canonical_time.py`)
- **Key Functions:**
  - `parse_canonical_scheduled_time(raw_time)`: Handles heterogeneous inputs including string ISO timestamps (`"2023-11-23 07:05:00"`), HH:MM strings (`"07:05"`), integers (`705`), floats (`705.0`), and explicit rollover `"2400"` / `2400`. Normalizes `"2400"` to `(0, 0, True)`.
  - `parse_canonical_flight_date(raw_date)`: Extracts ISO date (`YYYY-MM-DD`) from date, datetime, or timestamp string.
  - `build_canonical_scheduled_datetime(raw_date, raw_time, airport_code, day_offset)`: Computes local datetime, looks up authenticated IANA timezone via `AIRPORT_IANA_TIMEZONES` (e.g. `America/New_York` for ATL), transforms to timezone-aware UTC, and computes integer timeline minutes from 00:00 of the service date.
- **Fail-Closed Guarantees:** Any missing value, invalid hours ($> 23$ unless 2400), invalid minutes ($> 59$), or unrecognizable airport code raises `InvalidDatetimeError` or `UnknownAirportTimezoneError`.

### 2.2. Task G4.2: Deterministic Verified Pairing (`src/simulation/verified_pairing.py`)
- **Pairing Invariants:**
  1. **Strict Aircraft Identity:** Requires non-empty, matching `tail_number` (normalized via `.strip().upper()`). If either leg lacks a verified tail number, the pair is never marked as `VERIFIED_ROTATION`.
  2. **Hub Monotonicity:** Arrival leg must terminate at hub (`dest == 'ATL'`), and departure leg must originate from hub (`origin == 'ATL'`).
  3. **Temporal Feasibility:** Scheduled arrival must strictly precede departure ($T_{\text{arr}} < T_{\text{dep}}$) with dwell duration satisfying:
     $$\text{min\_turnaround\_min} (45\text{m}) \le T_{\text{dep}} - T_{\text{arr}} \le \text{max\_turnaround\_min} (720\text{m})$$
  4. **1-to-1 Cardinality:** Each arrival leg and departure leg may belong to at most one turn.
  5. **Deterministic Candidate Tie-Breaking:** When multiple candidate departures share a tail with an arrival, candidates are sorted by `(normalized_timeline_min, flight_id)` and the earliest feasible departure is selected.
  6. **Permutation Invariance:** Input legs are sorted by `flight_id` prior to partitioning and grouping, ensuring that arbitrary DataFrame row shuffling yields identical pairings.
  7. **Zero Flight Leg Loss:** Legs that cannot be verified or inferred are classified as `UNMATCHED_ARR` or `UNMATCHED_DEP` and preserved as individual gate-occupying entities in the solver.

### 2.3. Task G4.3: Strict REAL_ONLY Data Loader (`src/data/real_data_loader.py`)
- **Loader Modes:**
  - `REAL_ONLY`: Strict production and research certification mode. Fails immediately on missing partition files (`MissingPartitionError`), empty date slices (`EmptyDateRangeError`), or missing schema columns (`SchemaContractViolation`). Never borrows adjacent dates and never falls back to synthetic fixtures.
  - `ALLOW_SYNTHETIC`: Designated exclusively for isolated unit/smoke tests with explicit `SYNTHETIC_PAIR` labeling.
- **Mandatory Schema Columns:**
  - Inbound: `FL_DATE`, `OP_CARRIER`, `OP_CARRIER_FL_NUM`, `ORIGIN`, `DEST`, `CRS_DEP_TIME`, `CRS_ARR_TIME`, `CRS_ELAPSED_TIME`.
  - Outbound: `FL_DATE`, `OP_CARRIER`, `OP_CARRIER_FL_NUM`, `ORIGIN`, `DEST`, `CRS_DEP_TIME`, `CRS_ARR_TIME`, `CRS_ELAPSED_TIME`.

### 2.4. Task G4.4: Cryptographic Native Inference Verification
- **Arrival Model (P4):**
  - Checkpoint: `artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib`
  - Expected SHA-256: `e7e7462f17b65b276ebdee9c7beced15e090f69b088a18896d5a91aaa8cb062f`
  - Calls `.predict_distribution(X_arr)` to extract location $\mu$, scale $\sigma > 0$, and degrees of freedom $\nu > 2$.
- **Departure Model (Core Departure):**
  - Model Checkpoint: `artifacts/dual_core/models/departure_xgboost_baseline_v1.joblib`
  - Model SHA-256: `e483df5fd03ce4d0eefe7b431fc289b6804589c62eda17b48fb8051849f4f6e1`
  - Preprocessor Checkpoint: `artifacts/dual_core/models/departure_tree_preprocessor_v1.joblib`
  - Preprocessor SHA-256: `ce2bb0f6f0e0ed650df3ae82306013360de5c0fafac5814307e99dfb69f62017`
  - Transforms raw departure features and executes native `.predict(X_dep_trans)`.

### 2.5. Task G4.5: Orchestrator Refactoring (`scripts/run_native_dual_core_pipeline.py`)
- Integrates `RealDataLoader` and `DeterministicPairingEngine`.
- CLI options:
  - `--loader-mode`: `REAL_ONLY` (default) or `ALLOW_SYNTHETIC`.
  - `--limit-flights`: Limit number of legs per direction (default: 50).
  - `--allow-inferred-pairing`: Flag to enable heuristic same-carrier turnaround matching without claiming verified status.
- Preserves full backward compatibility with legacy P07 test fixtures (`build_synthetic_canonical_data`).
