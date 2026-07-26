# Phase 4 — Hyperparameter search and resource scheduling

## Goal

Deliver nine configurable hyperparameter search algorithms, independent advanced resource
schedulers, validation-only robust/multi-objective evaluation, durable resumption, reports, and a
real CPU PPO quickstart. Test data must remain structurally inaccessible to tuning.

## File changes

- `tuning/models.py`: mixed search-space, safe AST constraints, Trial, study, Pareto contracts.
- `tuning/searchers/`: common `SearchAlgorithm` plus Random, Grid, TPE, CMA-ES, NSGA-II, PSO, GA,
  DE, and SA.
- `tuning/schedulers/`: common `TrialScheduler` plus FIFO, median, ASHA, HyperBand, and PBT.
- `tuning/config.py`, `tuning/factory.py`: strict YAML models, factories, and compatibility checks.
- `tuning/store.py`: WAL-mode SQLite Trial and checkpoint persistence using strict JSON.
- `tuning/runner.py`: unified execution and failure isolation for every searcher/scheduler pair.
- `tuning/objectives.py`: robust portfolio score, multi-objective tuple, and Pareto extraction.
- `tuning/rl_objective.py`: train-only PPO training and validation-only objective calculation.
- `tuning/workflow.py`, `cli/app.py`: resumable `cmag tune --config` and locked parameters.
- `tuning/reports/`: deterministic JSON and Markdown study reports.
- `configs/train/ppo_tune_smoke.yaml`: eight-timestep CPU PPO Trial base.
- `configs/tune/ppo_pso_cpu.yaml`: four-particle, two-generation PSO/ASHA smoke study.
- `tests/tuning/`: properties, mathematical benchmarks, schedulers, persistence, reports,
  partition-safe PPO, resumption, and CLI integration.
- `docs/tuning-contract.md`: architecture, data, objective, persistence, and final-model rules.

## Design decisions

1. Searchers and resource schedulers use different protocols and registries. ASHA, HyperBand, and
   PBT cannot be selected as search algorithms.
2. All optimizers operate on a normalized unit vector, while one `SearchSpace` owns mixed-type
   decoding and constraint validation.
3. Conditional and cross-parameter expressions use a restricted AST interpreter. Dynamic
   execution, calls, attribute access, and unknown names are prohibited.
4. The nine algorithms use NumPy to keep the CPU reference dependency-light. Optional Optuna,
   SciPy, Ray, and GPU adapters must preserve the public contracts.
5. SQLite is the local source of truth. Searcher and scheduler random states are strict-JSON
   checkpoints, and failed Trials remain visible.
6. The scalar objective penalizes median drawdown, median turnover, and cross-seed Sharpe
   instability. Multi-objective mode retains the nondominated set under explicit directions.
   Stage B requires at least five seeds and expanding walk-forward validation.
7. The PPO evaluator constructs only train and validation partitions. It raises if a test
   capability appears, and reports contain an explicit no-test marker.
8. Candidate validation happens before training, including PPO rollout/batch geometry.
9. Primary, weighted, or Pareto-first selection locks parameters. PPO parameters are independently
   retrained with a non-HPO seed; final test evaluation remains separate and write-once.
10. CPU execution remains authoritative. Ray, multi-GPU execution, live early cancellation, and
    distributed weight transfer are later extensions.

## Tests

Tests cover Hypothesis-generated mixed spaces, conditional parameters, cross constraints, Sphere
and Rosenbrock for all nine algorithms, fixed-seed equivalence, JSON checkpoint/resume, bounds,
NSGA-II Pareto behavior, all five schedulers, compatibility rejection, PBT exploit patches, SQLite
identity checks, failed Trial continuation, split-run versus uninterrupted equivalence, robust
objective arithmetic, report contents, test-partition absence, real eight-timestep PPO validation,
PSO 4×2 execution, and CLI requirements.

The repository-wide leakage guard also verifies that core source contains no call to `eval`.

## Acceptance result

Phase 4 passed locally on Python 3.12.13, NumPy 2.1.3, Stable-Baselines3 2.6.0, and PyTorch
2.7.1+cpu:

| Check | Result |
|---|---|
| Search algorithms | 9/9 implemented and registered |
| Resource schedulers | FIFO, median, ASHA, HyperBand, PBT in a separate registry |
| Mathematical tests | Sphere and Rosenbrock passed for every searcher |
| Search checkpoint/resume | Fixed-seed next suggestions matched |
| Trial persistence | SQLite running/terminal/failure/checkpoint round trips passed |
| PPO CPU quickstart | PSO 4 particles × 2 generations = 8/8 completed Trials |
| PPO study resume | Second CLI run retained 8 Trials and the same best Trial 7 |
| Data authority | 8 validation audit files; zero test artifacts/access |
| Locked selection | Trial 7 selected on validation and independently retrained |
| Per-searcher PPO | 9/9 searchers completed a real partition-safe PPO Trial |
| Stage B policy | ≥5 seeds and ≥2 walk-forward folds enforced |
| Full test suite | 192 passed |
| Branch coverage | 88.11%, above the 85% gate |
| `ruff check src tests` | Passed |
| `mypy src` | Passed for 85 source files |
| `pip check` | No broken requirements |
| `python -m uv lock --check` | Passed; 111 packages resolved |

The machine-readable record is `docs/tuning/phase4-acceptance.json`. The synthetic sample objective
is an engineering smoke result and is not investment performance.

## Open issues

- The local scheduler API supports intermediate results, stopping, promotion, and PBT exploit
  patches. Long-running SB3 jobs still need an incremental executor to cancel at intermediate
  checkpoints rather than report only terminal resource.
- Phase 9 subsequently delivered optional Ray Trial evaluation and per-Trial GPU placement while
  preserving independent searcher/scheduler authority. Distributed PBT checkpoint transfer, live
  intermediate cancellation, and multi-node recovery remain future scaling work.
- Production studies require longer approved train/validation folds and more seeds than the CPU
  smoke configuration.
- The remote CUDA server remains unchanged because password-only authentication must not be placed
  in source, command history, logs, or process arguments. An SSH key or secure secret channel is
  required.
