# Phase 11 issue checklist — independent reproduction

Status: **release closing**. Tasks 1–8 are locally verified. The workspace owner reports multiple
independent participants completed testing with normal module operation and a completed P0/P1
zero-count audit. Linux CPU/Docker Task B–I evidence and the rc2 Release asset remain pre-tag
gates.

## Input conditions

- [x] `v1.0.0-rc1` exists; stable `v1.0.0` was not published directly from Phase 9.
- [x] Phase 10 reports and frozen rc1 contracts are present.
- [x] The source PPO run contains config, dataset manifest identity, checkpoint, validation
  artifacts, and a run manifest.
- [x] The workspace owner reported Phase 11.3 installation, environment, PPO, Agent, HPO, report,
  and artifact-hash checks as successful.
- [x] Phase 12 formal protocols/results and Benchmark freeze have not started.

## Tasks 1–4 — computational replay

- [x] Preserve the frozen `reproduce_run()` artifact-verification API.
- [x] Make default/`--verify-only` output identify `verification_mode=artifact_integrity`.
- [x] Report `computational_replay_executed=false` for artifact-only checks.
- [x] Require the explicit pair `--execute --compare` for retraining.
- [x] Read reviewed YAML first and support legacy `resolved_config.json`.
- [x] Revalidate the source run, dataset manifest, TrainerConfig hash, checkpoint, and partition.
- [x] Allocate a new replay directory and reject overwrite of a source or existing replay.
- [x] Recreate train/validation environments using the recorded split, seed, and TrainerConfig.
- [x] Never construct or access the test partition during replay.
- [x] Save replay config, source identity, training outputs, validation outputs, audit log,
  structured comparison, and run manifest.
- [x] Compare mean return, mean reward, maximum drawdown, mean turnover, total cost, trained
  timesteps, algorithm, dataset hash, TrainerConfig hash, execution protocol, and checkpoint
  loadability.
- [x] Implement `artifact_verified`, `bitwise_reproduced`, `numerically_reproduced`,
  `statistically_reproduced`, and `failed`.
- [x] Freeze absolute, relative, mandatory exact, and repeated-run thresholds in
  `configs/reproduction/phase11_cpu.yaml`.
- [x] Require at least numerical reproduction in the CPU comparison script.
- [x] Retain failed replay directories and structured failure evidence.

## Automation and tests

- [x] Add `scripts/repro_test_cpu.sh`.
- [x] Add `scripts/repro_test_docker.sh` with non-root, network-disabled runtime commands.
- [x] Add `scripts/compare_reproduced_run.py`.
- [x] Test artifact-only semantics and absence of a replay directory.
- [x] Integration-test actual PPO retraining, validation comparison, source immutability,
  checkpoint loadability, manifest verification, and test-partition absence.
- [x] Test replay-ID collision rejection.
- [x] Test strict tolerances and all computational reproduction-level branches.
- [x] Run targeted unit/integration tests, Ruff, and strict mypy.
- [x] Run the final full test, leakage, accounting, contract-freeze, and documentation gates.
- [x] Validate both Bash scripts with Git Bash syntax checking.
- [ ] Execute both Bash workflows on Linux.
- [ ] Execute the Docker protocol on a Docker host after final source synchronization.

## Tasks 5–8 — observation, evidence, and Agent audit semantics

- [x] Preserve raw `[N,L,F]` market data internally and implement `flat`/`tensor` observation
  layouts.
- [x] Make PPO/SAC SB3 quickstarts use `flat`; retain tensor policies with a required custom
  feature extractor.
- [x] Rerun the 64-step Gymnasium/SB3 smoke check with no image warnings and accounting error
  below `1e-8`.
- [x] Emit an accepted structured `SB3_BOX_IMAGE_HEURISTIC` explanation for tensor checks.
- [x] Record start/finish time, total/training/evaluation duration, device, language/framework,
  CPU, and GPU metadata.
- [x] Record evaluation episode/sample counts and explicit insufficient-sample warnings.
- [x] Audit the `cash_floor = max(agent_cash_floor, 1 - risk_budget)` derivation.
- [x] Separate configured conflict policy, conflict detection, aggregate outcome, selected and
  committee confidence.
- [x] Record dominant and stable secondary projection reasons.
- [x] Computationally replay the new flat-layout CPU PPO run at
  `numerically_reproduced`.

## Independent reproduction exit conditions

- [x] The workspace owner attests that multiple independent participants completed the protocol.
- [x] The workspace owner reports that all tested modules operated normally.
- [x] No participant identity or result detail absent from the workspace was fabricated.
- [ ] Same-seed results meet the reviewed tolerance.
- [x] The workspace owner completed the audit with P0 = 0 and P1 = 0.
- [ ] P2 items are fixed or explicitly accepted.
- [x] Documentation feedback is reported closed by the workspace owner.
- [ ] `v1.0.0-rc2` is released only after the prior gates pass.
- [x] Phase 12 remains blocked until Phase 11 is complete.
