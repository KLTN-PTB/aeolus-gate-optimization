# Full 2016 Reconstructed Schedule Flight Chain Audit

Date: 2026-08-26  
Year executed: **2016 only**  
Year status: **FULL_2016_PASS**  
Overall reconstructed status: **CANDIDATE_REQUIRES_REVIEW**

## Scope and protected boundaries

The approved production command ran through the Python 3.11 repository `.venv`
with `--years 2016 --chunk-size 100000` and no `--max-rows`. The configured
production root is `data/processed/flight_chain_reconstructed_v1/`. No 2017-2023
partition was executed or created, and 2024 remained blocked from development
access.

This remains a schedule/service-number context. It is not physical aircraft
rotation evidence. Stored canonical `flight_key_v1` values were reused without
recomputation. The original Aeolus raw Flight Chain remains `FINAL — NO_GO`, no
raw `.pt` archive or label was loaded, and Weather remains `DROP`.

## Full-year reconstruction statistics

| Metric | Full 2016 result |
|---|---:|
| Canonical source rows | 5,537,987 |
| Eligible source rows | 5,537,987 |
| Excluded rows | 0 |
| Mapped members | 5,537,987 |
| Coverage | 100% |
| Chains | 4,153,379 |
| Inbound ATL targets | 381,166 |
| Chain length min / median / p95 / max | 1 / 1 / 2 / 8 |
| Chains longer than 6 | 3,104 |
| Ambiguous chains | 0 |
| Ambiguous scheduled timestamps | 0 |
| Ambiguous members | 0 |
| Duplicate schedule signatures | 0 |
| Duplicate-signature excess rows | 0 |

Exclusion reasons were `{}`. The maximum full-chain size was 8; no membership
was truncated or padded at reconstruction time.

## Critical year-level gates

| Gate | Evidence | Result |
|---|---:|---|
| Mapped equals eligible | 5,537,987 = 5,537,987 | PASS |
| Unmapped eligible rows | 0 | PASS |
| Duplicate `flight_key` | 0 | PASS |
| Invalid/null `chain_id` | 0 | PASS |
| Multi-chain membership | 0 | PASS |
| Target fields in outputs | 0 | PASS |
| Actual/outcome fields in outputs | 0 | PASS |
| Weather fields in outputs | 0 | PASS |
| Uncertain fields / `FLIGHTS` | 0 / false | PASS |
| Raw `.pt` labels used | false | PASS |
| Raw path/size/`mtime_ns` changed | 0 | PASS |
| 2024 development access | blocked | PASS |

The logical content fingerprints are:

- chain groups: `3556297d22e835835afacee8c7db3f3182af046404f577b109373b1c3ef0732e`
- chain members: `32a6a1b0c1eb12f7740d5a8093e37d0ccd50ba6c48a5e424cbfde4a526ca02d3`
- inbound target map: `e6bb70b139bd2d480a7b974876c5144e1994e45664c51467e3345197b977f09d`
- combined: `14b41224aafc3e89ad4011ca157adc7eef0dbd4a0e4fafc530b64bdd3148ceaf`

## Independent real-data ATL validation

A separate bounded PyArrow scan projected canonical `DEST` across all 5,537,987
2016 source rows. Because production reported zero exclusions, every source row
was eligible. The independently normalized `DEST == "ATL"` count was 381,166.

| ATL mapping check | Count |
|---|---:|
| Eligible canonical `DEST == ATL` | 381,166 |
| Emitted inbound targets | 381,166 |
| ATL members in `chain_members` | 381,166 |
| Duplicate target `flight_key` | 0 |
| Duplicate ATL-member `flight_key` | 0 |
| Null target `chain_id` | 0 |
| Invalid target position | 0 |
| Target/member mapping mismatch | 0 |
| Missing target member | 0 |
| Extra ATL member | 0 |
| Missing referenced chain group | 0 |
| Duplicate referenced chain group | 0 |
| Target/group chain-length mismatch | 0 |

Every target key therefore maps to exactly one ATL chain member and one chain
ID. Every position satisfies `0 <= chain_position < chain_length`, and every
target length equals the referenced `chain_groups.member_count`.

Representative traceable stored identifiers:

| `flight_key` | `chain_id` | Pos/len | Source row | Service | Flight | Leg | CRS dep |
|---|---|---:|---:|---|---|---|---|
| `flight_key_v1_cb50863285b62969c24a99b8c44ef7da` | `schedule_chain_v1_b53c13fa6006e650db8e6f00303b3b6d` | 0/2 | 3,077,935 | 2016-01-01 | AA 1087 | DFW→ATL | 1330 |
| `flight_key_v1_6b66c4da149c8209fba31e4d6f8d26ae` | `schedule_chain_v1_0dec662ba768668b42099cfa8ab7a9e2` | 0/1 | 3,071,488 | 2016-01-01 | AA 1116 | LAX→ATL | 2300 |
| `flight_key_v1_7dfde61a1249dccbc20639c512ddc193` | `schedule_chain_v1_949e6938b8e49cf5b796817e7d07744e` | 0/1 | 3,077,936 | 2016-01-01 | AA 1178 | DFW→ATL | 2125 |
| `flight_key_v1_fce6a261f391250f5144b4bb0b582f48` | `schedule_chain_v1_8cffd4dd32045df07c42013dd494a4af` | 0/2 | 3,071,489 | 2016-01-01 | AA 1249 | LAX→ATL | 1000 |
| `flight_key_v1_40daa7b799bc5205386358309f6f9157` | `schedule_chain_v1_edb26e98673ad01aa3008ca7b02b1f5c` | 0/2 | 3,077,937 | 2016-01-01 | AA 1427 | DFW→ATL | 0906 |

## Measured resources

| Metric | Actual full-2016 measurement |
|---|---:|
| Runtime | 3,731.168 seconds (62.19 minutes) |
| Rows/second | 1,484.250 |
| Peak staging | 2,780,627,978 bytes |
| Peak SQLite | 2,321,006,592 bytes |
| Output Parquet | 459,621,386 bytes |
| Peak Python allocation | 208,393,447 bytes |
| Free disk before | 65,661,276,160 bytes |
| Free disk at peak/before cleanup | 62,879,313,920 bytes |
| Free disk after staging cleanup | 65,200,328,704 bytes |
| Staging cleanup | PASS; year staging removed, staging root empty |

`tracemalloc` does not measure all native PyArrow allocations. These are actual
full-year measurements, not extrapolations.

## Raw and holdout integrity

All 36 raw path/size/`mtime_ns` entries remained identical. The before and after
inventory BLAKE2b is
`c4071bfaad09e21d2d51cee64d01acf5a9b0fef5011f1122615ed379567a05c4`.
No changed Git path exists under `data/raw/**`, and no `torch.load` exists in the
reconstruction CLI/module. `CORE_WEATHER_POLICY` remains `DROP`; 2024
development access remains blocked.

## Decision boundary

Full 2016 passed its year-level and independent ATL gates. This does not permit
`GO_FOR_ABLATION`: development years 2017-2023 are still **NOT RUN**, so the
Reconstructed Schedule Flight Chain remains `CANDIDATE_REQUIRES_REVIEW` pending
explicit approval for later years and all-years validation.

Post-execution pytest, repository smoke test, and `git diff --check` are recorded
in the companion manifest after their final verification run.
