# Decision — Include Flight Chain

Decision date: 2026-08-23  
Decision owner: Week-2 feasibility gate  
Status: **FINAL — NO_GO**

## Decision

Flight Chain is excluded from the core project and from the Week-6 ablation. The project proceeds on the **Tabular-only** core route.

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

1. Tabular-only becomes the final core route.
2. `src/features/chain_context.py` must not be implemented in Week 3.
3. Week 6 will not run a Tabular-plus-Chain ablation.
4. Flight Chain remains a documented limitation/future-work direction.
5. Raw Chain files remain read-only and are retained unchanged.
6. The `.pt` split names never replace the locked year-based temporal manifests.

## Change control

Reopening requires new, versioned primary evidence for exact mapping, feature semantics, point-in-time availability at T−2h, leakage isolation, and cross-year reproducibility. Update the decision registry first and assess roadmap/config/code/test/report impact. Never reopen or change this decision based on 2024 performance.
