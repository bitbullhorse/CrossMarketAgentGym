# v1.0.0-rc1 release checklist

The checklist is a gate, not evidence by itself. Each checked item must cite a CI job or local
artifact in the Phase 10 completion report.

- [x] API inventory reviewed and frozen.
- [x] Configuration and persisted-format schemas exported and verified.
- [x] CPU and GPU dependency declarations reviewed; CPU lock installed cleanly.
- [x] Unit, property, leakage, integration, Mock/Replay, and HPO-resume tests pass locally.
- [x] Ruff and strict mypy pass locally.
- [x] Documentation verifier passes.
- [x] Wheel and source distribution build, inspect, and install in clean Python 3.11 and 3.12 environments.
- [x] CPU quickstart passes from the installed wheel.
- [x] Docker image builds and its unprivileged quickstart passes in Linux CI.
- [x] Credential scan and release-readiness checks pass.
- [x] Release blockers are zero.
- [x] Release notes and known issues are current.
- [x] Tag candidate is exactly `v1.0.0-rc1`.
- [x] No external publication occurs without explicit authorization.

External evidence: GitHub Actions
[`ci #4`](https://github.com/bitbullhorse/CrossMarketAgentGym/actions/runs/30212412694)
passed Python 3.11, Python 3.12, package, and Docker jobs on
`3e4dbc1a1d108c360c4d2b41863982ed23a43d4a`.
