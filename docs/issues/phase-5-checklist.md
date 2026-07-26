# Phase 5 issue checklist

## Provider contracts

- [x] Define strict Message, ToolCall, GenerationConfig, response, usage, and metadata models.
- [x] Enforce `deepseek-v4-pro` for every provider configuration.
- [x] Record temperature, token limit, timeout, retries, backoff, and structured-output mode.
- [x] Read API key values only from named environment variables.
- [x] Implement deterministic `MockProvider`.
- [x] Implement exact request-hash `ReplayProvider` and replay journal.
- [x] Implement OpenAI-compatible HTTP transport.
- [x] Support JSON-object and JSON-schema request modes.
- [x] Parse OpenAI-compatible function calls and JSON arguments.
- [x] Bound transport, HTTP, and schema retries.
- [x] Fail closed when the API key environment variable is absent.

## Structured output and fallback

- [x] Validate final JSON with the caller's Pydantic model.
- [x] Reject malformed JSON, arrays, unknown fields, and invalid values.
- [x] Allow intermediate tool-call turns without pretending they are final output.
- [x] Return an administrator-supplied static fallback on provider/schema failure.
- [x] Audit every fallback with a stable error code.
- [x] Bound the provider/tool loop by maximum rounds.

## Tool security

- [x] Define ToolDefinition and ToolResult exactly at the provider boundary.
- [x] Separate read, compute, write, and expensive permissions.
- [x] Enforce explicit tool and permission allowlists.
- [x] Enforce total, expensive-call, and cumulative-time budgets.
- [x] Validate inputs and outputs with Pydantic.
- [x] Restrict input and artifact paths to the workspace.
- [x] Enforce per-tool timeout and normalize handler exceptions.
- [x] Recursively redact successful outputs and warnings.
- [x] Add a static guard against shell-execution imports in Agent tools.
- [x] Register a read-only canonical dataset inspection tool.

## Audit, replay, and acceptance

- [x] Write messages, tool calls, fallbacks, Provider metadata, and Replay artifacts.
- [x] Record model, prompt version, request hash, attempts, latency, finish reason, and token usage.
- [x] Recursively redact credentials immediately before persistence.
- [x] Preserve public environment-variable names in audit metadata.
- [x] Add `cmag agent provider-check --config`.
- [x] Run a no-network Mock → tool → final JSON → Replay workflow.
- [x] Run malformed JSON and verify safe static fallback.
- [x] Verify the supplied API key and SSH password are absent from run/repository artifacts.
- [x] Run full tests, Ruff, strict MyPy, dependency, and lock checks.

## Deferred to later phases

- [ ] Build the unified single/multi-Agent runtime and six topologies in Phase 6.
- [ ] Add Research, Risk, and Hierarchical roles and deterministic constraint fusion in Phase 7.
- [ ] Register write/expensive train and tune tools only after runtime authorization is complete.
- [ ] Add optional asynchronous/distributed tool cancellation for uncooperative handlers.
