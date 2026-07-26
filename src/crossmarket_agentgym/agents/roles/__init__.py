"""Built-in and user-registered Agent roles."""

from crossmarket_agentgym.agents.roles.base import (
    AgentFactory,
    RoleServices,
    RuntimeRole,
)
from crossmarket_agentgym.agents.roles.builtin import (
    BUILTIN_ROLE_TYPES,
    HierarchicalStrategyAgent,
    ProviderRoleAgent,
    ResearchOrchestrationAgent,
    RiskManagementAgent,
)
from crossmarket_agentgym.agents.roles.registry import (
    ENTRY_POINT_GROUP,
    AgentRegistry,
)

__all__ = [
    "BUILTIN_ROLE_TYPES",
    "ENTRY_POINT_GROUP",
    "AgentFactory",
    "AgentRegistry",
    "HierarchicalStrategyAgent",
    "ProviderRoleAgent",
    "ResearchOrchestrationAgent",
    "RiskManagementAgent",
    "RoleServices",
    "RuntimeRole",
]
