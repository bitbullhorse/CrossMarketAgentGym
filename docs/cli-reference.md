# CLI reference

The executable is `cmag`. Commands fail closed when required configuration or run identity is
missing. The machine-readable frozen command/parameter tree is
`release/cli_inventory.json`.

```text
cmag --version
cmag --help
```

## CPU and data

```bash
cmag quickstart --smoke-steps 64
cmag data validate --config configs/data/sample.yaml
cmag env check --config configs/env/sample_cross_market.yaml
```

`quickstart` works from a source checkout or an installed wheel because the wheel contains the
synthetic four-market sample and environment configuration. It performs no download or LLM call.

## Training, evaluation, and tuning

```bash
cmag train --config configs/train/ppo.yaml
cmag evaluate --run-id <run-id>
cmag tune --config configs/tune/ppo_pso_cpu.yaml
```

Training and tuning use train/validation only. `evaluate` is the separate locked-test command.

## Agents

```bash
cmag agent provider-check --config configs/agents/provider_offline.yaml
cmag agent run --config configs/agents/runtime_single_offline.yaml
cmag agent run --config configs/agents/runtime_team_offline.yaml
cmag agent run --config configs/agents/phase7_full_stack_offline.yaml
```

Single and multi-Agent executions share `AgentRuntime`. Phase 7 layer configurations dispatch
through the same command and remain independently switchable.

## Reports and service

```bash
cmag report runs --workspace-root . --runs-root runs
cmag report --run-id <run-id>
cmag report softwarex --config configs/reporting/softwarex.yaml
cmag service run --config configs/reporting/service.yaml
```

The service is optional and read-only. Its default host is loopback.

## Reproduction

```bash
cmag reproduce --run-id phase3_ppo_cpu
cmag reproduce --run-id phase7-full-stack-offline
```

Reproduction is read-only. It verifies the whitelisted source fingerprint, recorded configuration
and data identities, train/validation selection boundaries, checkpoint archive integrity, Agent
Replay journals, or exact Phase 7 directive projection as applicable. It does not retrain, call a
Provider, read test results into tuning, or mutate account state.

## Release preparation

```bash
cmag release check --workspace-root .
cmag release freeze --workspace-root .
python -m build
python -m twine check dist/*.whl dist/*.tar.gz
cmag release verify --dist-dir dist
cmag release manifest --dist-dir dist
```

These commands produce and validate local artifacts only. Publishing requires an explicitly
authorized tag or manual GitHub Actions dispatch.
