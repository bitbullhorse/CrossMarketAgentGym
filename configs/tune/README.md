# Tuning configurations

Phase 4 keeps `searcher` and `scheduler` as separate top-level objects. Test-set metrics are not
exposed to objective evaluators.

Run the CPU acceptance study with:

```powershell
cmag tune --config configs/tune/ppo_pso_cpu.yaml
```

The configuration runs PSO with four particles for two generations over an eight-timestep PPO
objective. It verifies contracts and resumption; it is not an investable model.

`searcher_scheduler_contract.yaml` is the minimal boundary example.
`ppo_pso_cpu.yaml` is the executable train/validation-only quickstart.

`ppo_pso_ray_gpu.yaml` is the optional four-GPU Ray placement example. Ray only evaluates
independent Trial suggestions; the configured PSO searcher and ASHA scheduler remain separate
local-authority components. Install `.[ray,rl]` in a shared CUDA environment before use.
