"""Agent-provider policy tests established before provider implementation."""

from crossmarket_agentgym.config.models import REQUIRED_AGENT_MODEL, LLMConfig


def test_default_agent_model_is_deepseek_v4_pro() -> None:
    """The only permitted model is visible from a typed project constant."""
    assert LLMConfig().model == REQUIRED_AGENT_MODEL == "deepseek-v4-pro"
