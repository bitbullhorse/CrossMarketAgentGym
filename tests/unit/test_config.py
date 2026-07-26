"""Configuration-boundary tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from crossmarket_agentgym.config import LLMConfig, ProjectConfig, load_config


def test_phase0_example_loads() -> None:
    """The checked-in example is strict and credential-free."""
    config = load_config(Path("configs/examples/phase0.yaml"))

    assert config.project.seed == 1024
    assert config.llm.model == "deepseek-v4-pro"
    assert config.llm.api_key_env == "DEEPSEEK_API_KEY"


def test_configuration_is_immutable() -> None:
    """Resolved configuration cannot drift during a run."""
    config = ProjectConfig()

    with pytest.raises(ValidationError):
        config.seed = 7


def test_unknown_keys_are_rejected() -> None:
    """Typos and unsupported options fail loudly."""
    with pytest.raises(ValidationError):
        ProjectConfig.model_validate({"unexpected": True})


def test_model_policy_rejects_other_models() -> None:
    """Every future Agent must inherit the required project model."""
    with pytest.raises(ValidationError, match="deepseek-v4-pro"):
        LLMConfig(model="another-model")


def test_environment_names_cannot_contain_secret_values() -> None:
    """Credential fields contain names, not values."""
    with pytest.raises(ValidationError, match="environment-variable name"):
        LLMConfig(api_key_env="not-a-valid-name")


def test_non_mapping_yaml_is_rejected(tmp_path: Path) -> None:
    """A YAML sequence cannot masquerade as a root configuration."""
    path = tmp_path / "invalid.yaml"
    path.write_text("- item\n", encoding="utf-8")

    with pytest.raises(TypeError, match="mapping"):
        load_config(path)
