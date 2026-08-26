# Decision — Reconstructed Schedule Flight Chain

Decision date: 2026-08-26  
Decision owner: Full-development reconstruction gate  
Status: **GO_FOR_ABLATION**

## Decision

The versioned **Reconstructed Schedule Flight Chain** derived from canonical
Tabular is approved for later controlled ablation:

- Tabular-only;
- Tabular plus Reconstructed Chain Features.

It remains disabled by default and outside the core ML pipeline. Approval does
not assert predictive improvement or select it for the final model.

## Evidence

- Full 2016–2023 reconstruction: 48,389,162 source/eligible/mapped rows,
  100% coverage, 38,004,376 chains, and 2,713,268 inbound ATL targets.
- Every year passed unique stored `flight_key_v1`, valid `schedule_chain_v1`
  identifiers, single-chain membership, leakage, ATL mapping, raw-integrity,
  and 2024-isolation gates.
- Per-year logical fingerprints and the aggregate evidence are recorded in
  `artifacts/manifests/flight_chain_reconstructed_manifest_v1.json`.
- Final regression verification: 108 tests passed; smoke guard passed.

## Contract and claim boundary

The chain groups only normalized `source_year`, `FL_DATE`, `OP_CARRIER`, and
`OP_CARRIER_FL_NUM`, ordered by scheduled departure with deterministic
tie-breakers. It is a schedule/service-number context, not an aircraft ID,
tail number, registration, physical airframe, same-aircraft chain, or physical
aircraft rotation. `physical_aircraft_identity = false`.

Full membership is retained. Chains longer than six are not truncated or
padded; `max_context_length=6` belongs only to a future feature transformer.
Weather and `FLIGHTS` remain excluded, and 2024 remains the sealed final
holdout.

## Independent raw-chain decision

**Original Aeolus raw Flight Chain `.pt`: `FINAL — NO_GO`.** The raw archives
still lack exact canonical mapping, encoder provenance, and defensible temporal
safety. This decision does not reopen, reinterpret, or supersede
`docs/decisions/decision_include_chain.md`.

## Downstream authorization

The next permitted step is to design a separate, schedule-only feature
contract and run a development-only ablation. No chain feature is enabled in
the core route by this decision. No model training, HPO, SHAP, optimization,
simulation, or 2024 access occurred during reconstruction.
