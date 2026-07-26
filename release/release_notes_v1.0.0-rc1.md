# CrossMarketAgentGym v1.0.0-rc1

This first release candidate freezes the public surface needed for independent reproduction.

Highlights:

- Daily CN/HK/JP/US OHLCV ingestion with hashed manifests and leakage-safe time boundaries.
- Deterministic cross-market accounting, execution rules, risk projection, PPO/SAC/TD3, and
  locked test evaluation.
- One `AgentRuntime` for single and multi-Agent execution, with independently switchable
  Research Orchestration, Risk Management, and Hierarchical Strategy layers.
- DeepSeek-compatible `deepseek-v4-pro` provider plus offline Mock and exact Replay.
- Nine search algorithms, with ASHA, HyperBand, and PBT implemented as separate schedulers.
- Frozen API/config/artifact inventories, per-run provenance manifests, reproducibility commands,
  CPU-first packaging, and optional GPU/Ray/service extras.

This candidate contains no formal paper benchmark. Development results must not be reused as
Phase 12 formal results. The candidate must pass independent Phase 11 reproduction before rc2.
