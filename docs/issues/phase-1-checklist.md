# Phase 1 issue checklist

## Scope

- [x] Audit all four source-market layouts and encodings.
- [x] Implement strict immutable `OHLCVRecord`.
- [x] Enforce finite/non-negative OHLCV and high/low envelopes.
- [x] Enforce market/currency/timezone consistency.
- [x] Implement canonical CSV and Parquet loaders/writers.
- [x] Implement Yahoo-style HK/JP/US CSV adapter.
- [x] Implement RESSET CN `.xls`/`.xlsx` adapter.
- [x] Preserve local trading dates without UTC date shifts.
- [x] Preserve source row cardinality and report invalid rows.
- [x] Detect missing values, invalid numerics, duplicate keys, date order, and metadata mismatch.
- [x] Implement SHA-256 dataset Manifest construction and verification.
- [x] Reject Manifest path traversal.
- [x] Create a redistributable deterministic four-market sample.
- [x] Add instruments and FX sample artifacts.
- [x] Replace the Phase 1 CLI placeholder with `cmag data validate`.
- [x] Run a one-file-per-market source smoke audit.
- [x] Run the full 978-file source compatibility audit.
- [x] Add unit, property, leakage, integration, and hash-regression tests.
- [x] Pass 55 tests and the 85% coverage gate.
- [x] Pass `ruff check .`.
- [x] Pass `mypy src`.
- [x] Pass dependency and lock-file consistency checks.
- [ ] Normalize the full private source tree into canonical partitioned Parquet.

## Deferred by phase boundary

- Full canonical conversion is intentionally not performed until source anomalies have an approved
  handling policy; Phase 1 reports them without mutation.
- Trading calendars and FX conversion logic move to Phase 2.
- Leakage-safe feature fitting and walk-forward split capabilities move to Phases 2–3.
