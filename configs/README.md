# Configuration

Configuration is split by concern. Every resolved run will eventually store an immutable copy and
its SHA-256 digest. YAML is loaded with `yaml.safe_load` and validated with strict Pydantic models.

Phase 4 provides a runnable CPU study at `tune/ppo_pso_cpu.yaml`; searchers and resource
schedulers remain separate top-level configuration objects.

Phase 7 provides `agents/phase7_no_llm.yaml` for deterministic zero-Provider projection,
`agents/phase7_full_stack_offline.yaml` for the complete offline three-layer acceptance path, and
`agents/full_stack.yaml` for the online DeepSeek configuration. Online configuration stores
environment-variable names only.

Phase 8 provides `reporting/softwarex.yaml` for deterministic SoftwareX Markdown/HTML/table/figure
generation and `reporting/service.yaml` for the optional loopback-only read-only browser.
