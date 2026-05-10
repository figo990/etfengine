"""行业/板块轮动策略（动量打分法）"""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from src.strategies.base_strategy import BaseStrategy, TradeOrder


class SectorRotationStrategy(BaseStrategy):
    """行业板块轮动策略（动量打分法）

    对每只行业 ETF 计算综合动量得分:
      Score = w1 × ROC_1M + w2 × ROC_3M + w3 × ROC_6M + w4 × ROC_12M

    排序后选择 Top-N 持有，定期调仓。
    """

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        super().__init__(params)
        self.top_n = self.params.get("top_n", 3)
        self.rebalance_frequency = self.params.get("rebalance_frequency", "monthly")
        self.weights = self.params.get("weights", {
            "1m": 0.4,
            "3m": 0.3,
            "6m": 0.2,
            "12m": 0.1,
        })
        self.roc_periods = {
            "1m": 20,
            "3m": 60,
            "6m": 120,
            "12m": 250,
        }

        self._current_holdings: list[str] = []
        self._last_rebalance_month: int | None = None

    @property
    def name(self) -> str:
        return "行业动量轮动"

    @property
    def description(self) -> str:
        return f"多周期动量打分, Top-{self.top_n}持仓"

    def reset(self) -> None:
        super().reset()
        self._current_holdings = []
        self._last_rebalance_month = None

    def _calc_momentum_score(self, prices: pd.Series) -> float:
        """计算综合动量得分"""
        score = 0.0
        for period_name, weight in self.weights.items():
            period = self.roc_periods.get(period_name, 20)
            if len(prices) > period:
                roc = (prices.iloc[-1] / prices.iloc[-period - 1] - 1) * 100
                score += weight * roc
        return score

    def generate_signal(
        self,
        current_date: date,
        price_data: pd.DataFrame,
        **context: Any,
    ) -> TradeOrder | None:
        """
        context 需包含:
          - sector_prices: dict[str, pd.Series] — {ETF代码: 价格序列}
          - sector_names: dict[str, str] — {ETF代码: 名称} (可选)
          - position_value: float
        """
        sector_prices: dict[str, pd.Series] | None = context.get("sector_prices")
        if sector_prices is None or len(sector_prices) == 0:
            return None

        # 月度调仓控制
        month = current_date.month
        if self._last_rebalance_month == month:
            return None
        self._last_rebalance_month = month

        # 计算各行业动量得分
        scores: dict[str, float] = {}
        for code, prices in sector_prices.items():
            if len(prices) > self.roc_periods.get("12m", 250):
                scores[code] = self._calc_momentum_score(prices)

        if len(scores) < self.top_n:
            return None

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_codes = [code for code, _ in ranked[:self.top_n]]

        if set(top_codes) == set(self._current_holdings):
            return None

        old_holdings = self._current_holdings.copy()
        self._current_holdings = top_codes

        current_price = price_data["close"].iloc[-1]
        amount = context.get("position_value", 10000.0)
        sector_names = context.get("sector_names", {})

        top_names = [sector_names.get(c, c) for c in top_codes]
        top_scores = [f"{scores[c]:.1f}" for c in top_codes]

        return TradeOrder(
            trade_date=current_date,
            direction="buy",
            amount=amount,
            price=current_price,
            reason=f"行业轮动: {', '.join(top_names)} (得分: {', '.join(top_scores)})",
        )
