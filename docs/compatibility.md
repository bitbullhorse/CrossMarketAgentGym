# Compatibility matrix

The stable release supports Python 3.11 and 3.12. The core package is platform-independent;
PyTorch, Stable-Baselines3, Ray, and service dependencies are optional extras.

| Profile | Python | Accelerator | Status |
|---|---:|---|---|
| Windows CPU development | 3.12 | CPU | Verified |
| Clean wheel | 3.11, 3.12 | CPU | Verified |
| Linux CPU CI | 3.11, 3.12 | CPU | Verified |
| Linux Docker | 3.11 | CPU, non-root | Verified |
| Linux GPU/Ray | 3.12 | CUDA 12.6 | Declared; host-specific verification required |

Exact dependency pins are recorded in `constraints-cpu.txt`, `constraints-gpu.txt`, and
`uv.lock`. CPU operation must not resolve a CUDA-only dependency.
