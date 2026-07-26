# Architecture overview

The stable dependency direction is:

```text
CLI / Python API
        |
AgentRuntime ---- Research / Risk / Hierarchical roles
        |                         |
        |                  structured directives only
        v                         v
HPO runner                deterministic guardrails
 searcher + scheduler             |
        |                         v
RL trainer ---------------- portfolio environment
                                  |
                         execution + accounting
                                  |
                       canonical market data
```

Search algorithms propose candidates; resource schedulers allocate budgets or stop trials. Neither
is allowed to read the test partition. LLM roles can request permissioned tools and emit validated
directives, but only deterministic environment code can change account state.
