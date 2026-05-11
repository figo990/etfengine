"""大小盘动量轮动策略"""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from src.strategies.base_strategy import BaseStrategy, TradeOrder


class MomentumRotationStrategy(BaseStrategy):
    """大小盘动量轮动策略

    比较两个指数/ETF的近期动量（N日涨幅），
    持有动量更强的一方。

    经典配对：上证50 vs 中证1000

    参数:
        large_code: 大盘 ETF 代码
        small_code: 小盘 ETF 代码
        lookback_days: 动量回看天数
        rebalance_frequency: 调仓频率
    """

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        super().__init__(params)
        self.large_code = self.params.get("large_code", "510050")
        self.small_code = self.params.get("small_code", "512100")
        self.lookback_days = self.params.get("lookback_days", 20)
        self.rebalance_frequency = self.params.get("rebalance_frequency", "daily")

        self._current_holding: str | None = None  # "large" | "small"
        self._last_rebalance_month: int | None = None

    @property
    def name(self) -> str:
        return "大小盘动量轮动"

    @property
    def description(self) -> str:
        return f"ROC{self.lookback_days}日动量, {self.large_code} vs {self.small_code}"

    def reset(self) -> None:
        super().reset()
        self._current_holding = None
        self._last_rebalance_month = None

    def _calc_roc(self, prices: pd.Series, period: int) -> float | None:
        """计算 N 日涨幅 (Rate of Change)"""
        if len(prices) <= period:
            return None
        return (prices.iloc[-1] / prices.iloc[-period - 1] - 1) * 100

    def generate_signal(
        self,
        current_date: date,
        price_data: pd.DataFrame,
        **context: Any,
    ) -> TradeOrder | list[TradeOrder] | None:
        """需要 context 中传入 large_prices 和 small_prices"""
        large_prices: pd.Series | None = context.get("large_prices")
        small_prices: pd.Series | None = context.get("small_prices")

        if large_prices is None or small_prices is None:
            return None

        if len(large_prices) <= self.lookback_days or len(small_prices) <= self.lookback_days:
            return None

        roc_large = self._calc_roc(large_prices, self.lookback_days)
        roc_small = self._calc_roc(small_prices, self.lookback_days)

        if roc_large is None or roc_small is None:
            return None

        target = "large" if roc_large > roc_small else "small"

        if target == self._current_holding:
            return None

        current_price = price_data["close"].iloc[-1]
        amount = context.get("position_value", 10000.0)

        orders: list[TradeOrder] = []

        if self._current_holding is not None:
            prev_name = "大盘" if self._current_holding == "large" else "小盘"
            orders.append(TradeOrder(
                trade_date=current_date,
                direction="sell",
                amount=amount,
                price=current_price,
                reason=f"轮动卖出{prev_name}: ROC大盘={roc_large:.1f}% ROC小盘={roc_small:.1f}%",
            ))

        self._current_holding = target
        target_name = "大盘" if target == "large" else "小盘"

        orders.append(TradeOrder(
            trade_date=current_date,
            direction="buy",
            amount=amount,
            price=current_price,
            reason=f"轮动买入{target_name}: ROC大盘={roc_large:.1f}% ROC小盘={roc_small:.1f}%",
        ))

        return orders if len(orders) > 1 else orders[0]
