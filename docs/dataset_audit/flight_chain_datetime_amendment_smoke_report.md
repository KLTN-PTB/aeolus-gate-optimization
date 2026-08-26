# Reconstructed Chain Datetime Amendment and Bounded Smoke Audit

Date: 2026-08-26  
Status: **CANDIDATE_REQUIRES_REVIEW**

## Amendment boundary

The earlier full canonical datetime audit correctly returned
`AMENDMENT_REQUIRES_REVIEW` under the requirement to prove original `0000`
versus `2400` provenance. The design owner subsequently approved the narrow
`canonical_datetime_storage_amendment_v1` decision
`AMENDMENT_SUPPORTED_WITH_AMBIGUOUS_MIDNIGHT_FAIL_CLOSED`.

No schedule-chain semantic or identifier formula changed. ISO dates and
midnight canonical `FL_DATE` timestamps normalize to the same service date.
Same-service-date, non-midnight canonical `CRS_DEP_TIME` timestamps are accepted
and supply their clock HHMM plus ordering timestamp. Exact canonical midnight
fails as `AMBIGUOUS_CANONICAL_MIDNIGHT`; any previous/next calendar date fails
as `UNEXPECTED_CANONICAL_DATE_RELATION`. These violations abort a production
year and publish no output. Explicit HHMM `2400` retains its existing next-day
midnight behavior because that representation explicitly contains `2400`.

Original `0000`/`2400` provenance remains **NOT PROVEN**. `CRS_ARR_TIME` remains
schedule-only and preserved without rollover, duration, or ordering inference.
Stored canonical `flight_key_v1` values are reused unchanged.

## Environment and TDD

The pre-amendment baseline was Python 3.10.11 with 98 passing tests. Twelve
targeted amendment cases were observed RED before the production parser changed.
After the minimal implementation, all twelve were GREEN and the suite contained
108 passing tests. A Python 3.11.15 candidate environment was then built from
the exact pins, passed all 108 tests, and was promoted to `.venv`; the Python
3.10 environment remains preserved as `.venv310_backup_20260826`.

Resolved core versions are pandas 2.3.3, PyArrow 25.0.1, SQLite 3.50.4, NumPy
2.2.6, pytest 9.1.1, and PyYAML 6.0.3. The final full suite and
`scripts/smoke_test.py` both passed through the promoted `.venv`.

## Corrected bounded 2016 results

Both runs used `--max-rows 250000 --chunk-size 100000`, separate new output
roots, and the same 5,537,987-row canonical 2016 partition.

| Metric | Smoke A (`smoke_b`) | Smoke B (`smoke_c`) |
|---|---:|---:|
| Source rows | 250,000 | 250,000 |
| Eligible rows | 250,000 | 250,000 |
| Mapped rows | 250,000 | 250,000 |
| Chains | 249,755 | 249,755 |
| Inbound ATL targets | 0 | 0 |
| Excluded rows | 0 | 0 |
| Ambiguous chains/timestamps/members | 0 / 0 / 0 | 0 / 0 / 0 |
| Duplicate schedule signatures | 0 | 0 |
| Combined fingerprint | `5020cb1b6bffe8283f2f4d1c260211de932e5e6aa1a0b0eb927d572dbccfcb03` | same |
| Runtime | 168.129 s | 168.784 s |
| Rows/second | 1,486.955 | 1,481.185 |

All chain-group, chain-member, inbound-map, and combined logical fingerprints
were equal. A direct PyArrow equality comparison of all 250,000 ordered
`flight_key`, `chain_id`, and `chain_position` rows also passed. Both staging
directories were removed only after PASS.

The bounded prefix contained only `DEST=LAX` (210,706) and `DEST=DCA` (39,294),
so zero ATL targets is the deterministic content of this prefix. Consequently,
the real-data smoke did not exercise inbound target-map emission; that path is
covered by synthetic tests and remains a limitation of this bounded prefix.

## Resource review

| Metric | Value |
|---|---:|
| Peak staging | 128,246,136 bytes |
| Peak SQLite | 105,017,344 bytes |
| Staging / eligible row | 512.984544 bytes |
| SQLite / eligible row | 420.069376 bytes |
| Output | 23,228,792 bytes |
| Output / eligible row | 92.915168 bytes |
| Peak Python allocation | 185,874,263 bytes |
| Estimated full-2016 peak staging | 2,840,901,736 bytes |
| Estimated full-2016 SQLite | 2,326,338,743 bytes |
| Estimated full-2016 output | 514,562,992 bytes |
| Estimated full-2016 runtime | 3,738.9 s / 62.3 min |
| Current free disk | 65,661,325,312 bytes |
| Free / estimated staging | 23.11x |
| Conservative safety margin | 58,950,395,855 bytes |

The conservative margin subtracts twice the sum of estimated staging and
estimated output from current free disk; it intentionally overstates the need
because peak staging already includes staged Parquet output. `tracemalloc` does
not measure all native PyArrow allocations, so its peak is not total process
RSS. The scan remains bounded to one 100,000-row Arrow batch and one year.

The measured disk/runtime margin is acceptable for a later explicitly approved
full-2016 run. No full 2016 or 2016-2023 reconstruction was started here.

## Safety revalidation

- All 36 raw paths retain the same path, size, and `mtime_ns`; the before/after
  inventory BLAKE2b is
  `c4071bfaad09e21d2d51cee64d01acf5a9b0fef5011f1122615ed379567a05c4`.
- No raw `.pt` archive was loaded, and no `torch.load` exists in the
  reconstruction module or CLI.
- `CORE_WEATHER_POLICY` remains `DROP`.
- Development access to 2024 remains blocked.
- `FLIGHT_KEY_VERSION` remains `flight_key_v1`, and tests prove the stored key
  is emitted unchanged.
- Original Aeolus raw Flight Chain remains **FINAL — NO_GO**.

## Recommendation

Keep Reconstructed Schedule Flight Chain at `CANDIDATE_REQUIRES_REVIEW`.
Resource evidence supports a later full-2016 execution, but this task did not
authorize it. Do not run full 2016-2023 or set `GO_FOR_ABLATION`; those require
explicit approval and later full-data critical-gate validation.
