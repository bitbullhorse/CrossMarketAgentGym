# Release and archival guide

Phase 9 prepares release artifacts but does not publish them from a developer workstation.

## Local gate

Use Python 3.11 or 3.12 and the Tsinghua package mirror:

```bash
export PIP_INDEX_URL="https://pypi.tuna.tsinghua.edu.cn/simple"
python -m pip install -e ".[dev,rl,service,release]"
pytest
ruff check .
mypy src
cmag release check --workspace-root .
python -m build
python -m twine check dist/*.whl dist/*.tar.gz
cmag release verify --dist-dir dist
cmag release manifest --dist-dir dist
```

The build must contain one wheel, one source archive, and `release-manifest.json`. Inspect the
source archive before tagging; local market data, credentials, runs, reports, environments, and
checkpoints must be absent.

## Version and tag

`src/crossmarket_agentgym/_version.py` is the only version source. Hatch reads it for PyPI
metadata. `CITATION.cff` and `.zenodo.json` must carry the same stable version.

Create the protected rc2 tag only after the Phase 11 Linux CPU and Docker workflows succeed on
the exact commit and the evidence summaries are downloaded:

```bash
git tag -a v1.0.0-rc2 -m "CrossMarketAgentGym v1.0.0-rc2"
git push origin v1.0.0-rc2
```

Pushing the tag is an external publication authorization. Do not run these commands merely to test
the release workflow.

## PyPI trusted publishing

`.github/workflows/release.yml` builds once, checks the tag/version match, validates distributions,
and uses PyPI Trusted Publishing through GitHub OIDC. Configure the PyPI project and GitHub
`pypi` environment before the first tag. No long-lived PyPI token belongs in repository secrets.

A manual workflow dispatch defaults to `publish: false`. Changing it to true is an explicit
publication action.

## GitHub Release and Zenodo

A version tag creates a GitHub Release containing the wheel, source archive, and release manifest.
For rc2, also download the two commit-matched Phase 11 workflow artifacts, build the deterministic
evidence ZIP with `scripts/build_phase11_release_evidence.py`, and attach the ZIP plus checksum to
the Release. GitHub Actions artifacts are temporary; the Release asset is the permanent evidence.
Enable the repository in Zenodo's GitHub integration before tagging; Zenodo then archives the
GitHub Release using `.zenodo.json`.

After Zenodo mints the DOI:

1. add the version DOI to the release notes;
2. add the concept DOI and preferred citation to `CITATION.cff`;
3. update the README citation section;
4. prepare a metadata-only patch release if those changes must be archived.

No DOI is invented before Zenodo returns it.

## Docker

The default image contains core functionality and the read-only service:

```bash
docker build -t crossmarket-agent-gym:1.0.0-rc2 .
docker run --rm crossmarket-agent-gym:1.0.0-rc2 --version
docker run --rm crossmarket-agent-gym:1.0.0-rc2 quickstart --smoke-steps 16
```

To include Stable-Baselines3 and CPU PyTorch:

```bash
docker build --build-arg CMAG_EXTRAS=rl,service \
  -t crossmarket-agent-gym:1.0.0-rc2-rl .
```

The runtime uses an unprivileged `cmag` user. `.dockerignore` excludes credentials, raw market
data, runs, reports, environments, build products, tests, and paper drafts from the build context.

## Rollback

PyPI and Zenodo releases are immutable archival records. Never overwrite a released version.
Yank a defective PyPI version with a reason, mark the GitHub Release accordingly, and publish a
new patch version. Do not delete evidence required to explain the defect.
