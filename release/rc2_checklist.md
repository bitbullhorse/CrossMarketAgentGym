# v1.0.0-rc2 release checklist

This checklist is evidence-indexed. It must not be marked complete solely because a workflow file
or local test exists.

- [x] Multiple independent participants completed functional review.
- [x] The workspace owner completed the P0/P1 audit with P0 = 0 and P1 = 0.
- [x] Tasks 1–8 implementation and local computational replay pass.
- [x] Dockerfile/wheel contain configs, sample data, Mock, and Replay resources.
- [ ] `phase11-linux-cpu.yml` passes Tasks B–I from a clean wheel on `ubuntu-24.04`.
- [ ] The Linux CPU wheel has an `actions/attest@v4` provenance attestation.
- [ ] `phase11-docker.yml` passes Tasks B–I offline with 2 CPU, 7 GB, and CUDA disabled.
- [ ] Both unified `11_3_task_summary.json` files report `all_passed=true`.
- [ ] Both workflow artifacts and SHA-256 records are downloaded and commit-matched.
- [ ] A permanent deterministic Phase 11 Release evidence ZIP is attached to the rc2 Release.
- [ ] Package, tag, Citation, Zenodo, release notes, and evidence commit all agree.
- [ ] The exact annotated tag `v1.0.0-rc2` is pushed only after all prior gates pass.
- [ ] Phase 11 report records the two successful workflow run IDs and Release asset.
- [x] Phase 12 formal experiments have not started.
