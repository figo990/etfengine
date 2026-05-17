"""策略基类：所有策略的抽象接口"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pandas as pd


@dataclass
class TradeOrder:
    """交易订单"""

    trade_date: date
    direction: str  # "buy" | "sell"
    amount: float  # 交易金额
    price: float  # 成交价格
    shares: float = 0.0  # 成交份额
    reason: str = ""


@dataclass
class StrategyState:
    """策略运行状态"""

    total_invested: float = 0.0
    total_shares: float = 0.0
    avg_cost: float = 0.0
    cash: float = 0.0
    orders: list[TradeOrder] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


class BaseStrategy(ABC):
    """策略基类"""

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        self.params = params or {}
        self.state = StrategyState()

    @property
    @abstractmethod
    def name(self) -> str:
        """策略名称"""
        ...

    @property
    def description(self) -> str:
        """策略描述"""
        return ""

    @abstractmethod
    def generate_signal(
        self,
        current_date: date,
        price_data: pd.DataFrame,
        **context: Any,
    ) -> TradeOrder | list[TradeOrder] | None:
        """生成交易信号

        Args:
            current_date: 当前日期
            price_data: 截至当前日期的历史价格数据
            context: 额外上下文（估值、国债收益率等）

        Returns:
            TradeOrder if 有交易信号, None if 无操作
        """
        ...

    def reset(self) -> None:
        """重置策略状态（回测开始前调用）"""
        self.state = StrategyState()

    def on_order_filled(self, order: TradeOrder) -> None:
        """订单成交回调，更新内部状态"""
        if order.direction == "buy":
            self.state.total_invested += order.amount
            self.state.total_shares += order.shares
            if self.state.total_shares > 0:
                self.state.avg_cost = self.state.total_invested / self.state.total_shares
        elif order.direction == "sell":
            sell_shares = order.shares
            self.state.total_shares -= sell_shares
            if self.state.total_shares > 0:
                self.state.total_invested = self.state.avg_cost * self.state.total_shares
            else:
                self.state.total_invested = 0.0
                self.state.avg_cost = 0.0
            self.state.cash += order.amount

        self.state.orders.append(order)
