"""估值定投策略：根据 PE 百分位动态调整投入金额"""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from src.strategies.base_strategy import BaseStrategy, TradeOrder


class ValuationDCAStrategy(BaseStrategy):
    """估值定投策略

    根据指数 PE 百分位决定投入倍数：
    - PE百分位 < 20%: 2倍金额（极度低估）
    - PE百分位 < 40%: 1.5倍
    - PE百分位 < 60%: 1倍（正常）
    - PE百分位 < 80%: 0.5倍
    - PE百分位 >= 80%: 停止定投

    参数:
        base_amount: 基础定投金额
        pe_lookback_years: PE百分位回看年数
        tiers: 分档倍数配置
        frequency: 定投频率
    """

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        super().__init__(params)
        self.base_amount = self.params.get("base_amount", 1000.0)
        self.pe_lookback_years = self.params.get("pe_lookback_years", 5)
        self.frequency = self.params.get("frequency", "monthly")

        default_tiers = [
            {"percentile_max": 20, "multiplier": 2.0},
            {"percentile_max": 40, "multiplier": 1.5},
            {"percentile_max": 60, "multiplier": 1.0},
            {"percentile_max": 80, "multiplier": 0.5},
            {"percentile_max": 100, "multiplier": 0.0},
        ]
        self.tiers = self.params.get("tiers", default_tiers)

        self._last_invest_month: int | None = None
        self._trading_day_count_in_month: int = 0
        self._current_month: int | None = None

    @property
    def name(self) -> str:
        return "估值定投"

    @property
    def description(self) -> str:
        return f"PE百分位驱动, 基础金额{self.base_amount}元"

    def reset(self) -> None:
        super().reset()
        self._last_invest_month = None
        self._trading_day_count_in_month = 0
        self._current_month = None

    def _get_multiplier(self, pe_percentile: float) -> float:
        """根据 PE 百分位获取投入倍数"""
        for tier in self.tiers:
            if pe_percentile < tier["percentile_max"]:
                return tier["multiplier"]
        return 0.0

    def _calc_pe_percentile(self, pe_series: pd.Series, current_pe: float) -> float:
        """计算 PE 百分位"""
        if pe_series.empty or current_pe is None:
            return 50.0  # 默认正常
        return (pe_series < current_pe).mean() * 100

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

        valuation_data: pd.DataFrame | None = context.get("valuation_data")
        if valuation_data is None or valuation_data.empty:
            return TradeOrder(
                trade_date=current_date,
                direction="buy",
                amount=self.base_amount,
                price=price_data["close"].iloc[-1],
                reason="无估值数据, 按基础金额定投",
            )

        lookback_days = self.pe_lookback_years * 252
        recent_pe = valuation_data["pe"].tail(lookback_days)
        current_pe = valuation_data["pe"].iloc[-1] if not valuation_data.empty else None

        if current_pe is None or pd.isna(current_pe):
            return TradeOrder(
                trade_date=current_date,
                direction="buy",
                amount=self.base_amount,
                price=price_data["close"].iloc[-1],
                reason="PE数据缺失, 按基础金额定投",
            )

        pe_percentile = self._calc_pe_percentile(recent_pe, current_pe)
        multiplier = self._get_multiplier(pe_percentile)

        if multiplier <= 0:
            return None

        invest_amount = self.base_amount * multiplier
        return TradeOrder(
            trade_date=current_date,
            direction="buy",
            amount=invest_amount,
            price=price_data["close"].iloc[-1],
            reason=f"PE百分位={pe_percentile:.1f}%, 倍数={multiplier}x",
        )
