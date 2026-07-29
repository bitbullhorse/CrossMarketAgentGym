# Documentation

- [`operations-guide.zh-CN.md`](operations-guide.zh-CN.md) is the end-to-end Chinese operating
  manual for installation, data, environment checks, training, Agents, HPO, reproduction,
  reporting, Docker, Ray/GPU, audit, and troubleshooting.
- [`architecture/`](architecture/) describes the stable boundaries and planned package tree.
- [`phases/`](phases/) records delivery and acceptance evidence for each phase.
- [`issues/`](issues/) contains phase checklists.
- [`design-log.md`](design-log.md) records conservative decisions and secondary ambiguities.
- [`security.md`](security.md) records credential and LLM safety boundaries.
- [`tuning-contract.md`](tuning-contract.md) defines search, scheduling, persistence, objective,
  and train/validation-only HPO rules.
- [`provider-tool-contract.md`](provider-tool-contract.md) defines LLM transport, structured
  output, tool permissions, fallback, audit, and Replay rules.
- [`agent-runtime-contract.md`](agent-runtime-contract.md) defines Agent/team configuration, six
  topologies, role registration, partial failure, quorum, and structured conflict arbitration.
- [`directive-fusion-contract.md`](directive-fusion-contract.md) defines the three typed Agent
  layers, research tools, administrator risk intersection, cadence, constraint fusion, presets,
  and directive Replay.
- [`reporting-service-contract.md`](reporting-service-contract.md) defines deterministic SoftwareX
  reporting, whitelist run indexing, descriptive benchmarks, provenance, and the optional
  read-only service.
- [`api-reference.md`](api-reference.md) and [`cli-reference.md`](cli-reference.md) document the
  supported Python and command-line integration surfaces.
- [`release.md`](release.md) defines PyPI Trusted Publishing, Docker, GitHub Release, Zenodo,
  distribution manifests, and rollback.
- [`scaling.md`](scaling.md) defines optional Ray Trial execution, GPU placement, and its strict
  separation from search algorithms and resource schedulers.
- [`release/phase9-acceptance.json`](release/phase9-acceptance.json) records machine-readable
  Phase 9 quality, reproduction, distribution, and external-publication status.
