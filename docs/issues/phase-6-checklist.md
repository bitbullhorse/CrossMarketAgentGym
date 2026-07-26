# Phase 6 issue checklist

## Scope and configuration

- [x] Re-read the report's Phase 6, `AgentSpec`, `TeamSpec`, topology, and conflict sections.
- [x] Keep Phase 6 orchestration separate from Phase 7 trading fusion.
- [x] Implement strict `AgentSpec` with type, count, Provider, model, prompt, tools, weight,
  timeout, retries, enabled state, budgets, metadata, fallback, Mock, and Replay settings.
- [x] Implement strict `TeamSpec` with six topologies, supervisor/judge references, maximum rounds,
  quorum, conflict policy, and serial/parallel mode.
- [x] Reject duplicate names, invalid role references, impossible single/debate/map-reduce teams,
  unknown keys, non-project models, and teams larger than 128 instances.

## Runtime and roles

- [x] Use one `AgentRuntime` for single-Agent and multi-Agent execution.
- [x] Expand `count` into stable independent instance IDs and deterministic seeds.
- [x] Give each instance an independent Provider, messages, tool budget, audit, timeout, retries,
  and Replay journal.
- [x] Implement `single`, `pipeline`, `supervisor_worker`, `committee_vote`,
  `debate_then_judge`, and `map_reduce`.
- [x] Preserve configuration-order results for both serial and parallel execution.
- [x] Register all report-listed built-in role types.
- [x] Expose named Research Orchestration, Risk Management, and Hierarchical Strategy role classes.
- [x] Support explicit Python factories and installed entry points.
- [x] Prevent model output from importing or constructing arbitrary Python objects.

## Arbitration, failure, and safety

- [x] Communicate only through validated `AgentDecision`/`UpstreamDecision` schemas.
- [x] Implement weighted vote, majority vote, judge, most-conservative, and reject policies.
- [x] Prohibit majority voting over free-form text.
- [x] Implement deterministic conservative tie-breaking and risk-limit intersection.
- [x] Enforce quorum and fail closed when it is not reached.
- [x] Isolate plugin exceptions, retries, Provider fallbacks, and timeouts per instance.
- [x] Ensure a failed risk Provider returns a no-new-position static fallback.
- [x] Keep Agent packages unable to import account or execution mutation modules.
- [x] Preserve Phase 5 tool permissions, path containment, no-shell boundary, and secret redaction.

## Acceptance

- [x] Run a real offline single-Agent tool workflow through `cmag agent run`.
- [x] Run a real parallel 1+3+2 committee with one deliberate Provider failure.
- [x] Test all six topologies.
- [x] Test serial and parallel equivalence.
- [x] Test dynamic count, independent seeds, per-instance retries, timeout, and partial failure.
- [x] Test Python registration and entry-point discovery.
- [x] Run Ruff, Mypy, unit/integration/leakage tests, coverage, dependency, and lock checks.
- [x] Scan source, configuration, documentation, and run artifacts for supplied secrets.
- [x] Record design decisions, acceptance evidence, and deferred Phase 7 work.

## Deferred by phase boundary

- [ ] Phase 7: typed Research workflow directives and executable research tools.
- [ ] Phase 7: `RiskContext`/`RiskDirective` administrator hard-limit merge and projection.
- [ ] Phase 7: `HierarchicalDirective` constraint fusion and all LLM-layer presets.
- [ ] Optional distributed executor: process/Ray cancellation for uncooperative plugin code.
- [ ] Live DeepSeek smoke test when the credential is injected through the process environment.
