# Security boundaries

1. Credentials are accepted only through named environment variables.
2. Logs redact assignment-like secrets and `sk-...` tokens before handlers emit records.
3. YAML is loaded with `safe_load`; core source may not call Python `eval`.
4. Agent tool permissions distinguish read, compute, write, and expensive operations.
5. LLM outputs cannot execute shell text, mutate account state, widen administrator risk limits, or
   read hidden test metrics.
6. Raw market data, generated runs, checkpoints, `.env` files, and credentials are ignored.

The API credential supplied out of band is intentionally absent from every repository artifact.

## Phase 5 Provider boundary

- Online Provider construction fails unless `api_key_env` exists in the process environment.
- Base URLs containing userinfo, query strings, or fragments are rejected.
- Authorization headers and failure response bodies are never added to audit artifacts.
- Credential-like text in messages is redacted before online transport.
- Structured output must pass Pydantic validation; otherwise an administrator fallback is used.
- Model-requested tools pass external allowlists, budgets, schemas, paths, and timeouts.
- The Agent tool package contains no shell/subprocess bridge.
- Replay journals are redacted and require an exact canonical request hash.

## Phase 6 runtime boundary

- One Agent and teams use the same `AgentRuntime`; no reduced single-Agent bypass exists.
- Runtime role types must be pre-registered Python factories or installed entry points. Model text
  cannot name a module to import.
- The Agent package is statically prohibited from importing account or execution mutation modules.
- Topology messages and results are Pydantic models. Free-form text is never vote input.
- Per-instance Providers, tools, budgets, retries, timeouts, audit files, and Replay journals are
  isolated.
- Plugin exceptions and timeouts are removed from the vote; quorum failure returns static
  rejection.
- Risk Provider failure denies new positions and cannot loosen the conservative aggregate.
- Parallel completion order does not control arbitration order.
- The online team configuration stores only API-key environment-variable names.

## Phase 7 directive boundary

- All three layers emit strict Pydantic directives and execute through `AgentRuntime`.
- `no_llm` constructs no Provider runtime and makes no credential or network access.
- Research tools reject test partitions/test metrics and require budget estimation before an
  expensive train or tune call.
- Risk maxima are intersected by minimum, cash floors by maximum, and permissions by logical AND
  with immutable administrator policy.
- Risk committees are restricted to most-conservative arbitration; failure denies positions.
- Hierarchical output narrows deterministic constraints and cannot mutate policy weights or
  account state directly.
- The Agent package remains unable to import accounting or execution mutation modules.
- Directive journals are redacted, ordered, hashed, and verified before Replay.

## Phase 8 reporting boundary

- Run browsing is whitelist-based and never exposes raw prompts, Provider responses,
  configurations, checkpoints, credentials, or arbitrary run files.
- Source, evidence, and asset paths are resolved inside configured roots with size and count
  bounds.
- Report generation cannot write inside the runs tree and cannot mutate training, tuning, Agent,
  environment, or account state.
- Benchmark payloads carry `selection_authority: false`; hidden test metrics remain unavailable to
  search algorithms and resource schedulers.
- JSON and metrics reject NaN and infinity; missing evidence is shown as `N/A`.
- The optional service is loopback-only by default, has no mutation route, disables API docs by
  default, and serves only whitelisted report suffixes.
- Non-loopback binding requires explicit opt-in and does not provide or claim production
  authentication.
- CSP, MIME-sniffing, and referrer headers reduce passive report-browser exposure.

## Phase 9 release boundary

- The installed-wheel quickstart uses packaged synthetic data and performs no download, Provider
  request, training, tuning, or direct account mutation.
- Run reproduction is read-only: it verifies bounded, whitelisted artifacts and never retrains or
  feeds test metrics back into selection.
- Distribution inspection reads ZIP/TAR member names and bytes without extracting untrusted
  paths; local data, runs, reports, environments, credentials, and checkpoints are forbidden.
- Online Provider, Stable-Baselines3/PyTorch, Ray, and service imports remain lazy optional
  capabilities rather than core-wheel startup requirements.
- The Docker runtime copies only built distributions, excludes local/private build context, and
  runs as an unprivileged fixed UID.
- CI publishing uses short-lived GitHub OIDC through PyPI Trusted Publishing. No long-lived PyPI
  token is stored.
- PyPI, GitHub Release, tag push, and Zenodo deposition require explicit authorization. Release
  preparation alone performs no external publication.
- Ray workers receive explicit CPU/GPU placement only. They do not receive LLM credentials or gain
  access to hidden test metrics, search authority, scheduling authority, or account mutation.
