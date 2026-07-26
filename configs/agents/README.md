# Agent configurations

Every agent uses the OpenAI-compatible DeepSeek provider contract and model `deepseek-v4-pro`.
Credentials are referenced by environment-variable name only.

Phase 5 provider acceptance:

```powershell
cmag agent provider-check --config configs/agents/provider_offline.yaml
cmag agent provider-check --config configs/agents/provider_invalid_fallback.yaml
```

The first command runs Mock → `inspect_dataset` → structured JSON and verifies exact Replay
without network access. The second deliberately returns invalid JSON and demonstrates the static
safe fallback. Neither configuration contains a credential value.

After setting `DEEPSEEK_API_KEY` in the process environment, the same contract can be exercised
against the configured OpenAI-compatible endpoint:

```powershell
cmag agent provider-check --config configs/agents/provider_online_deepseek.yaml
```

Do not paste the key into YAML or command arguments.

Phase 6 runtime acceptance:

```powershell
cmag agent run --config configs/agents/runtime_single_offline.yaml
cmag agent run --config configs/agents/runtime_team_offline.yaml
```

The first command exercises one Agent through the same runtime used by teams. The second expands a
parallel 1+3+2 committee and deliberately fails one Provider so the static risk fallback and
most-conservative structured arbitration can be audited. `runtime_deepseek_team.yaml` is the
credential-free online equivalent. `full_stack.yaml` remains the Phase 7 directive-fusion draft.
