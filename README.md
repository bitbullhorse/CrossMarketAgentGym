# CrossMarketAgentGym

[![Phase 11 Linux CPU](https://github.com/bitbullhorse/CrossMarketAgentGym/actions/workflows/phase11-linux-cpu.yml/badge.svg)](https://github.com/bitbullhorse/CrossMarketAgentGym/actions/workflows/phase11-linux-cpu.yml)
[![Phase 11 Docker](https://github.com/bitbullhorse/CrossMarketAgentGym/actions/workflows/phase11-docker.yml/badge.svg)](https://github.com/bitbullhorse/CrossMarketAgentGym/actions/workflows/phase11-docker.yml)
[![Stable release](https://github.com/bitbullhorse/CrossMarketAgentGym/actions/workflows/release.yml/badge.svg)](https://github.com/bitbullhorse/CrossMarketAgentGym/actions/workflows/release.yml)

CrossMarketAgentGym is an auditable research platform for cross-market portfolio reinforcement
learning, configurable LLM Agent teams, and hyperparameter optimization over daily CN, HK, JP,
and US OHLCV data.

The stable release line is `v1.0.0`. Phase 12 formal experiments and the independently reviewed
Phase 13 `benchmark-v1` are frozen. Public PyPI, container, documentation and DOI availability
remain subject to the Phase 14 publication gates; source-tree readiness is not itself proof that
an external service has published an artifact.

## Installation and CPU quickstart

Python 3.11 and 3.12 are supported. From a source checkout:

```bash
export PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
python -m pip install -c constraints-cpu.txt -e ".[dev,legacy-data,release,service]"
cmag --help
cmag quickstart --smoke-steps 64
```

The quickstart uses only the packaged deterministic sample. It performs no data download, LLM
request, model training, tuning, test evaluation, or account mutation. See
[installation](docs/installation.md) and [quickstart](docs/quickstart.md).

## Core capabilities

- Hashed, versioned daily OHLCV manifests and mixed CSV/Excel adapters.
- Leakage-safe next-open execution, asynchronous calendars, FX conversion, market rules,
  deterministic risk projection, and accounting reconciliation.
- CPU-first PPO, SAC, and TD3 with separate train/validation selection and locked test evaluation.
- One `AgentRuntime` for single and multi-Agent teams with configurable type, count, tools, model,
  topology, rounds, quorum, retries, and conflict resolution.
- Independently switchable Research Orchestration, Risk Management, and Hierarchical Strategy
  Agents.
- Online OpenAI-compatible DeepSeek provider fixed to `deepseek-v4-pro`, plus offline Mock and
  exact Replay providers.
- Random, Grid, TPE, CMA-ES, NSGA-II, PSO, Genetic, Differential Evolution, and Simulated
  Annealing searchers.
- ASHA, HyperBand, and Population Based Training as independent resource schedulers.
- Immutable run evidence, format schemas, reproducibility checks, SoftwareX reports, and optional
  Ray/GPU/read-only service profiles.

## Non-negotiable safety boundaries

- A signal available after close on day `t` executes no earlier than the eligible open on `t+1`.
- HPO, early stopping, and parameter selection can read training and validation results, never
  test results.
- LLM output is schema-validated and cannot mutate account state or bypass deterministic
  administrator risk constraints.
- API credentials exist only in process environment variables and are redacted from logs.
- Search algorithms, resource schedulers, and execution backends are separate abstractions.
- Accounting, information-leakage, security, or deterministic-replay defects block release.

## Local GUI

The guarded GUI can validate and edit YAML, launch training, validation backtests, locked test
evaluation, Agent teams, HPO, reproduction, reports, and frozen experiment tasks, then follow
their status and logs. Start the local-only execution service and frontend:

```bash
cmag service run --config configs/reporting/gui.yaml
cd frontend
pnpm install --registry=https://registry.npmmirror.com
pnpm dev
```

The execution API is opt-in and loopback-only. The browser cannot submit arbitrary commands,
HPO has no test-partition input, validation backtests use an isolated output directory, and
credentials remain in the backend process environment. See the
[中文 GUI 操作指南](docs/gui.zh-CN.md).

## Reproduction commands

The Phase 11 clean-user path is:

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

These examples are development/reproduction checks only. They must not be reused as Phase 12
formal results. `--verify-only` checks artifact integrity; only the explicit
`--execute --compare` pair retrains and compares a new isolated replay.

## Frozen formal benchmark

Verify the write-once Phase 13 result snapshot before using any formal number:

```bash
cmag benchmark verify --benchmark benchmarks/v1
cmag paper export-tables \
  --benchmark benchmarks/v1 \
  --output <new-table-directory>
cmag paper export-figures \
  --benchmark benchmarks/v1 \
  --output <new-figure-directory>
```

The exporters refuse to overwrite an existing destination and never modify Benchmark v1.
See the [Benchmark v1 operator guide](docs/benchmark-v1.md) and
[Phase 13 report](docs/phases/phase-13.md).

## Online DeepSeek provider

Install the `llm` extra and set credentials only in the process environment:

```bash
export DEEPSEEK_API_KEY="set-in-your-shell"
export DEEPSEEK_BASE_URL="https://api.deepseek.com"
cmag agent run --config configs/agents/full_stack.yaml
```

Never store a real key in YAML, source, tests, reports, or run artifacts. All shipped online Agent
configs use model `deepseek-v4-pro`.

## Documentation

- [中文详细操作手册](docs/operations-guide.zh-CN.md)
- [中文 GUI 操作指南](docs/gui.zh-CN.md)
- [Data schema](docs/data_schema.md), [environment](docs/environment.md), and
  [market rules](docs/market_rules.md)
- [RL training](docs/rl_training.md) and [tuning](docs/tuning.md)
- [LLM Agents](docs/llm_agents.md) and [multi-Agent runtime](docs/multi_agent.md)
- [Reproducibility](docs/reproducibility.md), [API reference](docs/api-reference.md), and
  [stable API catalog](docs/stable-api.md), and [CLI reference](docs/cli-reference.md)
- [Benchmark v1](docs/benchmark-v1.md) and [Phase 13 acceptance](docs/phases/phase-13.md)
- [Stable release and archival guide](docs/release.md), [known limitations](docs/known-limitations.md),
  and [Phase 14 status](docs/phases/phase-14.md)
- [API stability](docs/api_stability.md), [versioning](docs/versioning_policy.md), and
  [deprecation](docs/deprecation_policy.md)
- [Security](docs/security.md), [troubleshooting](docs/troubleshooting.md), and [FAQ](docs/faq.md)

Ordered implementation and acceptance evidence is maintained in
[Phase 0–9 reports](docs/phases/) and the
[Phase 11 independent-reproduction report](docs/phases/phase-11.md). Local planning reports are
intentionally excluded from the public repository.

## Release preparation

Local preparation does not publish:

```bash
python scripts/verify_docs.py
cmag release freeze --workspace-root .
cmag release check --workspace-root .
python -m build
cmag release verify --version 1.0.0
scripts/verify_public_release.sh --offline
```

PyPI, GHCR, GitHub Pages, GitHub Release, and Zenodo changes require the exact verified stable
commit plus an explicitly authorized `v1.0.0` tag or workflow dispatch. A dry-run never claims
that these external surfaces exist.

## Citation

Please cite the software through [CITATION.cff](CITATION.cff). No placeholder DOI is claimed.

```text
CrossMarketAgentGym contributors (2026). CrossMarketAgentGym 1.0.0. Apache-2.0.
```

Phase status, tests, acceptance evidence, and unresolved blockers are recorded under
[docs/phases](docs/phases/).
