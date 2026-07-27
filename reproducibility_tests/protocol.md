# Phase 11 independent reproduction protocol

This protocol must be executed by participants who are not project authors. Authors may answer
through recorded issues but must not operate the participant machine. Phase 10/11 outputs are
development evidence and cannot be reused as Phase 12 formal experimental results.

## Participant profiles

The study requires at least three participants covering:

1. reinforcement learning experience without detailed financial-market-rule experience;
2. financial-data experience without Agent-system experience;
3. Python experience without prior CrossMarketAgentGym experience.

Five participants are preferred. Each participant starts from a clean checkout or clean container,
uses a unique evidence directory, and completes `participant_template.md`.

## CPU command protocol

Use Python 3.11 or 3.12 and record the exact package commit. Ordinary package downloads use the
Tsinghua mirror:

```bash
export PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
pip install -e ".[dev]"
bash scripts/repro_test_cpu.sh
```

The script executes data validation, environment validation, PPO training, single Research Agent,
multi-Agent risk committee, PSO/ASHA tuning, reporting, artifact verification, and isolated
computational replay in order. The equivalent final two commands are:

```bash
cmag reproduce --run-id repro-ppo-quickstart --verify-only
cmag reproduce \
  --run-id repro-ppo-quickstart \
  --execute \
  --compare \
  --tolerance-config configs/reproduction/phase11_cpu.yaml
```

`--verify-only` must report `artifact_verified` and
`computational_replay_executed=false`. The CPU replay must report either
`bitwise_reproduced` or `numerically_reproduced`.

## Docker protocol

On a Docker host:

```bash
bash scripts/repro_test_docker.sh
```

The runtime commands execute as UID/GID 10001 with `--network none`. Image dependency resolution
occurs during the build and uses the configured Tsinghua mirror. The source checkout's configs and
synthetic sample are mounted read-only; run evidence is written to a separate temporary mount.

## Evidence and comparison

Retain the source run and every replay, including failures. For each replay record:

- source/replay run IDs and code commit;
- `config.resolved.yaml`, source run fingerprint, and run manifests;
- TrainerConfig and dataset-manifest hashes;
- checkpoint SHA-256 and loadability;
- execution protocol and trained timesteps;
- the five validation metric comparisons and tolerances;
- `network_used`, `test_partition_accessed_by_replay`, and
  `account_state_mutated`;
- elapsed time, failures, documentation lookup time, author questions, and usability score.

The replay directory is
`runs/reproductions/<source-run-id>/<replay-run-id>/`. The authoritative comparison source is
`reproduction_comparison.json`; its artifact set is protected by `run_manifest.json`.

## Severity and exit gate

- P0: installation impossible, accounting error, information leakage, unsafe mutation, or severe
  result mismatch;
- P1: a core CLI, Agent, HPO, or replay command cannot run;
- P2: material documentation/error-message issue;
- P3: minor layout or usability issue.

Phase 11 is complete only after all required participants finish, CPU quickstart succeeds for
100%, core task completion is at least 90%, no author direct operation was needed, P0/P1 are zero,
P2 items are fixed or explicitly accepted, documentation is updated, and `v1.0.0-rc2` is released.
Until then Phase 12 must not start.
