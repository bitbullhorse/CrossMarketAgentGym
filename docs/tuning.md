# Hyperparameter optimization

The built-in search algorithms are Random Search, Grid Search, TPE, CMA-ES, NSGA-II, Particle
Swarm Optimization, Genetic Algorithm, Differential Evolution, and Simulated Annealing.

ASHA, HyperBand, and Population Based Training are independent resource schedulers. A scheduler
may stop, promote, or perturb trials; it does not suggest the initial search point. The local and
Ray executors are a third independent layer.

CPU example:

```bash
cmag tune --config configs/tune/ppo_pso_quickstart.yaml
```

The SQLite study has its own version, resumes completed/pending trial state, and rejects a future
unsupported database version. The objective uses train/validation only. Locked parameters are
retrained independently before any one-time test evaluation. A test metric must never be exposed
to a searcher, scheduler, early-stop callback, or selection report.

See [tuning contract](tuning-contract.md) for search-space constraints, budgets, multi-objective
selection, resume semantics, and Ray boundaries.
