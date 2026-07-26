"""Strict environment and accounting configuration."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from crossmarket_agentgym.data.schemas import Market

RewardName = Literal[
    "log_return",
    "return_minus_cost",
    "risk_adjusted",
    "differential_sharpe",
    "drawdown_penalty",
    "cvar_penalty",
]


class EnvironmentConfig(BaseModel):
    """Immutable hard constraints and daily execution settings."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    execution_protocol: Literal["close_signal_next_open"] = "close_signal_next_open"
    base_currency: str = "USD"
    lookback: int = Field(default=20, ge=1)
    initial_cash: float = Field(default=1_000_000.0, gt=0.0)
    allow_short: bool = False
    max_leverage: float = Field(default=1.0, ge=1.0, le=3.0)
    max_asset_weight: float = Field(default=0.10, gt=0.0, le=1.0)
    max_market_weight: float = Field(default=0.40, gt=0.0, le=3.0)
    market_weight_overrides: dict[Market, float] = Field(default_factory=dict)
    cash_floor: float = Field(default=0.05, ge=0.0, le=1.0)
    max_turnover: float = Field(default=1.0, ge=0.0, le=2.0)
    transaction_cost_bps: float = Field(default=10.0, ge=0.0, le=1000.0)
    slippage_bps: float = Field(default=5.0, ge=0.0, le=1000.0)
    reward: RewardName = "risk_adjusted"
    risk_aversion: float = Field(default=0.10, ge=0.0)
    drawdown_penalty: float = Field(default=0.50, ge=0.0)
    cvar_alpha: float = Field(default=0.05, gt=0.0, le=0.50)
    cvar_penalty: float = Field(default=0.50, ge=0.0)
    lot_sizes: dict[str, int] = Field(default_factory=dict)
    t_plus_one_markets: frozenset[Market] = frozenset({"CN"})
    max_episode_steps: int | None = Field(default=None, ge=1)
    accounting_tolerance: float = Field(default=1e-8, gt=0.0, le=1e-3)

    @field_validator("base_currency")
    @classmethod
    def normalize_base_currency(cls, value: str) -> str:
        """Normalize the portfolio currency without accepting blank codes."""
        normalized = value.strip().upper()
        if len(normalized) != 3:
            raise ValueError("base_currency must be a three-letter code")
        return normalized

    @field_validator("market_weight_overrides")
    @classmethod
    def validate_market_caps(cls, value: dict[Market, float]) -> dict[Market, float]:
        """Require every market override to be positive."""
        if any(cap <= 0.0 for cap in value.values()):
            raise ValueError("market weight overrides must be positive")
        return value

    @field_validator("lot_sizes")
    @classmethod
    def validate_lot_sizes(cls, value: dict[str, int]) -> dict[str, int]:
        """Lot sizes are explicit positive integers and never inferred."""
        if any(size < 1 for size in value.values()):
            raise ValueError("lot sizes must be positive integers")
        return value

    @model_validator(mode="after")
    def validate_related_limits(self) -> EnvironmentConfig:
        """Reject internally inconsistent hard limits."""
        if self.max_asset_weight > self.max_leverage:
            raise ValueError("max_asset_weight cannot exceed max_leverage")
        if self.max_market_weight > self.max_leverage:
            raise ValueError("max_market_weight cannot exceed max_leverage")
        if any(cap > self.max_leverage for cap in self.market_weight_overrides.values()):
            raise ValueError("market cap cannot exceed max_leverage")
        if not self.allow_short and self.max_leverage > 1.0:
            raise ValueError("long-only max_leverage cannot exceed 1.0")
        return self
