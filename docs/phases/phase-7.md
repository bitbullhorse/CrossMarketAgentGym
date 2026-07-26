# Phase 7 — three-layer Agent fusion

## Goal

Deliver independently switchable Research Orchestration, Risk Management, and Hierarchical
Strategy layers on the unified `AgentRuntime`. Add typed research workflows, immutable
administrator risk-policy intersection, first-version hierarchical constraint fusion, cadence,
six presets, and exact directive Replay. Keep all model output outside account mutation and
test-set selection.

## File changes

- `agents/directives.py`: strict domain schemas, static fallbacks, administrator merge, cadence,
  fusion, and deterministic projection adapter.
- `agents/layer_config.py`: layer modes, preset validation, team restrictions, and Phase 7 run
  configuration.
- `agents/layer_stack.py`: shared-runtime layer execution, cadence reuse, fusion, projection,
  journaling, and Replay.
- `agents/roles/builtin.py`: schema-specific Research, Risk, and Hierarchical Provider sessions
  while retaining Phase 6 compatibility.
- `agents/tools/builtin.py`, `agents/tools/registry.py`: the 12 bounded research tools, partition
  controls, path containment, and pre-expensive budget gate.
- `audit/directives.py`: redacted, sequence-numbered, SHA-256-protected directive journal.
- `cli/app.py`: automatic Phase 6 runtime versus Phase 7 stack dispatch for `cmag agent run`.
- `configs/agents/phase7_no_llm.yaml`: deterministic zero-Provider quickstart.
- `configs/agents/phase7_full_stack_offline.yaml`: offline Research + 3-Agent Risk committee +
  Hierarchical acceptance workflow.
- `configs/agents/full_stack.yaml`: credential-free online DeepSeek full-stack example.
- `tests/agents/test_directives.py`, `test_layer_config.py`, `test_layer_stack.py`,
  `test_research_tools.py`: schema, mode, hard-limit, preset, cadence, fallback, audit, Replay,
  CLI, and research-tool tests.
- `docs/directive-fusion-contract.md`: public safety and fusion contract.

## Design decisions

1. Each layer owns a `TeamSpec`, but all enabled teams execute through the same `AgentRuntime`.
   Disabled layers, especially `no_llm`, never construct a Provider runtime.
2. Research mode is enforced both at configuration time and tool-execution time. Expensive
   training/tuning requires explicit permission and a successful budget estimate in that session.
3. Research-facing evaluation is validation-only. Test metrics are unavailable to planning,
   comparison, and hyperparameter selection.
4. Risk proposals are not executable commands. Enforced proposals are intersected field-by-field
   with immutable administrator limits; advisory proposals are recorded but do not alter limits.
5. A Risk failure is maximally conservative: full cash, zero risk/exposure/turnover, and no new
   positions. Risk committees may only use the most-conservative arbitration policy.
6. Hierarchical fusion is constraint-only in Phase 7. Conditioning would change observation and
   policy interfaces and is explicitly deferred.
7. Fusion creates a stricter environment configuration and then calls the deterministic projector.
   It returns target weights only and has no import path to accounting or execution mutation.
8. Low-frequency layers reuse a previously validated directive when not due. Without one, they
   use a deterministic static fallback and do not call a Provider.
9. Replay uses validated directives and administrator configuration, not cached prose. It
   recomputes merge and projection and checks exact equality.
10. Short-position fusion and unknown market keys fail conservatively in this first version.

## Tests

Phase 7 tests cover strict and finite schemas, ordered research dependencies, test-partition
rejection, all 12 research tools, path containment, write permissions, compute-budget gating,
advisory/enforced risk behavior, administrator clipping, conservative committee arbitration,
failure fallback, hierarchical budget fusion, no-new-position masking, deterministic projection,
unknown markets, cadence, all six presets, zero-Provider `no_llm`, directive journaling, tamper
detection, Replay, and CLI execution.

## Acceptance result

Phase 7 passed locally on Python 3.12.13:

| Check | Result |
|---|---|
| Presets | All six passed in offline tests |
| `no_llm` quickstart | 0 Provider runtimes; no network; Replay verified |
| Offline full stack | Research 1 + Risk committee 3 + Hierarchical 1 |
| Research boundary | 12 tools; validation-only; budget required before expensive calls |
| Risk hard limits | Aggressive proposal could not widen administrator limits |
| Conservative committee | asset 0.15; cash 0.30; turnover 0.20; no new positions |
| Hierarchical fusion | global risk 0.50 and four market budgets intersected |
| Final effective constraints | cash 0.50; asset 0.15; turnover 0.20; no new positions |
| Directive Replay | Exact projection recomputation passed; tamper detection passed |
| Network during acceptance | Disabled |
| Full test suite | 278 passed; 4 existing SB3 observation warnings |
| Branch coverage | 87.73%, above the 85% gate |
| Ruff | Passed |
| Mypy | Passed for 111 source files |

Machine-readable evidence is written to `docs/agents/phase7-acceptance.json`.

## Open issues

- `conditioning` fusion is deferred because it changes the policy observation contract; Phase 7
  deliberately ships constraint fusion first.
- The online `full_stack.yaml` was schema-validated but the live endpoint was not called because
  `DEEPSEEK_API_KEY` was not injected into the current process. No credential value is stored.
- Phase 7 research train/tune tools expose guarded execution boundaries; distributed progress,
  cancellation, GPU/Ray placement, and server scheduling remain optional later adapters.
- Phase 8 subsequently delivered report rendering, benchmark views, and an optional read-only
  service without changing the directive/fusion safety contract.
