from __future__ import annotations

from typing import Any

import pytest

from crossmarket_agentgym.agents.roles import AgentRegistry
from crossmarket_agentgym.agents.roles.registry import ENTRY_POINT_GROUP


def _factory(*args: Any) -> Any:
    del args
    return object()


def test_python_role_registration_is_explicit_and_unique() -> None:
    registry = AgentRegistry(include_builtins=False)
    registry.register("custom_factor_reviewer", _factory)
    assert registry.registered_types() == ("custom_factor_reviewer",)
    with pytest.raises(ValueError, match="already registered"):
        registry.register("custom_factor_reviewer", _factory)


def test_installed_entry_point_factory_is_loaded(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeEntryPoint:
        name = "plugin_role"

        @staticmethod
        def load() -> Any:
            return _factory

    class FakeEntryPoints:
        @staticmethod
        def select(*, group: str) -> list[FakeEntryPoint]:
            assert group == ENTRY_POINT_GROUP
            return [FakeEntryPoint()]

    monkeypatch.setattr(
        "crossmarket_agentgym.agents.roles.registry.metadata.entry_points",
        lambda: FakeEntryPoints(),
    )
    registry = AgentRegistry(include_builtins=False)
    assert registry.load_entry_points() == ("plugin_role",)
    assert registry.registered_types() == ("plugin_role",)
