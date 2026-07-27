# Phase 12 — formal research experiments

Status: **in progress**. Protocol-v4 inputs are frozen and executable; the formal run matrix
and publication-eligible results are not yet frozen or executed.

## Goal and entry conditions

Run Groups A–F under one immutable, leakage-safe protocol. Phase 11 is closed on public release
`v1.0.0-rc2`; Linux CPU, bounded offline Docker, wheel provenance, computational replay,
independent functional-review attestation, and the owner-supplied P0/P1 clearance have passed.
Development quickstarts, debugging artifacts, single-seed best cases, and any HPO access to the
locked test partition are inadmissible.

## Blocking correction before formal execution

Protocol-v1 selected sources only when they covered the complete experiment window through
`2025-09-30`. That condition used future source availability and therefore created a
future-universe/survivorship leak. The issue was detected before the formal matrix was frozen and
before any formal result existed. Protocol-v1 and its original hashes remain preserved, while
`experiments/data/protocol_v1_supersession.json` marks it as blocked and superseded.

Protocol-v2 corrected the universe leak, but it bound a Prompt hash without a versioned Prompt
source path. It too was blocked before matrix freeze or formal execution. Protocol-v3 preserves
the v2 dataset contract and adds an independently verifiable Prompt bundle path and hash.

Protocol-v3 then exposed an execution-geometry bug during real-data CPU checking: physical-row
prefix censoring is invalid for a globally unsorted source containing multiple chronological
blocks. Two selected sources retained a 2024/2025 block instead of the formation window, delaying
common valuation until `2025-02-25`. It was blocked before matrix freeze or formal execution.

Protocol-v4 forms the fixed universe on `2021-02-01` using only data visible by that date.
Formal training begins on `2021-02-02`. Selection uses cutoff-window availability, cutoff-window
quality, and a salted outcome-independent hash. Later source errors cannot remove or replace a
symbol. Local bad-bar failures use a physical prefix; global ordering/duplicate failures retain
only the validated formation window. No row is imputed, repaired, sorted, deduplicated, or
future-backfilled.

## Frozen inputs

- `experiments/protocol_v4.yaml` and `.sha256`: current immutable experiment contract.
- `experiments/agents/prompt_bundle_v1.json`: exact formal role prompts and user-message
  serialization contract.
- `experiments/data/source_inventory_v3.json`: all 978 source identities, cutoff-visible
  eligibility, fixed selection decisions, and later censor audit.
- `experiments/data/ecb_exr_20201201_20250930.csv`: immutable official ECB EXR response.
- `experiments/data/dataset_snapshot_v3.json`: canonical snapshot build evidence.
- `data/processed/formal_v3/`: local, non-redistributed 80-symbol canonical snapshot.

| Item | SHA-256 |
|---|---|
| Source inventory v3 | `4102bbd96b71001dd44c397c2f406f2e4109d864b1a59cc25e67395bcd56f58d` |
| ECB EXR snapshot | `a84793dceb4a5d61f30cf97033c5c51805ee87b41c60df8bb74fa0576294ace1` |
| Processed dataset manifest v3 | `0ed9091f1ab96d24ef5fbd41d0d080668623e954e4f15e4a277f1c217e825eb9` |
| Prompt bundle v1 | `9ee7ad5d5e7cd91da1a0f629d39e7554005aeb0b1d8b0489ec46e388b6c2c938` |
| Protocol v4 | `90e40d212b5faaff644e0041eeef92c0b0056ce9a834095a047948a1d5e42529` |

The v3 dataset snapshot used by protocol-v4 contains 80 fixed symbols, 73,193 accepted daily rows, four markets, 16
model-visible and four held-out symbols per market, 82 manifest-controlled files, and zero
accepted-slice quality errors. It records 255 semantic non-OHLCV exclusions in selected source
files, 21 post-formation source censors, `source_rows_repaired=false`, and
`future_data_used_for_source_selection=false`.

## Frozen protocol decisions

1. Train, validation, locked test, and three walk-forward intervals are chronological. Random
   time shuffle is prohibited and normalizers fit only through the training capability.
2. Costs, slippage, next-open execution, asynchronous calendars, market rules, FX lookup, and
   deterministic risk projection are common across comparisons.
3. Group D never bypasses deterministic safety. Its least restrictive variant still enforces hard
   leverage, cash, and account-mutation invariants.
4. HPO receives train and walk-forward validation only. ASHA remains a resource scheduler;
   it is not represented as a search algorithm. Locked test evaluation occurs only after a
   configuration lock.
5. Agent runs fix `deepseek-v4-pro`, temperature zero, prompt hash, two-round limit,
   read/compute-only tools, replay, and a deterministic risk boundary.
6. Core comparisons use five frozen seeds and report dispersion, Student-t 95% intervals,
   paired Wilcoxon tests, Holm correction, and paired rank-biserial effect sizes.

## Automation and current acceptance

The experiment package implements strict protocol and matrix models, append-only run auditing,
Groups A–F drivers, statistics, tables, figures, and independent-review gating. The pre-matrix
gate passes 381 repository tests with 85.75% coverage, Ruff, strict mypy, the rc2 frozen-contract
check, the protocol-v4 input verifier, and the real 80-symbol CPU/accounting quickcheck. The
quickcheck confirms the first training execution is exactly `2021-02-02`, maximum accounting
error is `4.656612873077393e-10`, all ten hand-computable cases have zero error, and no test
metric is accessed. It remains development-only and is not eligible as a formal result.

Run-matrix-v4 was frozen against commit
`16490650fd984ab83b69c336d26e1c340b16048b`, then failed its first matrix-bound Linux GPU
gate: a CPU-selected model recorded the host's visible 4090 D as its active `gpu_model`. The
matrix, checksum, 60 completed records, and structured supersession notice are preserved, but
none is eligible for formal aggregation or a Benchmark. Protocol-v4 itself is unchanged because
the defect concerns runtime metadata, not data, partitions, methods, seeds, or statistical
rules. Corrected code must pass all gates and freeze run-matrix-v5 before experiments restart.

Run-matrix-v5, all eligible formal runs, aggregate statistics, and independent review remain
pending.

Phase 12 is not complete. Phase 13 is not ready.
