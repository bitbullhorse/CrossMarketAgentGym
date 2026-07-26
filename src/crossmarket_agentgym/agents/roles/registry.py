"""Explicit Python and entry-point registry for custom Agent roles."""

from __future__ import annotations

import re
from importlib import metadata

from crossmarket_agentgym.agents.models import AgentInstance
from crossmarket_agentgym.agents.roles.base import (
    AgentFactory,
    RoleServices,
    RuntimeRole,
)
from crossmarket_agentgym.agents.roles.builtin import (
    BUILTIN_ROLE_TYPES,
    provider_role_factory,
)

ENTRY_POINT_GROUP = "crossmarket_agentgym.agents"
_ROLE_TYPE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*$")


class AgentRegistry:
    """Resolve role factories without importing code named by model output."""

    def __init__(self, *, include_builtins: bool = True) -> None:
        self._factories: dict[str, AgentFactory] = {}
        if include_builtins:
            for role_type in BUILTIN_ROLE_TYPES:
                self.register(role_type, provider_role_factory)

    def register(
        self,
        role_type: str,
        factory: AgentFactory,
        *,
        replace: bool = False,
    ) -> None:
        """Register an administrator-selected callable under a stable type."""
        if _ROLE_TYPE.fullmatch(role_type) is None:
            raise ValueError("role_type must be a portable Agent identifier")
        if role_type in self._factories and not replace:
            raise ValueError(f"Agent role already registered: {role_type}")
        self._factories[role_type] = factory

    def create(
        self,
        instance: AgentInstance,
        services: RoleServices,
    ) -> RuntimeRole:
        """Construct one expanded independent role instance."""
        try:
            factory = self._factories[instance.spec.type]
        except KeyError as error:
            raise KeyError(f"unknown Agent role: {instance.spec.type}") from error
        return factory(instance, services)

    def load_entry_points(self) -> tuple[str, ...]:
        """Load explicitly installed role factories from the project entry-point group."""
        loaded: list[str] = []
        discovered = metadata.entry_points()
        selected = discovered.select(group=ENTRY_POINT_GROUP)
        for entry_point in sorted(selected, key=lambda item: item.name):
            factory = entry_point.load()
            if not callable(factory):
                raise TypeError(f"Agent entry point is not callable: {entry_point.name}")
            self.register(entry_point.name, factory)
            loaded.append(entry_point.name)
        return tuple(loaded)

    def registered_types(self) -> tuple[str, ...]:
        """Return a deterministic registry snapshot for audit and tests."""
        return tuple(sorted(self._factories))
