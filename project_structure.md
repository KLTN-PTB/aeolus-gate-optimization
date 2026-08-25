# Project structure

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

2023 được dành cho development; 2024 là final end-to-end holdout chỉ mở sau full-system freeze. Flight Chain đã nhận quyết định Week-2 `NO_GO`, vì vậy Tabular-only là core route cuối cùng; raw Chain vẫn read-only và các split `.pt` không phải temporal split chính.

Thứ tự đọc roadmap:

1. `docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V3_DONG_BO.md`
2. `docs/roadmap/02_Bo_cong_nghe_de_xuat_Aeolus_Gate_Optimization_V3_DONG_BO.md`
3. `docs/roadmap/03_Chi_tiet_tung_tuan_Roadmap_Aeolus_Gate_Optimization_V3_DONG_BO.md`
4. `project_structure.md`
