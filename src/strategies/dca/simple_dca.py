"""普通定投策略（DCA: Dollar Cost Averaging）"""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from src.strategies.base_strategy import BaseStrategy, TradeOrder


class SimpleDCAStrategy(BaseStrategy):
    """定期定额定投策略

    参数:
        amount: 每期定投金额
        frequency: 定投频率 ("monthly" | "weekly" | "biweekly")
        day_of_month: 每月第几个交易日执行（frequency=monthly 时）
    """

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        super().__init__(params)
        self.amount = self.params.get("amount", 1000.0)
        self.frequency = self.params.get("frequency", "monthly")
        self.day_of_month = self.params.get("day_of_month", 1)
        self._last_invest_month: int | None = None
        self._last_invest_week: int | None = None
        self._trading_day_count_in_month: int = 0
        self._current_month: int | None = None

    @property
    def name(self) -> str:
        return "普通定投(DCA)"

    @property
    def description(self) -> str:
        return f"定期定额 {self.amount}元/{self.frequency}"

    def reset(self) -> None:
        super().reset()
        self._last_invest_month = None
        self._last_invest_week = None
        self._trading_day_count_in_month = 0
        self._current_month = None

    def generate_signal(
        self,
        current_date: date,
        price_data: pd.DataFrame,
        **context: Any,
    ) -> TradeOrder | None:
        if self.frequency == "monthly":
            return self._monthly_signal(current_date, price_data)
        elif self.frequency == "weekly":
            return self._weekly_signal(current_date, price_data)
        elif self.frequency == "biweekly":
            return self._biweekly_signal(current_date, price_data)
        return None

    def _monthly_signal(
        self, current_date: date, price_data: pd.DataFrame
    ) -> TradeOrder | None:
        month = current_date.month

        if self._current_month != month:
            self._current_month = month
            self._trading_day_count_in_month = 0

        self._trading_day_count_in_month += 1

        if self._trading_day_count_in_month == self.day_of_month:
            if self._last_invest_month != month:
                self._last_invest_month = month
                return TradeOrder(
                    trade_date=current_date,
                    direction="buy",
                    amount=self.amount,
                    price=price_data["close"].iloc[-1],
                    reason=f"月度定投(第{self.day_of_month}个交易日)",
                )
        return None

    def _weekly_signal(
        self, current_date: date, price_data: pd.DataFrame
    ) -> TradeOrder | None:
        week = current_date.isocalendar()[1]
        if self._last_invest_week != week:
            if current_date.weekday() == 0:  # 每周一
                self._last_invest_week = week
                return TradeOrder(
                    trade_date=current_date,
                    direction="buy",
                    amount=self.amount,
                    price=price_data["close"].iloc[-1],
                    reason="周定投(每周一)",
                )
        return None

    def _biweekly_signal(
        self, current_date: date, price_data: pd.DataFrame
    ) -> TradeOrder | None:
        week = current_date.isocalendar()[1]
        if week % 2 == 1 and self._last_invest_week != week:
            if current_date.weekday() == 0:
                self._last_invest_week = week
                return TradeOrder(
                    trade_date=current_date,
                    direction="buy",
                    amount=self.amount,
                    price=price_data["close"].iloc[-1],
                    reason="双周定投",
                )
        return None
