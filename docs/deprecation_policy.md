# Deprecation policy

A stable public API is not removed or incompatibly changed without:

1. a documented replacement;
2. a runtime `DeprecationWarning`;
3. a changelog entry;
4. at least one compatible minor-release cycle before removal; and
5. removal only in a new major version unless a security correction requires faster action.

Provisional and experimental APIs may change sooner, but the release notes must identify the
change. Persisted data is never silently reinterpreted: readers validate `schema_version`, and an
incompatible change requires an explicit migration or a new versioned format.
