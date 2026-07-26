# Reproducibility and provenance

Each rc1 run directory is immutable evidence. `run_manifest.json` records schema and software
versions, run ID/kind, hashes of the resolved config, dataset and optional protocol, code commit
when discoverable, source state, seed, runtime identity, status, and every persisted artifact
hash.

Inspect and reproduce:

```bash
cmag report --run-id repro-ppo-quickstart
cmag reproduce --run-id repro-ppo-quickstart
```

Reproduction is read-only. It verifies files and fingerprints and performs deterministic Agent or
directive replay where applicable. It does not contact an LLM, retrain a model, read test metrics
for selection, or mutate account state.

Set `CMAG_CODE_COMMIT` and `CMAG_SOURCE_STATE=clean` in controlled runners when Git metadata is not
present inside the execution image. Formal experiment numbers must cite a run ID and source file.
Development results and Phase 10/11 smoke runs cannot be promoted into Phase 12 formal results.
