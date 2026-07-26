# Phase 4 issue checklist

## Search-space and algorithms

- [x] Define strict float, integer, categorical, and boolean parameter specifications.
- [x] Support log scale, finite step, conditional parameters, and cross-parameter constraints.
- [x] Reject invalid candidates before training.
- [x] Remove all dynamic `eval` use from condition and constraint handling.
- [x] Implement Random, Grid, TPE, CMA-ES, NSGA-II, PSO, GA, DE, and SA.
- [x] Verify fixed-seed determinism, bounds, failures, and checkpoint resumption.

## Resource scheduling

- [x] Define a `TrialScheduler` protocol separate from `SearchAlgorithm`.
- [x] Implement FIFO and median stopping.
- [x] Implement ASHA as an independent rung scheduler.
- [x] Implement HyperBand as independent deterministic ASHA brackets.
- [x] Implement PBT exploit/perturb decisions as an independent scheduler.
- [x] Define and test the searcher/scheduler compatibility matrix.

## Execution, objectives, and persistence

- [x] Implement the unified `TrialRunner`.
- [x] Persist running, completed, failed, and pruned Trial records in SQLite.
- [x] Persist strict-JSON searcher and scheduler checkpoints.
- [x] Resume without changing Trial IDs or candidate order.
- [x] Continue a study after a failed objective.
- [x] Implement robust and multi-objective validation-only scoring.
- [x] Generate Pareto, JSON, and Markdown reports.
- [x] Lock validation-selected parameters without test metrics.
- [x] Make primary, weighted, and Pareto-first final selection configurable.
- [x] Default Stage B to at least five seeds and expanding walk-forward folds.
- [x] Independently retrain locked PPO parameters with a non-HPO seed.
- [x] Reject resume when the immutable study configuration fingerprint changes.

## PPO and acceptance

- [x] Reuse Phase 3's unified trainer and partition capabilities.
- [x] Construct only train and validation environments during HPO.
- [x] Add a strict `cmag tune --config` workflow.
- [x] Add and run a PSO 4-particle, 2-generation CPU PPO study.
- [x] Run one real partition-safe PPO Trial through each of the nine searchers.
- [x] Rerun the same study and verify exact SQLite resumption.
- [x] Run all unit/integration/leakage tests.
- [x] Run Ruff, strict MyPy, dependency, and lock checks.

## Deferred extensions

- [x] Add optional Ray executors after preserving identical local contracts.
- [x] Add multi-GPU placement after the CPU executor remains the reference behavior.
- [ ] Connect intermediate SB3 checkpoints to live ASHA/HyperBand cancellation for long jobs.
- [ ] Add distributed PBT weight transfer; local PBT already emits deterministic exploit patches.
