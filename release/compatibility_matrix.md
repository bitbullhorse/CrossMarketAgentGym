# v1.0.0 compatibility matrix

| Profile | Python | PyTorch | Gymnasium | SB3 | Optuna | Ray | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| Windows CPU development | 3.12.13 | 2.7.1+cpu | 1.1.1 | 2.6.0 | 4.4.0 | — | verified |
| Windows clean core wheel | 3.11.15 | — | 1.1.1 | — | — | — | verified |
| Windows clean stable wheel | 3.12.13 | 2.7.1+cpu | 1.1.1 | 2.6.0 | — | — | verified; 64-step packaged quickstart |
| Linux CPU CI | 3.11, 3.12 | 2.7.1 CPU | 1.1.1 | 2.6.0 | 4.4.0 | — | verified |
| Phase 11 Linux CPU Task B–I | 3.12 | 2.7.1 CPU | 1.1.1 | 2.6.0 | 4.4.0 | — | independently verified |
| Phase 11 Docker Task B–I | 3.11 | 2.7.1 CPU | 1.1.1 | 2.6.0 | 4.4.0 | — | independently verified; non-root, 2 CPU / 7 GB / offline |
| Stable Linux Docker | 3.11 | CPU image | 1.1.1 | 2.6.0 | — | — | hosted workflow prepared; public image pending |
| Linux GPU/Ray | 3.12 | 2.7.1 CUDA 12.6 | 1.1.1 | 2.6.0 | 4.4.0 | 2.47.1 | Phase 12 formal execution verified on remote GPUs |

`constraints-cpu.txt`, `constraints-gpu.txt`, and `uv.lock` are the machine-readable dependency
records. A status changes to public only after a clean external install or pull. CPU operation
must never resolve a CUDA-only dependency.
