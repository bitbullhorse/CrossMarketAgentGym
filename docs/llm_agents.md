# LLM Agents

The three independently switchable layers are:

1. Research Orchestration Agent: creates a validation-only typed plan and invokes only configured
   tools.
2. Risk Management Agent: proposes risk budgets; deterministic code intersects them with
   administrator constraints.
3. Hierarchical Strategy Agent: proposes market/sector budgets and cadence as constraints, never
   account mutations.

Offline examples:

```bash
cmag agent run --config configs/agents/research_single_mock.yaml
cmag agent run --config configs/agents/risk_committee_mock.yaml
```

All configured online Agents use model name `deepseek-v4-pro`. The OpenAI-compatible adapter reads
`DEEPSEEK_API_KEY` and `DEEPSEEK_BASE_URL` from the process environment; values are neither placed
in YAML nor written to audit logs. Release and reproduction tests use Mock/Replay.

Messages, tool calls, responses, directives, and replay records are schema-validated and
versioned. See [provider/tool contract](provider-tool-contract.md) and
[directive fusion contract](directive-fusion-contract.md).
