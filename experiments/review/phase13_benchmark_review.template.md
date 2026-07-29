# Phase 13 benchmark-v1 non-author review

This template is not an approval. A real reviewer who did not generate benchmark-v1 must fill
it after independently running `cmag benchmark verify --benchmark benchmarks/v1`.

- Reviewer:
- Affiliation or role:
- Review date:
- Benchmark `checksums.json` SHA-256:
- Protocol SHA-256:
- Dataset Manifest SHA-256:
- Formal code commit:

## Checks

- [ ] The benchmark contains exactly 215 frozen formal runs.
- [ ] All file hashes pass.
- [ ] Every run maps to the frozen protocol, dataset and formal code commit.
- [ ] HPO used train/walk-forward validation only before the single locked-test evaluation.
- [ ] Agent Replay and deterministic-risk audit evidence are complete.
- [ ] All nine tables exist in CSV, LaTeX, Markdown and HTML.
- [ ] All ten required figure/source-data pairs exist.
- [ ] Table and figure provenance contains no unknown Phase 12 run IDs.
- [ ] Failed experiments, if any, have structured explanations.
- [ ] Benchmark files are read-only and a new revision cannot overwrite `benchmarks/v1`.

## Findings

- P0 count:
- P1 count:
- P2/P3 notes:
- Decision: `approved` / `changes_required`
- Signature or equivalent attestation:
