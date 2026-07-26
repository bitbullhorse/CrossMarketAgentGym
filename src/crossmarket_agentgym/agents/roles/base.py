"""Role plugin contract used by every AgentRuntime topology."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from crossmarket_agentgym.agents.models import (
    AgentContext,
    AgentInstance,
    RoleInvocation,
)
from crossmarket_agentgym.agents.tools import ToolRegistry


@dataclass(frozen=True)
class RoleServices:
    """Administrator-owned capabilities injected into a role factory."""

    workspace_root: Path
    run_dir: Path
    prompt_version: str
    tool_registry: ToolRegistry


class RuntimeRole(Protocol):
    """One independently stateful expanded Agent instance."""

    def run(self, context: AgentContext) -> RoleInvocation:
        """Return one structured decision or an administrator fallback."""
        ...

    def close(self) -> None:
        """Release Provider resources without changing runtime semantics."""
        ...


AgentFactory = Callable[[AgentInstance, RoleServices], RuntimeRole]
