# CrossMarketAgentGym v1.0.0

CrossMarketAgentGym 1.0.0 is the first stable release of the auditable cross-market research
platform.

## Highlights

- daily CN/HK/JP/US portfolio simulation with calendars, FX, trading rules and reconciled
  accounting;
- PPO, SAC and TD3 behind one trainer/evaluation contract;
- independently switchable Research Orchestration, Risk Management and Hierarchical Strategy
  Agents, all sharing the configurable single/multi-Agent `AgentRuntime`;
- DeepSeek `deepseek-v4-pro`, offline Mock and exact Replay providers;
- nine HPO search algorithms, with ASHA, HyperBand and PBT kept separate as resource schedulers;
- artifact verification and isolated computational replay;
- guarded local GUI for strategy configuration, experiments and backtests;
- reviewed, read-only `benchmark-v1` with 215 formal runs and complete provenance.

## Frozen research mapping

- Software release: `v1.0.0`
- Benchmark: `benchmark-v1`
- Formal dataset: `dataset-manifest-v3`
- Formal protocol: `protocol-v4`
- Formal experiment code: `6f03d3da3ed6ecbe918c5a7f9aa35cb9abfb2b83`

The v1/v2/v3 protocol drafts were superseded before eligible formal execution. Renaming the
accepted v4 protocol to match an earlier placeholder would destroy audit provenance.

## Data and safety

Restricted raw financial data is not included. The release contains metadata, hashes, public
synthetic fixtures and a lightweight deterministic sample checkpoint. LLMs cannot mutate account
state or bypass the deterministic risk layer, and HPO cannot access the test partition.

This software and its Benchmark are research tools, not investment advice or a guarantee of
profitability. See `release/known_issues.md`, `DATA_LICENSE.md` and `SECURITY.md`.

## DOI

The version DOI is added only after the archival service creates it. No placeholder DOI is
claimed.
