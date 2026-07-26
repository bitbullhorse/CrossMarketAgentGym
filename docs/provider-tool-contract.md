# LLM provider and tool contract

## Scope

Phase 5 supplies the provider, schema, tool, audit, fallback, and replay boundaries used by the
Phase 6 `AgentRuntime`. It does not implement team topology, role scheduling, voting, or conflict
resolution early.

## Provider interface

`LLMProvider.generate` accepts:

- an ordered list of strict `Message` objects;
- an optional Pydantic response model;
- provider-visible `ToolDefinition` objects;
- immutable `GenerationConfig`.

It returns `LLMResponse` containing text, validated structured data, parsed tool calls, normalized
token usage, and credential-free metadata. The project includes:

- `MockProvider`: deterministic scripted offline responses and deliberate failures;
- `ReplayProvider`: sequential replay requiring an exact canonical request SHA-256;
- `OpenAICompatibleProvider`: bounded HTTP retries for the configured DeepSeek-compatible API.

All providers enforce model `deepseek-v4-pro`. Provider configuration records model, public base
URL, temperature, token limit, timeout, retry count, retry backoff, structured-output mode, and
environment-variable names. API key values are read only from the configured environment
variable by the online provider and are held only in process memory.

## Structured output

When a response model is requested, final content must be one JSON object and pass Pydantic
validation. Prose, JSON arrays, malformed JSON, unknown fields, and out-of-range values fail
closed. Tool-call turns are allowed to omit final structured content; the final non-tool response
must satisfy the schema.

`ProviderToolSession` catches provider and schema failures and returns an administrator-supplied,
already validated fallback object. Model text is never converted into code, a shell command,
account mutation, or an unvalidated directive.

## OpenAI-compatible transport

The online adapter:

- reads the API key from `api_key_env`;
- reads the base URL from `base_url_env`, with a public fallback URL;
- rejects credentials, query parameters, and fragments in the base URL;
- sends the key only in the Authorization header;
- redacts credential-like text from messages before transport;
- retries only within the configured bound;
- never records request headers or HTTP response bodies on failure;
- supports JSON-object and JSON-schema request modes;
- parses function arguments as JSON objects before constructing a `ToolCall`.

Missing credentials fail with `missing_api_key`; there is no silent fallback to another provider
or model.

## Tool boundary

Tools are pre-registered typed Python callables. User or model text can never become a shell
command. Each `ToolDefinition` records name, description, input schema, output schema, permission
class, and timeout.

Permissions are:

- `read`: inspect manifests and metrics;
- `compute`: validation and evaluation;
- `write`: configuration and report artifacts;
- `expensive`: training and tuning.

Before handler execution, `ToolExecutor` enforces:

1. exact registered name;
2. allowed permission;
3. explicit tool allowlist;
4. total and expensive-call budgets;
5. cumulative-time budget;
6. workspace path containment;
7. Pydantic input validation;
8. configured timeout.

Outputs pass the registered Pydantic output model, artifact paths must remain inside the
workspace, and successful data/warnings are recursively redacted before returning to the model.
Every failure becomes a structured `ToolResult`; exceptions do not escape into the conversation.

The Phase 5 built-in registry intentionally contains only the read-only `inspect_dataset` tool.
Write and expensive tools will be added in later phases only with explicit administrator policy.

## Audit and replay

Every provider check writes:

```text
runs/<run_id>/
├── provider_check_summary.json
└── agent/
    ├── messages.jsonl
    ├── tool_calls.jsonl
    ├── fallbacks.jsonl          # only when fallback occurs
    ├── provider_metadata.json
    └── replay.jsonl
```

Audits include prompt version, message direction, parsed tool arguments, normalized tool results,
model, public base URL, request SHA-256, retry count, latency, finish reason, and token usage.
Recursive redaction runs immediately before every audit or replay write. Environment-variable
names remain visible; credential values do not.

Replay journals contain response content and metadata but no headers or raw credentials. A replay
request must have the same canonical messages, response schema, tool definitions, and generation
configuration. A mismatch fails explicitly rather than returning the wrong historical response.
