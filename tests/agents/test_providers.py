from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from crossmarket_agentgym.agents.providers import (
    GenerationConfig,
    Message,
    MockProvider,
    MockTurn,
    OpenAICompatibleProvider,
    ProviderConfig,
    ProviderConfigurationError,
    ProviderError,
    ReplayJournal,
    ReplayProvider,
    StructuredOutputError,
    ToolCall,
)


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    action: str
    confidence: float = Field(ge=0.0, le=1.0)


def test_message_and_provider_configuration_are_strict_and_credential_free() -> None:
    with pytest.raises(ValidationError, match="tool messages require"):
        Message(role="tool", content="missing ID")
    with pytest.raises(ValidationError, match="deepseek-v4-pro"):
        ProviderConfig(model="other-model")

    serialized = ProviderConfig().model_dump_json()
    assert "deepseek-v4-pro" in serialized
    assert "DEEPSEEK_API_KEY" in serialized
    assert "Bearer " not in serialized


def test_mock_provider_validates_structured_output_and_script_errors() -> None:
    provider = MockProvider(
        [
            MockTurn(content={"action": "hold", "confidence": 0.8}),
            MockTurn(error_code="offline_failure", error_message="deliberate"),
        ]
    )
    response = provider.generate(
        [Message(role="user", content="decide api_key=do-not-transmit")],
        Decision,
        None,
        GenerationConfig(),
    )
    assert response.structured_data == {"action": "hold", "confidence": 0.8}
    assert response.metadata.model == "deepseek-v4-pro"

    with pytest.raises(ProviderError, match="deliberate") as captured:
        provider.generate(
            [Message(role="user", content="again")],
            Decision,
            None,
            GenerationConfig(),
        )
    assert captured.value.code == "offline_failure"


def test_mock_provider_rejects_invalid_json_and_schema() -> None:
    invalid_json = MockProvider([MockTurn(content="not json")])
    with pytest.raises(StructuredOutputError) as captured:
        invalid_json.generate(
            [Message(role="user", content="decide")],
            Decision,
            None,
            GenerationConfig(),
        )
    assert captured.value.code == "invalid_json"

    invalid_schema = MockProvider(
        [MockTurn(content={"action": "hold", "confidence": 5.0})]
    )
    with pytest.raises(StructuredOutputError) as captured:
        invalid_schema.generate(
            [Message(role="user", content="decide")],
            Decision,
            None,
            GenerationConfig(),
        )
    assert captured.value.code == "schema_validation_failed"


def test_replay_requires_an_exact_request_and_redacts_journal(
    tmp_path: Path,
) -> None:
    messages = [Message(role="user", content="api_key=journal-secret decide")]
    generation = GenerationConfig()
    mock = MockProvider([MockTurn(content={"action": "cash", "confidence": 1.0})])
    response = mock.generate(messages, Decision, None, generation)
    journal_path = tmp_path / "replay.jsonl"
    ReplayJournal(journal_path).append(response.metadata.request_sha256, response)
    assert "journal-secret" not in journal_path.read_text(encoding="utf-8")

    replay = ReplayProvider(journal_path)
    replayed = replay.generate(messages, Decision, None, generation)
    assert replayed.structured_data == response.structured_data
    assert replayed.metadata.replayed is True

    mismatch = ReplayProvider(journal_path)
    with pytest.raises(ProviderError) as captured:
        mismatch.generate(
            [Message(role="user", content="different")],
            Decision,
            None,
            generation,
        )
    assert captured.value.code == "replay_mismatch"


def test_openai_compatible_retries_invalid_structure_and_never_serializes_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PHASE5_TEST_KEY", "transport-secret")
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        content = (
            "not-json"
            if len(calls) == 1
            else json.dumps({"action": "hold", "confidence": 0.75})
        )
        return httpx.Response(
            200,
            headers={"x-request-id": "request-2"},
            json={
                "choices": [
                    {
                        "message": {"content": content},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 4,
                    "total_tokens": 14,
                },
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    config = ProviderConfig(
        api_key_env="PHASE5_TEST_KEY",
        default_base_url="https://provider.invalid",
    )
    provider = OpenAICompatibleProvider(config, client=client)
    response = provider.generate(
        [Message(role="user", content="decide")],
        Decision,
        None,
        GenerationConfig(max_retries=1, retry_backoff_seconds=0.0),
    )

    assert response.structured_data == {"action": "hold", "confidence": 0.75}
    assert response.metadata.attempts == 2
    assert response.usage.total_tokens == 14
    assert len(calls) == 2
    assert calls[0].headers["authorization"] == "Bearer transport-secret"
    sent_payload = json.loads(calls[0].content)
    assert "do-not-transmit" not in sent_payload["messages"][-1]["content"]
    assert "transport-secret" not in response.model_dump_json()
    provider.close()
    client.close()


def test_openai_compatible_parses_tool_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PHASE5_TEST_KEY", "tool-secret")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "type": "function",
                                    "function": {
                                        "name": "inspect_dataset",
                                        "arguments": '{"manifest_path":"data/sample/dataset_manifest.json"}',
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleProvider(
        ProviderConfig(
            api_key_env="PHASE5_TEST_KEY",
            default_base_url="https://provider.invalid",
        ),
        client=client,
    )
    response = provider.generate(
        [Message(role="user", content="inspect")],
        Decision,
        None,
        GenerationConfig(max_retries=0),
    )
    assert response.tool_calls == (
        ToolCall(
            id="call-1",
            name="inspect_dataset",
            arguments={"manifest_path": "data/sample/dataset_manifest.json"},
        ),
    )
    assert response.structured_data is None
    client.close()


def test_openai_compatible_requires_key_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PHASE5_MISSING_KEY", raising=False)
    with pytest.raises(ProviderConfigurationError) as captured:
        OpenAICompatibleProvider(
            ProviderConfig(api_key_env="PHASE5_MISSING_KEY")
        )
    assert captured.value.code == "missing_api_key"
    assert "PHASE5_MISSING_KEY" in str(captured.value)


def test_openai_compatible_rejects_credentials_in_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PHASE5_TEST_KEY", "safe-header-only")
    monkeypatch.setenv(
        "PHASE5_UNSAFE_URL",
        "https://provider.invalid/chat?api_key=query-secret",
    )
    with pytest.raises(ProviderConfigurationError) as captured:
        OpenAICompatibleProvider(
            ProviderConfig(
                api_key_env="PHASE5_TEST_KEY",
                base_url_env="PHASE5_UNSAFE_URL",
            )
        )
    assert captured.value.code == "unsafe_base_url"
    assert "query-secret" not in str(captured.value)
