# Phase 12 — formal research experiments

Status: **machine gates passed; awaiting independent review**. Protocol-v4, run-matrix-v6,
all 215 formal runs, statistics, figures, and post-experiment software gates are complete.
The results are not publication-eligible and Phase 13 is not ready until a real independent
reviewer approves them with P0/P1 equal to zero.

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
rules.

Run-matrix-v5 then passed the corrected Linux GPU test gate but failed its pre-execution
resource audit before any formal task ran: the formal HPO subclass still inherited a CPU-only
trainer override, and the remote convenience script did not disable the whole-repository
coverage threshold when selecting only experiment/leakage tests. Its zero-result matrix and
supersession notice are preserved. The DeepSeek endpoint separately returned HTTP 200 for the
exact frozen `deepseek-v4-pro` identifier without persisting the credential or response body.

Run-matrix-v6 is frozen against commit
`6f03d3da3ed6ecbe918c5a7f9aa35cb9abfb2b83`, with SHA-256
`c809334e9c8de407119610bf0c78c811ead7eabc8b38cb4662e183e193569c62`.
It contains 215 tasks: A 10, B 40, C 45, D 45, E 35, and F 40. Every task completed, every
group boundary passed, no formal run failed or went missing, and no development result was used.
The full immutable remote evidence occupies approximately 230 GB under
`results/formal/protocol-v4-matrix-v6`.

Group C's `single_market` and `leave_one_market_out` tasks each contain four separately locked
target-market subruns. Their audit count of four test evaluations means one evaluation per
locked model, not four evaluations of one selected model. The initial external boundary checker
incorrectly expected one; its failed report is preserved, the checker semantics were corrected,
and all 40 affected subruns were verified to have individual pre-test locks.

The formal aggregation contains 2,390 normalized metric rows, 494 descriptive-statistic rows,
200 paired tests, and five generated SVG figures. Every non-environment comparison has at least
five seeds. The Agent audit covers 35 runs and 100 Replay files; Replay consistency is true,
the deterministic risk layer was never bypassed, and a scan of 556 Agent text artifacts found
no credential pattern. Every HPO method has five seeds, 24 trials per seed, three walk-forward
folds, at least 72 validation artifacts per run, and exactly one locked-test access. ASHA is
recorded only as `resource_only`.

Post-experiment gates on the matrix-bound commit passed:

- protocol and input integrity: passed;
- unit: 91 passed;
- integration: 16 passed and one local-source-data test skipped;
- leakage: 14 passed;
- reproduction: 15 passed;
- frozen rc2 contracts: 10 passed;
- full suite: 380 passed, one skipped, 85.69% coverage;
- Ruff: passed;
- strict mypy: 152 source files passed.

The automated summary currently reports exactly one blocker:
`INDEPENDENT_REVIEW_MISSING`. A credential-free review archive with 4,744 files was generated
at `results/formal/protocol-v4-matrix-v6/review/phase12-review-v1.tar.gz`, SHA-256
`fc33a0e37f141d0033fbf3b475b8b79a0417a6007c727c456c87cafe78c7e023`.

## Provisional completion report

### Summary

All executable Phase 12 work and machine-verifiable exit criteria are complete. Independent
review is the sole remaining blocking input.

### Added files

- `experiments/run_matrix_v6.json`
- `experiments/run_matrix_v6.sha256`
- machine evidence, statistics, figures, gates, and review package under the ignored formal
  result root

### Modified files

- `docs/issues/phase-12-checklist.md`
- `docs/phases/phase-12.md`
- `docs/design-log.md`

### Design decisions

- Preserve superseded protocols and matrices rather than editing frozen identities.
- Treat a multi-target Group C task as one test access per independently locked submodel.
- Keep external GPU allocation separate from HPO search and ASHA scheduling.
- Do not fabricate independent reviewer identity, findings, or approval.

### Tests and acceptance

All formal run, leakage, accounting, Replay, HPO isolation, statistics, unit, integration,
reproduction, lint, type, and frozen-contract machine gates passed. The review gate correctly
fails closed.

### Known issue and next-phase readiness

`experiments/review/phase12_independent_review.md` is intentionally absent. Phase 12 remains
open and Phase 13 remains blocked until an independent reviewer completes the supplied package,
records P0/P1 as zero, and approves the results. After that input is received,
`scripts/summarize_phase12.py` must be rerun and must return `phase12_complete=true` and
`phase13_ready=true`.
