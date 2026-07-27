# Single and multi-Agent runtime

Single and multi-Agent execution use the same `AgentRuntime`. Configuration defines Agent type,
count, provider/model, tool allowlist, permissions, topology, maximum rounds, quorum, retries,
parallelism, and conflict policy.

Built-in topologies include single, coordinator, pipeline, committee vote, hierarchical, and
blackboard. Risk committees with more than one active risk manager must use
`most_conservative`. Provider failures, missing quorum, invalid schemas, and timeouts resolve by a
declared deterministic fallback; they never widen risk.

Committee output distinguishes configuration from outcome:

- `configured_conflict_policy` is the selected arbitration policy;
- `conflict_detected` records whether non-abstaining directives disagreed;
- `aggregate_decision` is the resolved decision;
- `selected_directive_confidence` records the selected directive;
- `committee_confidence` is the minimum confidence across valid committee directives, with
  `confidence_aggregation: minimum`.

The legacy `policy` and nested `decision` field names remain for existing consumers, but must not be
interpreted as “the policy rejected the proposal.”

Examples:

```bash
cmag agent run --config configs/agents/runtime_single_offline.yaml
cmag agent run --config configs/agents/runtime_team_offline.yaml
```

The exact role registry, entry-point boundary, scheduling, aggregation, audit layout, and replay
rules are in [AgentRuntime contract](agent-runtime-contract.md).
