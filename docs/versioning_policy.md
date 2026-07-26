# Versioning policy

CrossMarketAgentGym uses PEP 440 package versions and SemVer-compatible release labels. The Python
version `1.0.0rc1` maps to release label `1.0.0-rc1` and Git tag `v1.0.0-rc1`.

- Patch releases contain compatible fixes.
- Minor releases may add compatible APIs and schemas.
- Major releases may remove deprecated stable APIs or introduce incompatible formats.
- Release candidates freeze a review boundary but are not formal benchmark releases.

The package version, tag, `CITATION.cff`, `.zenodo.json`, data manifest, built distributions, and
release notes must agree. Phase 10 may prepare rc1 locally; publication requires explicit
authorization. Stable `v1.0.0` is not allowed before the ordered Phase 11–14 gates.
