# Phase 9 — release preparation

## Goal

Turn the Phase 0–8 implementation into an installable, inspectable, and citable `0.1.0` release.
Deliver an offline installed-wheel quickstart, read-only run reproduction, PyPI/Docker/GitHub/
Zenodo preparation, API and CLI documentation, examples, SoftwareX paper material, and an
optional Ray/GPU Trial executor without weakening the CPU reference, leakage, accounting, or
deterministic risk boundaries.

## File changes

- `release/models.py`, `quickstart.py`: strict release schemas and packaged-resource CPU
  quickstart.
- `release/checks.py`, `distribution.py`, `manifest.py`: local readiness, wheel/sdist inspection,
  forbidden-content checks, and deterministic SHA-256 distribution manifest.
- `release/reproduction.py`: read-only Phase 3/4/6/7 provenance and deterministic Replay checks.
- `cli/app.py`: `quickstart`, real `reproduce`, and `release check|verify|manifest` commands.
- `_version.py`, `py.typed`, `pyproject.toml`, `uv.lock`: stable dynamic version, typed-package
  marker, release dependencies, packaged resources, source archive policy, and lock update.
- `agents/providers/__init__.py`, `agents/providers/factory.py`: lazy online transport so the core
  wheel does not require `httpx`.
- `agents/runtime_workflow.py`, `agents/layer_stack.py`: canonical LF configuration artifacts for
  cross-platform identity.
- `tuning/executors/`: ordered local and optional Ray Trial-batch executors.
- `tuning/config.py`, `runner.py`, `workflow.py`: independent executor configuration and
  delegation while preserving searcher/scheduler contracts and CPU study identity.
- `configs/train/ppo_tune_gpu.yaml`, `configs/tune/ppo_pso_ray_gpu.yaml`: explicit CUDA training
  plus separately configured PSO, ASHA, and Ray placement.
- `Dockerfile`, `.dockerignore`: multi-stage bounded build and unprivileged runtime.
- `.github/workflows/ci.yml`, `.github/workflows/release.yml`: Python 3.11/3.12 gates, archive
  inspection, PyPI Trusted Publishing, and GitHub Release.
- `CITATION.cff`, `.zenodo.json`, `SECURITY.md`, `CHANGELOG.md`: citation, archival, disclosure,
  and release metadata.
- `docs/api-reference.md`, `cli-reference.md`, `release.md`, `scaling.md`: public interfaces,
  release/rollback, and Ray/GPU operating contract.
- `examples/cpu_quickstart.py`, `examples/reproduce_run.py`: installed-package examples.
- `paper/`: SoftwareX outline and source-to-artifact map without fabricated experimental claims.
- `tests/release/`, `tests/tuning/test_executors.py`, and existing regression/CLI tests: Phase 9
  release, reproduction, dependency-isolation, distribution, and distributed-executor coverage.

## Design decisions

1. `crossmarket_agentgym/_version.py` is the executable and distribution version source.
   Citation and Zenodo metadata are checked against it.
2. The wheel contains only the redistributable deterministic sample and reference configurations,
   not local `stock_data/`, runs, reports, checkpoints, or credentials.
3. CPU quickstart is an offline validation workflow. It does not download data, contact an LLM,
   train/tune a model, or mutate a real account.
4. “Reproduce” reports the strongest supported level honestly: exact deterministic Agent/directive
   Replay where journals exist; provenance and archive integrity for hardware-sensitive training
   artifacts. It never silently retrains.
5. Search generation, resource scheduling, and Trial placement are three independent abstractions.
   Ray restores completion results to suggestion order before optimizer observation.
6. The local executor remains authoritative for CPU reproducibility. Ray and CUDA are optional
   extras; CUDA wheel selection remains an operator/driver concern.
7. Release archives are inspected without extracting untrusted paths. `twine check` and content
   verification are both required because they prove different properties.
8. PyPI, GitHub Release, tag push, and Zenodo are external publication actions and remain gated by
   explicit authorization. The repository does not claim a placeholder DOI.
9. Docker builds a wheel in a separate stage and runs the bounded runtime as UID 10001.
10. The supplied remote password is never written to source, command arguments, process logs, or
    captured output; a real GPU acceptance run awaits a secure key or secret channel.

## Tests

Phase 9 tests cover strict release models, version and citation consistency, missing assets,
credential-shaped source scans, non-root Docker policy, manifest determinism, exact wheel/sdist
membership, forbidden paths, packaged configuration/sample resources, CPU quickstart, CLI
surfaces, training/tuning/Agent/Phase 7 reproduction, tamper detection, train/validation-only
selection, lazy optional dependencies, local executor ordering/failure isolation, Ray resource
requests, result-order restoration, configuration validation, and shutdown ownership.

The full suite also reruns the existing leakage, execution timing, projection, accounting,
partition-capability, HPO namespace, AgentRuntime, three-layer directive, reporting, and
dependency-compatibility regressions.

## Acceptance result

Phase 9 passed the locally available gates on Python 3.12.13:

| Check | Result |
|---|---|
| Full test suite | 302 passed; 12 SB3 observation-shape warnings |
| Branch coverage | 87.58%, above the 85% gate |
| Ruff | Passed |
| Strict Mypy | Passed for 130 source files |
| Dependency check | No broken requirements |
| Lock check | 134 packages resolved |
| Installed wheel | Core wheel installed and quickstart ran outside source checkout |
| Packaged sample | CN/HK/JP/US, 20 canonical OHLCV rows |
| Real run reproduction | Phase 3 training provenance and Phase 7 exact projection passed |
| CPU tuning compatibility | Existing eight-Trial study resumed without identity change |
| External network/LLM | Not used |
| Test-set HPO access | `false` |
| Direct Agent account mutation | `false` |

The final wheel, source archive, Twine result, content verification, and distribution hashes are
recorded outside the archives in `dist/release-manifest.json`; machine-readable gate evidence is
in `docs/release/phase9-acceptance.json`.

## Definition of Done review

- Installable package, CPU quickstart, Gymnasium/SB3 checks, PPO/SAC/TD3, and four-market sample:
  complete.
- Three independently switchable LLM layers and unified configurable single/multi-Agent runtime:
  complete.
- Nine searchers and independent ASHA/HyperBand/PBT schedulers: complete.
- Train/validation-only HPO, auditability, leakage/accounting tests, and read-only reproduction:
  complete.
- Documentation, examples, Apache-2.0 license, citation, and SoftwareX report generation:
  complete.
- External publication and DOI minting: prepared, intentionally not executed without explicit
  authorization.

## Open issues

- Docker is not installed on the local Windows host, so Dockerfile policy is statically tested but
  the final image still needs a real `docker build`/quickstart gate.
- Ray is exercised with a deterministic fake runtime; a real four-GPU CUDA run requires a secure
  remote authentication channel and compatible CUDA PyTorch installation.
- Live SB3 checkpoint cancellation for ASHA/HyperBand, distributed PBT weight transfer, and
  multi-node recovery require an incremental objective/checkpoint transport protocol.
- Cross-stock zero-shot, leave-one-market-out, and publication-scale multi-seed ablations remain
  planned/partial in the Phase 8 report; no results are fabricated for release.
- Production report serving still requires operator-supplied authentication, TLS, and deployment
  policy.
- PyPI/GitHub/Zenodo publication, DOI insertion, and protected tag creation remain authorized
  external actions.
