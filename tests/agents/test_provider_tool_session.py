from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from crossmarket_agentgym.agents.providers import (
    GenerationConfig,
    Message,
    MockProvider,
    MockTurn,
    ReplayJournal,
    ReplayProvider,
    ToolCall,
)
from crossmarket_agentgym.agents.session import ProviderToolSession
from crossmarket_agentgym.agents.tools import (
    ToolExecutor,
    ToolPolicy,
    build_builtin_tool_registry,
)
from crossmarket_agentgym.audit.agent import AgentAuditWriter


class OfflineSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str
    markets: tuple[str, ...]
    safe_to_continue: bool


def _executor() -> ToolExecutor:
    return ToolExecutor(
        build_builtin_tool_registry(Path.cwd()),
        ToolPolicy(
            allowed_permissions=frozenset({"read"}),
            allowed_tools=frozenset({"inspect_dataset"}),
            max_total_calls=2,
        ),
        Path.cwd(),
    )


def _audit(tmp_path: Path, name: str) -> AgentAuditWriter:
    return AgentAuditWriter(
        tmp_path / name,
        provider_config={
            "provider": "mock",
            "model": "deepseek-v4-pro",
            "api_key_env": "DEEPSEEK_API_KEY",
        },
        prompt_version="phase5.v1",
    )


def test_offline_tool_loop_audit_and_replay(tmp_path: Path) -> None:
    initial = [
        Message(
            role="user",
            content="Inspect the sample. api_key=message-secret",
        )
    ]
    script = [
        MockTurn(
            tool_calls=(
                ToolCall(
                    id="inspect-1",
                    name="inspect_dataset",
                    arguments={
                        "manifest_path": "data/sample/dataset_manifest.json"
                    },
                ),
            )
        ),
        MockTurn(
            content={
                "status": "validated",
                "markets": ["CN", "HK", "JP", "US"],
                "safe_to_continue": True,
            }
        ),
    ]
    journal_path = tmp_path / "offline-replay.jsonl"
    first = ProviderToolSession(
        provider=MockProvider(script),
        tool_executor=_executor(),
        audit=_audit(tmp_path, "mock-run"),
        replay_journal=ReplayJournal(journal_path),
    ).run(
        initial,
        response_schema=OfflineSummary,
        fallback=OfflineSummary(
            status="fallback",
            markets=(),
            safe_to_continue=False,
        ),
        generation_config=GenerationConfig(),
        tool_names=["inspect_dataset"],
    )
    assert first.used_fallback is False
    assert first.rounds == 2
    assert first.value.markets == ("CN", "HK", "JP", "US")

    replayed = ProviderToolSession(
        provider=ReplayProvider(journal_path),
        tool_executor=_executor(),
        audit=_audit(tmp_path, "replay-run"),
    ).run(
        initial,
        response_schema=OfflineSummary,
        fallback=OfflineSummary(
            status="fallback",
            markets=(),
            safe_to_continue=False,
        ),
        generation_config=GenerationConfig(),
        tool_names=["inspect_dataset"],
    )
    assert replayed.used_fallback is False
    assert replayed.value == first.value

    for run_name in ("mock-run", "replay-run"):
        agent_dir = tmp_path / run_name / "agent"
        assert (agent_dir / "messages.jsonl").exists()
        assert (agent_dir / "tool_calls.jsonl").exists()
        assert (agent_dir / "provider_metadata.json").exists()
        combined = "".join(
            path.read_text(encoding="utf-8")
            for path in agent_dir.iterdir()
            if path.is_file()
        )
        assert "message-secret" not in combined
        assert "DEEPSEEK_API_KEY" in combined


def test_invalid_output_uses_static_safe_fallback_and_is_audited(
    tmp_path: Path,
) -> None:
    fallback = OfflineSummary(
        status="safe_default",
        markets=(),
        safe_to_continue=False,
    )
    outcome = ProviderToolSession(
        provider=MockProvider([MockTurn(content="not-json")]),
        tool_executor=_executor(),
        audit=_audit(tmp_path, "fallback-run"),
    ).run(
        [Message(role="user", content="inspect")],
        response_schema=OfflineSummary,
        fallback=fallback,
        generation_config=GenerationConfig(max_retries=0),
        tool_names=["inspect_dataset"],
    )
    assert outcome.used_fallback is True
    assert outcome.value == fallback
    assert outcome.error_code == "invalid_json"
    fallback_log = (
        tmp_path / "fallback-run" / "agent" / "fallbacks.jsonl"
    ).read_text(encoding="utf-8")
    assert "invalid_json" in fallback_log
