"""Explicit market-window layouts without changing financial data semantics."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

MarketWindowLayout = Literal["flat", "tensor"]


class ObservationConfig(BaseModel):
    """Presentation layout for the raw ``[N,L,F]`` financial tensor."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    market_window_layout: MarketWindowLayout = "tensor"
