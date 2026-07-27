# Versioning policy

CrossMarketAgentGym uses PEP 440 package versions and SemVer-compatible release labels. The Python
version `1.0.0rc2` maps to release label `1.0.0-rc2` and Git tag `v1.0.0-rc2`.

- Patch releases contain compatible fixes.
- Minor releases may add compatible APIs and schemas.
- Major releases may remove deprecated stable APIs or introduce incompatible formats.
- Release candidates freeze a review boundary but are not formal benchmark releases.

The package version, tag, `CITATION.cff`, `.zenodo.json`, data manifest, built distributions, and
release notes must agree. Phase 10 produced rc1; Phase 11 may produce rc2 only after independent
P0/P1 clearance and Linux CPU/Docker evidence. Stable `v1.0.0` is not allowed before the ordered
Phase 12–14 gates.
