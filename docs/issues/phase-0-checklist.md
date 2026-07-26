# Phase 0 issue checklist

## Scope

- [x] Read the detailed execution report in full.
- [x] Select final distribution, import, and CLI names.
- [x] Create the complete package and test directory skeleton.
- [x] Draft `pyproject.toml` with Python 3.11–3.12 and capability extras.
- [x] Add CPU and GPU constraint files.
- [x] Generate and validate `uv.lock`.
- [x] Add strict Phase 0 configuration models and safe YAML loading.
- [x] Pin every Agent configuration to `deepseek-v4-pro`.
- [x] Add credential redaction and environment-only credential references.
- [x] Add placeholder CLI command tree.
- [x] Add Linux/Python 3.11 CPU CI.
- [x] Add initial unit, property, integration, leakage, Agent, tuning, and regression tests.
- [x] Add documentation, design log, license, citation, and contributor files.
- [x] Verify editable installation and `cmag --help`.
- [x] Run `pytest`.
- [x] Run `ruff check .`.
- [x] Run `mypy src`.
- [x] Initialize the local Git repository on branch `main`.
- [ ] Probe the remote interpreter, create the remote project directory, and upload code.
  SSH connectivity was reached, but non-interactive authentication was rejected. No password was
  persisted or placed on a command line.

## Explicitly deferred

- Phase 1: source-data parsing, canonical schemas, manifests, and sample data.
- Phase 2: environment, accounting ledger, costs, masks, rewards, and market rules.
- Phase 3: PPO/SAC/TD3 and non-RL baselines.
- Phase 4: nine search algorithms and independent ASHA/HyperBand/PBT schedulers.
- Phases 5–7: providers, tools, unified AgentRuntime, and the three Agent layers.
- Phases 8–9: reports, service, packaging, publication, and SoftwareX artifacts.
