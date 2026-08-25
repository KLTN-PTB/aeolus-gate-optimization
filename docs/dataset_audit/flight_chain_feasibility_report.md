# Flight Chain Final Feasibility Report — Week 2

Audit date: 2026-08-23  
Decision: **NO_GO**  
Scope: structural and provenance feasibility only; no model training or performance access.

This report supersedes the provisional conclusion in `flight_chain_feasibility_v0.md`. Flight Chain remains raw, read-only evidence, but it is not included in the core project route.

## Evidence inspected

1. All 27 local archives under `data/raw/chain/<2016-2024>/`, one file at a time, using `src/data/chain_inspection.py`.
2. The ZIP central directory and the small `data.pkl` member only. No tensor storage member was opened, extracted, or deserialized.
3. Generated evidence: `artifacts/manifests/flight_chain_structure_audit_v1.json`.
4. The three synchronized V3 roadmaps, canonical schema v1, data dictionary v1, leakage/weather audits, and temporal manifests.
5. Official Aeolus preprocessing source, [`Datasets/Flight_chain.py`](https://github.com/Flnny/Delay-data/blob/6d10cab7a5d542733ff6a8b88d1ab4d4f98b1c6f/Datasets/Flight_chain.py), pinned to commit `6d10cab7a5d542733ff6a8b88d1ab4d4f98b1c6f` dated 2025-07-29.

The official source is evidence for its documented construction logic. It is not assumed to be the exact producer of every local archive when the observed archive structure contradicts it.

## Resource and safety boundary

| Check | Result |
|---|---|
| Files inspected | 27/27; train/val/test for every year 2016–2024 |
| Total source bytes represented | 13,751,334,923 |
| Processing mode | Sequential, one archive at a time |
| Maximum metadata pickle read per archive | 535 bytes observed; hard limit 65,536 bytes |
| Tensor storage payload read | 0 bytes |
| `torch.load` | Not used |
| Raw file write/re-serialization | Not performed |
| 2024 purpose | `schema_audit` only; logged in `week2_2024_access_log.json` |
| Model/performance access | Not performed |

## Feature semantics

For 2016–2023, the five observed tensor positions match the five objects created by the pinned official source:

| Position | Observed shape/dtype | Source-defined meaning | Feasibility finding |
|---|---|---|---|
| 0 | `(N, 6, 7)`, `float32` | `O_TEMP`, `D_TEMP`, `O_PRCP`, `D_PRCP`, `O_WSPD`, `D_WSPD`, `FLIGHTS` | All weather fields are excluded by E002; `FLIGHTS` remains unresolved under T002. This tensor is not a safe core predictor block. |
| 1 | `(N, 6, 8)`, `int16` | `MONTH`, `DAY_OF_WEEK`, scheduled arrival/departure hour, `ORIGIN_INDEX`, `DEST_INDEX`, encoded carrier, encoded flight number | Names are documented, but per-year encoders and mappings are not stored with the archives. |
| 2 | `(N, 6, 2)`, `int8` | Arrival/departure delay labels using strict `> 15` | Direct outcome labels. The arrival definition conflicts with core D009, which is `ARR_DELAY >= 15`. |
| 3 | `(N,)`, `int64` | Valid sequence length | Structural metadata only. |
| 4 | `(N, 6, 2)`, `int16` | Signed actual arrival/departure delays | Direct realized outcomes; prohibited from candidate predictors. |

The source groups rows by encoded carrier, encoded flight number, and date; sorts within a group by scheduled departure time; then truncates/pads to length six. It does not save feature names, group keys, source row ordinals, dates, complete timestamps, encoder mappings, or a sample-to-Tabular map in the `.pt` output.

For 2024, all three archives instead contain four tensors:

- `(N, 6, 7)` `float32`
- `(N, 6, 8)` `float32`
- `(N, 6)` `float32`
- `(N,)` `int64`

Because this signature differs from the five-tensor output in the inspected official source, the meaning of the changed/removed positions is **not documented by the available evidence**. No semantic label was inferred from shape or values.

## Mapping evidence

**Result: NOT SUPPORTED.**

The archives contain no `flight_key`, source row number, source filename, original group key, date, complete scheduled timestamp, or mapping table. The official construction code also does not persist these values. Carrier and flight-number values are encoded independently per year, and the fitted encoder mappings are not saved.

Reconstructing links from tensor values, shape similarity, or correlations would be heuristic reverse engineering. Re-running a presumed source pipeline cannot validate an exact mapping for the existing archives—especially because the 2024 archive signature and filename order differ from the inspected source output. Therefore a row/sample ↔ canonical Tabular flight mapping cannot be established reproducibly from current evidence.

The dataset does **not** prove `TAIL_NUM`, aircraft registration, same physical aircraft, or aircraft rotation. The source grouping rule is insufficient evidence for any of those identities.

## Temporal safety

**Result: NOT SUPPORTED at `T_cutoff = CRS_DEP_TIME - 2 hours`.**

- The archive does not store the target flight's complete scheduled timestamp or an information-availability timestamp for each context value.
- Six dense fields fail the completed weather timing audit; `FLIGHTS` remains semantically and temporally unresolved.
- Outcome label/delay tensors coexist in the same container and require explicit isolation.
- The source train/validation/test split randomly assigns days within each month using seed 42. These splits are not and cannot replace the locked expanding-year protocol.
- The absence of an exact canonical flight map prevents enforcing target-relative T−2h filtering reproducibly.

Scheduled fields in one tensor may be individually pre-flight information, but that is insufficient to make the archive or a derived context transformation temporally safe.

## Leakage risks

| Risk | Evidence | Status |
|---|---|---|
| Direct targets/outcomes | 2016–2023 tensors include binary labels and signed actual delays | Critical; must never enter `X` |
| Threshold mismatch | Source uses strict `>15`; core contract uses `>=15` | Incompatible source label |
| Weather look-ahead/provenance | Six weather values have no proven T−2h availability | Unsafe; core DROP |
| Unknown aggregate | `FLIGHTS` semantics/timing unresolved | Unsafe by default |
| Mapping leakage control | No sample-to-canonical-flight mapping | Cannot verify target-relative isolation |
| 2024 semantics | Structure differs and no matching construction documentation was found | Insufficient evidence |

## Cross-year findings

| Years | Files | Structural signature | Finding |
|---|---:|---|---|
| 2016–2023 | 24 | Five tensors; widths `7/8/2/scalar/2`; dtypes `float32/int16/int8/int64/int16`; sequence length 6 | Structurally consistent within this period |
| 2024 | 3 | Four tensors; widths `7/8/1/scalar`; all sequence tensors `float32`; sequence length 6 | Structural drift from 2016–2023 and from pinned source |
| 2016–2024 | 27 | Two incompatible signatures | Cross-year consistency: **UNSTABLE** |

Sample counts vary by year/split as expected for archive metadata and are fully recorded in the machine-readable manifest. They were not interpreted as performance or temporal split evidence.

## Decision-rule assessment

| Core GO condition | Finding | Status |
|---|---|---|
| Semantics sufficiently clear | Partial for 2016–2023; undocumented 2024 structure and unresolved `FLIGHTS` | FAIL |
| Reliable mapping to Tabular or safe context construction | No persisted mapping/key/row identity | FAIL |
| Temporal-safe at T−2h | Cannot enforce target-relative cutoff; weather unresolved/unsafe | FAIL |
| No need to infer protected identity | No safe mapping independent of unsupported identity interpretation | FAIL |
| No serious target/future leakage | Outcome tensors and unsafe fields are present | FAIL |
| Reproducible Week-6 transformation | Cannot reproduce/validate existing mapping across all years | FAIL |

## Final decision

**FLIGHT_CHAIN_DECISION: NO_GO**

Missing mapping and temporal evidence are decisive under D004's fail-closed rule. Structural drift in 2024 is an additional blocker, not the sole reason. This is a successful feasibility conclusion and does not fail Week 2.

## Downstream impact

- Tabular-only is the final core route.
- Do not implement `src/features/chain_context.py` in Week 3.
- Remove the planned Flight Chain ablation from Week 6.
- Record Flight Chain only as a limitation/future-work item unless new versioned mapping and point-in-time evidence triggers formal change control.
- Keep all raw Chain archives unchanged and read-only; do not delete them.
- Source `.pt` train/val/test splits remain non-authoritative for the thesis temporal protocol.

## Reopening rule

NO_GO may be reconsidered only with versioned primary evidence that supplies field semantics, exact sample/row mapping, point-in-time availability, and a reproducible transformation compatible with D008/D011. Registry, config, policies, and tests must be updated before any use. 2024 performance cannot be used to reopen this decision.
