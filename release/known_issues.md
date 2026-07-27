# Known issues for v1.0.0-rc2

- Tensor-layout financial observations require a configured custom feature extractor. Packaged
  PPO/SAC quickstarts use `flat`, so SB3 emits no image-dtype/range/resolution warning.
- GPU and Ray execution are optional. The declared CUDA 12.6 environment must be validated on a
  compatible NVIDIA driver before it is recorded as verified.
- Online DeepSeek requests require a user-provided `DEEPSEEK_API_KEY`. Offline quickstarts and all
  release gates use Mock or Replay providers and require no credential.

Security, accounting, information leakage, installation, or deterministic replay defects are not
accepted known issues; they are release blockers. `release_blockers.md` records the Phase 10 and
Phase 11 P0/P1 clearance.
