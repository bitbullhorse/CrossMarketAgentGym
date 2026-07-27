# CrossMarketAgentGym v1.0.0-rc2

This release candidate closes the Phase 11 independent-reproduction and usability gate. It does
not contain Phase 12 formal experiment results or a frozen paper Benchmark.

Highlights:

- honest separation of artifact verification and isolated computational replay;
- ordered bitwise, numerical, statistical, and failed reproduction levels;
- reviewed metric tolerances with exact TrainerConfig/data/protocol invariants;
- flat/tensor financial observation layouts without changing OHLCV dtype or scale;
- complete training runtime identity and evaluation sample-sufficiency evidence;
- explicit Risk cash-floor derivation and committee conflict/confidence/projection audit fields;
- Linux CPU wheel execution of Phase 11.3 Tasks B–I with wheel provenance attestation;
- non-root, network-disabled Docker execution limited to 2 CPU and 7 GB RAM;
- permanent commit-bound Phase 11.3 Release evidence package.

The package still prohibits test-set HPO, LLM account mutation, deterministic-risk bypass, and
promotion of development or Phase 11 smoke results into formal paper numbers.
