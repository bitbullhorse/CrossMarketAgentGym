# Phase 6 — unified single/multi-Agent runtime

## Goal

Deliver one configuration-driven `AgentRuntime` for both one Agent and teams: strict `AgentSpec`
and `TeamSpec`, six communication topologies, dynamic instance counts, role plugins, serial and
parallel execution, bounded rounds, partial failure isolation, and deterministic structured
arbitration. Preserve the Phase 5 Provider/tool contract and do not cross the Phase 7 boundary into
account mutation or DRL constraint fusion.

## File changes

- `agents/models.py`: runtime configuration, structured communication, execution, and aggregate
  models.
- `agents/runtime.py`: deterministic expansion, six topology schedules, serial/parallel executor,
  timeouts, retries, partial failures, and shared result path.
- `agents/roles/base.py`: plugin factory and runtime role protocols.
- `agents/roles/builtin.py`: Provider-backed built-in roles and named three-layer role classes.
- `agents/roles/registry.py`: Python registration and installed entry-point discovery.
- `agents/aggregation/policies.py`: five structured conflict policies and quorum.
- `agents/runtime_workflow.py`: guarded run directory, redacted resolved configuration, hashes, and
  runtime summary.
- `audit/runtime.py`: resolved topology, invocation event, and aggregate audit.
- `agents/config.py`, `agents/__init__.py`, `cli/app.py`: loader, public API, and
  `cmag agent run --config`.
- `configs/agents/runtime_single_offline.yaml`: one-Agent read-tool quickstart.
- `configs/agents/runtime_team_offline.yaml`: parallel 1+3+2 conservative committee.
- `configs/agents/runtime_deepseek_team.yaml`: credential-free online configuration.
- `tests/agents/test_runtime*.py`, `test_aggregation.py`, `test_role_registry.py`: schema,
  topology, execution, plugin, workflow, and CLI coverage.
- `tests/leakage/test_architecture_boundaries.py`: account/execution import prohibition.
- `docs/agent-runtime-contract.md`: public runtime and security contract.

## Design decisions

1. A single Agent is exactly one enabled instance in the `single` topology. It is not a separate
   code path or reduced API.
2. Dynamic count expansion happens before role construction. IDs, seeds, Provider state, messages,
   tool budgets, retries, timeouts, audits, and Replay journals are instance-local.
3. All topology messages are validated structured envelopes. Arbitration reads the decision enum
   and constraint fields; it never votes on arbitrary prose.
4. Parallel execution changes scheduling only. Results and audit order remain configuration-stable
   so a fixed seed remains reproducible.
5. Risk Provider failure creates a conservative static decision and remains visible as `fallback`.
   Plugin failure/timeout remains visible as partial failure; quorum then determines whether the
   team can resolve.
6. `most_conservative` maximizes cash, minimizes exposure/turnover limits, and makes denial of new
   positions dominant. This is still advice; Phase 7 must intersect it with administrator limits
   and deterministic projection.
7. Custom roles enter through an in-process Python factory or an installed entry point. Runtime
   configuration names a registered type only; LLM text cannot name a module to import.
8. `max_rounds` caps feedback interaction. Pipelines are one dependency round; supervisor,
   debate/judge, and map/reduce schedules never exceed the configured cap.
9. Runtime configuration is redacted before persistence. Provider credentials remain environment
   values owned exclusively by the OpenAI-compatible adapter.
10. Threads provide portable CPU parallelism. Timed-out calls are isolated from aggregation, but
    forceful process cancellation remains a distributed/process executor concern.

## Tests

Phase 6 tests cover strict schema rejection, required model policy, disabled roles, dynamic count,
stable independent seeds, shared/per-instance Mock scripts, all six topologies, serial/parallel
equivalence, dependency messages, supervisor/reducer/judge references, per-instance retry,
timeout, 1+3+2 partial failure, weighted/majority votes, conservative ties, reject-on-conflict,
judge selection, quorum, conservative limit intersection, built-in Provider sessions, Replay
artifacts, Python factories, entry points, workflow paths, CLI, and the static account-mutation
import boundary.

## Acceptance result

Phase 6 passed locally on Python 3.12.13:

| Check | Result |
|---|---|
| Single-Agent quickstart | 1 instance, 1 read tool, 1 structured approval, no network |
| 1+3+2 committee | 6 independent instances and seeds |
| Deliberate Provider failure | 5 successes, 1 static risk fallback, team continued |
| Conservative result | Reject; cash floor 1.0; asset cap 0.0; turnover 0.0; no new positions |
| Topologies | All six passed |
| Scheduling | Serial and parallel passed with stable ordered results |
| Plugins | Python registration and entry-point loading passed |
| Partial failures | Provider fallback, plugin failure, retry, timeout, and quorum passed |
| Model policy | Every configured Agent requires `deepseek-v4-pro` |
| Network during acceptance | Disabled |
| Security | No shell bridge; no Agent account/execution imports; redacted audits |
| Full test suite | 242 passed; 4 existing SB3 observation warnings |
| Branch coverage | 87.88%, above the 85% gate |
| Ruff | Passed |
| Mypy | Passed for 107 source files |

Machine-readable evidence is written to `docs/agents/phase6-acceptance.json`.

## Open issues

- Phase 7 must implement the domain-specific Research, Risk, and Hierarchical directive schemas,
  administrator risk-policy merge, deterministic constraint projection, cadence, fusion, and all
  layer presets. Named role classes are independently configurable now, but they cannot trade.
- The live DeepSeek endpoint was not called because `DEEPSEEK_API_KEY` was not injected through the
  current process environment. The online multi-Agent configuration contains environment-variable
  names only.
- Python threads cannot forcibly terminate uncooperative custom plugin code. Timed-out results are
  excluded and fail through quorum; process/Ray isolation is deferred.
- Windows should invoke tests as `python -m pytest` in workspaces with non-ASCII paths; the
  standalone `pytest.exe` launcher did not reliably place this workspace on `sys.path`.
