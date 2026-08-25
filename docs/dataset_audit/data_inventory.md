# Aeolus Data Inventory

Scope: filesystem metadata only. No CSV content was read and no `.pt` file was loaded. Paths below are relative to the project root.

## Dataset roles

- **Tabular = CORE** data source for ML.
- **Chain = OPTIONAL** context, subject to the Week 1–2 feasibility GO/NO-GO decision.
- **Flight Network = NOT IN CORE**.

The `train`/`val`/`test` labels below are inferred solely from Chain filenames. They are source-file split labels, **not** the thesis temporal split; the locked temporal protocol remains 2016–2022 rolling development, 2023 development, and sealed 2024 final holdout.

## Tabular inventory

| Year | Path | Filename | Size (bytes) | Extension | Exists |
|---|---|---|---:|---|---|
| 2016 | `data/raw/tabular/2016/flight_with_weather_2016.csv` | `flight_with_weather_2016.csv` | 1,538,427,452 | `.csv` | Yes |
| 2017 | `data/raw/tabular/2017/flight_with_weather_2017.csv` | `flight_with_weather_2017.csv` | 1,549,837,485 | `.csv` | Yes |
| 2018 | `data/raw/tabular/2018/flight_with_weather_2018.csv` | `flight_with_weather_2018.csv` | 1,941,406,432 | `.csv` | Yes |
| 2019 | `data/raw/tabular/2019/flight_with_weather_2019.csv` | `flight_with_weather_2019.csv` | 1,990,370,667 | `.csv` | Yes |
| 2020 | `data/raw/tabular/2020/flight_with_weather_2020.csv` | `flight_with_weather_2020.csv` | 1,197,858,795 | `.csv` | Yes |
| 2021 | `data/raw/tabular/2021/flight_with_weather_2021.csv` | `flight_with_weather_2021.csv` | 1,600,032,487 | `.csv` | Yes |
| 2022 | `data/raw/tabular/2022/flight_with_weather_2022.csv` | `flight_with_weather_2022.csv` | 1,782,648,882 | `.csv` | Yes |
| 2023 | `data/raw/tabular/2023/flight_with_weather_2023.csv` | `flight_with_weather_2023.csv` | 1,847,433,387 | `.csv` | Yes |
| 2024 | `data/raw/tabular/2024/flight_with_weather_2024.csv` | `flight_with_weather_2024.csv` | 1,748,350,586 | `.csv` | Yes |

## Flight Chain inventory

| Year | Split inferred from filename | Path | Filename | Size (bytes) | Extension | Exists |
|---|---|---|---|---:|---|---|
| 2016 | test | `data/raw/chain/2016/test_flight_chain_2016.pt` | `test_flight_chain_2016.pt` | 265,574,980 | `.pt` | Yes |
| 2016 | train | `data/raw/chain/2016/train_flight_chain_2016.pt` | `train_flight_chain_2016.pt` | 736,545,099 | `.pt` | Yes |
| 2016 | val | `data/raw/chain/2016/val_flight_chain_2016.pt` | `val_flight_chain_2016.pt` | 277,126,461 | `.pt` | Yes |
| 2017 | test | `data/raw/chain/2017/test_flight_chain_2017.pt` | `test_flight_chain_2017.pt` | 270,152,516 | `.pt` | Yes |
| 2017 | train | `data/raw/chain/2017/train_flight_chain_2017.pt` | `train_flight_chain_2017.pt` | 744,832,267 | `.pt` | Yes |
| 2017 | val | `data/raw/chain/2017/val_flight_chain_2017.pt` | `val_flight_chain_2017.pt` | 282,654,973 | `.pt` | Yes |
| 2018 | test | `data/raw/chain/2018/test_flight_chain_2018.pt` | `test_flight_chain_2018.pt` | 343,048,964 | `.pt` | Yes |
| 2018 | train | `data/raw/chain/2018/train_flight_chain_2018.pt` | `train_flight_chain_2018.pt` | 949,427,339 | `.pt` | Yes |
| 2018 | val | `data/raw/chain/2018/val_flight_chain_2018.pt` | `val_flight_chain_2018.pt` | 361,722,941 | `.pt` | Yes |
| 2019 | test | `data/raw/chain/2019/test_flight_chain_2019.pt` | `test_flight_chain_2019.pt` | 354,560,772 | `.pt` | Yes |
| 2019 | train | `data/raw/chain/2019/train_flight_chain_2019.pt` | `train_flight_chain_2019.pt` | 976,201,867 | `.pt` | Yes |
| 2019 | val | `data/raw/chain/2019/val_flight_chain_2019.pt` | `val_flight_chain_2019.pt` | 370,291,517 | `.pt` | Yes |
| 2020 | test | `data/raw/chain/2020/test_flight_chain_2020.pt` | `test_flight_chain_2020.pt` | 222,317,316 | `.pt` | Yes |
| 2020 | train | `data/raw/chain/2020/train_flight_chain_2020.pt` | `train_flight_chain_2020.pt` | 615,880,587 | `.pt` | Yes |
| 2020 | val | `data/raw/chain/2020/val_flight_chain_2020.pt` | `val_flight_chain_2020.pt` | 232,687,357 | `.pt` | Yes |
| 2021 | test | `data/raw/chain/2021/test_flight_chain_2021.pt` | `test_flight_chain_2021.pt` | 303,737,028 | `.pt` | Yes |
| 2021 | train | `data/raw/chain/2021/train_flight_chain_2021.pt` | `train_flight_chain_2021.pt` | 836,919,371 | `.pt` | Yes |
| 2021 | val | `data/raw/chain/2021/val_flight_chain_2021.pt` | `val_flight_chain_2021.pt` | 317,606,269 | `.pt` | Yes |
| 2022 | test | `data/raw/chain/2022/test_flight_chain_2022.pt` | `test_flight_chain_2022.pt` | 332,956,676 | `.pt` | Yes |
| 2022 | train | `data/raw/chain/2022/train_flight_chain_2022.pt` | `train_flight_chain_2022.pt` | 919,515,083 | `.pt` | Yes |
| 2022 | val | `data/raw/chain/2022/val_flight_chain_2022.pt` | `val_flight_chain_2022.pt` | 346,965,757 | `.pt` | Yes |
| 2023 | test | `data/raw/chain/2023/test_flight_chain_2023.pt` | `test_flight_chain_2023.pt` | 343,329,540 | `.pt` | Yes |
| 2023 | train | `data/raw/chain/2023/train_flight_chain_2023.pt` | `train_flight_chain_2023.pt` | 944,545,547 | `.pt` | Yes |
| 2023 | val | `data/raw/chain/2023/val_flight_chain_2023.pt` | `val_flight_chain_2023.pt` | 356,794,301 | `.pt` | Yes |
| 2024 | test | `data/raw/chain/2024/flight_chain_test_2024.pt` | `flight_chain_test_2024.pt` | 370,582,841 | `.pt` | Yes |
| 2024 | train | `data/raw/chain/2024/flight_chain_train_2024.pt` | `flight_chain_train_2024.pt` | 1,118,279,679 | `.pt` | Yes |
| 2024 | val | `data/raw/chain/2024/flight_chain_val_2024.pt` | `flight_chain_val_2024.pt` | 557,077,875 | `.pt` | Yes |

## Summary

| Measure | Tabular | Chain | Combined |
|---|---:|---:|---:|
| File count | 9 | 27 | 36 |
| Total bytes | 15,196,366,173 | 13,751,334,923 | 28,947,701,096 |
| Years present | 2016–2024 | 2016–2024 | 2016–2024 |
| Years missing | None | None | None |
| Duplicate filenames | None | None | None |

All nine Tabular years have one CSV. All nine Chain years have three filename-identifiable source splits: train, val, and test.

## Inventory limitations and policy

This inventory establishes only path, filename, extension, existence, and size. It makes no assertion about columns, tensors, labels, row counts, train/validation/test semantics, feature mapping, temporal safety, or dataset quality. Raw files remain read-only under decision D013; Chain use remains optional under D004.
# Audit update — 2026-08-23 (schema audit v0.1.0)

The complete read-only Tabular audit recorded 54,674,003 rows: 2016 5,537,987; 2017 5,575,872; 2018 6,986,842; 2019 7,161,827; 2020 4,312,091; 2021 5,755,666; 2022 6,413,416; 2023 6,645,461; 2024 6,284,841. Per-year machine summaries are under `artifacts/manifests/schema_audit/`; the canonical schema is `canonical_schema_v1`. This audit is structural only and does not unseal 2024 for development.
