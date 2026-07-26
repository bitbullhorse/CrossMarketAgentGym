"""Online, deterministic mock, and strict replay LLM providers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from crossmarket_agentgym.agents.providers.base import LLMProvider, request_fingerprint
from crossmarket_agentgym.agents.providers.factory import create_provider
from crossmarket_agentgym.agents.providers.mock import MockProvider, MockTurn
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
    ToolCall,
)
from crossmarket_agentgym.agents.providers.replay import (
    ReplayJournal,
    ReplayProvider,
    ReplayRecord,
)

if TYPE_CHECKING:
    from crossmarket_agentgym.agents.providers.openai_compatible import (
        OpenAICompatibleProvider,
    )

__all__ = [
    "GenerationConfig",
    "LLMProvider",
    "LLMResponse",
    "Message",
    "MockProvider",
    "MockTurn",
    "OpenAICompatibleProvider",
    "ProviderConfig",
    "ProviderConfigurationError",
    "ProviderError",
    "ProviderMetadata",
    "ReplayJournal",
    "ReplayProvider",
    "ReplayRecord",
    "StructuredOutputError",
    "TokenUsage",
    "ToolCall",
    "create_provider",
    "request_fingerprint",
]


def __getattr__(name: str) -> Any:
    """Load the online transport only when the optional class is requested."""
    if name == "OpenAICompatibleProvider":
        from crossmarket_agentgym.agents.providers.openai_compatible import (
            OpenAICompatibleProvider,
        )

        return OpenAICompatibleProvider
    raise AttributeError(name)
