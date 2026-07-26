"""OpenAI-compatible HTTP provider for the configured DeepSeek model."""

from __future__ import annotations

import json
import os
import time
from time import perf_counter
from typing import Any

import httpx
from pydantic import BaseModel

from crossmarket_agentgym.agents.providers.base import request_fingerprint
from crossmarket_agentgym.agents.providers.models import (
    GenerationConfig,
    LLMResponse,
    Message,
    ProviderConfig,
    ProviderConfigurationError,
    ProviderError,
    ProviderMetadata,
    StructuredOutputError,
    TokenUsage,
)
from crossmarket_agentgym.agents.providers.parsing import (
    parse_structured_content,
    parse_tool_calls,
)
from crossmarket_agentgym.agents.tools.models import ToolDefinition
from crossmarket_agentgym.audit.logging import redact_secrets


def _message_payload(message: Message) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "role": message.role,
        "content": redact_secrets(message.content),
    }
    if message.name is not None:
        payload["name"] = message.name
    if message.tool_call_id is not None:
        payload["tool_call_id"] = message.tool_call_id
    if message.tool_calls:
        payload["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.name,
                    "arguments": json.dumps(
                        call.arguments,
                        allow_nan=False,
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                },
            }
            for call in message.tool_calls
        ]
    return payload


def _tool_payload(tool: ToolDefinition) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.input_schema,
        },
    }


class OpenAICompatibleProvider:
    """Synchronous HTTP adapter with bounded retries and schema validation."""

    name = "openai_compatible"

    def __init__(
        self,
        config: ProviderConfig,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        if config.provider != "openai_compatible":
            raise ValueError("OpenAICompatibleProvider requires matching config")
        api_key = os.environ.get(config.api_key_env)
        if not api_key:
            raise ProviderConfigurationError(
                "missing_api_key",
                f"required environment variable {config.api_key_env} is not set",
            )
        base_url = os.environ.get(
            config.base_url_env,
            config.default_base_url,
        ).rstrip("/")
        if not base_url.startswith(("https://", "http://")):
            raise ProviderConfigurationError(
                "invalid_base_url",
                f"environment variable {config.base_url_env} is not an HTTP URL",
            )
        parsed_url = httpx.URL(base_url)
        if (
            parsed_url.username
            or parsed_url.password
            or parsed_url.query
            or parsed_url.fragment
        ):
            raise ProviderConfigurationError(
                "unsafe_base_url",
                "provider base URL cannot contain credentials, query, or fragment",
            )
        self.config = config
        self.base_url = base_url
        self._api_key = api_key
        self._client = client or httpx.Client()
        self._owns_client = client is None

    def _request_payload(
        self,
        messages: list[Message],
        response_schema: type[BaseModel] | None,
        tools: list[ToolDefinition] | None,
        generation_config: GenerationConfig,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": [_message_payload(message) for message in messages],
            "temperature": generation_config.temperature,
            "max_tokens": generation_config.max_tokens,
        }
        if generation_config.seed is not None:
            payload["seed"] = generation_config.seed
        if tools:
            payload["tools"] = [_tool_payload(tool) for tool in tools]
            payload["tool_choice"] = "auto"
        if response_schema is not None:
            if self.config.structured_output_mode == "json_schema":
                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": response_schema.__name__,
                        "strict": True,
                        "schema": response_schema.model_json_schema(),
                    },
                }
            else:
                payload["response_format"] = {"type": "json_object"}
                payload["messages"] = [
                    {
                        "role": "system",
                        "content": (
                            "Return only one JSON object matching this JSON Schema: "
                            + json.dumps(
                                response_schema.model_json_schema(),
                                ensure_ascii=False,
                                separators=(",", ":"),
                                sort_keys=True,
                            )
                        ),
                    },
                    *payload["messages"],
                ]
        return payload

    def generate(
        self,
        messages: list[Message],
        response_schema: type[BaseModel] | None,
        tools: list[ToolDefinition] | None,
        generation_config: GenerationConfig,
    ) -> LLMResponse:
        """POST one chat completion with bounded transport/schema retries."""
        request_hash = request_fingerprint(
            messages,
            response_schema,
            tools,
            generation_config,
        )
        payload = self._request_payload(
            messages,
            response_schema,
            tools,
            generation_config,
        )
        started = perf_counter()
        last_error: ProviderError | None = None
        for attempt in range(1, generation_config.max_retries + 2):
            try:
                response = self._client.post(
                    self.base_url + self.config.endpoint,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=generation_config.timeout_seconds,
                )
                if response.status_code >= 400:
                    code = (
                        "retryable_http_error"
                        if response.status_code == 429 or response.status_code >= 500
                        else "http_error"
                    )
                    last_error = ProviderError(
                        code,
                        f"provider returned HTTP {response.status_code}",
                    )
                    if code == "http_error":
                        break
                    raise last_error
                decoded = response.json()
                if not isinstance(decoded, dict):
                    raise ProviderError(
                        "invalid_response",
                        "provider response is not a JSON object",
                    )
                choices = decoded.get("choices")
                if not isinstance(choices, list) or not choices:
                    raise ProviderError(
                        "missing_choice",
                        "provider response contains no choices",
                    )
                choice = choices[0]
                if not isinstance(choice, dict) or not isinstance(
                    choice.get("message"),
                    dict,
                ):
                    raise ProviderError(
                        "invalid_choice",
                        "provider response choice is malformed",
                    )
                response_message = choice["message"]
                calls = parse_tool_calls(response_message.get("tool_calls"))
                content_value = response_message.get("content")
                content = "" if content_value is None else str(content_value)
                structured = (
                    None
                    if calls
                    else parse_structured_content(content, response_schema)
                )
                usage_raw = decoded.get("usage", {})
                usage = usage_raw if isinstance(usage_raw, dict) else {}
                return LLMResponse(
                    content=content,
                    structured_data=structured,
                    tool_calls=calls,
                    usage=TokenUsage(
                        prompt_tokens=int(usage.get("prompt_tokens", 0)),
                        completion_tokens=int(usage.get("completion_tokens", 0)),
                        total_tokens=int(usage.get("total_tokens", 0)),
                    ),
                    metadata=ProviderMetadata(
                        provider=self.name,
                        model=self.config.model,
                        base_url=self.base_url,
                        request_id=response.headers.get("x-request-id"),
                        finish_reason=(
                            None
                            if choice.get("finish_reason") is None
                            else str(choice["finish_reason"])
                        ),
                        attempts=attempt,
                        latency_seconds=perf_counter() - started,
                        request_sha256=request_hash,
                        structured=response_schema is not None,
                    ),
                )
            except StructuredOutputError as error:
                last_error = error
            except ProviderError as error:
                last_error = error
            except (httpx.TimeoutException, httpx.TransportError) as error:
                last_error = ProviderError(
                    "transport_error",
                    f"provider transport failed: {error.__class__.__name__}",
                )
            except (json.JSONDecodeError, ValueError) as error:
                last_error = ProviderError(
                    "invalid_response",
                    f"provider response parsing failed: {error.__class__.__name__}",
                )
            if attempt <= generation_config.max_retries:
                time.sleep(generation_config.retry_backoff_seconds * attempt)
        assert last_error is not None
        raise last_error

    def close(self) -> None:
        """Close only an internally owned HTTP client."""
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> OpenAICompatibleProvider:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
