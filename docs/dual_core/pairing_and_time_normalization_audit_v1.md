# Phase P6 — Aeolus Time Normalization & Arrival-Departure Pairing Audit Report

**System**: Aeolus Dual Core Gate Optimization System  
**Protocol**: Dual Core Architecture Protocol V2 (`ModelTask.CORE_ARRIVAL` & `ModelTask.CORE_DEPARTURE`)  
**Phase**: P6 — Time Normalization & Arrival-Departure Pairing  
**Date**: October 8, 2026  
**Auditor / Engineer**: Aviation Data Engineer & Operations Research Engineer  
**Quality Gate Verdict**: **`PASS` (Synthetic Fixture Certified; Real-Data Turn Scheduling BLOCKED)**  

---

## 1. Executive Summary & Architecture Context

The Aeolus pipeline operates across four stages: **Predict $\to$ Simulate $\to$ Optimize $\to$ Evaluate**.
- **Core Arrival** predicts signed arrival delay (`ARR_DELAY`) at cutoff $T - 2\text{h}$ for inbound flights (`DEST = ATL`).
- **Core Departure** predicts signed departure delay (`DEP_DELAY`) at cutoff $T - 2\text{h}$ for outbound flights (`ORIGIN = ATL`).
- **Downstream Gate Optimization** allocates flights to physical gates over continuous gate occupancy time intervals $[A_{\text{gate\_in}}, D_{\text{gate\_out}} + \text{buffer}]$.

### The Physical Aircraft Identity Gap in Historical Data
A fundamental data audit finding confirmed in P1 and re-verified here: **The canonical BTS dataset does NOT contain authenticated physical aircraft airframe identifiers (`TAIL_NUM`)**.
- `flight_key` is merely a row identifier.
- BTS schedule flight chains (`chain_id` / `chain_group_id`) are reconstructed schedule heuristics, not proof that two flights are operated by the exact same physical airframe.
- Airlines frequently swap tails due to maintenance, flow management, or delays.
- Therefore, historical BTS data cannot be naively paired into real-world aircraft turns without verified rotation tracking.

### Ground Truth vs. Synthetic Simulation Fixture
The schedule file [`atl_1500_flights_cpsat_turnaround_schedule.csv`](file:///D:/Study/Code/Python/Aelous/src/artifacts/predictions/atl_1500_flights_cpsat_turnaround_schedule.csv) is a **synthetic simulation fixture**, not ground truth historical training data:
- It models 1,500 flight operations (745 arrivals and 755 departures).
- It provides simulated sessions (`session_id`) and simulated aircraft identities (`sim_aircraft_id`).
- All pairings derived from it are strictly classified as `SYNTHETIC_PAIR` and must **never** be promoted to `VERIFIED_PAIR`.

---

## 2. Core Contracts & Data Entities

The contracts implemented in [`src/contracts/turn_contracts.py`](file:///D:/Study/Code/Python/Aelous/src/contracts/turn_contracts.py) enforce immutable, audit-safe structures:

### 2.1 `FlightLeg`
Immutable representation of a single flight event with strict temporal and provenance tracking:
- `flight_id`: Canonical record identifier.
- `direction`: `LegDirection.ARR` or `LegDirection.DEP`.
- `carrier`, `flight_number`, `origin`, `destination`.
- `scheduled_event_local`: Timezone-aware local datetime.
- `scheduled_event_utc`: Converted UTC datetime.
- `event_timezone`: Authenticated IANA timezone identifier (e.g. `America/New_York`).
- `scheduled_elapsed_min`: Official planned duration (`CRS_ELAPSED_TIME`).
- `model_prediction_cutoff_utc`: Cutoff timestamp (e.g. $T - 2\text{h}$ in UTC).
- `planning_snapshot_at_utc`: Decision epoch when the schedule/planning window was frozen.
- `prediction_generated_at_utc`: Exact timestamp when the ML prediction was materialized.
- `prediction_provenance`: Identifies the originating model and experiment.
- `scenario_id` & `session_id`: Synthetic fixture provenance.
- `aircraft_type`: Equipment class (`NARROWBODY`, `WIDEBODY`, `REGIONAL`).
- `tail_number`: Authenticated airframe identifier (None if unverified).
- `normalized_timeline_min`: Integer elapsed minutes from reference epoch.

### 2.2 `TurnPair`
Immutable representation of an aircraft turn at a hub gate:
- `pair_id`: Unique identifier.
- `arrival_leg_id`: Inbound arrival leg ID (or None for `UNMATCHED_DEP`).
- `departure_leg_id`: Outbound departure leg ID (or None for `UNMATCHED_ARR`).
- `pair_type`:
  - `VERIFIED_PAIR`: Permitted ONLY when authenticated airframe tracking is present.
  - `SYNTHETIC_PAIR`: Established by simulation session or scenario generator.
  - `UNMATCHED_ARR`: Arrival without associated outbound flight.
  - `UNMATCHED_DEP`: Departure without associated inbound flight.
- `linkage_source`: `VERIFIED_ROTATION`, `SIMULATION_SESSION`, `SCHEDULE_CHAIN_HEURISTIC`, `UNPAIRED`.
- `validation_status`: `VALID`, `INVALID`, `REVIEW_REQUIRED`, `QUARANTINED`.
- `scheduled_turnaround_min`: Scheduled ground buffer ($D_{\text{sched}} - A_{\text{sched}}$).
- `evidence_metadata`: Auditable dictionary storing linkage evidence.
- `rejection_reasons`: Tuple of specific invariant violation messages.

---

## 3. Time Normalization Architecture

The time normalization engine implemented in [`src/data/time_normalization.py`](file:///D:/Study/Code/Python/Aelous/src/data/time_normalization.py) resolves local wall-clock anomalies:

### 3.1 Authenticated Airport IANA Timezones
- ATL operates on **`America/New_York`** (US Eastern Time: EST $\text{UTC}-5$, EDT $\text{UTC}-4$).
- A comprehensive mapping covering all 147 airports in the CPSAT turnaround fixture and canonical domestic dataset is verified via Python's standard `zoneinfo` module.
- **Fail-Closed Lookup**: Unrecognized airport codes raise `UnknownAirportTimezoneError`. Default timezone assumptions are strictly forbidden.

### 3.2 Daylight Saving Time (DST) Anomaly Guards
- **DST Spring-Forward Gap (Nonexistent Clock Time)**:
  - On the second Sunday of March, local clocks jump from 01:59:59 to 03:00:00.
  - Times such as `2024-03-10 02:30:00` do not exist.
  - The engine detects roundtrip wall-clock mismatches and raises `DSTGapError`.
- **DST Fall-Back Fold (Ambiguous Clock Time)**:
  - On the first Sunday of November, the 01:00:00–01:59:59 hour occurs twice (EDT then EST).
  - The engine flags ambiguous times (`is_dst_ambiguous = True`) and requires explicit fold disambiguation (`fold=0` for daylight time, `fold=1` for standard time).

### 3.3 Overnight Flights & Day Rollover Reconciliation
- Naive subtraction $\Delta t = \text{CRS\_ARR\_TIME} - \text{CRS\_DEP\_TIME}$ is **strictly prohibited** because canonical data stores dates mapped to `FL_DATE` without timezone conversion.
- **Causal UTC Reconciliation**:
  $$T_{\text{dep,utc}} = \text{to\_utc}(T_{\text{dep,local}}, \text{tz}_{\text{origin}})$$
  $$T_{\text{arr,utc}} = T_{\text{dep,utc}} + \text{timedelta}(\text{minutes}=\text{CRS\_ELAPSED\_TIME})$$
  $$T_{\text{arr,local}} = T_{\text{arr,utc}}.\text{astimezone}(\text{tz}_{\text{dest}})$$
  $$\text{is\_overnight} = T_{\text{arr,local}}.\text{date}() > T_{\text{dep,local}}.\text{date}()$$
- If raw `CRS_ARR_TIME` diverges from the causally computed arrival by $> 30$ minutes, or if `CRS_ELAPSED_TIME` is missing, the record is flagged as **`REVIEW_REQUIRED`**.

### 3.4 Operational Temporal Causality Firewall
To prevent lookahead leakage into optimization decisions:
1. **Planning Snapshot Rule**:
   $$T_{\text{prediction\_generated\_utc}} \le T_{\text{planning\_snapshot\_utc}}$$
   A prediction generated after the gate planning snapshot cannot be treated as known prior to that decision.
2. **Cutoff Rule**:
   $$T_{\text{model\_prediction\_cutoff\_utc}} \le T_{\text{scheduled\_event\_utc}}$$
   Cutoff must precede the operational event.

---

## 4. Pairing Validator & Business Invariants

The [`PairingValidator`](file:///D:/Study/Code/Python/Aelous/src/data/pairing_validator.py) audits and enforces strict operational rules:

1. **Strict 1-to-1 Cardinality**:
   - Each flight leg may participate in at most **one** turn pair.
   - Many-to-one (multiple arrivals mapped to one departure) and one-to-many (one arrival mapped to multiple departures) are rejected with `CARDINALITY_VIOLATION`.
2. **Unique Pair Identifiers**:
   - Pair IDs must be globally unique across the schedule.
3. **Chronological Monotonicity at the Gate**:
   - For an aircraft turn at ATL, the arrival must precede the departure:
     $$T_{\text{arr,utc}} \le T_{\text{dep,utc}}$$
   - Chronological reversals ($T_{\text{dep}} < T_{\text{arr}}$) or negative turnaround durations are rejected with `CHRONOLOGICAL_REVERSAL_DEP_BEFORE_ARR`.
4. **Airframe Evidence Guard**:
   - Promoting pairs to `PairType.VERIFIED_PAIR` requires matching verified `tail_number` values and `LinkageSource.VERIFIED_ROTATION`.
   - Pairs lacking physical tail authentication are quarantined with `UNVERIFIED_AIRCRAFT_EVIDENCE_FOR_VERIFIED_PAIR`.
5. **Prohibited Pairing Heuristics**:
   - Pairing purely by `flight_number` is forbidden (flight numbers are reused across airframes).
   - Pairing purely by `chain_id` is forbidden (schedule chains are synthetic).
   - Pairing purely by temporal proximity is forbidden (coincidental time alignment is not aircraft continuity).
6. **Synthetic Scenario Governance**:
   - Every `SYNTHETIC_PAIR` must declare an explicit `scenario_id` or `session_id`.

---

## 5. Audit Results: `atl_1500_flights_cpsat_turnaround_schedule.csv`

We conducted an automated audit of the 1,500-flight CPSAT turnaround fixture using [`validate_cpsat_turnaround_schedule_csv`](file:///D:/Study/Code/Python/Aelous/src/data/pairing_validator.py):

| Metric / Check | Value / Result | Audit Verdict |
| :--- | :---: | :---: |
| **Total Input Records** | 1,500 | Exactly conforms to fixture specification |
| **Arrival Legs (ARR)** | 745 | Exactly conforms ($49.67\%$) |
| **Departure Legs (DEP)** | 755 | Exactly conforms ($50.33\%$) |
| **PAIRED_TURN Records** | 1,298 | 649 distinct 2-leg sessions |
| **UNMATCHED_ARR Records** | 96 | 96 single-leg arrival sessions |
| **UNMATCHED_DEP Records** | 106 | 106 single-leg departure sessions |
| **Total Turn Pairs Formed** | **851** | $649 + 96 + 106 = 851$ |
| **Synthetic Pairs Count** | **649** | All 649 turns classified strictly as `SYNTHETIC_PAIR` |
| **Verified Pairs Count** | **0** | **Zero false promotion to `VERIFIED_PAIR`** |
| **Valid Pairs** | **851** | 100% of constructed pairs pass validation |
| **Invalid Pairs** | **0** | Zero schema, reversal, or cardinality errors |
| **Quarantined Pairs** | **0** | No unverified claims |
| **Cardinality Violations** | 0 | Perfect 1-to-1 matching across all legs |
| **Chronological Reversals** | 0 | All arrivals strictly precede departures |
| **Overall Dataset Cleanliness** | **True** | **PASS** |

### Leakage Quarantine of Simulation Outputs
The fixture CSV contains several columns generated during downstream simulation:
- `actual_delay_min`, `actual_time_min`, `actual_deviation_str`
- `p_delay`, `p_delay_pct`, `delay_est_min`, `effective_delay_min`
- `assigned_gate`, `evaluation_status`, `buffer_margin_min`, `is_covered_by_gate_window`

**Firewall Policy**: These fields represent simulation realization and solver assignment outcomes. They are strictly quarantined in `raw_metadata` and are **prohibited from being used as ML features** in either Core Arrival or Core Departure models.

### Gate Topology Caution
The fixture contains gate strings ranging from `G01` to `G165`. **This does NOT imply that ATL has 50 physical contact gates**. The number and topology of gates are determined strictly by airport layout specifications in Phase P7, not by gate label frequency in this simulation fixture.

---

## 6. Test Suite & Verification Matrix

The test suite in [`tests/test_pairing_and_time_normalization.py`](file:///D:/Study/Code/Python/Aelous/tests/test_pairing_and_time_normalization.py) contains 18 comprehensive tests covering all required fixtures and failure modes:

| Test Case | Scenario / Fixture | Expected Behavior | Result |
| :--- | :--- | :--- | :---: |
| `test_airport_timezone_lookup` | Major hubs (ATL, ORD, DEN, LAX, HNL, SJU) | Accurate IANA timezone string | **PASS** |
| `test_unknown_airport_fails_closed` | Airport code `'ZZZ'` | Raises `UnknownAirportTimezoneError` | **PASS** |
| `test_dst_spring_forward_gap_rejection` | Spring-forward nonexistent time (02:30 EDT) | Raises `DSTGapError` | **PASS** |
| `test_dst_fall_back_fold_detected` | Fall-back ambiguous time (01:30) | Flags ambiguous, tests 1-hour fold delta | **PASS** |
| `test_parse_hhmm_time` | Various HHMM representations (int, str, colon) | Accurate (hour, minute), rejects invalid | **PASS** |
| `test_overnight_flight_reconciliation` | Late ATL departure (22:30 EDT) to SEA (Pacific) | Accurately identifies day rollover (+1 day) | **PASS** |
| `test_normalized_timeline_minutes` | Reference UTC epoch alignment | Accurate integer minute calculation | **PASS** |
| `test_normal_sameday_pair` | Standard arrival $\to$ departure same day | Valid `SYNTHETIC_PAIR`, turnaround = 90m | **PASS** |
| `test_overnight_pair` | Late arrival (23:30) $\to$ morning departure (06:30) | Valid `SYNTHETIC_PAIR`, turnaround = 420m | **PASS** |
| `test_different_timezones_conversion` | SEA (Pacific) $\to$ ATL (Eastern) $\to$ ORD (Central) | Correct UTC alignment, turnaround = 90m | **PASS** |
| `test_duplicate_pair_id_rejected` | Two pairs with identical `pair_id` | Both marked `INVALID` (`DUPLICATE_PAIR_ID`) | **PASS** |
| `test_many_to_one_and_one_to_many_rejected` | One ARR mapped to two DEPs | Both marked `INVALID` (`CARDINALITY_VIOLATION`) | **PASS** |
| `test_dep_before_arr_chronological_reversal_rejected` | DEP scheduled before ARR at gate | Marked `INVALID` (`CHRONOLOGICAL_REVERSAL`) | **PASS** |
| `test_unmatched_arr_and_unmatched_dep` | Single-leg arrival and single-leg departure | Correctly classified, valid | **PASS** |
| `test_missing_aircraft_evidence_quarantines_verified_label` | `VERIFIED_PAIR` with no tail numbers | Quarantined (`UNVERIFIED_AIRCRAFT_EVIDENCE`) | **PASS** |
| `test_verified_pair_succeeds_with_authenticated_tail` | Verified tail `'N999DL'` on both legs | Valid `VERIFIED_PAIR` | **PASS** |
| `test_prediction_generated_after_planning_snapshot_rejected` | Prediction generated at $T_{gen} > T_{snapshot}$ | Marked `INVALID` (`PREDICTION_POSTDATES_SNAPSHOT`) | **PASS** |
| `test_cpsat_fixture_audit` | Full CSV `atl_1500_flights_cpsat_turnaround_schedule.csv` | Exactly 1500 legs, 851 pairs, clean=True | **PASS** |

**Full Project Regression Suite**: Running the complete test suite across all modules (`pytest tests/test_pairing_and_time_normalization.py tests/test_departure_probabilistic_models.py tests/test_departure_point_training.py tests/test_departure_preprocessing.py tests/test_core_departure_contracts.py tests/test_r27_certification_hardening.py -v`) yields **117 PASSED, 0 FAILED** in 6.99 seconds.

---

## 7. Quality Gate Assessment & Downstream Boundary Statement

### Quality Gate Checkpoints:
1. **Ambiguous Pairs**: Zero ambiguous pairs accepted silently. All unproven pairs are quarantined or classified as synthetic.
2. **Cardinality Safety**: Zero legs reused across multiple turns.
3. **Timestamp Integrity**: Unverified arrival timestamps are marked `REVIEW_REQUIRED`. All timezones resolved to IANA standards.
4. **DST Safety**: Both spring-forward gaps and fall-back folds explicitly handled and tested.
5. **Class Distinction**: `VERIFIED_PAIR`, `SYNTHETIC_PAIR`, `UNMATCHED_ARR`, and `UNMATCHED_DEP` strictly separated.
6. **Model Protection**: Core Arrival and Core Departure models and checkpoints remain 100% frozen and untouched.

### Operational Boundary Decision:
> [!IMPORTANT]
> **REAL-DATA SCHEDULING STATUS**: **`BLOCKED`**  
> Because canonical historical BTS records lack authenticated aircraft tail numbers (`TAIL_NUM`), real-data turn scheduling cannot be certified for operational gate assignment without external airframe rotation records.
> 
> **DOWNSTREAM SIMULATION STATUS**: **`PASS` (CERTIFIED FOR PHASE P7)**  
> Phase P7 (Downstream Simulation & Joint Turn Coupling) is authorized to proceed using synthetic scenario fixtures (including the audited 1,500-flight schedule fixture) where timeline and session boundaries are explicitly defined.
> 
> **EXECUTION DIRECTIVE**: STOPPING IMMEDIATELY AFTER PHASE P6.
