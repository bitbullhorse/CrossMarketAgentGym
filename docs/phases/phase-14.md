# Phase 14 — stable v1.0.0 release

Status: **in progress; Phase 15 not ready**.

## Goal and input validation

Phase 14 publishes one publicly installable, citable and archived stable release. Phase 13 is
accepted with P0/P1 equal to zero. Benchmark v1 binds 215 formal runs, Dataset Manifest v3,
protocol-v4 and formal code commit `6f03d3da3ed6ecbe918c5a7f9aa35cb9abfb2b83`.

The Phase 14 report's dataset/protocol v1 labels were placeholders. They are not used because
the accepted experiment deliberately superseded those revisions to correct leakage and
data-semantic defects.

## Added files

- `DATA_LICENSE.md`
- `data/sample/checkpoints/`
- `mkdocs.yml`
- `release/release_manifest_v1.0.0.{json,sha256}`
- `release/release_notes_v1.0.0.md`
- `scripts/create_stable_release_manifest.py`
- `scripts/create_release_archive.py`
- `scripts/create_archive.sh`
- `scripts/publish_pypi.sh`
- `scripts/publish_docker.sh`
- `scripts/verify_public_release.{py,sh}`
- `scripts/build_versioned_docs.py`
- `scripts/run_phase14_acceptance.py`
- `docs/compatibility.md`
- `docs/known-limitations.md`
- `docs/issues/phase-14-checklist.md`
- `docs/experiments/phase14-machine-acceptance.json`
- `docs/phases/phase-14.md`
- `tests/release/test_stable_manifest.py`

## Modified files

- `.github/workflows/release.yml`
- `.zenodo.json`
- `CITATION.cff`
- `README.md`
- `SECURITY.md`
- `data/sample/dataset_manifest.json`
- `docs/faq.md`
- `docs/release.md`
- `pyproject.toml`
- `release/compatibility_matrix.md`
- `release/known_issues.md`
- frozen contract inventories under `release/` and `schemas/rc1/`
- `src/crossmarket_agentgym/_version.py`
- `src/crossmarket_agentgym/cli/app.py`
- `src/crossmarket_agentgym/release/checks.py`
- `src/crossmarket_agentgym/release/distribution.py`
- release and version tests
- `uv.lock`

## Design decisions

- The stable manifest records the real accepted inputs: Dataset Manifest v3 and protocol-v4.
  Renaming these to satisfy older placeholders would break scientific provenance.
- The formal raw OHLCV data is never redistributed. Public archives contain hashes, metadata,
  a synthetic sample and a model-independent sample checkpoint.
- The release workflow uses PyPI OIDC and the GitHub repository token. Long-lived publication
  credentials are not stored.
- Manual workflow dispatch defaults to a dry-run. Stable tag publication remains gated by every
  build, test, CPU, container and docs job.
- The stable tag is not created from an uncommitted or unverified tree.
- A DOI is never guessed. Phase 14 remains open until a real DOI resolves.

## Automation

```bash
python scripts/create_stable_release_manifest.py --verify
scripts/create_archive.sh --dry-run
scripts/publish_pypi.sh --dry-run
scripts/publish_docker.sh --dry-run
python scripts/build_versioned_docs.py --dry-run
scripts/verify_public_release.sh --offline
python scripts/run_phase14_acceptance.py
```

The hosted workflow builds and attests stable artifacts, installs the wheel in a fresh CPU
environment, runs a bounded offline container, builds all documentation aliases and separates
PyPI, GHCR, Pages and GitHub Release publication.

## Tests and current acceptance

The stable-manifest tests cover accepted-input mapping, deterministic regeneration, adjacent
checksum validation and fail-closed Benchmark identity handling. Existing distribution tests now
require the public checkpoint, data license, stable manifest and release automation in built
archives.

Verified locally on Python 3.12.13:

- 406 tests passed with 85.20% branch-aware coverage;
- Ruff passed;
- strict mypy passed for 159 source files;
- the documentation contract passed for 31 required files;
- strict MkDocs built all selected pages;
- the frozen contract passed with 251 API records, 11 configuration Schemas and 20 artifact
  Schemas;
- deterministic double-build produced byte-identical wheel and sdist pairs;
- wheel and sdist metadata, contents and exclusions passed;
- a fresh wheel environment reported PyTorch 2.7.1+cpu and
  `torch.cuda.is_available() == false`;
- the installed wheel completed the packaged 64-step quickstart with Gymnasium and SB3 checks
  passing, no warnings, no network/LLM use and maximum accounting error
  `2.3283064365386963e-10`;
- the consumer GUI build, three rendered-HTML tests and ESLint passed.

`docs/experiments/phase14-machine-acceptance.json` records every local mapping and artifact
check as passing. It deliberately reports Phase 14 incomplete because no stable tag or public
service evidence exists yet. The local workstation has no Docker executable, so Docker is left
for the Linux hosted or authorized remote gate rather than being inferred from the Dockerfile.

## Exit conditions and remaining blockers

Local implementation is not equivalent to a public release. Phase 14 cannot close until:

- final wheel/sdist and CPU/Docker fresh-install gates pass;
- PyPI, GHCR and all three docs aliases are publicly verified;
- a DOI is minted and its archive is checked for restricted data;
- the exact clean release commit is tagged `v1.0.0`;
- the GitHub Release and all checksums/provenance attestations are accessible;
- P0/P1 remain zero.

Until those checks pass, `phase14_complete` and `phase15_ready` remain false.
