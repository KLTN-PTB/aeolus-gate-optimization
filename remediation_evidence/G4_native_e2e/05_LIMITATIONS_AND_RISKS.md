# AEOLUS-G4 — DELIVERABLE 05: METHODOLOGICAL LIMITATIONS AND OPERATIONAL RISKS

## 1. Executive Summary

Scientific integrity requires complete transparency regarding the empirical limitations of the underlying datasets and operational assumptions. While Gate G4 successfully eliminates fraudulent practices (such as row-index pairing, timestamp manipulation, and silent synthetic fallback), several intrinsic domain limitations must be documented for the undergraduate thesis defense and future engineering milestones.

---

## 2. Inherent Dataset Limitation: The Absence of `TAIL_NUM`

### 2.1. The Empirical Reality
- **Root Cause:** In the standard NeurIPS 2025 Aeolus curated dataset derived from BTS TranStats, the physical aircraft tail number field (`TAIL_NUM` / `tail_number`) was explicitly omitted by the original dataset authors during data reduction.
- **Verification Proof:** An exhaustive scan across all parquet partitions in `data/processed/` and raw CSV files in `data/raw/` confirms that `TAIL_NUM` is absent (0 occurrences).
- **Formal Architecture Decision:** Decision `D014` in `docs/decisions/decision_registry.md` explicitly locks:
  > *"D014: Do not use or reconstruct real `TAIL_NUM`/aircraft identity. `TURN_ID` and `SIM_AIRCRAFT_ID` are synthetic simulation identifiers only. LOCKED."*

### 2.2. Scientific Consequence for Aircraft Pairing
- In `REAL_ONLY` mode, without authenticated physical tail numbers, the deterministic pairing engine strictly refuses to fabricate tail numbers or use carrier flight numbers (`OP_CARRIER_FL_NUM`) as proxies.
- Consequently, on raw historical Aeolus data, **the number of authenticated `VERIFIED_ROTATION` turns is exactly 0**.
- Attempting to claim a positive verified turn count on this dataset without external tail feeds would constitute scientific fraud.
- Instead, each historical flight leg operates as an independent gate-occupying job (`UNMATCHED_ARR` or `UNMATCHED_DEP`) with realistic gate turnaround requirements (`default_dwell_minutes = 60m`).
- When heuristic same-carrier turnaround matching is explicitly authorized via `--allow-inferred-pairing`, turns are categorized strictly as `INFERRED_PAIR`, never as verified rotations.

---

## 3. Mathematical Distinction: Flight Legs vs. Aircraft Turns

A frequent source of confusion in prior documentation was the equivalence between flight legs and aircraft turns:
- **Flight Leg ($L$):** A single flight segment between an origin and destination airport (e.g., ORD $\to$ ATL is 1 arrival leg; ATL $\to$ LGA is 1 departure leg).
- **Aircraft Turn / Rotation ($T$):** The operational gate dwell session of an aircraft at the hub, linking an inbound leg to an outbound leg ($L_{\text{arr}} \to L_{\text{dep}}$).
- **Cardinality Relationship:**
  - For paired turns: $N_{\text{legs}} = 2 \times N_{\text{turns}}$. A scenario with 100 turns contains exactly 200 flight legs.
  - For unpaired legs: $N_{\text{legs}} = 1 \times N_{\text{turns}}$. Each inbound leg occupies the gate for $(A_{\text{sim}}, A_{\text{sim}} + T_{\text{dwell}} + B_{\text{buffer}})$.
- **Thesis Guidance:** The student must never report 100 legs as "100 turns" or vice-versa. In our Thanksgiving Day pilot, 200 real flight legs yielded 200 independent gate jobs (or 141 gate jobs under inferred pairing: 59 paired turns + 41 arrival turns + 41 departure turns).

---

## 4. Retrospective Rotation vs. Pre-Operational Dispatch

Even when tail numbers are present in historical aviation databases (e.g. raw BTS TranStats):
1. **The Tactical Aircraft Swap Hazard:** Airlines execute tactical aircraft swaps at hub airports (such as Delta at ATL) between $T-90$m and $T-30$m before departure to mitigate delay propagation.
2. **Survival Bias in Historical Data:** Historical BTS records report the airframe that *actually flew* the leg post-flight. Pairing based on historical post-flight tail numbers assumes that the flight dispatcher at $T-2$h knew with 100% certainty that no aircraft swap would occur.
3. **Operational Requirement:** A true production system requires a real-time airline dispatch operational feed (ACARS / OOD / Movement Message) frozen at the $T-2$h planning snapshot, rather than retrospective historical matching.

---

## 5. Solver Scalability Boundaries

| Solver Algorithm | Strengths | Operational Limitations & Scaling Hazards |
| :--- | :--- | :--- |
| **CP-SAT (Exact)** | Proven optimality, zero hard constraint violations. | Non-linear runtime growth. At 300+ flights over 50 gates, solving to optimality may exceed 30–60 seconds, requiring strict time limits ($5.0$–$10.0$s) and accepting feasible sub-optimal bounds. |
| **Greedy (Heuristic)** | Microsecond execution ($< 50$ms), predictable linear time. | Myopic decision-making. Can lead to higher remote apron overflow assignments if early flights take optimal contact gates. |
| **Hybrid (Greedy + CP-SAT / SA)** | Balances fast initial assignment with tactical optimization. | Parameter tuning required (neighborhood size, temperature schedule). |

---

## 6. Recommendations for Thesis Defense

1. **Acknowledge Data Bounds Honestly:**
   Present the absence of `TAIL_NUM` in Aeolus as a notable finding of the forensic audit, citing Decision `D014` and NeurIPS 2025 data provenance.
2. **Defend the Gate Job Formulation:**
   Explain that modeling flights as independent arrival and departure gate jobs is standard hub operations practice when airframe rotations are uncoupled, ensuring 100% causal reproducibility.
3. **Highlight Zero Constraint Violations:**
   Emphasize that the optimization engine achieves 0 hard constraint violations and optimal objective values across all real-data pilot runs.
