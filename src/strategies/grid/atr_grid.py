"""ATR 动态网格策略"""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from src.strategies.base_strategy import BaseStrategy, TradeOrder


class ATRGridStrategy(BaseStrategy):
    """ATR 动态网格策略

    根据 ATR（真实波动幅度）自动调整网格间距：
    - 市场波动大时拉大间距（避免频繁交易）
    - 市场波动小时缩小间距（捕捉小波动利润）

    网格间距 = ATR(N日) × K 系数
    """

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        super().__init__(params)
        self.atr_period = self.params.get("atr_period", 14)
        self.atr_multiplier = self.params.get("atr_multiplier", 1.5)
        self.amount_per_grid = self.params.get("amount_per_grid", 500.0)
        self.max_grids = self.params.get("max_grids", 20)

        self._last_buy_price: float | None = None
        self._last_sell_price: float | None = None
        self._current_atr: float = 0.0

    @property
    def name(self) -> str:
        return "ATR动态网格"

    @property
    def description(self) -> str:
        return f"ATR({self.atr_period})×{self.atr_multiplier}, 每格{self.amount_per_grid}元"

    def reset(self) -> None:
        super().reset()
        self._last_buy_price = None
        self._last_sell_price = None
        self._current_atr = 0.0

    def _calc_atr(self, price_data: pd.DataFrame) -> float:
        """计算 ATR (Average True Range)"""
        if len(price_data) < self.atr_period + 1:
            return 0.0

        high = price_data["high"]
        low = price_data["low"]
        close = price_data["close"]

        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        return tr.tail(self.atr_period).mean()

    def generate_signal(
        self,
        current_date: date,
        price_data: pd.DataFrame,
        **context: Any,
    ) -> TradeOrder | None:
        if len(price_data) < self.atr_period + 1:
            return None

        current_price = price_data["close"].iloc[-1]
        self._current_atr = self._calc_atr(price_data)

        if self._current_atr <= 0:
            return None

        grid_spacing = self._current_atr * self.atr_multiplier

        # 初始建仓
        if self._last_buy_price is None and self._last_sell_price is None:
            self._last_buy_price = current_price
            self._last_sell_price = current_price
            return TradeOrder(
                trade_date=current_date,
                direction="buy",
                amount=self.amount_per_grid * 5,
                price=current_price,
                reason=f"ATR网格初始建仓, ATR={self._current_atr:.4f}",
            )

        # 价格下跌超过一个网格间距 → 买入
        if current_price <= self._last_buy_price - grid_spacing:
            self._last_buy_price = current_price
            self._last_sell_price = current_price
            return TradeOrder(
                trade_date=current_date,
                direction="buy",
                amount=self.amount_per_grid,
                price=current_price,
                reason=f"ATR网格买入, 间距={grid_spacing:.4f}",
            )

        # 价格上涨超过一个网格间距 → 卖出
        if self.state.total_shares > 0 and current_price >= self._last_sell_price + grid_spacing:
            self._last_sell_price = current_price
            self._last_buy_price = current_price
            sell_amount = min(self.amount_per_grid, self.state.total_shares * current_price)
            return TradeOrder(
                trade_date=current_date,
                direction="sell",
                amount=sell_amount,
                price=current_price,
                reason=f"ATR网格卖出, 间距={grid_spacing:.4f}",
            )

        return None
