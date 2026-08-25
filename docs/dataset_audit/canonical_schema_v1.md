# Canonical schema v1

Evidence basis: complete 2016–2024 schema audit (`audit_version 0.1.0`, 54,674,003 rows). All fields below are present in all nine years and need no schema-level rename. `normalization_needed` means parse/cast needed when materializing processed data; it does not alter raw files.

The logical canonical `string` type is materialized by the selected Pandas/PyArrow writer as Parquet/Arrow `large_string`; this is the intended physical representation and is validated in the processed-data check.

| Field group | Canonical storage dtype | Normalization needed | Schema role |
|---|---|---|---|
| `FL_DATE`, `CRS_DEP_TIME`, `DEP_TIME`, `WHEELS_OFF`, `WHEELS_ON`, `CRS_ARR_TIME`, `ARR_TIME` | string | yes: explicit date/time parsing in processed layer | schedule/actual timestamp fields |
| `OP_CARRIER`, `ORIGIN`, `DEST` | string | trim/validate only | categorical identifiers |
| `OP_CARRIER_FL_NUM`, `DEP_DELAY`, `TAXI_OUT`, `TAXI_IN`, `ARR_DELAY`, `CRS_ELAPSED_TIME`, `ACTUAL_ELAPSED_TIME`, `AIR_TIME`, `FLIGHTS`, `O_TEMP`, `O_PRCP`, `O_WSPD`, `D_TEMP`, `D_PRCP`, `D_WSPD`, `O_LATITUDE`, `O_LONGITUDE`, `D_LATITUDE`, `D_LONGITUDE` | float64 | yes: numeric validation | numeric measurement/target candidate |
| `MONTH`, `DAY_OF_MONTH`, `DAY_OF_WEEK`, `ORIGIN_INDEX`, `DEST_INDEX` | Int64 nullable | yes: nullable integer cast | calendar/index fields |

`ARR_DELAY` remains a schema target field; final prediction-time safety is governed by the data dictionary/leakage audit. Actual-operation fields remain present because canonicalization does not perform model-driven exclusion.
