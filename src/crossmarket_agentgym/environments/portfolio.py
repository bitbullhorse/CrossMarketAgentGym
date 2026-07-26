"""Gymnasium-compatible cross-market portfolio environment."""

from __future__ import annotations

import math
from typing import Any, Literal

import gymnasium as gym
import numpy as np
from gymnasium import spaces
from numpy.typing import NDArray

from crossmarket_agentgym.data.partitions import PartitionCapability
from crossmarket_agentgym.environments.accounting import AccountState
from crossmarket_agentgym.environments.config import EnvironmentConfig
from crossmarket_agentgym.environments.execution import ExecutionEngine
from crossmarket_agentgym.environments.panel import MarketDataPanel
from crossmarket_agentgym.environments.projection import ConstraintProjector
from crossmarket_agentgym.environments.rewards import RewardCalculator


class CrossMarketPortfolioEnv(gym.Env[dict[str, NDArray[Any]], NDArray[np.float32]]):
    """Daily portfolio environment using close signals and next-open execution."""

    metadata = {
        "render_modes": ["human", "ansi", "rgb_array"],
        "render_fps": 1,
    }

    def __init__(
        self,
        panel: MarketDataPanel,
        config: EnvironmentConfig,
        *,
        render_mode: Literal["human", "ansi", "rgb_array"] | None = None,
        partition: PartitionCapability | None = None,
    ) -> None:
        """Create an environment without accessing future panel rows."""
        super().__init__()
        if render_mode not in {None, *self.metadata["render_modes"]}:
            raise ValueError(f"unsupported render mode: {render_mode}")
        self.panel = panel
        self.config = config
        self.render_mode = render_mode
        minimum_start = max(
            config.lookback - 1,
            panel.first_fully_valued_index,
        )
        self.partition = partition or PartitionCapability(
            dataset_id="unlabeled_smoke",
            partition="smoke",
            start_signal_index=minimum_start,
            end_execution_index=panel.session_count - 1,
        )
        self._start_index = self.partition.start_signal_index
        self._end_index = self.partition.end_execution_index
        if self._start_index < minimum_start:
            raise ValueError("partition starts before leakage-safe lookback history")
        if self._end_index >= panel.session_count:
            raise ValueError("partition ends after available panel sessions")
        if self._start_index >= self._end_index:
            raise ValueError("panel needs a next session after the initial observation")
        self._projector = ConstraintProjector(config, panel.markets)
        self._engine = ExecutionEngine(
            config,
            symbols=panel.symbols,
            markets=panel.markets,
        )
        self._rewards = RewardCalculator(config)
        self._state = AccountState.initial(
            asset_count=panel.asset_count,
            cash=config.initial_cash,
        )
        self._index = self._start_index
        self._episode_steps = 0
        self._last_turnover = 0.0
        self._done = False

        asset_count = panel.asset_count
        feature_count = len(panel.feature_names)
        float_limit = np.finfo(np.float32).max
        self.action_space = spaces.Box(
            low=-1.0,
            high=1.0,
            shape=(asset_count + 1,),
            dtype=np.float32,
        )
        self.observation_space = spaces.Dict(
            {
                "market_window": spaces.Box(
                    low=-float_limit,
                    high=float_limit,
                    shape=(asset_count, config.lookback, feature_count),
                    dtype=np.float32,
                ),
                "portfolio_weights": spaces.Box(
                    low=-config.max_leverage,
                    high=1.0 + config.max_leverage,
                    shape=(asset_count + 1,),
                    dtype=np.float32,
                ),
                "cash_ratio": spaces.Box(
                    low=-config.max_leverage,
                    high=1.0 + config.max_leverage,
                    shape=(1,),
                    dtype=np.float32,
                ),
                "tradable_mask": spaces.MultiBinary(asset_count),
                "market_ids": spaces.Box(
                    low=0,
                    high=3,
                    shape=(asset_count,),
                    dtype=np.int32,
                ),
                "currency_ids": spaces.Box(
                    low=0,
                    high=max(3, int(panel.currency_ids.max(initial=0))),
                    shape=(asset_count,),
                    dtype=np.int32,
                ),
                "risk_state": spaces.Box(
                    low=-float_limit,
                    high=float_limit,
                    shape=(4,),
                    dtype=np.float32,
                ),
                "time_features": spaces.Box(
                    low=-1.0,
                    high=1.0,
                    shape=(4,),
                    dtype=np.float32,
                ),
            }
        )

    def _weights_at_close(self) -> NDArray[np.float64]:
        """Return account weights at the current close."""
        return self._state.weights(self.panel.close_prices[self._index])

    def _observation(self) -> dict[str, NDArray[Any]]:
        """Build an observation using rows no later than the current close."""
        weights = self._weights_at_close()
        recent_values = self._rewards._returns[-20:]  # noqa: SLF001 - same runtime boundary
        rolling_volatility = (
            float(np.std(recent_values, ddof=0)) if recent_values else 0.0
        )
        gross_exposure = float(np.abs(weights[1:]).sum())
        current_date = self.panel.dates[self._index]
        weekday_angle = 2.0 * math.pi * current_date.weekday() / 7.0
        month_angle = 2.0 * math.pi * (current_date.month - 1) / 12.0
        return {
            "market_window": self.panel.market_window(
                self._index, self.config.lookback
            ).astype(np.float32),
            "portfolio_weights": weights.astype(np.float32),
            "cash_ratio": np.asarray([weights[0]], dtype=np.float32),
            "tradable_mask": self.panel.tradable_mask[self._index].astype(np.int8),
            "market_ids": self.panel.market_ids.copy(),
            "currency_ids": self.panel.currency_ids.copy(),
            "risk_state": np.asarray(
                [
                    self._state.drawdown,
                    rolling_volatility,
                    gross_exposure,
                    self._last_turnover,
                ],
                dtype=np.float32,
            ),
            "time_features": np.asarray(
                [
                    math.sin(weekday_angle),
                    math.cos(weekday_angle),
                    math.sin(month_angle),
                    math.cos(month_angle),
                ],
                dtype=np.float32,
            ),
        }

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[dict[str, NDArray[Any]], dict[str, Any]]:
        """Reset to cash at the first leakage-safe close."""
        super().reset(seed=seed)
        del options
        self._state = AccountState.initial(
            asset_count=self.panel.asset_count,
            cash=self.config.initial_cash,
        )
        self._index = self._start_index
        self._episode_steps = 0
        self._last_turnover = 0.0
        self._done = False
        self._rewards.reset()
        if seed is not None:
            self.action_space.seed(seed)
        return self._observation(), {
            "observation_date": self.panel.dates[self._index].isoformat(),
            "execution_protocol": self.config.execution_protocol,
            "base_currency": self.config.base_currency,
            "data_partition": self.partition.partition,
        }

    def step(
        self,
        action: NDArray[np.float32],
    ) -> tuple[dict[str, NDArray[Any]], float, bool, bool, dict[str, Any]]:
        """Project a close signal, execute next open, and mark next close."""
        if self._done:
            raise RuntimeError("step called after episode completion; call reset")
        next_index = self._index + 1
        previous_value = self._state.last_value
        pretrade_weights = self._state.weights(self.panel.open_prices[next_index])
        execution_tradable = self.panel.tradable_mask[next_index]
        projection = self._projector.project(
            np.asarray(action, dtype=np.float64),
            current_weights=pretrade_weights,
            tradable_mask=execution_tradable,
        )
        execution = self._engine.execute(
            self._state.begin_session(),
            target_weights=projection.projected_weights,
            open_prices=self.panel.open_prices[next_index],
            close_prices=self.panel.close_prices[next_index],
            tradable_mask=execution_tradable,
            suspension_mask=self.panel.suspension_mask[next_index],
            limit_up_mask=self.panel.limit_up_mask[next_index],
            limit_down_mask=self.panel.limit_down_mask[next_index],
        )
        self._state = execution.state
        self._index = next_index
        self._episode_steps += 1
        self._last_turnover = execution.turnover

        net_return = execution.end_value / previous_value - 1.0
        costs = execution.fees + execution.slippage_cost
        gross_return = (execution.end_value + costs) / previous_value - 1.0
        cost_ratio = costs / previous_value
        reward = self._rewards.calculate(
            net_return=net_return,
            gross_return=gross_return,
            cost_ratio=cost_ratio,
            drawdown=self._state.drawdown,
        )
        terminated = not np.isfinite(execution.end_value) or execution.end_value <= 0.0
        data_exhausted = self._index >= self._end_index
        step_limit = (
            self.config.max_episode_steps is not None
            and self._episode_steps >= self.config.max_episode_steps
        )
        truncated = bool(data_exhausted or step_limit)
        self._done = bool(terminated or truncated)

        end_weights = self._weights_at_close()
        market_exposures = {
            market: float(
                end_weights[1:][
                    np.asarray(self.panel.markets, dtype=object) == market
                ].sum()
            )
            for market in sorted(set(self.panel.markets))
        }
        info: dict[str, Any] = {
            "execution_protocol": self.config.execution_protocol,
            "signal_date": self.panel.dates[next_index - 1].isoformat(),
            "execution_date": self.panel.dates[next_index].isoformat(),
            "raw_action": projection.raw_action.copy(),
            "normalized_weights": projection.normalized_weights.copy(),
            "projected_weights": projection.projected_weights.copy(),
            "clipping_reasons": list(projection.clipping_reasons),
            "unresolved_constraints": list(projection.unresolved_constraints),
            "execution_tradable_mask": execution_tradable.copy(),
            "executed_quantities": execution.executed_quantities.copy(),
            "rejected_orders": list(execution.rejected_orders),
            "trade_value": float(
                np.dot(
                    np.abs(execution.executed_quantities),
                    self.panel.open_prices[next_index],
                )
            ),
            "transaction_cost": execution.fees,
            "slippage": execution.slippage_cost,
            "turnover": execution.turnover,
            "portfolio_value": execution.end_value,
            "drawdown": self._state.drawdown,
            "accounting_error": execution.accounting_error,
            "market_exposures": market_exposures,
        }
        return self._observation(), reward, bool(terminated), truncated, info

    def render(self) -> Any:
        """Render a compact account snapshot."""
        text = (
            f"{self.panel.dates[self._index].isoformat()} "
            f"value={self._state.last_value:.2f} "
            f"drawdown={self._state.drawdown:.4f}"
        )
        if self.render_mode == "ansi":
            return text
        if self.render_mode == "human":
            print(text)
            return None
        if self.render_mode == "rgb_array":
            image = np.full((64, 256, 3), 255, dtype=np.uint8)
            width = min(255, int(round(self._state.drawdown * 255)))
            image[:, :width, 0] = 220
            image[:, :width, 1:] = 40
            return image
        return None
