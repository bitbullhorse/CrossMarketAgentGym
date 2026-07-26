# Python API reference

CrossMarketAgentGym follows semantic versioning from `0.1.0`. Objects documented here are the
supported integration surface; internal helpers beginning with `_` may change without notice.

## Data

`crossmarket_agentgym.data`

- `validate_manifest_dataset(root)` verifies every packaged OHLCV artifact and manifest hash.
- `validate_legacy_dataset(root, ...)` performs bounded, non-destructive mixed-source inspection.
- `validate_configured_dataset(config, ...)` dispatches the strict configured validation path.
- `MarketDataPanel.from_manifest(...)` builds the aligned cross-market panel used by environments.

Canonical schema, timezone, currency, and manifest rules are defined in `data-contract.md`.

## Environment

`crossmarket_agentgym.environments`

- `CrossMarketPortfolioEnv(panel, config, partition=...)` is the Gymnasium portfolio environment.
- `ConstraintProjector(config, markets).project(...)` maps proposed actions into the deterministic
  feasible set.
- `run_environment_checks(config)` executes Gymnasium/SB3 compatibility, finite-value, random
  action, and accounting checks.
- `EnvironmentConfig` is the immutable market, cost, reward, and hard-risk configuration.

The LLM packages do not own or import the account/execution mutation implementation.

## Training and evaluation

`crossmarket_agentgym.rl`

- `load_train_run_config(path)` loads a strict train/validation configuration.
- `execute_training_run(config)` fits only on the train capability and writes validation evidence.
- `evaluate_saved_run(run_dir, partition="test")` is the separate locked-test boundary.
- `TrainerConfig` selects PPO, SAC, TD3, or the optional A2C compatibility path.

## Hyperparameter optimization

`crossmarket_agentgym.tuning`

- `execute_tuning_run(config)` runs the train/validation-only tuning workflow.
- `build_searcher(config, search_space)` constructs one of the nine core search algorithms.
- `build_scheduler(config)` constructs FIFO, Median Stopping, ASHA, HyperBand, or PBT
  independently of the searcher.
- `StudyStore` persists trials and component state in SQLite.
- `LocalTrialExecutor` is the deterministic reference evaluator.
- `RayTrialExecutor` optionally allocates per-Trial CPU/GPU resources while preserving result
  order and the independent scheduler authority.

Searchers generate candidates. Schedulers allocate resources and stop/promote/exploit trials; the
two registries and protocols remain separate from local/Ray execution.

## Agents

`crossmarket_agentgym.agents`

- `AgentRuntime(config, ...)` executes both one-instance and multi-instance teams.
- `execute_agent_runtime(config)` is the audited Phase 6 workflow.
- `execute_phase7_stack(config)` runs independently enabled Research, Risk, and Hierarchical
  layers through the same runtime.
- `replay_phase7_bundle(path)` recomputes administrator intersection, fusion, and projection from
  validated directives.
- `AgentRegistry.register(...)` and the `crossmarket_agentgym.agents` entry-point group support
  custom typed roles.

All online Agent configurations require model `deepseek-v4-pro`; credentials are environment-only.

## Reporting and service

`crossmarket_agentgym.reporting`

- `build_run_index(workspace_root, runs_root, ...)` creates the bounded metadata whitelist.
- `build_softwarex_report(config)` generates Markdown, HTML, CSV, JSON, SVG, and manifest
  artifacts.
- `build_benchmark_comparison(...)` creates a descriptive comparison with
  `selection_authority=False`.

`crossmarket_agentgym.api`

- `create_app(config)` creates the optional read-only FastAPI application.
- `run_service(config)` starts the explicit Uvicorn process.

## Release and reproduction

`crossmarket_agentgym.release`

- `run_cpu_quickstart(workspace_root=".", smoke_steps=64)` validates the packaged sample and
  environment without network or LLM use.
- `reproduce_run(workspace_root, runs_root, run_id)` verifies provenance and performs the
  available deterministic Replay without retraining or account mutation.
- `check_release_readiness(workspace_root=".")` validates local release metadata and security
  assets without publishing.
- `build_release_manifest(dist_dir)` hashes built wheel/source archives into a credential-free
  manifest.

Every public result is a strict Pydantic model and can be serialized with
`model_dump(mode="json")` or `model_dump_json()`.
