# Reproducibility and provenance

Each rc1 run directory is immutable evidence. `run_manifest.json` records schema and software
versions, run ID/kind, hashes of the resolved config, dataset and optional protocol, code commit
when discoverable, source state, seed, runtime identity, status, and every persisted artifact
hash.

Artifact verification and computational replay are different operations:

```bash
cmag report --run-id repro-ppo-quickstart
cmag reproduce --run-id repro-ppo-quickstart --verify-only
cmag reproduce \
  --run-id repro-ppo-quickstart \
  --execute \
  --compare \
  --tolerance-config configs/reproduction/phase11_cpu.yaml
```

The default command and `--verify-only` are read-only artifact-integrity checks. They verify the
run fingerprint and manifest, resolved TrainerConfig and dataset identities, checkpoint archive,
training partition, and the recorded network/test/account boundaries. Their result is
`artifact_verified`; they do not claim that training was recomputed.

`--execute --compare` is the explicit computational operation for a training run. It first
requires the source artifact check to pass, then creates
`runs/reproductions/<source-run-id>/<replay-run-id>/`. It reconstructs the train and validation
environments with the recorded seed and TrainerConfig, trains a new model, evaluates only the
same validation partition, and writes a new checkpoint, metrics, trades, weights, audit journal,
run manifest, and `reproduction_comparison.json`. The source directory and every pre-existing
replay directory are immutable.

The structured report uses these ordered levels:

- `artifact_verified`: hashes verified without retraining;
- `bitwise_reproduced`: all required invariants and core artifact bytes match;
- `numerically_reproduced`: exact invariants match and all five validation metrics pass the
  reviewed numerical tolerances;
- `statistically_reproduced`: at least three comparable replays satisfy the reviewed
  distribution rule when one run is not numerically identical;
- `failed`: an integrity, invariant, tolerance, execution, or source-immutability check failed.

Phase 11 CPU quickstart accepts only `bitwise_reproduced` or `numerically_reproduced`. It compares
`mean_return`, `mean_reward`, `max_drawdown`, `mean_turnover`, `total_cost`, trained timesteps,
algorithm, dataset manifest hash, TrainerConfig hash, execution protocol, and checkpoint
loadability. Absolute and relative tolerances are frozen in
`configs/reproduction/phase11_cpu.yaml`; callers cannot remove a mandatory invariant.

Computational replay never creates a test environment, never contacts an LLM or other network
service, and never mutates external account state. A failed replay directory is retained as
evidence rather than deleted.

Training replay also preserves the configured `market_window_layout`. The Phase 11 flat-layout
smoke source `phase11-flat-metadata-smoke` was retrained as
`replay-phase11-flat-metadata-smoke-001`: all five metric differences were zero and it reached
`numerically_reproduced`. This remains development evidence, not a Phase 12 formal result.

Set `CMAG_CODE_COMMIT` and `CMAG_SOURCE_STATE=clean` in controlled runners when Git metadata is not
present inside the execution image. Formal experiment numbers must cite a run ID and source file.
Development results and Phase 10/11 smoke runs cannot be promoted into Phase 12 formal results.
