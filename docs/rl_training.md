# RL training

The CPU quickstart trains PPO on the packaged sample:

```bash
cmag train --config configs/train/ppo_quickstart.yaml
```

PPO, SAC, and TD3 share the same environment, split model, callback boundaries, validation
artifacts, and accounting checks. Training and validation may be used during development. Locked
test evaluation is separate:

```bash
cmag evaluate --run-id repro-ppo-quickstart
```

Do not run that evaluation while selecting hyperparameters. Every training directory stores the
resolved config, checkpoint, validation artifacts, summary, and `run_manifest.json` with hashes,
runtime identity, seed, dataset version, code commit when available, and source-state declaration.

See [training contract](training-contract.md) for split geometry, callback behavior, deterministic
evaluation, supported policies, and artifact definitions.
