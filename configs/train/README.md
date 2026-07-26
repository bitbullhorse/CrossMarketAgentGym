# Training configurations

- `ppo.yaml`: required 1,000-step CPU quickstart using the shared-asset MLP.
- `sac.yaml`: small off-policy CPU compatibility run.
- `td3.yaml`: small Transformer-policy CPU compatibility run.
- `ppo_tune_gpu.yaml`: optional CUDA base configuration used by the Phase 9 Ray example.

Every configuration has explicit train, validation, and locked test transition boundaries.
`cmag train` reads train and validation only. `cmag evaluate --run-id ...` is the separate test
capability boundary.
