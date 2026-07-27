# Phase 12 issue checklist — formal research experiments

Status: **in progress**. Cutoff-safe protocol-v4 and source identities are frozen. No formal result is accepted
until its run audit, leakage gate, five-seed coverage, and independent-review gate pass.

## Input conditions

- [x] Phase 11 is closed and `v1.0.0-rc2` is the experiment software release.
- [x] Linux CPU and bounded, network-disabled Docker evidence passed on the rc2 commit.
- [x] Independent participants reported normal operation and the owner completed P0/P1 clearance.
- [x] No Phase 12 result or Benchmark was created from development/smoke runs.
- [x] The Phase 12 requirements in the Phase 10–17 execution report were read in full.

## Protocol and data freeze

- [x] Inventory every raw source by path, SHA-256, market, symbol, coverage, and quality result.
- [x] Validate universe eligibility using only observations available by `2021-02-01`.
- [x] Retain fixed selected symbols after formation; censor from the first later invalid
  observation without repair, replacement, or future-informed reselection.
- [x] Record exact non-OHLCV rows whose five price/volume fields are all absent.
- [x] Select 20 symbols per market by frozen salted SHA-256 order.
- [x] Reserve four symbols per market as unseen-stock evaluation assets.
- [x] Save the official ECB EXR response as an immutable local input.
- [x] Build and integrity-check the 80-symbol canonical dataset snapshot.
- [x] Freeze train, validation, locked test, and three walk-forward intervals.
- [x] Freeze market rules, risk constraints, algorithms, HPO budgets, Agent contract, seeds,
  statistics, and Groups A–F.
- [x] Block and preserve protocol-v1 after detecting its future-coverage selection condition,
  before any formal matrix or formal result was created.
- [x] Block and preserve protocol-v2 after detecting its missing Prompt source binding,
  before any formal matrix or formal result was created.
- [x] Bind the exact formal Prompt bundle path and hash in protocol-v3.
- [x] Block and preserve protocol-v3 after detecting invalid physical-prefix censor semantics
  for globally unsorted sources, before any formal matrix or formal result was created.
- [x] Freeze global ordering/duplicate failures to the formation window only.
- [x] Write `experiments/protocol_v4.sha256` once and reject overwrite.
- [x] Verify protocol, source inventory, ECB snapshot, and processed-manifest hashes.
- [x] Preserve and supersede run-matrix-v4 after the matrix-bound Linux GPU gate detected
  misleading CPU/GPU runtime metadata; declare all 60 completed v4 records ineligible.
- [x] Freeze and preserve run-matrix-v5 against the corrected metadata commit.
- [x] Supersede run-matrix-v5 before formal execution after its resource audit found CPU-only
  formal HPO trials and a coverage-flag defect in the remote convenience script.
- [ ] Freeze run-matrix-v6 against the GPU-enabled corrected code without changing protocol-v4.

## Isolation and safety gates

- [x] Fit normalizers only on the training capability (the frozen Phase 12 drivers do not fit a
  cross-partition normalizer).
- [x] Deny HPO any test capability, test metric, or test-derived selection signal.
- [x] Deny random time shuffle and future FX/universe/adjustment lookup.
- [x] Keep the deterministic risk layer mandatory in every Agent and ablation run.
- [x] Prevent LLM tools from mutating account state.
- [x] Retain failed run directories and structured failure reasons.
- [ ] Prove that every formal run references protocol, dataset, commit, seed, environment,
  hardware, duration, and status.

## Group A — environment correctness

- [ ] Cost, slippage, T+1, suspension, price limit, lot, holiday, FX, projection, cash,
  holdings, and NAV cases are hand-computable and automated.
- [ ] Accounting error is no greater than `1e-8`.
- [ ] Structured expected/observed/error evidence is written.

## Group B — strategy compatibility

- [ ] Cash, Buy-and-Hold, Equal-Weight, Risk-Parity, and Mean-Variance use the shared protocol.
- [ ] PPO, SAC, and TD3 run for all five frozen seeds.
- [ ] Rebalancing, costs, risk constraints, and metrics are identical across methods.

## Group C — cross-market generalization

- [ ] All four leave-one-market-out routes run for five seeds.
- [ ] Single-market, joint-market, unseen-stock, and rule-sensitivity comparisons are complete.

## Group D — market mechanism ablation

- [ ] Every frozen mechanism ablation runs for five seeds.
- [ ] The safety-preserving minimum-risk-projection ablation is clearly distinguished from
  bypassing the deterministic risk layer.

## Group E — LLM Agent ablation

- [ ] All seven frozen Agent presets run with `deepseek-v4-pro`.
- [ ] Prompt hash, temperature, round count, permissions, Provider identity, and Replay are fixed.
- [ ] Full credential-redacted Replay, tool audit, safety audit, token/cost, and timing are saved.

## Group F — HPO

- [ ] Default, Random, TPE, CMA-ES, PSO, GA, DE, and NSGA-II use equal budgets.
- [ ] ASHA is recorded solely as an independent resource scheduler.
- [ ] Selection reads train/walk-forward validation only.
- [ ] The locked test is evaluated once after configuration lock.

## Statistics, automation, and exit conditions

- [ ] Every core comparison has at least five successful frozen seeds and fold-level evidence.
- [ ] Mean, standard deviation, median, 95% CI, best, and worst are generated automatically.
- [ ] Wilcoxon paired tests, Holm correction, and paired rank-biserial effect sizes are generated.
- [ ] Tables and figures are generated only from auditable formal run IDs.
- [ ] Re-run unit, integration, leakage, reproduction, Ruff, and strict mypy gates on the
  matrix-v6-bound code commit (matrix-v4 Linux gate: 379 passed, one skipped, one blocking
  metadata assertion failed; protocol, frozen contracts, Ruff, mypy, and 48 targeted tests
  passed).
- [ ] Independent review is recorded without inventing participant evidence.
- [ ] All Phase 12 exit criteria pass before Phase 13 begins.
