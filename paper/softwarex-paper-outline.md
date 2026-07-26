# CrossMarketAgentGym: an auditable environment for cross-market agent research

Status: technical outline for a SoftwareX submission.

## Metadata requiring author confirmation

- Authors and affiliations
- Corresponding author
- Funding and acknowledgements
- Conflict-of-interest statement
- Data licensing statement for any experiment beyond the synthetic sample
- Zenodo concept/version DOI

## Abstract

CrossMarketAgentGym is a CPU-first research platform for cross-market portfolio reinforcement
learning, configurable LLM-agent orchestration, deterministic risk enforcement, and independently
composed hyperparameter search and resource scheduling. The software aligns daily OHLCV,
calendars, currencies, execution timing, costs, and market-specific rules across CN, HK, JP, and US
equities. Single and multi-Agent configurations share one runtime, while Research Orchestration,
Risk Management, and Hierarchical Strategy layers remain independently switchable. Model output
is schema-validated and can only narrow administrator constraints before deterministic projection.
Nine search algorithms compose with separate ASHA, HyperBand, and PBT schedulers. Audit artifacts,
offline Replay, locked test evaluation, and deterministic reporting support reproducible software
experiments.

## Motivation and significance

Cross-market trading research frequently combines asynchronous calendars, different currencies,
market-specific settlement/trading rules, RL training, model selection, and increasingly LLM-based
orchestration. Implementations that collapse these concerns make leakage, accounting errors, and
unreviewed model authority difficult to detect. CrossMarketAgentGym treats leakage prevention,
accounting correctness, reproducibility, and deterministic risk constraints as architecture
boundaries rather than reporting conventions.

## Software architecture

Describe:

1. canonical data schemas, manifests, quality reports, calendars, and FX;
2. the close-signal/next-open environment protocol and accounting engine;
3. PPO, SAC, TD3, policies, callbacks, checkpoints, and traditional baselines;
4. the searcher/scheduler separation and validation-only objectives;
5. the unified AgentRuntime, typed tools, six communication topologies, and arbitration;
6. three-layer directive fusion and administrator hard-limit intersection;
7. deterministic reports, read-only browsing, release manifests, and reproduction commands.

## Safety and correctness

- No train/validation/test capability escalation
- No future observation or execution-price leakage
- No direct addition of unconverted currency values
- No LLM account mutation or deterministic-risk bypass
- No shell execution from Agent text
- No API credentials in configuration, logs, Replay, reports, or release artifacts

## Illustrative example

Use the packaged four-market synthetic sample:

```bash
cmag quickstart --smoke-steps 64
cmag train --config configs/train/ppo.yaml
cmag agent run --config configs/agents/phase7_full_stack_offline.yaml
cmag report softwarex --config configs/reporting/softwarex.yaml
cmag reproduce --run-id phase7-full-stack-offline
```

The sample is deterministic engineering evidence and is not an investment-performance claim.

## Experiments

Required matrix:

1. environment correctness and market rules;
2. PPO/SAC/TD3 and traditional baselines;
3. cross-stock zero-shot;
4. leave-one-market-out;
5. market-mechanism ablations;
6. Agent and HPO ablations.

Report return, Sharpe, Sortino, maximum drawdown, Calmar, CVaR, turnover, cost, cross-seed
variance, runtime, Agent success, configuration validity, leakage violations, tool accuracy, LLM
cost, and reproduction rate. Hyperparameter selection uses train/validation only.

## Limitations

The packaged data are synthetic. Current quickstart experiments are deliberately small and do not
establish economic performance. Cross-stock and leave-one-market-out experiments require dedicated
locked runs. The optional service is not a production trading or authentication system. LLM
outputs remain advisory/narrowing inputs to deterministic policy.

## Availability and reproducibility

- License: Apache-2.0
- Python: 3.11–3.12
- Package: `crossmarket-agent-gym`
- CLI: `cmag`
- Container: non-root multi-stage image
- Archive DOI: pending Zenodo release; do not insert a placeholder DOI
- Evidence: phase acceptance JSON, run fingerprints, release manifest, and SoftwareX report
