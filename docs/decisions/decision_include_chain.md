# Decision — Include Flight Chain

Decision date: 2026-08-23  
Decision owner: Week-2 feasibility gate  
Status: **FINAL — NO_GO**

## Decision

The original Aeolus raw Flight Chain `.pt` is excluded from the core project
and from every ablation. This evidence decision applies only to the raw
archives. The project proceeds without raw-Chain features.

## Evidence

- Bounded structural audit of 27/27 raw archives: `artifacts/manifests/flight_chain_structure_audit_v1.json`.
- Final evidence report: `docs/dataset_audit/flight_chain_feasibility_report.md`.
- Official construction source pinned at commit `6d10cab7a5d542733ff6a8b88d1ab4d4f98b1c6f`.
- Canonical schema v1, data dictionary v1, T−2h leakage/weather audits, and locked temporal manifests.

The available source documents a five-tensor layout for 2016–2023-like archives, but the archives persist no exact row/sample-to-Tabular mapping or encoder mappings. Their dense block includes weather fields excluded by the completed timing audit and unresolved `FLIGHTS`; separate tensors include source labels and realized delays. The source uses strict `>15`, not the locked `>=15` classification rule. All three 2024 archives have a different four-tensor signature without matching construction documentation.

The dataset does **not** prove `TAIL_NUM`, aircraft registration, same physical aircraft, or aircraft rotation.

## Rationale

D004 permits GO only when semantics, mapping, T−2h safety, leakage control, and reproducibility are supported by evidence. Current evidence fails every complete-GO gate: semantics are incomplete across years, exact mapping is absent, target-relative timing cannot be enforced, unsafe/outcome fields coexist in the container, and the 2024 structure drifts. Missing evidence therefore resolves to NO_GO, not an assumed safe mapping.

## Downstream impact

1. Raw-Chain features never enter the core or an ablation.
2. No feature module may load or reverse-engineer the raw `.pt` archives.
3. Week 6 will not run any ablation using the original raw Chain.
4. The original raw Flight Chain remains a documented limitation/future-work direction.
5. Raw Chain files remain read-only and are retained unchanged.
6. The `.pt` split names never replace the locked year-based temporal manifests.

## Change control

Reopening requires new, versioned primary evidence for exact mapping, feature semantics, point-in-time availability at T−2h, leakage isolation, and cross-year reproducibility. Update the decision registry first and assess roadmap/config/code/test/report impact. Never reopen or change this decision based on 2024 performance.

## V4 clarification — 2026-08-26

E003 remains `FINAL — NO_GO`. A different artifact reconstructed from
canonical Tabular, `schedule_chain_v1`, subsequently passed full 2016–2023
validation under E005 and is `GO_FOR_ABLATION`. Its planned Week-6 comparison
uses only `reconstructed_chain_features_v1`; it does not reopen, map, or reuse
the original `.pt` archives and it does not claim physical aircraft rotation.
