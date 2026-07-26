# AgentRuntime contract

## Scope

`AgentRuntime` is the only execution path for both a single Agent and a configured team. A single
Agent is a team whose `single` topology expands to one enabled instance. Phase 6 schedules and
arbitrates structured advice; it does not mutate an account, execute orders, or replace the
deterministic risk projection required in Phase 7.

## AgentSpec

Each `AgentSpec` configures:

- registered role `type`, stable base `name`, `enabled`, and dynamic `count` from 1 to 32;
- Provider kind, mandatory model `deepseek-v4-pro`, credential environment-variable names,
  temperature, token limit, timeout, retry policy, and structured-output mode;
- prompt, exact tool allowlist, permission classes, call/time/expensive budgets, and tool-loop
  limit;
- vote weight, administrator fallback, metadata, Mock scripts, or Replay path.

When `count > 1`, instance IDs are `<name>_0..<name>_<count-1>`. Each expanded instance receives a
stable SHA-256-derived seed, its own Provider, tool budget, audit directory, message stream,
timeout, retry state, and Replay journal. A shared Mock script is copied into independent
Providers; alternatively, configuration may supply one script per instance.

## TeamSpec

The six supported topologies are:

| Topology | Deterministic schedule |
|---|---|
| `single` | Exactly one expanded instance |
| `pipeline` | Configuration order; every stage receives prior structured outputs |
| `supervisor_worker` | Team review followed by one supervisor synthesis when rounds permit |
| `committee_vote` | One serial or parallel committee round |
| `debate_then_judge` | Bounded debate rounds followed by the configured judge |
| `map_reduce` | Parallel/serial mappers followed by the configured reducer (`supervisor`) |

`max_rounds` is a hard interaction-round cap. `parallel=false` preserves the same topology and
result schema using one worker. Results are emitted in configuration order even when execution is
parallel.

## Role registration

Built-in role names are:

```text
research_coordinator
data_quality
experiment_designer
environment_reviewer
training
hyperparameter_tuning
market_regime
risk_manager
portfolio_reviewer
backtest_auditor
report_writer
judge
custom
```

The three named layer classes—`ResearchOrchestrationAgent`, `RiskManagementAgent`, and
`HierarchicalStrategyAgent`—already use the same runtime and can be independently enabled. Phase 7
adds their domain directive schemas and deterministic DRL constraint fusion.

Python registration is explicit:

```python
registry.register("custom_factor_reviewer", custom_factory)
```

Installed plugins may register an administrator-installed callable through:

```toml
[project.entry-points."crossmarket_agentgym.agents"]
custom_factor_reviewer = "my_package.agent:factory"
```

Model output cannot name an import path or dynamically load code. Only pre-registered types are
constructible.

## Structured communication and arbitration

Every topology edge carries `UpstreamDecision`, never arbitrary executable text. Every role returns
an `AgentDecision` with a finite decision enum, confidence, risk score, optional constraints, and
structured payload.

Policies:

- `majority_vote`: counts only the validated decision enum;
- `weighted_vote`: applies configured positive Agent weights;
- `judge`: selects only the configured judge's validated decision;
- `most_conservative`: selects `reject > revise > approve > abstain`, maximizes cash, minimizes
  asset/market/turnover limits, and gives `allow_new_positions=false` priority;
- `reject`: rejects disagreement or lack of an affirmative structured decision.

Ties fail toward the more conservative enum. Missing quorum produces a static rejection with
100% cash, zero new exposure, and zero turnover. Free-text majority voting is not supported.

## Failure and security semantics

- A Provider/schema/tool failure uses the role's prevalidated administrator fallback.
- A plugin exception is retried only within that instance's configured retry count.
- A timeout or terminal plugin error is isolated as a partial failure.
- Quorum decides whether remaining structured results may be aggregated.
- Risk fallback denies new exposure and participates in conservative arbitration, so a failed risk
  Agent cannot silently loosen the team result.
- Agent code has no import path to account or execution state. Tools remain typed Python
  capabilities and cannot execute user shell text.
- Runtime, instance, Provider, tool, fallback, and Replay artifacts are credential-redacted.

## Audit layout

```text
runs/<run_id>/
├── config.resolved.yaml
├── config.sha256
├── runtime_summary.json
├── agent/
│   ├── team.resolved.json
│   ├── runtime_events.jsonl
│   └── team_summary.json
└── agent_instances/<instance_id>/agent/
    ├── messages.jsonl
    ├── provider_metadata.json
    ├── fallbacks.jsonl        # when applicable
    ├── tool_calls.jsonl       # when applicable
    └── replay.jsonl           # Mock/online runs
```
