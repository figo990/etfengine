"""均线偏离度定投策略"""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from src.strategies.base_strategy import BaseStrategy, TradeOrder


class MADeviationDCAStrategy(BaseStrategy):
    """均线偏离度定投策略

    根据价格与长期均线的偏离程度动态调整投入金额：
    - 偏离度 < -12.5%: 4倍（深度低于均线）
    - 偏离度 < -5%: 3倍
    - 偏离度 < 0%: 2倍
    - 偏离度 < 10%: 1倍
    - 偏离度 < 20%: 0.6倍
    - 偏离度 < 30%: 0.3倍
    - 偏离度 >= 30%: 停止

    参数:
        base_amount: 基础定投金额
        ma_period: 均线周期(交易日，默认250)
        tiers: 偏离度分档配置
        frequency: 定投频率
    """

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        super().__init__(params)
        self.base_amount = self.params.get("base_amount", 1000.0)
        self.ma_period = self.params.get("ma_period", 250)
        self.frequency = self.params.get("frequency", "monthly")

        default_tiers = [
            {"deviation_max": -12.5, "multiplier": 4.0},
            {"deviation_max": -5.0, "multiplier": 3.0},
            {"deviation_max": 0.0, "multiplier": 2.0},
            {"deviation_max": 10.0, "multiplier": 1.0},
            {"deviation_max": 20.0, "multiplier": 0.6},
            {"deviation_max": 30.0, "multiplier": 0.3},
            {"deviation_max": 100.0, "multiplier": 0.0},
        ]
        self.tiers = self.params.get("tiers", default_tiers)

        self._last_invest_month: int | None = None
        self._trading_day_count_in_month: int = 0
        self._current_month: int | None = None

    @property
    def name(self) -> str:
        return "均线偏离定投"

    @property
    def description(self) -> str:
        return f"MA{self.ma_period}偏离度驱动, 基础{self.base_amount}元"

    def reset(self) -> None:
        super().reset()
        self._last_invest_month = None
        self._trading_day_count_in_month = 0
        self._current_month = None

    def _get_multiplier(self, deviation_pct: float) -> float:
        """根据偏离度获取投入倍数"""
        for tier in self.tiers:
            if deviation_pct < tier["deviation_max"]:
                return tier["multiplier"]
        return 0.0

    def _calc_deviation(self, price_data: pd.DataFrame) -> float | None:
        """计算当前价格与 MA 的偏离度（百分比）"""
        closes = price_data["close"]
        if len(closes) < self.ma_period:
            return None

        ma = closes.tail(self.ma_period).mean()
        current = closes.iloc[-1]

        if ma == 0:
            return None

        return (current - ma) / ma * 100

    def generate_signal(
        self,
        current_date: date,
        price_data: pd.DataFrame,
        **context: Any,
    ) -> TradeOrder | None:
        month = current_date.month

        if self._current_month != month:
            self._current_month = month
            self._trading_day_count_in_month = 0

        self._trading_day_count_in_month += 1

        if self._trading_day_count_in_month != 1:
            return None

        if self._last_invest_month == month:
            return None
        self._last_invest_month = month

        deviation = self._calc_deviation(price_data)

        if deviation is None:
            return TradeOrder(
                trade_date=current_date,
                direction="buy",
                amount=self.base_amount,
                price=price_data["close"].iloc[-1],
                reason=f"历史数据不足{self.ma_period}日, 按基础金额",
            )

        multiplier = self._get_multiplier(deviation)

        if multiplier <= 0:
            return None

        invest_amount = self.base_amount * multiplier
        return TradeOrder(
            trade_date=current_date,
            direction="buy",
            amount=invest_amount,
            price=price_data["close"].iloc[-1],
            reason=f"MA{self.ma_period}偏离={deviation:.1f}%, 倍数={multiplier}x",
        )
