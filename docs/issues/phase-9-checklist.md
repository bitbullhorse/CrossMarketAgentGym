# Phase 9 issue checklist

## Stable package and CPU reproduction

- [x] Promote the package to stable version `0.1.0` with one executable version source.
- [x] Keep Python 3.11 and 3.12 support in package metadata and CI.
- [x] Include `py.typed`, reference configurations, and the synthetic CN/HK/JP/US sample in the
  wheel.
- [x] Add a source-tree and installed-wheel CPU quickstart with no data download or LLM call.
- [x] Add read-only reproduction for Phase 3 training, Phase 4 tuning, Phase 6 Agent, and Phase 7
  directive artifacts.
- [x] Verify training provenance, checkpoint integrity, and train-only fitting capability.
- [x] Verify tuning used train/validation only and locked the recorded validation-selected
  parameters.
- [x] Verify strict Agent Replay journals and recompute Phase 7 directive fusion/projection.
- [x] Canonicalize configuration hashes across LF/CRLF platforms.

## Search, scheduling, Ray, and GPU separation

- [x] Define an executor protocol independently from search and scheduling.
- [x] Keep the ordered local executor as the CPU reference.
- [x] Add an optional lazy Ray executor with explicit per-Trial CPU/GPU resources.
- [x] Restore distributed results to suggestion order.
- [x] Preserve failed-Trial persistence and reject result count, ID, or parameter mismatches.
- [x] Keep Random/Grid/TPE/CMA-ES/NSGA-II/PSO/GA/DE/SA as searchers.
- [x] Keep ASHA/HyperBand/PBT as standalone schedulers.
- [x] Add a PSO + ASHA + Ray + CUDA example with separate configuration objects.
- [x] Preserve existing CPU tuning fingerprints and exact resume behavior.

## Distribution and publication preparation

- [x] Add release-readiness checks for metadata, version consistency, documentation, credentials,
  non-root Docker, and required files.
- [x] Build one wheel and one source archive.
- [x] Validate metadata with Twine.
- [x] Inspect wheel/source contents without extracting untrusted paths.
- [x] Generate a deterministic SHA-256 distribution manifest.
- [x] Add a multi-stage non-root Dockerfile and bounded `.dockerignore`.
- [x] Add PyPI Trusted Publishing and GitHub Release workflows.
- [x] Add Zenodo metadata without inventing a DOI.
- [x] Add citation, security reporting, contribution, conduct, license, and changelog materials.
- [x] Keep publishing, tag push, and Zenodo deposition behind explicit external authorization.

## Documentation and SoftwareX material

- [x] Document Python APIs, CLI commands, release/rollback, and optional Ray/GPU scaling.
- [x] Add installed-wheel quickstart and reproduction examples.
- [x] Add SoftwareX paper outline and artifact map.
- [x] Cross-link release, citation, and phase documentation from the README.
- [x] Record Phase 9 design decisions and security boundaries.
- [ ] Add the real Zenodo DOI after Zenodo mints it.

## Acceptance

- [x] Test release models, readiness, manifests, archive inspection, quickstart, reproduction, CLI,
  optional-dependency isolation, Ray resources, failure handling, and ordering.
- [x] Verify an isolated installed wheel can run outside the source checkout.
- [x] Verify real Phase 3 and Phase 7 artifacts.
- [x] Resume the existing CPU tuning study without changing its identity.
- [ ] Validate the Docker image on a host with Docker.
- [ ] Run a real Ray/CUDA multi-GPU study through a secure remote credential channel.
- [x] Run the final full unit suite, branch coverage, Ruff, strict Mypy, dependency, lock, archive,
  and credential gates.

## Deferred external actions

- [ ] Create and push the protected `v0.1.0` tag after repository ownership and CI are configured.
- [ ] Configure the PyPI Trusted Publisher and publish the validated artifacts.
- [ ] Enable Zenodo GitHub integration and archive the GitHub Release.
- [ ] Add production service authentication/TLS if remote report serving is required.
