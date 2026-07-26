# Phase 3 issue checklist

## Scope

- [x] Define one `RLTrainer` protocol for train/evaluate/save/load.
- [x] Implement unified Stable-Baselines3 PPO, SAC, TD3, and optional A2C adapters.
- [x] Implement MLP, shared-asset MLP, and Transformer policy extractors.
- [x] Retain a non-exclusive IR-MoE adapter interface.
- [x] Implement Cash, Buy and Hold, Equal Weight, Risk Parity, Mean-Variance, Momentum, and Minimum
  Variance baselines.
- [x] Implement shared trades, weights, and metrics evaluation records.
- [x] Implement checkpoint, validation evaluation, early stop, NaN/Inf guard, max-drawdown guard,
  resource monitor, audit, and metrics callbacks.
- [x] Record seed, configuration hash, dataset hash, dependency versions, and checkpoint metadata.
- [x] Add explicit train, validation, test, and smoke partition capabilities.
- [x] Isolate each partition in a copied market panel.
- [x] Prevent the trainer from accepting test or smoke capabilities.
- [x] Prevent feature-standardizer fitting on validation or test.
- [x] Ensure training does not construct a test environment.
- [x] Make test evaluation a separate non-overwriting CLI operation.
- [x] Replace Phase 3 `train` and `evaluate` placeholders.
- [x] Add strict PPO, SAC, and TD3 CPU configurations.
- [x] Run the PPO 1,000-timestep CPU quickstart.
- [x] Run SAC and TD3 CPU compatibility training.
- [x] Verify checkpoint reload with zero deterministic action difference.
- [x] Verify independent same-seed CPU runs have exact action equality.
- [x] Pass 115 tests and the 85% branch-coverage gate.
- [x] Pass `ruff check .`.
- [x] Pass `mypy src`.
- [x] Pass `pip check`.
- [x] Pass `python -m uv lock --check`.

## Deferred by phase boundary

- Production-scale training remains blocked on the approved source-anomaly remediation and
  canonical conversion policy.
- Multi-seed walk-forward experiments and hyperparameter optimization belong to Phase 4.
- Remote CUDA validation requires a non-logged SSH key or another secure authentication channel.
- Ray distributed training is an optional extension after the CPU workflow and Phase 4 scheduler
  contracts are stable.
- The synthetic five-session validation/test metrics are not financial-performance evidence.
