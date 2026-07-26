# CrossMarketAgentGym

CrossMarketAgentGym is an auditable research platform for cross-market portfolio
reinforcement learning, configurable LLM-agent teams, and hyperparameter optimization.
It targets daily OHLCV data from the CN, HK, JP, and US equity markets.

## Installation

CrossMarketAgentGym supports Python 3.11 and 3.12. The CPU research installation is:

```bash
python -m pip install "crossmarket-agent-gym[rl]"
cmag quickstart --smoke-steps 64
```

From a source checkout, use the Tsinghua mirror and install development, service, and release
tools when needed:

```bash
export PIP_INDEX_URL="https://pypi.tuna.tsinghua.edu.cn/simple"
python -m pip install -e ".[dev,rl,service,release]"
```

The quickstart uses the packaged deterministic four-market sample. It performs no data download,
LLM call, training, tuning, or account mutation.

The project is being implemented in the ordered phases defined in
[`CrossMarketAgentGym_详细执行报告.md`](CrossMarketAgentGym_详细执行报告.md). Phases 0–7
provide the installable skeleton, canonical daily OHLCV contract, mixed legacy adapters,
non-destructive quality reports, hashed manifests, a redistributable four-market sample, and a
leakage-safe Gymnasium portfolio environment with deterministic risk/accounting plus CPU-first
PPO, SAC, TD3, baselines, callbacks, and reproducible checkpoints.

## Non-negotiable safety boundaries

- Signals available after close on day `t` execute no earlier than the corresponding market open
  on day `t+1`.
- Hyperparameter optimization can read training and validation results, never test results.
- LLM output is schema-validated and cannot mutate account state or bypass deterministic risk
  projection.
- API credentials are read only from environment variables and are redacted from logs.
- Search algorithms and resource schedulers are separate abstractions.

## Phase 0 quickstart

```bash
python -m pip install -e ".[dev]"
cmag --help
python -m pytest
ruff check .
mypy src
```

The default LLM model policy is `deepseek-v4-pro`. Set credentials only in the process
environment:

```bash
export DEEPSEEK_API_KEY="..."
export DEEPSEEK_BASE_URL="https://api.deepseek.com"
```

No network call is made by Phase 0.

## Phase 1 data validation

```bash
cmag data validate --config configs/data/sample.yaml
cmag data validate --config configs/data/local_stock_data.yaml
```

The first command validates the packaged synthetic sample and all recorded hashes. The second
performs a bounded read-only smoke test against the local mixed CSV/Excel source tree. Use
`configs/data/local_stock_data_full.yaml` for a full source audit.

## Phase 2 environment validation

```bash
python -m pip install -c constraints-cpu.txt -e ".[dev,rl]"
cmag env check --config configs/env/cross_market.yaml
```

This runs Gymnasium and Stable-Baselines3 compatibility checks plus 1,000 seeded random actions
against the synthetic four-market sample. The exact timing, projection, currency, accounting, and
audit guarantees are defined in [`docs/environment-contract.md`](docs/environment-contract.md).

## Phase 3 DRL quickstart

```bash
cmag train --config configs/train/ppo.yaml
cmag evaluate --run-id phase3_ppo_cpu
```

The first command uses train and validation only. The second is the separate locked-test boundary.
SAC and TD3 configurations are under `configs/train/`; all seven non-RL baselines can be exercised
with `python examples/evaluate_baselines.py`. See
[`docs/training-contract.md`](docs/training-contract.md) for partition and artifact guarantees.

## Phase 4 HPO quickstart

```bash
cmag tune --config configs/tune/ppo_pso_cpu.yaml
```

Search algorithms and resource schedulers are independent. The CPU Stage A example uses
train/validation only, resumes from SQLite, locks validation-selected parameters, and retrains
them independently before any test evaluation.

## Phase 5 Provider quickstart

```bash
python -m pip install -e ".[llm]"
cmag agent provider-check --config configs/agents/provider_offline.yaml
```

This command performs a no-network Mock → read-only tool → structured response workflow and then
verifies exact Replay. The OpenAI-compatible DeepSeek adapter reads credentials only from
`DEEPSEEK_API_KEY`; see [`docs/provider-tool-contract.md`](docs/provider-tool-contract.md).

## Phase 6 AgentRuntime quickstart

```bash
cmag agent run --config configs/agents/runtime_single_offline.yaml
cmag agent run --config configs/agents/runtime_team_offline.yaml
```

Both commands are CPU-only and make no network calls. The first runs one Agent through the same
runtime used by teams. The second expands a parallel 1+3+2 committee, injects one deterministic
Provider failure, applies the static risk fallback, and resolves with the most-conservative
structured policy. Six topologies, custom Python/entry-point roles, serial/parallel scheduling,
timeouts, retries, and quorum are defined in
[`docs/agent-runtime-contract.md`](docs/agent-runtime-contract.md).

`configs/agents/runtime_deepseek_team.yaml` uses the same runtime with the online Provider and reads
the API key from `DEEPSEEK_API_KEY`; it never stores a credential value.

## Phase 7 three-layer fusion quickstart

```bash
cmag agent run --config configs/agents/phase7_no_llm.yaml
cmag agent run --config configs/agents/phase7_full_stack_offline.yaml
```

The first command performs administrator-only deterministic projection and starts zero Provider
runtimes. The second runs Research Orchestration, a three-Agent most-conservative Risk committee,
and Hierarchical Strategy through the same `AgentRuntime`, then intersects validated directives
with hard limits and verifies exact Replay. Both are CPU-only and offline. The online
`configs/agents/full_stack.yaml` uses `deepseek-v4-pro` and reads the key only from
`DEEPSEEK_API_KEY`.

The directive schemas, 12 research tools, validation-only and compute-budget gates, cadence, six
presets, fusion order, and no-account-mutation boundary are defined in
[`docs/directive-fusion-contract.md`](docs/directive-fusion-contract.md).

## Phase 8 reporting quickstart

```bash
cmag report softwarex --config configs/reporting/softwarex.yaml
```

This CPU-only command generates deterministic Markdown, HTML, four CSV tables, four SVG figures, a
static run browser, JSON payloads, and a hashed manifest under `reports/phase8-softwarex/`.
Comparison is descriptive and has no hyperparameter-selection authority; missing experiments and
metrics remain explicitly planned, partial, or `N/A`.

The optional local read-only browser is:

```bash
python -m pip install -e ".[service]"
cmag service run --config configs/reporting/service.yaml
```

It binds to `127.0.0.1` by default. See
[`docs/reporting-service-contract.md`](docs/reporting-service-contract.md) for indexing,
provenance, route, and security guarantees.

## Phase 9 reproduction and release

Verify a recorded run in one read-only command:

```bash
cmag reproduce --run-id phase3_ppo_cpu
cmag reproduce --run-id phase7-full-stack-offline
```

The command verifies recorded configuration, data and source fingerprints, checkpoint archive,
train/validation selection boundary, Agent Replay journals, or exact Phase 7 directive projection
as applicable. It never retrains, contacts a Provider, uses test metrics for HPO, or mutates account
state.

Local release preparation is:

```bash
cmag release check --workspace-root .
python -m build
python -m twine check dist/*
cmag release verify --dist-dir dist
cmag release manifest --dist-dir dist
```

PyPI Trusted Publishing, GitHub Release, and Zenodo archival are configured but require an
explicit authorized tag or workflow dispatch. Container and archival instructions are in
[`docs/release.md`](docs/release.md); the Python and CLI surfaces are documented in
[`docs/api-reference.md`](docs/api-reference.md) and
[`docs/cli-reference.md`](docs/cli-reference.md).

Optional Ray/GPU Trial evaluation is configured independently from searchers and schedulers; see
[`docs/scaling.md`](docs/scaling.md) and `configs/tune/ppo_pso_ray_gpu.yaml`.

## Citation

Please cite the software using [`CITATION.cff`](CITATION.cff). The Zenodo DOI will be added only
after Zenodo returns a real concept/version DOI; no placeholder DOI is claimed.

```text
CrossMarketAgentGym contributors (2026). CrossMarketAgentGym 0.1.0. Apache-2.0.
```

## Project status

Phase status, design decisions, tests, acceptance evidence, and open issues are recorded under
[`docs/phases/`](docs/phases/).
