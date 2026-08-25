# Flight Chain Feasibility V0

> Historical provisional artifact. The final Week-2 decision is `NO_GO`; see `flight_chain_feasibility_report.md` and `docs/decisions/decision_include_chain.md`.

## Status and scope

This is a bounded, initial feasibility assessment of the 2016 Flight Chain files. It is **not** the final Flight Chain GO/NO-GO decision. The final evidence-based decision belongs to Week 2.

At the time of this Week-1 assessment, Flight Chain was **OPTIONAL** under D004 and disabled by default with `pending_feasibility` status. Nothing in this historical V0 established identity semantics, feature admissibility, a safe Tabular join, or permission to use Chain in modeling. E003 has since resolved the final outcome to `NO_GO`.

Only `data/raw/chain/2016/` was inspected. No 2017–2024 Chain payload was opened, and no 2024 Chain content was accessed.

## Inspection performed

### Filesystem metadata

The split labels below are inferred only from filenames.

| Filename | Filename-inferred split | Size (bytes) | Exists |
|---|---|---:|---|
| `test_flight_chain_2016.pt` | test | 265,574,980 | Yes |
| `train_flight_chain_2016.pt` | train | 736,545,099 | Yes |
| `val_flight_chain_2016.pt` | val | 277,126,461 | Yes |
| **Total** | — | **1,279,246,540** | **3 files** |

These `train`/`val`/`test` names describe source-file splits only. They are not the thesis temporal protocol and may not replace rolling development in 2016–2022, development/model selection in 2023, and final holdout in 2024.

### Container metadata

The first eight bytes and ZIP central directory were inspected for all three 2016 files. No tensor storage member was extracted or decompressed.

| Split | Container | Archive members | Tensor-storage members | `data.pkl` metadata bytes | Storage payload read |
|---|---|---:|---:|---:|---:|
| test | PyTorch ZIP archive | 7 | 5 | 535 | 0 |
| train | PyTorch ZIP archive | 7 | 5 | 535 | 0 |
| val | PyTorch ZIP archive | 7 | 5 | 535 | 0 |

Each archive contains one small `data.pkl`, five `data/<n>` storage members, and a two-byte archive-version member. Archive member sizes indicate stored and uncompressed tensor payload sizes are equal; loading a split would therefore allocate substantial tensor memory.

### Bounded structural inspection of one split

`test_flight_chain_2016.pt` was selected because it is the smallest 2016 split. Its 535-byte `data.pkl` was analyzed with Python `pickletools`, which decodes pickle opcodes without constructing the serialized Python object or loading tensor storage payloads.

The pickle metadata declares:

- top-level serialized object: `torch.utils.data.dataset.TensorDataset`;
- object-state key: `tensors`;
- tensor/container count: 5;
- device recorded in storage metadata: CPU;
- no named feature metadata;
- no named flight identifier metadata;
- no named timestamp or availability metadata.

Tensor metadata observed in the test split:

| Tensor position | Serialized storage type | Inferred dtype | Shape | Stride | Semantic status |
|---:|---|---|---|---|---|
| 0 | `FloatStorage` | `float32` | `(862250, 6, 7)` | `(42, 7, 1)` | Unknown |
| 1 | `ShortStorage` | `int16` | `(862250, 6, 8)` | `(48, 8, 1)` | Unknown |
| 2 | `CharStorage` | `int8` | `(862250, 6, 2)` | `(12, 2, 1)` | Unknown |
| 3 | `LongStorage` | `int64` | `(862250,)` | `(1,)` | Unknown |
| 4 | `ShortStorage` | `int16` | `(862250, 6, 2)` | `(12, 2, 1)` | Unknown |

All five tensors share a first dimension of 862,250 in the serialized metadata. Four rank-3 tensors share a middle dimension of length 6, which is a **candidate sequence axis based on shape only**. There is no evidence in the archive metadata that positions along this axis belong to one physical aircraft, and this report does not assign that meaning.

The one-dimensional `int64` tensor is not labeled. It must not be called a flight ID, target, row index, or aircraft identifier without external documentation or verified mapping evidence. Likewise, the feature-width dimensions 7, 8, 2, and 2 have no documented names or semantics in the inspected metadata.

## Resource usage / safety

- No `torch.load` call was made.
- No mmap was needed because shape/type information was available in the tiny pickle metadata.
- No tensor storage payload was read, extracted, decompressed, materialized, or scanned.
- No sample values, prefixes, minima, maxima, unique counts, or full statistics were computed.
- At most one 535-byte `data.pkl` payload was read for structural decoding; the other archive checks used filesystem and ZIP central-directory metadata only.
- The smallest split is approximately 265.6 MB before Python/PyTorch object overhead, so avoiding object construction materially reduced memory risk.
- The three files remained read-only and were not rewritten or reserialized.
- No model, LSTM, Transformer, feature generation, merge, or training operation was performed.

## Evidence found

Supported evidence at V0 scope:

1. All three expected filename-inferred 2016 splits exist and match the sizes recorded in `data_inventory.md`.
2. All three are structurally readable PyTorch ZIP archives with the same high-level archive-member pattern: one pickle metadata member and five tensor storage members.
3. The bounded test-split metadata identifies a `TensorDataset` holding five shape-compatible tensors with a common sample dimension.
4. Four test-split tensors have a shared length-6 axis, but its semantics are undocumented.
5. No feature names, flight-level join key, timestamps, T-2h availability metadata, or aircraft identity semantics were found in the inspected container metadata.
6. The Tech Stack V3 notes that source `.pt` data has a `>15` label, while the core target must still be derived from Tabular as `ARR_DELAY >= 15`. This creates a concrete leakage/target-semantics audit requirement; it does not identify which unnamed tensor contains that source label.

Evidence that was deliberately not claimed:

- sequence equals one physical aircraft;
- any tensor is a flight ID, label, timestamp, or feature group;
- Chain can currently be joined to Tabular;
- source split membership is temporal or admissible for thesis evaluation;
- any Chain feature is available at `T = CRS_DEP_TIME - 2 hours`;
- Chain is useful for prediction or should be kept.

## F1–F8 table

| ID | Feasibility question | Assessment | Evidence and interpretation |
|---|---|---|---|
| F1 | Có documented feature semantics không? | NOT_SUPPORTED | The archive exposes five unnamed tensors and no feature-name metadata. No reviewed source dictionary assigning semantics to the tensor dimensions was found in the required project documents. |
| F2 | Có flight-level identifier để map với Tabular không? | UNKNOWN | No named flight identifier exists in inspected metadata. The unnamed `int64` vector cannot be labeled or interpreted without evidence. |
| F3 | Có timestamp/context cho biết dữ liệu có sẵn tại T-2h không? | UNKNOWN | No named timestamp, provenance, issue time, or availability metadata was found. Tensor values were not loaded, and availability cannot be inferred from shape or dtype. |
| F4 | Có evidence sequence = same physical aircraft không? | NOT_SUPPORTED | A shared length-6 axis exists, but no aircraft identity/rotation metadata supports that interpretation. D004/D014 prohibit making this inference. |
| F5 | Có thể map Chain -> Tabular mà không suy đoán không? | NOT_SUPPORTED | At V0 there is no documented join key or verified row-level mapping. A heuristic join would be speculation and is prohibited. |
| F6 | Split `.pt` có thể dùng làm temporal split chính không? | NOT_SUPPORTED | D011 and all V3 roadmaps lock the year-based temporal protocol; source `train`/`val`/`test` labels cannot replace it. |
| F7 | Có nguy cơ target/future leakage không? | SUPPORTED | Feature semantics and T-2h availability are unknown, and Tech Stack V3 records a source `>15` label. Both facts create a real leakage risk requiring explicit audit before any use. |
| F8 | Có đủ evidence để đưa Chain sang Tuần 2 feasibility investigation không? | SUPPORTED | The container is structurally readable with bounded methods, aligned tensor metadata is available, and the unresolved mapping/semantics/leakage questions are specific and testable. This supports audit-only continuation, not KEEP or integration. |

## Provisional conclusion

**FLIGHT_CHAIN_V0: PROVISIONAL_GO**

This means only that Flight Chain has enough structural evidence to continue a controlled feasibility investigation in Week 2. It does **not** mean:

- final GO;
- Chain is kept;
- Chain can be mapped to Tabular;
- Chain is temporally safe;
- Chain improves prediction;
- sequence represents a physical aircraft;
- Chain may be used for features, training, ablation, or downstream simulation now.

The final GO/NO-GO remains a Week 2 deliverable. If Week 2 cannot establish documented feature semantics, a non-heuristic flight-level mapping, and T-2h safety, the required outcome is NO-GO/DROP without forcing a merge.

## Required Week-2 follow-up

1. Locate and review authoritative source documentation or generation code for the five tensors, their axes, feature names, units, missing-value conventions, and the source `>15` label.
2. Establish whether an explicit flight-level identifier exists and define an exact, testable Chain-to-Tabular mapping. Do not derive a heuristic key merely to force coverage.
3. Verify every candidate Chain field against `T = CRS_DEP_TIME - 2 hours`, including raw timestamp provenance and any context-window construction.
4. Identify the source label tensor and prove it cannot enter predictors directly or indirectly; retain Tabular-derived `ARR_DELAY >= 15` as the core classification ground truth.
5. Determine the meaning and ordering of the length-6 axis. Do not interpret it as aircraft continuity unless independent documentation proves that meaning; even then, observe D014 claim boundaries.
6. Quantify mapping coverage, one-to-one/one-to-many behavior, duplicates, unmatched records, and temporal consistency using a bounded, reproducible audit before any merge artifact is created.
7. Keep source split labels separate from the locked year-based temporal protocol. Any permitted Chain use must be repartitioned or evaluated under the same temporal contract as Tabular.
8. Use a memory-bounded inspection implementation: one year/split at a time, CPU, mmap/lazy path when supported, explicit memory estimate, and no full-tensor statistics unless separately approved and justified.
9. Record the final evidence and decision in the Week 2 `decision_include_chain.md`; only a documented final GO may authorize the later 2023 ablation.
10. Keep 2024 Chain content sealed from development and do not use it to resolve feature, mapping, or model decisions.

## Cross-check

- **D004 / T004:** Chain remains optional and pending evidence; final GO/NO-GO is deferred to Week 2.
- **D008:** No Chain field is admitted as T-2h-safe.
- **D011:** Source `.pt` split names are explicitly rejected as the thesis temporal split.
- **D013:** Raw files were inspected read-only and not modified.
- **D014:** No field is named or treated as real aircraft identity, and the length-6 axis is not interpreted as aircraft rotation.
- **D020:** No 2024 Chain content was accessed or used.
- **`data_inventory.md`:** Current 2016 filenames and byte sizes match the recorded inventory.
- **`data_dictionary_v0.md`:** Tabular remains core; Chain mapping remains unresolved in a separate feasibility track.
- **`configs/base.yaml`:** `flight_chain.enabled_by_default: false` and `status: pending_feasibility` remain unchanged.

No mismatch with the three synchronized V3 roadmap documents or the decision registry was found at V0 scope.
