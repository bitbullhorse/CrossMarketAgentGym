"""Dictionary feature extractors for cross-market observations."""

from __future__ import annotations

from math import prod
from typing import Any, cast

import torch
from gymnasium import spaces
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor
from torch import nn


def _stable_scale(values: torch.Tensor) -> torch.Tensor:
    """Compress raw prices and volumes without fitting future-aware statistics."""
    floating = values.float()
    return torch.sign(floating) * torch.log1p(torch.abs(floating))


class FlatDictionaryExtractor(BaseFeaturesExtractor):
    """CPU-friendly MLP over every flattened dictionary field."""

    def __init__(
        self,
        observation_space: spaces.Dict,
        features_dim: int = 64,
        hidden_dim: int = 64,
    ) -> None:
        """Create a compact deterministic MLP."""
        super().__init__(observation_space, features_dim)
        self._keys = tuple(observation_space.spaces)
        input_dim = sum(
            prod(observation_space.spaces[key].shape or ())
            for key in self._keys
        )
        self.network = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, features_dim),
            nn.ReLU(),
        )

    def forward(self, observations: dict[str, torch.Tensor]) -> torch.Tensor:
        """Flatten fields in stable key order and return finite features."""
        flattened = [
            _stable_scale(observations[key]).flatten(start_dim=1)
            for key in self._keys
        ]
        return cast(torch.Tensor, self.network(torch.cat(flattened, dim=1)))


class SharedAssetMLPExtractor(BaseFeaturesExtractor):
    """Apply one shared MLP to every asset before cross-asset pooling."""

    def __init__(
        self,
        observation_space: spaces.Dict,
        features_dim: int = 64,
        asset_hidden_dim: int = 32,
    ) -> None:
        """Create shared asset parameters and a portfolio head."""
        super().__init__(observation_space, features_dim)
        market_shape = observation_space["market_window"].shape
        if market_shape is None or len(market_shape) != 3:
            raise ValueError("market_window must have shape [N,L,F]")
        _, lookback, feature_count = market_shape
        self._extra_keys = tuple(
            key for key in observation_space.spaces if key != "market_window"
        )
        extra_dim = sum(
            prod(observation_space.spaces[key].shape or ())
            for key in self._extra_keys
        )
        self.asset_encoder = nn.Sequential(
            nn.Linear(lookback * feature_count, asset_hidden_dim),
            nn.ReLU(),
            nn.Linear(asset_hidden_dim, asset_hidden_dim),
            nn.ReLU(),
        )
        self.portfolio_head = nn.Sequential(
            nn.Linear(2 * asset_hidden_dim + extra_dim, features_dim),
            nn.ReLU(),
        )

    def forward(self, observations: dict[str, torch.Tensor]) -> torch.Tensor:
        """Pool shared per-asset encodings with the remaining state."""
        market = _stable_scale(observations["market_window"])
        encoded = self.asset_encoder(market.flatten(start_dim=2))
        pooled = torch.cat((encoded.mean(dim=1), encoded.amax(dim=1)), dim=1)
        extras = torch.cat(
            [
                _stable_scale(observations[key]).flatten(start_dim=1)
                for key in self._extra_keys
            ],
            dim=1,
        )
        return cast(
            torch.Tensor,
            self.portfolio_head(torch.cat((pooled, extras), dim=1)),
        )


class MarketTransformerExtractor(BaseFeaturesExtractor):
    """Transformer encoder across asset-time tokens plus portfolio state."""

    def __init__(
        self,
        observation_space: spaces.Dict,
        features_dim: int = 64,
        model_dim: int = 32,
        attention_heads: int = 4,
        layers: int = 1,
    ) -> None:
        """Create a small batch-first encoder suitable for CPU quickstarts."""
        super().__init__(observation_space, features_dim)
        market_shape = observation_space["market_window"].shape
        if market_shape is None or len(market_shape) != 3:
            raise ValueError("market_window must have shape [N,L,F]")
        assets, lookback, feature_count = market_shape
        if model_dim % attention_heads != 0:
            raise ValueError("model_dim must be divisible by attention_heads")
        self._extra_keys = tuple(
            key for key in observation_space.spaces if key != "market_window"
        )
        extra_dim = sum(
            prod(observation_space.spaces[key].shape or ())
            for key in self._extra_keys
        )
        self.input_projection = nn.Linear(feature_count, model_dim)
        self.position = nn.Parameter(torch.zeros(1, assets * lookback, model_dim))
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=model_dim,
            nhead=attention_heads,
            dim_feedforward=2 * model_dim,
            dropout=0.0,
            batch_first=True,
            activation="gelu",
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=layers)
        self.output = nn.Sequential(
            nn.Linear(model_dim + extra_dim, features_dim),
            nn.ReLU(),
        )

    def forward(self, observations: dict[str, torch.Tensor]) -> torch.Tensor:
        """Encode market tokens and concatenate non-market observations."""
        market = _stable_scale(observations["market_window"])
        batch = market.shape[0]
        tokens = market.reshape(batch, -1, market.shape[-1])
        encoded = self.encoder(self.input_projection(tokens) + self.position)
        pooled = encoded.mean(dim=1)
        extras = torch.cat(
            [
                _stable_scale(observations[key]).flatten(start_dim=1)
                for key in self._extra_keys
            ],
            dim=1,
        )
        return cast(torch.Tensor, self.output(torch.cat((pooled, extras), dim=1)))


ExtractorType = type[BaseFeaturesExtractor]


def extractor_kwargs(
    name: str,
    *,
    features_dim: int,
    transformer_model_dim: int = 32,
    transformer_heads: int = 4,
    transformer_layers: int = 1,
) -> dict[str, Any]:
    """Return SB3 policy kwargs for an approved extractor name."""
    if name == "mlp":
        extractor: ExtractorType = FlatDictionaryExtractor
        kwargs = {"features_dim": features_dim}
    elif name == "shared_mlp":
        extractor = SharedAssetMLPExtractor
        kwargs = {"features_dim": features_dim}
    elif name == "transformer":
        extractor = MarketTransformerExtractor
        kwargs = {
            "features_dim": features_dim,
            "model_dim": transformer_model_dim,
            "attention_heads": transformer_heads,
            "layers": transformer_layers,
        }
    else:
        raise ValueError(f"unsupported policy extractor: {name}")
    return {
        "features_extractor_class": extractor,
        "features_extractor_kwargs": kwargs,
    }
