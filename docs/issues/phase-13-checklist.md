# Phase 13 issue checklist — benchmark-v1 freeze

Status: **complete; Phase 14 ready**. On 2026-07-29 the project owner confirmed that the
non-author review approved Benchmark v1 and P0/P1 were both zero. No reviewer identity,
signature, or review body was invented or persisted.

## Input conditions

- [x] Phase 12 external audit completion and P0/P1 clearance were confirmed by the owner.
- [x] The independent-review body is not fabricated or persisted.
- [x] Frozen protocol SHA-256 is
  `90e40d212b5faaff644e0041eeef92c0b0056ce9a834095a047948a1d5e42529`.
- [x] Frozen Dataset Manifest SHA-256 is
  `0ed9091f1ab96d24ef5fbd41d0d080668623e954e4f15e4a277f1c217e825eb9`.
- [x] Matrix-v6 contains 215 completed formal runs and no failed/missing run.
- [x] Formal experiment code commit is
  `6f03d3da3ed6ecbe918c5a7f9aa35cb9abfb2b83`.
- [x] Development results are excluded.

## Implementation

- [x] Add `cmag benchmark build --protocol ...`.
- [x] Add `cmag benchmark verify --benchmark ...`.
- [x] Add `cmag paper export-tables --benchmark ...`.
- [x] Add `cmag paper export-figures --benchmark ...`.
- [x] Reject overwrite of an existing Benchmark destination.
- [x] Verify all 4,743 source-package hashes before building.
- [x] Verify task/config/run identity for every formal run.
- [x] Store trades, weights and checkpoint identities by path, size and SHA-256.
- [x] Include 100 Agent Replay/directive records and a machine-readable index.
- [x] Include all 40 HPO study reports and an HPO isolation audit.
- [x] Keep ASHA classified solely as `resource_only`.
- [x] Copy the frozen protocol and Dataset Manifest into Benchmark v1.
- [x] Generate symbols, splits, seeds and run indexes.

## Tables and figures

- [x] Generate dataset, environment, strategy, cross-market, mechanism, Agent, HPO,
  runtime/cost and third-party reproduction tables.
- [x] Export every table as CSV, LaTeX, Markdown and HTML.
- [x] Generate architecture, training, return/drawdown, market, turnover, Agent-call,
  HPO-convergence, Pareto, cross-market and confidence-interval SVGs.
- [x] Store source data and run-ID mappings for every generated table and figure.
- [x] Export the verified tables and figures to `paper/generated/benchmark-v1`.

## Verification and tests

- [x] Unit tests cover build, no-overwrite, tamper detection and paper export.
- [x] Integration test covers CLI verify and both paper export commands.
- [x] Leakage tests prove HPO test invisibility and formal-results-only input.
- [x] Reproduction test proves repeated verification is identical.
- [x] Full repository suite passes: 403 tests with 85.23% coverage.
- [x] Ruff passes.
- [x] Strict mypy passes.
- [x] Frozen API/CLI/Schema contract verification passes after the planned CLI addition.
- [x] `checksums.json` verifies all 232 content files plus itself as the 233rd file.
- [x] All 233 Benchmark files have filesystem write bits removed.

## Exit conditions

- [x] `benchmarks/v1` is a write-once snapshot: the builder rejects overwrite,
  all content is checksummed, and the original build output is filesystem-sealed.
  Fresh VCS checkouts rely on the checksum contract because Git does not preserve
  ordinary-file read-only bits.
- [x] All included paper values have a source file and/or formal run IDs.
- [x] Tables and figures are generated automatically.
- [x] Hash, run/config, HPO isolation and Agent log checks pass.
- [x] Representative figure payload hashes match both embedded files and formal-run indexes.
- [x] `benchmark_report.html` is complete.
- [x] At least one non-author has reviewed Benchmark v1, as confirmed by the project owner.
- [x] The review reports zero P0/P1 findings and approves Benchmark v1.
- [x] Phase 13 is complete and Phase 14 is ready.
