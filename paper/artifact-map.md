# Manuscript artifact map

| Manuscript item | Generated or source artifact | Status |
|---|---|---|
| Environment correctness | `docs/environment/phase2-acceptance.json` | complete |
| PPO/SAC/TD3 comparison | `reports/phase8-softwarex/tables/benchmark_comparison.csv` | descriptive validation evidence |
| Experiment readiness | `reports/phase8-softwarex/figures/experiment_readiness.svg` | generated |
| Return comparison | `reports/phase8-softwarex/figures/benchmark_return.svg` | generated |
| Drawdown comparison | `reports/phase8-softwarex/figures/benchmark_drawdown.svg` | generated |
| Agent/HPO signals | `reports/phase8-softwarex/figures/agent_hpo_signal.svg` | partial engineering evidence |
| HPO implementation | `docs/tuning/phase4-acceptance.json` | complete engineering acceptance |
| Three-layer Agent fusion | `docs/agents/phase7-acceptance.json` | complete engineering acceptance |
| Phase 8 report provenance | `docs/reporting/phase8-acceptance.json` | complete |
| Phase 9 release provenance | `docs/release/phase9-acceptance.json` | generated at Phase 9 acceptance |
| Cross-stock zero-shot | dedicated locked runs required | planned |
| Leave-one-market-out | dedicated locked runs required | planned |
| Publication-scale ablations | multi-seed locked runs required | partial/planned |

Every generated figure must be regenerated from the declared configuration immediately before
submission. A report artifact is descriptive evidence and never authorizes HPO selection.
