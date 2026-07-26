# Phase 7 issue checklist

## Typed layers and shared runtime

- [x] Re-read the report's three-layer schemas, modes, tools, presets, and acceptance criteria.
- [x] Implement strict `ResearchDirective`, `RiskContext`, `RiskDirective`, and
  `HierarchicalDirective`.
- [x] Make Research, Risk, and Hierarchical teams independently switchable.
- [x] Execute every enabled single/multi-Agent layer through the Phase 6 `AgentRuntime`.
- [x] Preserve configurable type, count, tools, Provider/model, topology, maximum rounds, quorum,
  and conflict policy.
- [x] Require `deepseek-v4-pro` for all configured model-backed Agents.
- [x] Implement all six exact presets and a strict custom mode.

## Research safety

- [x] Register all 12 report-listed research tools with typed inputs and outputs.
- [x] Implement `plan_only`, `dry_run`, and `execute` permission boundaries.
- [x] Require a successful compute-budget estimate before training or tuning.
- [x] Confine all file paths to the configured workspace.
- [x] Reject test partitions and test-metric-shaped research inputs.
- [x] Keep data inspection and validation non-destructive.
- [x] Keep tools as registered Python callables with no shell bridge.

## Risk, hierarchy, and projection

- [x] Derive an immutable administrator policy from `EnvironmentConfig`.
- [x] Implement advisory recording and enforced hard-limit intersection.
- [x] Ensure Agent output cannot widen risk, asset, market, turnover, cash, cadence, or permission
  limits.
- [x] Require risk committees to use `most_conservative`.
- [x] Fail closed to full cash, zero exposure/turnover, and no new positions.
- [x] Implement first-version Hierarchical `constraint` fusion.
- [x] Implement daily, weekly, and monthly cadence with previous-directive reuse.
- [x] Apply deterministic projection after fusion without account mutation.
- [x] Reject unknown markets and unsupported Phase 7 short fusion conservatively.

## Audit, Replay, and acceptance

- [x] Persist redacted, hashed, sequence-numbered directive records.
- [x] Persist a typed Replay bundle and recompute effective constraints and projection.
- [x] Detect directive-journal tampering.
- [x] Run all six presets in offline tests.
- [x] Prove `no_llm` starts zero Provider runtimes and requires no LLM credential.
- [x] Run an offline full-stack Research + 3-Agent Risk committee + Hierarchical workflow.
- [x] Test aggressive Risk proposals against stricter administrator limits.
- [x] Test Provider failure and static risk fallback.
- [x] Run Ruff, Mypy, full tests, coverage, dependency, lock, and credential checks.
- [x] Record design decisions, acceptance evidence, and remaining work.

## Deferred by phase boundary

- [ ] Hierarchical policy-observation `conditioning`.
- [x] Phase 8 HTML/Markdown reporting, optional service, run browser, and benchmark comparison.
- [ ] Optional process/Ray isolation and distributed execution.
- [ ] Live DeepSeek endpoint smoke test when the key is injected into the process environment.
