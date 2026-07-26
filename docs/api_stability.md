# API stability

The reviewed inventory is `release/api_inventory.csv`. Every exported symbol is classified:

- `stable`: compatible for the 1.x line, subject to the deprecation policy.
- `provisional`: usable, but may change after notice in a release candidate.
- `experimental`: opt-in research or scaling surface with no 1.x compatibility promise.
- `internal`: not a supported integration point.

Only names listed as stable are covered by the compatibility promise. Importing from an
implementation module or relying on an unlisted file is internal use. The canonical public
entry points are the package namespaces documented in [API reference](api-reference.md) and
[stable API catalog](stable-api.md), the `cmag` CLI, and the JSON Schemas under `schemas/rc1/`.

Run `cmag release freeze --workspace-root .` to detect drift. Regeneration requires the explicit
`--write` flag and a reviewed API change.
