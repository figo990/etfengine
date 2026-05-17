"""红利轮动策略（A股红利 vs 港股红利）"""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from src.strategies.base_strategy import BaseStrategy, TradeOrder


class DividendRotationStrategy(BaseStrategy):
    """红利轮动策略

    参考 EarlETF 思路，在 A股红利 和 港股红利 之间轮动：
    - 计算两者40日收益差
    - 收益差过高时多配港股红利（A股红利相对跑快了）
    - 收益差过低时多配A股红利（港股红利相对跑快了）

    同时支持 红利 vs 全A 轮动，避免追高红利。
    """

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        super().__init__(params)
        self.return_diff_period = self.params.get("return_diff_period", 40)
        self.switch_threshold = self.params.get("switch_threshold", 0.05)
        self.a_code = self.params.get("a_code", "515080")  # 中证红利
        self.hk_code = self.params.get("hk_code", "159691")  # 港股红利

        self._current_holding: str | None = None  # "a_dividend" | "hk_dividend"

    @property
    def name(self) -> str:
        return "红利轮动"

    @property
    def description(self) -> str:
        return f"{self.return_diff_period}日收益差驱动, A股红利 vs 港股红利"

    def reset(self) -> None:
        super().reset()
        self._current_holding = None

    def generate_signal(
        self,
        current_date: date,
        price_data: pd.DataFrame,
        **context: Any,
    ) -> TradeOrder | None:
        """
        context 需包含:
          - a_prices: pd.Series (A股红利价格序列)
          - hk_prices: pd.Series (港股红利价格序列)
          - position_value: float
        """
        a_prices: pd.Series | None = context.get("a_prices")
        hk_prices: pd.Series | None = context.get("hk_prices")

        if a_prices is None or hk_prices is None:
            return None

        if len(a_prices) <= self.return_diff_period or len(hk_prices) <= self.return_diff_period:
            return None

        ret_a = (a_prices.iloc[-1] / a_prices.iloc[-self.return_diff_period - 1]) - 1
        ret_hk = (hk_prices.iloc[-1] / hk_prices.iloc[-self.return_diff_period - 1]) - 1
        diff = ret_a - ret_hk

        if diff > self.switch_threshold:
            target = "hk_dividend"
        elif diff < -self.switch_threshold:
            target = "a_dividend"
        else:
            return None

        if target == self._current_holding:
            return None

        self._current_holding = target
        current_price = price_data["close"].iloc[-1]
        amount = context.get("position_value", 10000.0)
        target_name = "港股红利" if target == "hk_dividend" else "A股红利"

        return TradeOrder(
            trade_date=current_date,
            direction="buy",
            amount=amount,
            price=current_price,
            reason=(
                f"红利轮动至{target_name}: A股{ret_a * 100:.1f}% "
                f"港股{ret_hk * 100:.1f}% 差值{diff * 100:.1f}%"
            ),
        )
