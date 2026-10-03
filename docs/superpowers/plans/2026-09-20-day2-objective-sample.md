# Day 2 Objective and Sample-Size Plan

## Scope

Run only the locked Phase A Fold 4 protocol: train years 2016--2021,
validation year 2022, monthly stratified sampling, five seeds 42--46.
The work uses V1 and V1.1 only, keeps the Week 5 XGBoost parameters frozen,
and never reads 2023/2024 or actual-operation/weather/chain fields.

## Sequence

1. Confirm the HPO selection metric and the benchmark training objective.
2. Add a new objective benchmark script with four versioned A/B reports:
   V1/V1.1 crossed with `reg:squarederror` and `reg:absoluteerror`.
3. Select the better objective by mean skill score, then scan 25K/75K/150K/
   250K training rows per year while keeping validation at 25K.
4. Rerun the best sample size with ten seeds for stability.
5. Write a Day 2 note with evidence, gates, and a Day 3 recommendation.

## Verification

- Focused unit tests verify objective construction and frozen HPO parameter
  handling before benchmark execution.
- Existing suite is rerun with a workspace-local pytest temporary directory.
- Reports include source hashes, allowed years, seeds, sample sizes, and
  execution status; Day 1 reports/manifests remain untouched.
