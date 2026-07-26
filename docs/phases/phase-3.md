# Phase 3 — DRL and baselines

## Goal

Deliver CPU-first PPO, SAC, and TD3 training through one Trainer contract; provide traditional
baselines, policy extractors, validation and safety callbacks, auditable evaluation outputs, and
reproducible checkpoints without exposing test data to training.

## File changes

- `data/partitions.py`: immutable partition capabilities and access enforcement.
- `features/normalization.py`: train-only fitted standardization.
- `environments/portfolio.py`, `environments/panel.py`: bounded transition intervals and isolated
  copied panel slices.
- `rl/config.py`, `rl/artifacts.py`: strict algorithm/callback/split configuration and checkpoint
  provenance.
- `rl/policies/`: MLP, shared-asset MLP, Transformer, registry, and IR-MoE adapter interface.
- `rl/trainers/`: common protocol plus PPO/SAC/TD3/A2C Stable-Baselines3 implementation.
- `rl/callbacks/`: checkpoint, validation, early-stop, finite, drawdown, resource, audit, and
  metrics callbacks.
- `evaluation/`: seven deterministic baselines and common trades/weights/metrics result schemas.
- `rl/workflow.py`, `cli/app.py`: partition-safe train and locked test-evaluate workflows.
- `configs/train/`: runnable PPO, SAC, and TD3 CPU configurations.
- `tests/`: policy, baseline, partition leakage, callbacks, three-algorithm, checkpoint,
  reproducibility, workflow, and CLI coverage.

## Design decisions

1. Training accepts only a `train` capability; validation metrics are callback-visible, while test
   metrics are available only to `cmag evaluate`.
2. Each partition receives a copied panel ending at its authorized execution boundary. A train
   environment has no object reference to validation/test arrays.
3. Adjacent partitions share a boundary observation for lookback continuity but never share an
   executed-return transition.
4. Algorithm-specific SB3 options live behind one `RLTrainer` interface and one artifact schema.
5. All three required policy families consume the unchanged Dict observation. IR-MoE remains an
   optional adapter rather than the only strategy.
6. Fitted normalization requires a train capability. Built-in policy compression is stateless,
   deterministic, and partition-independent.
7. Validation can trigger early stopping; the test partition cannot influence model selection,
   training duration, or checkpoint choice.
8. Test output is write-once by default to reduce repeated-peeking and accidental overwrite.
9. Actual PPO timesteps may exceed the request to finish a complete SB3 rollout; both values are
   recorded.

## Tests

Tests cover all policy extractor shapes, seven baseline actions, common evaluation artifacts,
partition interval boundaries, isolated panel copies, train-only normalizer fitting, test
capability rejection, all required callbacks, PPO/SAC/TD3 and optional A2C training, checkpoint
save/load, deterministic action replay, independent fixed-seed reproducibility, CLI workflows, and
write-once test evaluation.

## Acceptance result

Phase 3 passed on Python 3.12.13 with Stable-Baselines3 2.6.0 and PyTorch 2.7.1 CPU:

| Check | Result |
|---|---|
| PPO CPU quickstart | Requested 1,000; completed 1,024 rollout-aligned timesteps |
| SAC CPU compatibility | 128/128 timesteps |
| TD3 CPU compatibility | 128/128 timesteps |
| Optional A2C | Integration test passed |
| Policy families | MLP, shared MLP, Transformer passed |
| Baselines | 7/7 produced finite sum-one actions |
| Output artifacts | Separate metrics, trades, and weights passed |
| Locked test evaluation | Passed; second write rejected |
| Checkpoint replay | Two loads, maximum deterministic action difference `0.0` |
| Fixed seed | Independent CPU runs produced exact-equal actions |
| `pytest` | 115 passed |
| Branch coverage | 88.75%, above the 85% gate |
| `ruff check .` | Passed |
| `mypy src` | Passed for 72 source files |
| `pip check` | No broken requirements |
| `python -m uv lock --check` | Passed; 111 packages resolved |

The machine-readable record is `docs/rl/phase3-acceptance.json`. Synthetic sample returns are not
reported as investment performance.

## Open issues

- Production-scale experiments require approved canonical source data and materially longer splits.
- Phase 4 must add multi-seed walk-forward evaluation and keep HPO restricted to train/validation.
- The remote CUDA host has not been modified because only password authentication is available to
  this non-interactive, logged workflow; use an SSH key or secure secret channel.
- Ray and multi-GPU scaling remain optional extensions after CPU and scheduler contracts.
