"""股债轮动策略"""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from src.strategies.base_strategy import BaseStrategy, TradeOrder


class BondEquityRotationStrategy(BaseStrategy):
    """股债轮动策略

    基于股债性价比 (ERP = 1/PE - 10年国债收益率) 决定股债配置比例：
    - ERP > high_threshold: 100% 权益
    - ERP > mid_threshold:  70% 权益 + 30% 债券
    - ERP > low_threshold:  30% 权益 + 70% 债券
    - ERP <= low_threshold: 100% 债券
    """

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        super().__init__(params)
        self.high_threshold = self.params.get("high_threshold", 3.0)
        self.mid_threshold = self.params.get("mid_threshold", 1.0)
        self.low_threshold = self.params.get("low_threshold", -1.0)
        self.equity_code = self.params.get("equity_code", "510300")
        self.bond_code = self.params.get("bond_code", "511010")
        self.rebalance_frequency = self.params.get("rebalance_frequency", "monthly")

        self._current_equity_weight: float | None = None
        self._last_rebalance_month: int | None = None

    @property
    def name(self) -> str:
        return "股债轮动"

    @property
    def description(self) -> str:
        return f"ERP驱动, 阈值[{self.low_threshold}, {self.mid_threshold}, {self.high_threshold}]"

    def reset(self) -> None:
        super().reset()
        self._current_equity_weight = None
        self._last_rebalance_month = None

    def _calc_target_weight(self, erp: float) -> float:
        """根据 ERP 计算权益目标仓位"""
        if erp > self.high_threshold:
            return 1.0
        elif erp > self.mid_threshold:
            return 0.7
        elif erp > self.low_threshold:
            return 0.3
        else:
            return 0.0

    def generate_signal(
        self,
        current_date: date,
        price_data: pd.DataFrame,
        **context: Any,
    ) -> TradeOrder | None:
        """
        context 需包含:
          - current_pe: float (当前宽基PE)
          - bond_yield_10y: float (10年国债收益率, 百分比如 2.5)
          - position_value: float (总头寸价值)
        """
        current_pe: float | None = context.get("current_pe")
        bond_yield: float | None = context.get("bond_yield_10y")

        if current_pe is None or bond_yield is None or current_pe <= 0:
            return None

        # 月度调仓频率控制
        if self.rebalance_frequency == "monthly":
            month = current_date.month
            if self._last_rebalance_month == month:
                return None
            self._last_rebalance_month = month

        earnings_yield = 100.0 / current_pe
        erp = earnings_yield - bond_yield
        target_weight = self._calc_target_weight(erp)

        if self._current_equity_weight is not None:
            if abs(target_weight - self._current_equity_weight) < 0.1:
                return None

        old_weight = self._current_equity_weight
        self._current_equity_weight = target_weight

        current_price = price_data["close"].iloc[-1]
        position_value = context.get("position_value", 10000.0)
        equity_amount = position_value * target_weight

        direction = "buy" if target_weight > (old_weight or 0) else "sell"
        amount = abs(equity_amount - position_value * (old_weight or 0))

        if amount < 100:
            return None

        return TradeOrder(
            trade_date=current_date,
            direction=direction,
            amount=amount,
            price=current_price,
            reason=(
                f"股债轮动: ERP={erp:.2f}% 权益{target_weight * 100:.0f}%"
                f" (PE={current_pe:.1f} 国债={bond_yield:.2f}%)"
            ),
        )
