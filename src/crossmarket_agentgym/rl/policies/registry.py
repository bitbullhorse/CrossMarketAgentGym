"""Policy names and the optional IR-MoE adapter boundary."""

from __future__ import annotations

from typing import Any, Literal, Protocol, runtime_checkable

from crossmarket_agentgym.rl.policies.extractors import extractor_kwargs

PolicyName = Literal["mlp", "shared_mlp", "transformer"]


@runtime_checkable
class IRMoEPolicyAdapter(Protocol):
    """Optional adapter contract; IR-MoE is never the only policy path."""

    name: str

    def policy_kwargs(self) -> dict[str, Any]:
        """Return Stable-Baselines3 policy keyword arguments."""
        ...


def build_policy_kwargs(
    policy: PolicyName,
    *,
    features_dim: int,
    net_arch: list[int],
    transformer_model_dim: int,
    transformer_heads: int,
    transformer_layers: int,
) -> dict[str, Any]:
    """Build shared policy kwargs for on- and off-policy algorithms."""
    result = extractor_kwargs(
        policy,
        features_dim=features_dim,
        transformer_model_dim=transformer_model_dim,
        transformer_heads=transformer_heads,
        transformer_layers=transformer_layers,
    )
    result["net_arch"] = net_arch
    return result
