# Single and multi-Agent runtime

Single and multi-Agent execution use the same `AgentRuntime`. Configuration defines Agent type,
count, provider/model, tool allowlist, permissions, topology, maximum rounds, quorum, retries,
parallelism, and conflict policy.

Built-in topologies include single, coordinator, pipeline, committee vote, hierarchical, and
blackboard. Risk committees with more than one active risk manager must use
`most_conservative`. Provider failures, missing quorum, invalid schemas, and timeouts resolve by a
declared deterministic fallback; they never widen risk.

Examples:

```bash
cmag agent run --config configs/agents/runtime_single_offline.yaml
cmag agent run --config configs/agents/runtime_team_offline.yaml
```

The exact role registry, entry-point boundary, scheduling, aggregation, audit layout, and replay
rules are in [AgentRuntime contract](agent-runtime-contract.md).
