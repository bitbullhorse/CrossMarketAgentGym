# v1.0.0-rc2 compatibility matrix

| Profile | Python | PyTorch | Gymnasium | SB3 | Optuna | Ray | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| Windows CPU development | 3.12.13 | 2.7.1+cpu | 1.1.1 | 2.6.0 | 4.4.0 | — | verified |
| Windows clean core wheel | 3.11.15 | — | 1.1.1 | — | — | — | verified; NumPy 2.3.5 and Pydantic 2.13.4 |
| Windows clean core wheel | 3.12.13 | — | 1.1.1 | — | — | — | verified; NumPy 2.3.5 and Pydantic 2.13.4 |
| Linux CPU CI | 3.11.15 | 2.7.1 CPU | 1.1.1 | 2.6.0 | 4.4.0 | — | verified in `ci #4` |
| Linux CPU CI | 3.12.13 | 2.7.1 CPU | 1.1.1 | 2.6.0 | 4.4.0 | — | verified in `ci #4` |
| Linux Docker CPU | 3.12 | CPU-only image | 1.1.1 | — | — | — | verified non-root quickstart in `ci #4` |
| Phase 11 Linux CPU Task B–I | 3.12 | 2.7.1 CPU | 1.1.1 | 2.6.0 | 4.4.0 | — | pending `phase11-linux-cpu.yml` |
| Phase 11 Docker Task B–I | 3.11 | 2.7.1 CPU | 1.1.1 | 2.6.0 | 4.4.0 | — | pending `phase11-docker.yml`; 2 CPU / 7 GB / offline |
| Linux GPU/Ray | 3.12 | 2.7.1 CUDA 12.6 | 1.1.1 | 2.6.0 | 4.4.0 | 2.47.1 | declared; hardware verification pending |

`constraints-cpu.txt`, `constraints-gpu.txt`, and `uv.lock` are the machine-readable dependency
records. A status is changed to verified only by a recorded test run. CPU operation must never
resolve a CUDA-only dependency.
