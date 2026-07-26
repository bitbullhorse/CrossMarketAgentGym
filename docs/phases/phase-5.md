# Phase 5 — LLM providers and permissioned tools

## Goal

Deliver deterministic Mock and Replay providers, a production-shaped OpenAI-compatible DeepSeek
adapter, strict structured output, permissioned tools, bounded fallback, credential-redacted audit,
and a fully offline acceptance workflow. Phase 5 must establish safe components without
prematurely implementing Phase 6 team orchestration.

## File changes

- `agents/providers/models.py`: Message, ToolCall, GenerationConfig, configuration, response,
  usage, metadata, and safe error contracts.
- `agents/providers/base.py`: shared `LLMProvider` protocol and canonical request SHA-256.
- `agents/providers/mock.py`: deterministic scripted offline Provider.
- `agents/providers/replay.py`: redacted JSONL journal and exact request-matched Replay Provider.
- `agents/providers/openai_compatible.py`: DeepSeek/OpenAI-compatible HTTP transport, retries,
  schema modes, tool parsing, and credential boundary.
- `agents/providers/factory.py`: explicit Provider construction without silent substitution.
- `agents/tools/models.py`: ToolDefinition, ToolPolicy, ToolPayload, and ToolResult.
- `agents/tools/registry.py`: typed Python registry, permissions, budgets, path containment,
  timeout, output validation, and error normalization.
- `agents/tools/builtin.py`: read-only `inspect_dataset` canonical-manifest tool.
- `agents/session.py`: bounded provider/tool conversation with validated static fallback.
- `agents/config.py`, `agents/workflow.py`: strict Phase 5 offline workflow and Replay verification.
- `audit/agent.py`, `audit/logging.py`: Agent audit artifacts and recursive secret redaction.
- `cli/app.py`: `cmag agent provider-check --config`.
- `configs/agents/provider_offline.yaml`: successful no-network tool and Replay quickstart.
- `configs/agents/provider_invalid_fallback.yaml`: deterministic malformed-output fallback example.
- `tests/agents/`: Provider, HTTP transport, Replay, tools, session, workflow, audit, and CLI tests.
- `tests/leakage/test_architecture_boundaries.py`: static no-shell-import guard for Agent tools.
- `docs/provider-tool-contract.md`: complete Provider/tool/security/replay contract.

## Design decisions

1. All providers use the same synchronous `LLMProvider` protocol. Phase 6 may schedule calls
   concurrently, but Provider semantics do not change between single and multi-Agent execution.
2. The only permitted model is `deepseek-v4-pro`, including Mock and Replay metadata, so offline
   experiments exercise the same model policy.
3. API key values are read only by `OpenAICompatibleProvider` from `api_key_env`. They are never
   Pydantic fields, repr values, YAML values, request hashes, response metadata, or audit fields.
4. OpenAI-compatible request headers and failure response bodies are never logged. Public base
   URLs containing userinfo, query, or fragment are rejected before network access.
5. Structured output is exact JSON plus Pydantic validation. There is no heuristic extraction from
   prose and no attempt to execute model text.
6. Invalid output and Provider failures select an immutable administrator fallback. The fallback
   is not generated or relaxed by the model.
7. Tools are registered Python callables. No shell or subprocess bridge exists in the tool
   package, and a static architecture test protects that decision.
8. Permission class, exact allowlist, budgets, workspace paths, schemas, timeout, and output paths
   are all checked outside the LLM.
9. Tool timing is audited but excluded from the tool message sent back to the model, keeping Replay
   request hashes deterministic.
10. Replay is strict and sequential. A mismatched request fails rather than returning a plausible
    but incorrect historical response.
11. Recursive redaction occurs immediately before audit/replay persistence and before tool output
    is returned to the model. Public environment-variable names and token counts remain visible.
12. The Phase 5 built-in registry is read-only. Training, tuning, file writes, and account mutation
    are not implicitly authorized.

## Tests

Tests cover strict configuration, required model policy, missing environment key, unsafe base URL,
message redaction before HTTP transport, retry after malformed JSON, HTTP tool-call parsing,
malformed JSON, schema violations, Mock exhaustion/errors, exact Replay and mismatch rejection,
Replay redaction, permission denial, allowlists, call/expensive/time budgets, input validation,
workspace escape, timeout, output schema, artifact paths, exception redaction, duplicate
registration, the real sample manifest tool, complete two-round offline conversation, exact
offline Replay, audit files, CLI execution, and deterministic safe fallback.

Repository-wide tests also verify that core source never calls `eval`, Agent tools do not import
shell execution modules, and source/config/docs contain no API key-shaped values.

## Acceptance result

Phase 5 passed locally on Python 3.12.13 and HTTPX 0.28.1:

| Check | Result |
|---|---|
| Providers | Mock, Replay, OpenAI-compatible implemented |
| Required model | `deepseek-v4-pro` enforced |
| Online transport tests | Retry, schema, function call, missing key, unsafe URL passed |
| Offline quickstart | 2 rounds, 1 read tool call, no fallback |
| Replay | Exact two-request conversation reproduced successfully |
| Invalid output | `invalid_json` selected `safe_to_continue=false` fallback |
| Network during acceptance | Disabled |
| Audit | Messages, tool calls, Provider metadata, fallback, Replay generated |
| Credential scan | Supplied API key and SSH password absent |
| Tool security | Permissions, budgets, schemas, paths, timeout, no-shell guard passed |
| Full test suite | 213 passed |
| Branch coverage | 87.68%, above the 85% gate |
| `ruff check src tests` | Passed |
| `mypy src` | Passed for 99 source files |
| `pip check` | No broken requirements |
| `python -m uv lock --check` | Passed; 111 packages resolved |

The machine-readable record is `docs/agents/phase5-acceptance.json`.

## Open issues

- The live DeepSeek endpoint was not called during automated acceptance because no secret was
  injected through the process environment. HTTP behavior was exercised with HTTPX's in-process
  transport, including the real Authorization-header boundary.
- Phase 6 still needs the shared `AgentRuntime`, configurable Agent counts, six topologies, partial
  failure handling, and conflict policies.
- Phase 7 must implement the Research, Risk, and Hierarchical roles; the Provider cannot mutate
  account state or bypass deterministic risk projection.
- Python threads cannot forcibly terminate an uncooperative handler after timeout. Current built-in
  tools are bounded read-only operations; process-isolated expensive tools remain a later executor.
