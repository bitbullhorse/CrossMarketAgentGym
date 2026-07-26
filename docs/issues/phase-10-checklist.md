# Phase 10 issue checklist — `v1.0.0-rc1`

Status: **complete**. All mandatory Phase 10 exit criteria have local or immutable CI evidence.
GPU/Ray remains an explicitly optional, unverified profile and is not an rc1 CPU/Docker gate.

## Input conditions

- [x] Phase 0–9 acceptance reports are present.
- [x] A pre-Phase-10 local baseline commit exists (`b17e7f6`).
- [x] Packaged four-market CPU quickstart passes.
- [x] PPO, SAC, and TD3 train/evaluate paths pass.
- [x] Research, Risk, and Hierarchical Agents are independently switchable.
- [x] Single and multi-Agent teams share `AgentRuntime`.
- [x] Nine search algorithms and separate ASHA/HyperBand/PBT schedulers pass.
- [x] HPO resume passes without test-set access.
- [x] Leakage, accounting, risk-boundary, integration, property, and Replay tests pass locally.
- [x] Immutable candidate commit is reachable from the configured private GitHub remote.
- [x] Python 3.11 and 3.12 Linux CI passes.

## Version and release channel

- [x] Python version is PEP 440 `1.0.0rc1`.
- [x] Human release label and candidate tag map to `1.0.0-rc1` / `v1.0.0-rc1`.
- [x] GitHub workflow marks `-rc` tags as prereleases.
- [x] `CITATION.cff`, `.zenodo.json`, sample data manifest, wheel, sdist, and release notes agree.
- [x] Workflow has a non-publishing dry-run path.
- [x] No v1.0.0 tag or external publication occurred.
- [x] Docker image and unprivileged container quickstart pass.
- [x] Release blocker count is zero.

## Public API and CLI freeze

- [x] `release/api_inventory.csv` inventories and classifies all 248 reviewed exports.
- [x] Stable, provisional, and experimental classifications are explicit.
- [x] Every stable export has a generated signature, summary, and version-added record.
- [x] `docs/stable-api.md` and high-level API docs cover the stable surface.
- [x] API stability, versioning, and deprecation policies exist.
- [x] Drift verification fails on unreviewed export/signature/schema changes.
- [x] Namespace mismatches in earlier API documentation are reconciled.
- [x] `release/cli_inventory.json` freezes commands, options, defaults, and parameter types.
- [x] Root and leaf commands required by Phase 11 are present.
- [x] `cmag report --run-id <RUN_ID>` works.
- [x] `cmag release freeze` verifies by default and writes only with `--write`.
- [x] Phase 11 fixed configuration filenames and commands exist.

## Configuration and persisted formats

- [x] Eleven root configuration JSON Schemas are exported and hashed.
- [x] Twenty persisted-artifact Schemas are exported and hashed.
- [x] Path defaults generate portable deterministic JSON Schema without warnings.
- [x] OHLCV, data manifest, training/evaluation, Provider, Replay, team, directive, reporting,
  release, and reproduction formats are versioned.
- [x] Every new workflow writes a shared `run_manifest.json`.
- [x] Run manifests include config/data/protocol hashes, commit when available, source state, seed,
  runtime identity, status, and exact artifact hashes.
- [x] Manifest verification rejects tampering, missing files, and extra files.
- [x] HPO SQLite uses `PRAGMA user_version=1`, upgrades legacy version zero, and rejects future
  unsupported versions.
- [x] Existing pre-rc1 Phase 3/4/6/7 artifacts remain readable.
- [x] Frozen API/CLI/schema verification passes in a fresh Python process.

## Dependencies and environments

- [x] Core wheel excludes Excel, RL, HPO, online LLM, Ray, and service dependencies.
- [x] `legacy-data`, `rl`, `hpo`, `llm`, `ray`, `service`, `release`, `dev`, and `all` extras are
  explicit.
- [x] `.[dev]` contains the CPU requirements used by the Phase 11 protocol.
- [x] `uv.lock`, CPU/GPU constraints, and CPU/GPU Conda environment files exist.
- [x] Ordinary package downloads use the Tsinghua mirror.
- [x] No dependency uses an unpinned Git URL.
- [x] Local Python 3.12 `.[dev,legacy-data,release,service]` install succeeds.
- [x] `pip check` and `uv lock --check` pass.
- [x] Compatibility matrix distinguishes verified from declared profiles.
- [x] Python 3.11.15 clean-wheel install, CLI help, packaged quickstart, and `pip check` pass.
- [x] CUDA/Ray remains declared as optional and unverified; no GPU validation claim is made for
  rc1.

## Documentation and release files

- [x] All report-required installation, quickstart, data, environment, market, RL, LLM,
  multi-Agent, tuning, reproducibility, troubleshooting, security, and FAQ documents exist.
- [x] README uses the rc1 lifecycle and exact Phase 11 commands.
- [x] Offline documentation link/command verifier passes for 18 required documents.
- [x] rc1 checklist, API/CLI/config/format inventories, blockers, known issues, compatibility
  matrix, and release notes exist.
- [x] Phase 10 status report lists goals, files, decisions, tests, results, and remaining issues.
- [x] Phase 10/11 smoke outputs are explicitly prohibited from Phase 12 formal results.

## Automation and tests

- [x] Build, verify, clean-wheel, API/schema export, documentation, and double-build scripts exist.
- [x] Required Bash scripts pass `bash -n`.
- [x] 313 full tests pass with 87.51% branch coverage locally.
- [x] Ruff passes.
- [x] Strict mypy passes for 133 source files.
- [x] Mock/Replay and deterministic directive replay pass without an online key.
- [x] Exact Phase 11 environment, PPO, research Mock, risk committee Mock, and PSO/ASHA commands
  run locally.
- [x] Exact PPO and Agent reproduction commands pass.
- [x] Exact HPO command resumes to identical trial/selection state.
- [x] Wheel/sdist build, Twine, archive contents, and credential scan pass.
- [x] Python 3.12 clean-wheel CLI and packaged-data quickstart pass.
- [x] Two same-epoch builds produce byte-identical wheel and sdist hashes.
- [x] Python 3.11 clean-wheel command passes.
- [x] CI CPU matrix, package job, and Docker job pass on candidate commit `3e4dbc1a`.

## Exit conditions

- [x] Stable API and frozen formats are documented.
- [x] Local security, accounting, information-leakage, Replay, and HPO-resume blockers are zero.
- [x] Local CPU and clean Python 3.12 wheel quickstarts pass.
- [x] Locks, compatibility matrix, release notes, and known issues are current.
- [x] Docker quickstart passes as the unprivileged `cmag` container user.
- [x] Linux Python 3.11/3.12 gates pass.
- [x] Python 3.11 clean-wheel gate passes.
- [x] Release blocker count is zero.
- [x] The immutable passing candidate is tag-ready as exactly `v1.0.0-rc1`.
- [x] Phase 10 report status changes from blocked to complete.
- [x] Phase 11 technical readiness is explicitly approved; participant execution remains a
  separate Phase 11 action.

## Phase 11 boundary

- [x] Reproduction commands/configurations are prepared.
- [x] Real independent participants have not started before Phase 10 completion.
- [x] rc2 is not published before third-party reproduction and P0/P1 clearance.
- [x] Formal Phase 12 experiments do not reuse development or rc1 smoke results.
