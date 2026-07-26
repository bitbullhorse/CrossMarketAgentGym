# Phase 0 — Engineering skeleton

## Goal

Create an installable CPU-first Python project with the complete package boundaries, validated
configuration, secret-safe logs, placeholder CLI, minimal CI, documentation framework, and quality
gates needed before data, environment, RL, HPO, or Agent implementation.

## File changes

- Root metadata: `pyproject.toml`, constraint files, project governance, license, citation,
  container stub, ignore rules, and environment template.
- Package: complete `src/crossmarket_agentgym/` namespace, CLI, minimal configuration loader, and
  logging redaction.
- Configuration: local dataset layout note, Phase 0 smoke config, DeepSeek full-stack draft, and
  explicit searcher/scheduler split.
- Quality: initial tests and Linux/Python 3.11 CPU CI.
- Documentation: architecture, target tree, design log, security boundary, issue checklist, and
  this acceptance record.

## Design decisions

See `docs/design-log.md`. The key Phase 0 decisions are Python 3.11–3.12 support, CPU-first extras,
environment-only credentials, exact `deepseek-v4-pro` model policy, structural test isolation, and
separate searcher/scheduler namespaces.

## Tests

The first batch covers package metadata, all CLI placeholders, immutable strict configuration,
model enforcement, safe YAML, secret redaction, deterministic seed configuration, dependency
compatibility, absence of `eval`, namespace separation, and distribution metadata.

## Acceptance result

Local Phase 0 acceptance passed on Windows with Python 3.12.13:

| Check | Result |
|---|---|
| Editable install with CPU constraints | Passed |
| `cmag --help` | Passed; complete placeholder command tree displayed |
| `pytest` | 28 passed |
| Branch coverage | 97.26%, above the 85% gate |
| `ruff check .` | Passed |
| `mypy src` | Passed for 37 source files |
| `pip check` | No broken requirements |
| `uv lock --check` | Passed; 105 packages resolved |
| Local Git repository | Initialized on `main` |

## Open issues

- Linux/Python 3.11 is represented by CI and cannot be executed on this Windows host.
- SSH reached `czj@10.108.24.182`, but `BatchMode` authentication returned
  `Permission denied (publickey,password)`. The remote directory and
  `/mnt/sdb/czj/conda_envs/pytorch_3.12/bin/python` probe are therefore not yet confirmed. Use a
  loaded SSH key or a non-logged secret channel before upload.
- Dataset schema and the nested CN layout are intentionally deferred to Phase 1.
