# P3 — Bounded Smoke & Fold-Safe Preprocessing Report

- **Protocol**: Aeolus Dual Core Architecture Protocol V2
- **Phase**: P3 Core Departure Feature Engineering & Preprocessing
- **Auditor / Engineer**: Senior ML Engineer
- **Date**: 2026-10-08
- **Dataset Evaluated**: `data/processed/outbound_atl/year=2022` (Real BTS Parquet Partition)
- **Batch Size**: 25,000 Real Outbound Flights
- **Status**: **`PASS`**

---

## 1. Executive Summary

Phase P3 introduces the reproducible, leakage-free feature engineering and fold-safe preprocessing engine for **Core Departure V1**.
The pipeline operates strictly under two isolated modes:
1. `prepare_departure_training`: Ingestion of historical flight records, building continuous signed $y_{\text{dep\_reg}}$ and binary classification $y_{\text{dep\_cls}}$, retaining identifiers (`flight_key`, `source_year`, `source_row_number`), and asserting zero data leakage.
2. `prepare_departure_inference`: Schedule-only production inference pipeline that strictly does not require, accept, or consume actual operational delay metrics (`DEP_DELAY`, `ARR_DELAY`, actual timestamps).

---

## 2. Bounded Smoke Test Performance (25,000 Records)

| Metric | Measured Value | Standard / Evaluation |
| :--- | :--- | :--- |
| **Data Ingestion Time** | 0.2523 s | High-throughput PyArrow batch slice |
| **Training Feature Prep Time** | 0.2781 s | **89,905 rows / second** |
| **Inference Feature Prep Time** | 0.2444 s | **102,289 rows / second** |
| **Pipeline Fitting Time (Train Only)** | 0.2064 s | Fold-safe statistics computation |
| **Transform Throughput** | 0.0659 s | **379,450 rows / second** |
| **Total End-to-End Elapsed Time** | 1.0711 s | Highly optimized vectorization |
| **Peak Memory Consumption** | **45.14 MB** | Minimal memory footprint |

---

## 3. Data Integrity & Target Verification

- **Total Input Rows**: 25,000
- **Outbound Filter (`ORIGIN == "ATL"`)**: 25,000 (100% compliant)
- **Eligible Processed Rows**: 25,000 (0 missing targets, 0 dropped rows)
- **Signed Delay Continuity**:
  - Early departures ($y_{\text{dep\_reg}} < 0$): **12,836 flights (51.34%)**
  - Late departures ($y_{\text{dep\_reg}} \ge 15$ min): **5,541 flights (22.16%)**
  - **No clipping applied**: Extreme and negative values preserved as physical operational pushback times.
  - **No imputation applied**: Missing values are dropped according to contract, not filled with zero.

---

## 4. Preprocessing Architecture & Fold-Safety

- **Numeric Pipeline**:
  - Features (7): `CRS_ELAPSED_TIME`, `calendar_month`, `calendar_day_of_month`, `calendar_day_of_week`, `is_weekend`, `scheduled_departure_hour`, `scheduled_departure_minute`.
  - Strategy: `SimpleImputer(strategy="median", add_indicator=True)` + `StandardScaler()` (for Linear) or raw (for Tree).
  - Statistics frozen on training fold only.
- **Categorical Pipeline**:
  - Features (2): `OP_CARRIER`, `DEST`.
  - Strategy: `OneHotEncoder(handle_unknown="ignore")` (Linear) or `OrdinalEncoder` (Tree).
  - Unseen validation/test categories zeroed out with zero future vocabulary leakage.
- **High-Cardinality Pipeline**:
  - Feature (1): `OP_CARRIER_FL_NUM`.
  - Strategy: `DepartureFrequencyEncoder` (Train-only frequency mapping; unseen flight numbers map to $0.0$).
- **Cryptographic Provenance**:
  - Persisted at: `artifacts/dual_core/preprocessing/departure_preprocessing_manifest_v1.json`
  - SHA256 Fingerprint: `66ca0e05907323739858fd574385bf7863e56afc41c86e02fd9ad321783653bd`
