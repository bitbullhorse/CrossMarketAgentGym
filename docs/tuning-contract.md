# Hyperparameter tuning contract

## Component boundary

The tuning pipeline is:

`SearchAlgorithm -> TrialSuggestion -> TrialScheduler -> ObjectiveEvaluator -> StudyStore`

Search algorithms choose parameter candidates. Resource schedulers decide whether a running
candidate should continue, stop, promote, or exploit another trial. Schedulers never generate a
new search candidate, and searchers never own resource allocation.

## Search algorithms

The built-in registry contains exactly these nine CPU-capable algorithms:

- Random Search
- Grid Search
- Tree-structured Parzen Estimator (TPE)
- Covariance Matrix Adaptation Evolution Strategy (CMA-ES)
- Non-dominated Sorting Genetic Algorithm II (NSGA-II)
- Particle Swarm Optimization (PSO)
- Genetic Algorithm (GA)
- Differential Evolution (DE)
- Simulated Annealing (SA)

Every implementation accepts a fixed seed, stays within normalized bounds, handles mixed
parameter types through one `SearchSpace`, and exposes strict-JSON checkpoint state.

## Resource schedulers

FIFO, median stopping, ASHA, HyperBand, and Population Based Training are in a separate scheduler
registry. ASHA owns asynchronous rungs, HyperBand owns deterministically assigned ASHA brackets,
and PBT emits an explicit exploit source plus parameter patch. A compatibility matrix rejects
unsupported pairings before any Trial starts.

## Search-space safety

Parameter kinds are float, integer, categorical, and boolean. Log scales, finite steps,
conditional activation, and cross-parameter constraints are supported. Conditions and constraints
are interpreted by a restricted AST evaluator; neither Python `eval` nor arbitrary calls are
permitted. Invalid candidates, including PPO batch/rollout violations, are rejected before
training.

## Data boundary

HPO may use only training and validation capabilities. The PPO objective calls
`build_partitioned_environments(..., include_test=False)` and rejects any environment set other
than `{train, validation}`. Training receives only the train capability; objective calculation
accepts only a validation result. Test metrics are absent from SQLite, reports, and locked
parameters.

Stage B is the default and requires at least five distinct seeds plus two or more expanding-train,
forward-validation folds (three folds by default). The explicitly labeled Stage A budget may use
fewer seeds/folds for CPU contract smoke tests. Cross-seed instability is calculated after
aggregating each seed across its walk-forward folds.

The default robust objective is:

`median(validation Sharpe) - 0.5 * median(max drawdown) - 0.05 * median(turnover)
- 0.25 * population standard deviation(validation Sharpe)`

Multi-objective mode returns median Sharpe (maximize), median max drawdown (minimize), median
turnover (minimize), Sharpe instability (minimize), and optionally median training time
(minimize). NSGA-II and the report generator retain the nondominated Pareto front.

## Persistence and resumption

SQLite stores immutable study directions and configuration fingerprint, stable Trial IDs,
parameters, terminal status,
objectives, metrics, resource use, errors, and component checkpoints. JSON serialization rejects
NaN and Infinity. Suggestions are persisted before objective execution. A repeated `cmag tune`
command resumes the same searcher and scheduler state.

## Final model policy

Tuning locks parameters using a configurable primary, weighted, or stable Pareto-first rule and
records `test_set_accessed=false`. A locked PPO configuration is independently retrained with a
seed excluded from HPO before any final test evaluation. Test evaluation remains the separate,
write-once Phase 3 command, and its result must never be fed back into the study.
