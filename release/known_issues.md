# Known issues for v1.0.0-rc1

- Stable-Baselines3 may warn that the structured `market_window` observation resembles an image.
  The shipped MLP and custom feature extractors consume the dictionary observation correctly;
  the warning does not change accounting or action projection.
- GPU and Ray execution are optional. The declared CUDA 12.6 environment must be validated on a
  compatible NVIDIA driver before it is recorded as verified.
- Online DeepSeek requests require a user-provided `DEEPSEEK_API_KEY`. Offline quickstarts and all
  release gates use Mock or Replay providers and require no credential.

Security, accounting, information leakage, installation, or deterministic replay defects are not
accepted known issues; they are release blockers. `release_blockers.md` records that no Phase 10
P0/P1 blocker remains open.
