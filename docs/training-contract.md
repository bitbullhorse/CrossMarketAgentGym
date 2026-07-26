# Training, validation, and checkpoint contract

Phase 3 uses one `RLTrainer` protocol for PPO, SAC, TD3, and optional A2C. The Stable-Baselines3
implementation changes algorithm-specific optimization details without changing environment,
partition, evaluation, or artifact contracts.

## Partition capabilities

Each environment carries an immutable `PartitionCapability`:

- `train`: accepted by `RLTrainer.train`;
- `validation`: accepted by validation evaluation and early stopping;
- `test`: accepted only by the separate saved-run evaluation workflow;
- `smoke`: environment compatibility only, never accepted by the trainer.

Train, validation, and test environments receive separately copied `MarketDataPanel` slices.
The train object does not retain validation or test arrays, and `execute_training_run` does not
construct a test environment. Adjacent partitions share only the boundary signal observation; their
executed-return intervals do not overlap.

`TrainOnlyStandardizer.fit` additionally requires a `train` capability. Validation and test data
may be transformed with frozen training statistics but cannot refit them.

## Policies

All policies consume the Phase 2 Dict observation:

- `mlp`: compact flattened dictionary MLP;
- `shared_mlp`: one parameter-shared asset encoder followed by cross-asset pooling;
- `transformer`: attention over asset-time tokens plus portfolio state;
- `IRMoEPolicyAdapter`: optional extension boundary, not a required or exclusive policy.

Raw price/volume magnitudes use deterministic signed `log1p` compression inside the extractor.
This transform has no fitted statistics and therefore cannot observe future partitions.

## Callbacks

The callback factory composes:

1. periodic checkpoints;
2. validation-only evaluation;
3. validation-patience early stopping;
4. NaN/Inf reward and observation guard;
5. maximum-drawdown stop;
6. CPU/CUDA resource records;
7. environment audit JSON Lines;
8. online metrics JSON Lines.

Validation metrics may change training duration. Test metrics are never visible to callbacks.

## Run artifacts

`cmag train --config ...` writes:

```text
runs/<run_id>/
├── resolved_config.json
├── training_artifact.json
├── run_summary.json
├── audit.jsonl
├── resources.jsonl
├── training_metrics.jsonl
├── validation.jsonl
├── checkpoints/
│   ├── final_model.zip
│   └── step_*_steps.zip
└── validation/
    ├── metrics.json
    ├── trades.json
    └── weights.json
```

The training artifact records the algorithm, policy, requested and actual timesteps, seed,
configuration SHA-256, dataset Manifest SHA-256, data partition, checkpoint path, Python, SB3,
PyTorch, and NumPy versions.

`cmag evaluate --run-id <id>` loads the resolved configuration and final checkpoint, constructs only
the locked test partition, then writes the same metrics/trades/weights schema under `test/`. A
second test evaluation is rejected instead of overwriting the first result.

## Interpretation boundary

The packaged dataset contains only five synthetic sessions. Its returns are compatibility evidence,
not a research result or investment performance claim. Production training requires approved
canonical data, authoritative calendars and FX, longer temporal splits, multiple seeds, and
walk-forward evaluation.
