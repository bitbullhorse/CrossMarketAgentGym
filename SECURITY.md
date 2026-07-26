# Security policy

## Supported version

Security fixes are prepared for the current `0.1.x` release line.

## Reporting a vulnerability

Use GitHub private vulnerability reporting for the repository. Do not include API keys, market
data, account details, private run artifacts, or exploit payloads in a public issue.

Include the affected version, the smallest reproducible case, expected security boundary, and
observed behavior. Maintainers should acknowledge a private report before any public disclosure.

## Runtime boundaries

- Credentials are accepted only through environment-variable names declared in configuration.
- LLM output cannot mutate account state or widen deterministic administrator risk limits.
- Training/tuning paths cannot use locked test metrics for selection.
- Agent tools are registered typed Python callables and do not expose user-controlled shell
  execution.
- The report service is read-only and loopback-bound unless the operator explicitly opts into a
  remote host.
- Release archives reject local data, credentials, run outputs, environments, and checkpoints;
  the Docker runtime is unprivileged.
- PyPI publication uses short-lived OIDC and is separate from local release preparation.

The detailed implementation boundaries and phase-specific checks are maintained in
`docs/security.md`.
