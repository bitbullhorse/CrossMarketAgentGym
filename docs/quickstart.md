# CPU quickstart and independent reproduction commands

The packaged quickstart is offline, deterministic, and uses only `data/sample`:

```bash
cmag quickstart --smoke-steps 64
```

Phase 11 participants use the following commands, in order, from a clean checkout:

```bash
pip install -e ".[dev]"
cmag data validate --config configs/data/sample.yaml
cmag env check --config configs/env/sample_cross_market.yaml
cmag train --config configs/train/ppo_quickstart.yaml
cmag agent run --config configs/agents/research_single_mock.yaml
cmag agent run --config configs/agents/risk_committee_mock.yaml
cmag tune --config configs/tune/ppo_pso_quickstart.yaml
cmag report --run-id repro-ppo-quickstart
cmag reproduce --run-id repro-ppo-quickstart --verify-only
cmag reproduce --run-id repro-ppo-quickstart --execute --compare
```

All Agent commands above use Mock plus Replay and make no network request. The tuning command reads
training and validation partitions only. Test evaluation is a separate, explicit action and is
not part of HPO. The first reproduction command verifies immutable artifacts; the second creates
an isolated training replay and must reach at least `numerically_reproduced` on the CPU profile.

Run IDs are immutable evidence directories. If a run ID already exists, choose a new isolated
workspace; do not delete or overwrite evidence to make a command pass.
