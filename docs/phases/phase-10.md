# Phase 10 — v1.0.0-rc1 contract freeze

Status: **complete**. Mandatory local, Linux CPU, package, and unprivileged Docker gates pass;
the immutable candidate is ready for the exact tag `v1.0.0-rc1`. No PyPI or Zenodo publication
is part of Phase 10.

## Goal and input validation

The goal is to freeze the rc1 public API, CLI, configuration and persisted formats, dependency
profiles, run provenance, documentation, and local release pipeline before independent Phase 11
reproduction.

Phase 0–9 reports were present. The packaged four-market CPU quickstart passed. Existing PPO,
SAC, TD3, three independently switchable LLM layers, shared single/multi-Agent runtime, nine HPO
searchers, independent schedulers, leakage tests, accounting tests, Mock/Replay, and HPO resume
were revalidated. A local baseline commit was created before Phase 10 changes.
The candidate is reachable from the private
[`bitbullhorse/CrossMarketAgentGym`](https://github.com/bitbullhorse/CrossMarketAgentGym)
repository.

## Added files

- `release/`: rc1 checklist, blockers, API/config/format inventories, compatibility matrix, known
  issues, and release notes.
- `schemas/rc1/`: 11 configuration and 20 persisted-artifact JSON Schemas plus SHA-256 registry.
- `scripts/`: build, release verification, clean-wheel, API/schema export, documentation, and
  deterministic double-build automation.
- `environment-cpu.yml`, `environment-gpu.yml`, and updated `uv.lock`.
- Stable API, lifecycle, installation, quickstart, data, environment, market, RL, Agent,
  multi-Agent, tuning, reproducibility, troubleshooting, and FAQ documents.
- Phase 11 fixed configs: sample environment, PPO quickstart, research-only Mock, three-member
  risk committee Mock, and PPO/PSO/ASHA quickstart.
- Versioned run-manifest implementation and Phase 10 contract tests.
- Clean-checkout HPO report sources plus regression guards for ignored source files, archive
  exclusions, and cross-platform CLI error rendering.

## Modified files

- Package/release metadata, Docker and CI/release workflows, package extras and archive contents.
- Public Agent/environment exports, CLI report/freeze interfaces, release checks/distribution
  verification, RL/Agent/HPO workflows, audit envelopes, schema-bearing models, HPO SQLite store,
  README/API/CLI docs, and affected tests.

## Design decisions

1. Python uses PEP 440 `1.0.0rc1`; human release label/tag are `1.0.0-rc1` and
   `v1.0.0-rc1`.
2. Unlisted imports are internal. Reviewed exports are stable, provisional, or experimental;
   every stable export has a generated signature and docstring summary.
3. JSON Schema generation canonicalizes unordered defaults. `Path` defaults validate from
   portable strings, avoiding WindowsPath schema warnings.
4. Every new run stores a schema-versioned manifest containing config/data/protocol hashes,
   source/runtime identity, seed, status, and the exact artifact set. Locked evaluation refreshes
   the manifest after adding test artifacts.
5. Legacy pre-rc1 runs remain readable. New rc1 writers emit explicit schema versions; HPO SQLite
   uses `PRAGMA user_version=1` and rejects a future version.
6. Excel readers moved to `legacy-data`. `.[dev]` intentionally includes CPU reproduction
   dependencies required by the Phase 11 protocol. Online LLM, Ray, service, and release remain
   explicit profiles.
7. The CPU path is authoritative for rc1. CUDA 12.6/Ray is declared but remains unverified until
   a secure driver/hardware probe.
8. Formal benchmarks are absent by design. Phase 10/11 development results cannot become Phase 12
   formal results.
9. Historical Phase 9 distributions were moved intact to ignored `dist-phase9-backup/`; they were
   not deleted or overwritten.
10. Runtime-output ignore rules are anchored to the repository root so that a legitimate source
    package such as `tuning/reports` cannot be omitted from a clean checkout.
11. Release archive exclusions distinguish root-level `runs/` and `reports/` artifacts from
    same-named source packages.
12. GitHub Actions uses Node 24 action generations. A release-candidate tag may create a GitHub
    prerelease, but PyPI publishing requires an explicit manual `workflow_dispatch` with
    `publish=true`; stable PyPI publication remains Phase 14 work.

## Automated local results

| Gate | Result |
|---|---|
| Full pytest, property, leakage, integration, Mock/Replay, HPO resume | 313 passed |
| Branch coverage | 87.51% (required 85%) |
| Ruff | passed |
| Strict mypy | passed, 133 source files |
| Frozen contracts | 248 API records, 11 config Schemas, 20 artifact Schemas; no drift |
| Documentation verifier | passed, 18 required documents |
| Dependency checks | `pip check` and `uv lock --check` passed |
| Phase 11 fixed command smoke | environment, PPO, research Mock, risk committee Mock, PSO/ASHA all passed |
| Reproduction | PPO provenance and both Phase 7 directive replays passed |
| HPO resume | second run returned the same four trials and selected parameters |
| Build | wheel and sdist built; Twine/archive checks passed |
| Clean wheel | Python 3.11.15 and 3.12.13 installs, CLI help, packaged quickstart, and `pip check` passed |
| Reproducible build | two wheel/sdist builds were byte-identical at one source epoch |
| Bash syntax | three required shell wrappers passed Git Bash `bash -n` |
| Docker | Linux image build and non-root quickstart passed |
| Linux/Python 3.11/3.12 CI | both CPU jobs passed |

The immutable external evidence is GitHub Actions
[`ci #4`](https://github.com/bitbullhorse/CrossMarketAgentGym/actions/runs/30212412694)
on `3e4dbc1a1d108c360c4d2b41863982ed23a43d4a`: Python 3.11, Python 3.12,
package, and Docker all completed successfully. Earlier failed runs remain available and record
the discovery of an over-broad ignore rule, an over-broad archive exclusion, and ANSI-sensitive
CLI assertions; none was deleted or overwritten.

The local sample environment completed 64 random actions with maximum accounting error
`2.3283064365386963e-10`. The clean installed-wheel quickstart completed 16 actions with maximum
accounting error `1.1641532182693481e-10`.

The candidate commit is always resolved from the commit containing this report. Its epoch and
wheel/sdist hashes are generated after commit by `scripts/verify_reproducible_build.py` and
`cmag release manifest`; this avoids embedding a self-invalidating commit identity in a tracked
source file. These are candidate artifacts, not Phase 12 formal experiment results.

## Exit criteria and release readiness

- Stable API documentation, release notes, known issues, schema freeze, locks, local tests,
  Python 3.11/3.12 clean-wheel installs, CPU quickstart, and reproducible builds: **passed**.
- Docker build/unprivileged quickstart: **passed in Linux CI**.
- Linux Python 3.11/3.12 CI: **passed**.
- Release blockers zero: **satisfied**.
- Exact release-candidate tag: **ready as `v1.0.0-rc1`**.
- Phase 11 technical readiness: **approved**; real independent participant execution starts only
  as an explicit Phase 11 action.

The authoritative blocker list is `release/release_blockers.md`; it records zero open P0/P1
items. This report does not convert Phase 10/11 smoke output into formal experimental evidence.

## Remaining issues

- Securely probe the remote GPU driver before claiming the optional CUDA/Ray profile is verified.
- Do not publish rc2 before independent Phase 11 reproduction and P0/P1 clearance.
- Do not reuse development or rc1 smoke results as Phase 12 formal results.
