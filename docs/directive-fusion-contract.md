# Three-layer directive and fusion contract

Phase 7 adds three independently switchable LLM layers without granting any model authority over
portfolio accounting or order execution. Every enabled layer is a normal `TeamSpec` executed by
the same `AgentRuntime` delivered in Phase 6. A one-Agent layer is a one-instance team.

## Research Orchestration

`ResearchDirective` is a strict, replayable plan with an objective, ordered dependency graph,
mode, estimated compute, validation/test declarations, execution safety flag, rationale, and
confidence. The supported modes are:

- `plan_only`: no tool invocation;
- `dry_run`: read/compute tools only, with no training, tuning, or writes;
- `execute`: explicitly permissioned operations, with a successful compute-budget estimate before
  an expensive call.

The built-in registry exposes exactly:

`inspect_dataset`, `validate_dataset`, `list_markets`, `list_symbols`, `create_split`,
`validate_experiment_config`, `estimate_compute_budget`, `train_rl`, `tune_rl`,
`evaluate_checkpoint`, `compare_runs`, and `generate_report`.

All arguments pass Pydantic schemas and workspace path containment. Training and tuning
configuration may use only train and validation partitions. Checkpoint evaluation exposed to the
research Agent is validation-only, comparison reads `validation_metrics`, and test-shaped fields
are rejected. Tools are typed Python callables; no shell bridge exists.

## Risk Management

The Agent receives only a validated `RiskContext` and returns a validated `RiskDirective`.
`advisory` records the proposal but applies the administrator baseline. `enforced` intersects the
proposal with `AdministratorRiskPolicy`:

- risk, asset, market, and turnover maxima use the smaller value;
- the cash floor uses the larger value;
- permission to open positions uses logical AND;
- rebalance frequency may become slower, never faster than the administrator minimum.

The effective cash reserve is derived explicitly:

```text
agent_cash_floor = max(administrator_cash_floor, risk_agent_cash_floor)
risk_budget_implied_value = 1 - effective_risk_budget
effective_cash_floor = max(agent_cash_floor, risk_budget_implied_value)
```

The directive journal stores all three values, the `max` operator, and the reason
`Invested capital cannot exceed risk budget.` Thus an Agent proposal of `cash_floor=0.3` with
`risk_budget=0.6` produces an effective floor of `0.4`.

Missing or invalid output selects a static directive with zero risk and turnover, full cash, zero
position limits, and no new positions. A risk committee must use `most_conservative`.

## Hierarchical Strategy

`HierarchicalDirective` contains a market regime, market/optional sector budgets, global risk
budget, rebalance interval, normalized objective weights, and confidence. Phase 7 implements only
`fusion: constraint`: the directive narrows the deterministic projection set. Policy-observation
conditioning is intentionally outside this phase.

## Fusion and projection

The order is fixed:

1. construct immutable limits from `EnvironmentConfig`;
2. merge the Risk directive with administrator policy;
3. intersect the Hierarchical budgets;
4. apply tradability and no-new-position masks;
5. call the deterministic `ConstraintProjector`;
6. return proposed weights and reasons without mutating account state.

An LLM limit can only tighten this set. Unknown markets and Phase 7 short-selling fusion are
rejected conservatively. Risk and hierarchy run on configured daily, weekly, or monthly cadence;
when a layer is not due, its validated previous directive is reused or a static fallback is used.

Projection audit records a single `dominant_projection_reason` plus the stable diagnostic set
`max_asset_weight`, `cash_floor`, `max_turnover`, and `market_weight_limits` as
`secondary_projection_reasons`. When all capital is cash and new positions are disabled, the
dominant reason is `no_new_positions_from_all_cash_state`.

## Presets and Replay

The strict presets are `no_llm`, `research_only`, `risk_only`, `hierarchical_only`,
`research_plus_risk`, and `full_stack`. Presets must exactly match layer enabled states.
`no_llm` constructs no Provider runtime and performs deterministic administrator projection only.

Every accepted proposal, effective merge, fusion, and projection is stored in a redacted,
sequence-numbered, SHA-256-protected directive journal. A Replay bundle recomputes merge and
projection from validated directives and verifies exact equality with the original result.
