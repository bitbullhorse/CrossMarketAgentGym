"""Provider construction from credential-free configuration."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from crossmarket_agentgym.agents.providers.base import LLMProvider
from crossmarket_agentgym.agents.providers.mock import MockProvider, MockTurn
from crossmarket_agentgym.agents.providers.models import ProviderConfig
from crossmarket_agentgym.agents.providers.replay import ReplayProvider

if TYPE_CHECKING:
    import httpx


def create_provider(
    config: ProviderConfig,
    *,
    mock_script: Iterable[MockTurn | dict[str, object]] | None = None,
    client: httpx.Client | None = None,
) -> LLMProvider:
    """Construct online, mock, or replay providers without implicit fallback."""
    if config.provider == "openai_compatible":
        from crossmarket_agentgym.agents.providers.openai_compatible import (
            OpenAICompatibleProvider,
        )

        return OpenAICompatibleProvider(config, client=client)
    if config.provider == "mock":
        if mock_script is None:
            raise ValueError("mock provider requires a script")
        return MockProvider(mock_script, model=config.model)
    assert config.replay_path is not None
    return ReplayProvider(config.replay_path, model=config.model)
