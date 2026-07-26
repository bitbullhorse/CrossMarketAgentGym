"""Policy extractor shape and stability tests."""

from __future__ import annotations

import numpy as np
import pytest
import torch

from crossmarket_agentgym.environments import (
    CrossMarketPortfolioEnv,
    EnvironmentConfig,
    MarketDataPanel,
)
from crossmarket_agentgym.rl.policies import extractor_kwargs
from tests.helpers import make_us_ohlcv


@pytest.mark.parametrize("name", ["mlp", "shared_mlp", "transformer"])
def test_policy_extractor_returns_finite_fixed_width_features(name: str) -> None:
    """All mandatory policy families accept the exact Phase 2 Dict observation."""
    env = CrossMarketPortfolioEnv(
        MarketDataPanel.from_frame(make_us_ohlcv(days=4)),
        EnvironmentConfig(
            lookback=2,
            max_asset_weight=1.0,
            max_market_weight=1.0,
        ),
    )
    observation, _ = env.reset()
    specification = extractor_kwargs(
        name,
        features_dim=16,
        transformer_model_dim=8,
        transformer_heads=2,
    )
    extractor_class = specification["features_extractor_class"]
    extractor = extractor_class(
        env.observation_space,
        **specification["features_extractor_kwargs"],
    )
    batch = {
        key: torch.as_tensor(np.expand_dims(value, axis=0))
        for key, value in observation.items()
    }

    output = extractor(batch)

    assert output.shape == (1, 16)
    assert torch.isfinite(output).all()


def test_transformer_rejects_incompatible_attention_width() -> None:
    """Invalid attention geometry fails at configuration construction."""
    env = CrossMarketPortfolioEnv(
        MarketDataPanel.from_frame(make_us_ohlcv(days=4)),
        EnvironmentConfig(lookback=2),
    )
    specification = extractor_kwargs(
        "transformer",
        features_dim=16,
        transformer_model_dim=10,
        transformer_heads=3,
    )
    with pytest.raises(ValueError, match="divisible"):
        specification["features_extractor_class"](
            env.observation_space,
            **specification["features_extractor_kwargs"],
        )
