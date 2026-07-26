# Phase 10 rc1 release blockers

Status: **OPEN**. The local implementation is not a completed Phase 10 release.

| ID | Severity | Blocker | Required evidence |
|---|---|---|---|
| B10-001 | P1 | Docker is unavailable on the current Windows host. | Linux CI builds `Dockerfile` and runs `cmag quickstart --smoke-steps 16` as user `cmag`. |
| B10-002 | P1 | This local repository has no configured remote, so the required Python 3.11/3.12 Linux CI matrix has not run. | Reachable immutable commit plus passing `ci.yml` CPU jobs for both Python versions. |

GPU/Ray hardware validation is tracked as a declared but unverified optional profile in
`compatibility_matrix.md`; it does not replace any CPU/Docker gate. No security, accounting,
information-leakage, credential, Mock/Replay, or HPO-resume blocker is open in the local results.

Closed locally:

- B10-003: Python 3.11.15 clean-wheel install, CLI help, packaged quickstart, and `pip check`
  passed.
