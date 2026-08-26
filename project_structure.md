# Project structure

The reconstructed schedule context is a versioned derived dataset at
`data/processed/flight_chain_reconstructed_v1/`, partitioned by year into
`chain_groups`, `chain_members`, and `inbound_target_map`. Its source universe
is the full `tabular_by_year` partition; only the target map filters
`DEST == ATL`. Per-year SQLite files are disposable staging under the selected
derived output root and are deleted only after that year passes validation.
They never reside under `data/raw`.

Implementation entry points are
`src/data/flight_chain_reconstruction.py` and
`scripts/reconstruct_flight_chain.py`. A reconstructed `chain_id` means only
same carrier, operating flight number, and service date. It must not be
interpreted as physical aircraft identity or a same-aircraft rotation. The raw
`.pt` archives remain read-only evidence with their independent Week-2
`FINAL — NO_GO` decision.

The production derived partitions for exactly 2016–2023 passed full-data and
cross-year validation. Their separate status is `GO_FOR_ABLATION`; they remain
disabled by default, excluded from core, and contain no `year=2024` partition.

```text
Aeolus/
├── configs/
│   ├── .gitkeep
│   └── base.yaml                    # Cấu hình nền tảng Tuần 1
├── data/
│   ├── raw/tabular/<2016-2024>/     # Raw Tabular core, read-only
│   ├── raw/chain/<2016-2024>/       # Raw Flight Chain optional, read-only
│   ├── processed/
│   │   ├── tabular_by_year/year=<YYYY>/ # Canonical Parquet, schema v1
│   │   ├── inbound_atl/year=<YYYY>/     # Logical atl_inbound.parquet dataset
│   │   └── outbound_atl/year=<YYYY>/    # Logical atl_outbound.parquet dataset
│   └── simulation/                  # Generated simulation data
├── docs/roadmap/                    # Ba tài liệu V3
├── docs/dataset_audit/
│   ├── 2016/                        # Subfolder rỗng được phép giữ lại
│   ├── data_inventory.md
│   ├── schema_audit_plan.md
│   ├── schema_compatibility_matrix.md
│   ├── canonical_schema_v1.md
│   ├── data_dictionary_v0.md
│   ├── data_dictionary_v1.md
│   ├── leakage_audit.md
│   ├── weather_timing_audit.md
│   ├── flight_chain_feasibility_v0.md  # Historical provisional audit
│   └── flight_chain_feasibility_report.md # Final Week-2 NO_GO
├── docs/decisions/
│   ├── decision_registry.md
│   └── decision_include_chain.md
├── docs/experiments/
│   └── experiment_log.md
├── docs/thesis_notes/
│   ├── assumptions.md
│   └── limitations.md
├── notebooks/
├── scripts/
│   ├── inspection/
│   ├── run_schema_audit.py
│   ├── canonicalize_tabular.py
│   ├── build_temporal_manifests.py
│   ├── validate_processed_data.py
│   └── smoke_test.py
├── src/                             # Source packages, chưa có ML implementation
│   ├── data/                        # Loader/auditor + access guard + project logging
│   ├── features/
│   ├── models/
│   ├── simulation/
│   ├── optimization/
│   └── evaluation/
├── dashboard/
├── tests/                           # Config, guard, loader và schema-audit tests
├── reports/development/
├── reports/final/
├── reports/figures/
├── artifacts/
│   └── manifests/                   # Versioned schema, processed-data, split, access manifests
├── results/development_2023/        # Development 2023
├── results/final_2024/              # Final holdout 2024
├── .gitignore
├── README.md
└── project_structure.md
```

`data/raw/` là bất biến về nội dung: chỉ move/rename để chuẩn hóa đường dẫn; không rewrite, convert, normalize, delete hoặc tái serialize dữ liệu. `src/` là source code. `data/processed/`, `data/simulation/`, `artifacts/` và `results/` là generated artifacts và được ignore khỏi Git. Canonical storage contract hiện tại là `artifacts/manifests/canonical_schema_v1.json`; temporal contract là `artifacts/manifests/temporal_folds_manifest.json` và `split_manifest.json`.

2023 được dành cho development; 2024 là final end-to-end holdout chỉ mở sau full-system freeze. Raw Flight Chain `.pt` vẫn `FINAL — NO_GO`; Reconstructed Schedule Flight Chain riêng biệt là `GO_FOR_ABLATION`, optional và không phải physical aircraft rotation. Các split `.pt` không phải temporal split chính.

Thứ tự đọc roadmap:

1. `docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V3_DONG_BO.md`
2. `docs/roadmap/02_Bo_cong_nghe_de_xuat_Aeolus_Gate_Optimization_V3_DONG_BO.md`
3. `docs/roadmap/03_Chi_tiet_tung_tuan_Roadmap_Aeolus_Gate_Optimization_V3_DONG_BO.md`
4. `project_structure.md`
