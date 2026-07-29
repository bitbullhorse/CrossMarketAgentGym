# Phase 14 issue checklist — stable v1.0.0 release

Status: **in progress; Phase 15 not ready**.

## Input conditions

- [x] Phase 13 is complete and Benchmark v1 was independently accepted.
- [x] Phase 13 P0/P1 are zero.
- [x] `benchmark-v1` passes all eight machine checks.
- [x] The formal experiment commit is an ancestor of the release source line.
- [x] Stable release uses the accepted `dataset-manifest-v3` and `protocol-v4`.

## Stable release implementation

- [x] Set the package, citation, Zenodo metadata and public sample version to `1.0.0`.
- [x] Add `release/release_manifest_v1.0.0.json` and its SHA-256.
- [x] Bind the Release to Benchmark v1, the formal commit, Dataset Manifest and protocol hashes.
- [x] Add a redistributable lightweight sample checkpoint and checksum.
- [x] Add `DATA_LICENSE.md`.
- [x] Expand wheel and sdist content verification.
- [x] Support `cmag release verify --version 1.0.0`.
- [x] Add deterministic restricted-data-free source archive automation.
- [x] Add PyPI and Docker dry-run scripts.
- [x] Add offline and online public release verification.
- [x] Add versioned docs build for `v1.0.0`, `stable`, and `latest`.
- [x] Upgrade the hosted release workflow with CPU, Docker, docs and provenance gates.

## Local verification

- [x] Regenerate and verify the frozen API, CLI and Schema inventories for stable v1.0.0.
- [x] Run unit, integration, leakage and reproduction tests.
- [x] Pass Ruff.
- [x] Pass strict mypy.
- [x] Pass the documentation contract and strict MkDocs build.
- [x] Double-build wheel and sdist reproducibly.
- [x] Install the wheel in a fresh CPU environment.
- [x] Run the 64-step CPU quickstart from the installed wheel.
- [x] Build and verify the non-root Docker image with no network, 2 CPUs,
  7 GB memory and CUDA disabled in the hosted dry-run.
- [x] Complete the non-publishing Stable release workflow dry-run and create
  attested wheel, source, Benchmark, documentation and container evidence.
- [x] Generate the local Phase 14 acceptance record.

## Public verification

- [ ] Configure/verify PyPI Trusted Publishing.
- [ ] Configure/verify GHCR package publication.
- [x] Configure GitHub Pages to use Actions as its build source.
- [ ] Deploy and publicly verify the versioned GitHub Pages site.
- [ ] Enable the archival integration and reserve/mint a DOI.
- [ ] Commit the exact release source and confirm a clean tree.
- [ ] Create annotated tag `v1.0.0` on that exact commit.
- [ ] Confirm the stable release workflow succeeds.
- [ ] Install `crossmarket-agent-gym==1.0.0` from public PyPI in a fresh CPU environment.
- [ ] Pull and run `ghcr.io/bitbullhorse/crossmarket-agent-gym:1.0.0`.
- [ ] Verify the public docs aliases `v1.0.0`, `stable`, and `latest`.
- [ ] Verify the DOI resolves and contains no restricted raw data.
- [ ] Verify the GitHub Release evidence and SHA-256 files.
- [ ] Run `scripts/verify_public_release.sh --online`.

## Exit conditions

- [ ] PyPI installation and quickstart succeed independently.
- [ ] Docker pull and bounded offline quickstart succeed independently.
- [ ] DOI and all documentation aliases are public.
- [x] Release-to-Benchmark mapping is machine-verifiable locally.
- [x] Software and data-license boundaries are explicit.
- [x] Citation, security and known-limitations statements are present.
- [x] `cmag release verify --version 1.0.0` passes against local stable distributions.
- [ ] No P0/P1 security, accounting, leakage or publication defect remains.
- [ ] Phase 14 is complete and Phase 15 is ready.
