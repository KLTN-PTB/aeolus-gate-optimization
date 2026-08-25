# Limitations — current through Week 2

This project is deliberately scoped to the claims supported by the V3 protocol. The following limitations must remain visible in later reports, dashboard, and thesis materials.

- Future gate assignments and Aircraft Turns are synthetic constructs for controlled simulation; they are not real ATL gate operations or gate schedules.
- The project does not use or reconstruct real `TAIL_NUM` or other real aircraft identity. Synthetic identifiers, if later created, do not establish physical aircraft rotation.
- Flight Chain received a final Week-2 `NO_GO`: exact sample-to-Tabular mapping and T−2h safety are not evidenced, while 2024 also has an undocumented structural drift. Tabular-only is the core route; Chain remains limitation/future work.
- The Week-2 timing audit found insufficient point-in-time provenance for all six raw weather fields. The core pipeline therefore drops them from candidate `X` while retaining them in stored data; they cannot be promoted without new versioned T-2h evidence.
- The 2016–2024 Tabular schemas were audited year by year and canonical schema v1 is versioned; this does not justify assuming future/raw revisions remain compatible without re-audit.
- Canonical schema compatibility is a storage contract, not proof that every field is point-in-time safe or admissible as an ML predictor. `FLIGHTS` semantics remain unresolved and the field is blocked from candidate predictors.
- Year 2024 is sealed for final end-to-end evaluation after full-system freeze. It cannot be used for development, feature/model/HPO selection, pairing, gate configuration, solver settings, or robustness tuning.
- Future 100/200/300 movement scenarios are sampled/synthetic benchmarks, not representations of all ATL operations in a day.
- Optimizer outcomes address simulated gate-related consequences of delay; they do not demonstrate a reduction in real flight delay minutes.
- Source Chain train/val/test filenames are not the thesis temporal split and cannot replace the locked year-based protocol.

These limitations do not invalidate the planned study; they define the boundary for defensible interpretation.
