# Stable release and archival guide

Stable `v1.0.0` is published only from the protected release workflow after its local and hosted
gates pass. A developer workstation may build and verify the same artifacts, but a local dry-run
does not constitute a public release.

## Version mapping

The release manifest binds these immutable identities:

| Surface | Identity |
|---|---|
| Software | `v1.0.0` |
| Benchmark | `benchmark-v1` |
| Formal dataset manifest | `dataset-manifest-v3` |
| Formal experiment protocol | `protocol-v4` |
| Formal experiment commit | `6f03d3da3ed6ecbe918c5a7f9aa35cb9abfb2b83` |

The original Phase 14 report used v1 placeholders for the dataset and protocol. The accepted
formal experiment uses v3/v4 because earlier revisions were superseded by stricter leakage and
data-semantic corrections. Release metadata must not rename or downgrade those frozen inputs.

## Local gate

Use Python 3.11 or 3.12. A mainland China mirror can be selected for dependency resolution:

```bash
export PIP_INDEX_URL="https://pypi.tuna.tsinghua.edu.cn/simple"
python -m pip install -e ".[dev,release,docs,rl,llm]"
cmag release freeze --workspace-root .
cmag benchmark verify --benchmark benchmarks/v1
python scripts/create_stable_release_manifest.py --verify
python scripts/verify_docs.py
pytest
ruff check .
mypy src
python -m build
python -m twine check dist/*.whl dist/*.tar.gz
cmag release verify --version 1.0.0
```

Use the provided dry-runs before any external state change:

```bash
scripts/create_archive.sh --dry-run
scripts/publish_pypi.sh --dry-run
scripts/publish_docker.sh --dry-run
scripts/verify_public_release.sh --offline
```

## Tag and hosted release

`src/crossmarket_agentgym/_version.py` is the package version source. `CITATION.cff`,
`.zenodo.json`, and `release/release_manifest_v1.0.0.json` must agree with it.

Create `v1.0.0` only after:

- every local release gate passes on the exact commit;
- PyPI Trusted Publishing is configured for the GitHub `pypi` environment;
- GitHub Pages and GHCR publication are enabled;
- the archival integration is enabled and a DOI can be minted without restricted data.

The tag launches `.github/workflows/release.yml`. It builds and attests the wheel, sdist, source
evidence archive, Benchmark archive, public sample checkpoint, and checksums. Publication jobs
use GitHub OIDC or the scoped repository token; no long-lived PyPI or registry credential belongs
in the repository.

Pushing a stable tag is an irreversible publication action. Do not create or push it merely to
test the workflow; use a manual dispatch with every publication input left `false`.

## PyPI verification

After publication, use a new CPU environment and the canonical package name:

```bash
python -m venv verify-v1
verify-v1/bin/python -m pip install "crossmarket-agent-gym==1.0.0"
verify-v1/bin/cmag --version
verify-v1/bin/cmag quickstart --smoke-steps 64
```

PyPI normalizes project names, but documentation consistently uses
`crossmarket-agent-gym`.

## Container verification

The public image uses `cmag` as its entrypoint and runs as the unprivileged `cmag` user:

```bash
docker pull ghcr.io/bitbullhorse/crossmarket-agent-gym:1.0.0
docker run --rm \
  --network none \
  --cpus 2 \
  --memory 7g \
  --env CUDA_VISIBLE_DEVICES="" \
  ghcr.io/bitbullhorse/crossmarket-agent-gym:1.0.0 \
  quickstart --smoke-steps 64
```

The final argument is `quickstart`, not `cmag quickstart`, because the image entrypoint already is
`cmag`.

## Documentation and DOI

The docs job builds byte-equivalent `v1.0.0`, `stable`, and `latest` trees. The archival package
contains source, documentation, synthetic samples, manifests, Benchmark metadata, release notes,
citation metadata, and licenses.

It must not contain restricted raw financial records. For those data, only acquisition
instructions, Schema, symbol universe, date ranges, hashes, and the redistributable synthetic
sample may be archived. `DATA_LICENSE.md` is the controlling redistribution statement.

No DOI is invented before the archive service returns it. After minting, add the version DOI and
preferred citation to `CITATION.cff`, the release manifest, and the README through a metadata-only
patch if the stable tag has already been published.

## Final public verification

```bash
scripts/verify_public_release.sh --online
```

This checks PyPI, the CPU container, all three documentation aliases, the DOI, and the local
release-to-Benchmark mapping. Phase 14 remains open until every online check passes.

## Rollback

Published PyPI, container, Release, and archival records are immutable evidence. Never overwrite
a released version. Yank a defective package with a reason, mark the Release, and publish a patch
version. Retain the original evidence explaining the defect.
