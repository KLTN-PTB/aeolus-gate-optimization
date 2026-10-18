# AEOLUS-G4 — DELIVERABLE 07: DETERMINISTIC PAIRING RULES AND AUDIT

## 1. Specification of Pairing Rules & Operational Contracts

Aircraft turn pairing links an inbound arrival leg ($L_{\text{arr}}$) to an outbound departure leg ($L_{\text{dep}}$) at a hub airport gate. In Gate G4, pairing is strictly governed by deterministic mathematical contracts.

---

## 2. Minimum Conditions for `VERIFIED_ROTATION`

A candidate pair $(L_{\text{arr}}, L_{\text{dep}})$ is classified as `VERIFIED_ROTATION` (or `PairType.VERIFIED_PAIR`) **if and only if** all of the following conditions are simultaneously satisfied:

1. **Authenticated Physical Tail Match:**
   $$\text{tail}(L_{\text{arr}}) \neq \emptyset \land \text{tail}(L_{\text{dep}}) \neq \emptyset \land \text{norm}(\text{tail}(L_{\text{arr}})) = \text{norm}(\text{tail}(L_{\text{dep}}))$$
   Both legs must possess a non-empty, valid physical airframe registration string. String matching is case-insensitive and whitespace-stripped.
2. **Hub Connection Verification:**
   $$\text{dest}(L_{\text{arr}}) = \text{hub\_airport} \land \text{origin}(L_{\text{dep}}) = \text{hub\_airport} \quad (\text{ATL})$$
3. **Strict Chronological Monotonicity:**
   $$T_{\text{arr}} < T_{\text{dep}}$$
   Scheduled arrival must strictly precede scheduled departure in monotonic timeline minutes.
4. **Physical Turnaround Bounds:**
   $$\text{min\_turnaround\_min} \le T_{\text{dep}} - T_{\text{arr}} \le \text{max\_turnaround\_min}$$
   Default research parameters: $\text{min\_turnaround\_min} = 45$ minutes; $\text{max\_turnaround\_min} = 720$ minutes (12 hours).
5. **1-to-1 Cardinality (Zero Leg Reuse):**
   $$\forall i \neq j: L_{\text{arr}}^{(i)} \neq L_{\text{arr}}^{(j)} \land L_{\text{dep}}^{(i)} \neq L_{\text{dep}}^{(j)}$$
   No arrival leg and no departure leg may belong to more than one turn.

If any condition fails, the candidate pair **cannot** be classified as a verified rotation.

---

## 3. Pairing Classification Hierarchy

```
+--------------------------------------------------------------------------------------------------+
|                                  PAIRING CLASSIFICATION TAXONOMY                                 |
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|   Candidate Leg Ingestion                                                                        |
|          |                                                                                       |
|          +--> Do both legs possess authenticated matching physical TAIL_NUM?                     |
|          |    |                                                                                  |
|          |    +-- YES --> Satisfies chronological & min turnaround bounds?                       |
|          |    |           |                                                                      |
|          |    |           +-- YES --> [VERIFIED_ROTATION / VERIFIED_PAIR]                        |
|          |    |           +-- NO  --> [QUARANTINED / REJECTED]                                   |
|          |    |                                                                                  |
|          |    +-- NO (tail missing / unauthenticated):                                           |
|          |        |                                                                              |
|          |        +-- Is --allow-inferred-pairing enabled?                                       |
|          |            |                                                                          |
|          |            +-- YES --> Same carrier + 45m <= Dwell <= 180m?                           |
|          |            |           |                                                              |
|          |            |           +-- YES --> [INFERRED_PAIR] (Heuristic schedule linkage)       |
|          |            |           +-- NO  --> [UNMATCHED_ARR / UNMATCHED_DEP]                    |
|          |            |                                                                          |
|          |            +-- NO  --> [UNMATCHED_ARR / UNMATCHED_DEP] (Individual gate jobs)        |
|          |                                                                                       |
|          +--> Synthetic fixture / simulation session? --> [SYNTHETIC_PAIR]                      |
|                                                                                                  |
+--------------------------------------------------------------------------------------------------+
```

---

## 4. Deterministic Candidate Tie-Breaking Algorithm

When an arrival leg $L_{\text{arr}}$ has multiple feasible departure candidates sharing the same tail number:
1. Candidate departures are sorted in ascending order by scheduled departure minute:
   $$\text{candidates} = \text{sort}(L_{\text{dep}}, \text{key}=(T_{\text{dep}}, \text{flight\_id}))$$
2. The engine greedily selects the earliest feasible departure satisfying $T_{\text{dep}} \ge T_{\text{arr}} + 45$m.
3. If two candidates have the exact same departure minute, lexicographical sorting on `flight_id` breaks the tie deterministically.
4. Input legs are pre-sorted by `flight_id`, guaranteeing that DataFrame row shuffling has zero effect on matching outcomes (Permutation Invariance).

---

## 5. Timeline Synthesis & Operational Formulas

For any synthesized turn:
- **Simulated Arrival:** $A_{\text{sim}} = \text{round}(A_{\text{sched}} + \hat{y}_{\text{arr}})$
- **ML Pushback Time:** $D_{\text{ml}} = \text{round}(D_{\text{sched}} + \hat{y}_{\text{dep}})$
- **Earliest Physical Departure:** $D_{\text{min}} = A_{\text{sim}} + T_{\text{turnaround\_min}}$
- **Simulated Gate Departure:** $D_{\text{sim}} = \max(D_{\text{ml}}, D_{\text{min}})$
- **Gate Release Time:** $\text{Gate\_release} = D_{\text{sim}} + B_{\text{buffer}}$
- **Gate Occupancy Window:** $[A_{\text{sim}}, \text{Gate\_release})$ (half-open interval).

---

## 6. Code Comparison: Legacy P07 vs. Remediated G4

### Legacy P07 Implementation (Flawed):
```python
# scripts/run_native_dual_core_pipeline.py (legacy P07)
for i in range(n_pairs):
    in_row = inbound_df.iloc[i]   # Arbitrary row index!
    out_row = outbound_df.iloc[i] # Arbitrary row index!
    
    # Forced feasibility via schedule mutation!
    if dep_clock_min <= arr_clock_min + 45:
        dep_clock_min = arr_clock_min + 75  # Overwrote real timetable!
    
    # Conflated flight number with tail number!
    tail_in = in_row.get("TAIL_NUM") or in_row.get("OP_CARRIER_FL_NUM")
```

### Remediated G4 Implementation (`src/simulation/verified_pairing.py`):
```python
# Pre-sort to guarantee permutation invariance
sorted_leg_ids = sorted(legs.keys())

# Strict grouping by authenticated airframe tail
for dep_leg in dep_candidates:
    dwell = dep_leg.normalized_timeline_min - arr_leg.normalized_timeline_min
    if min_turnaround_min <= dwell <= max_turnaround_min:
        best_dep = dep_leg
        break  # Earliest feasible chosen deterministically

# Zero schedule modification; real timetables preserved 100%
# Transparent classification: VERIFIED_PAIR vs INFERRED_PAIR vs UNMATCHED
```
