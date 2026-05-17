"""等差网格交易策略"""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from src.strategies.base_strategy import BaseStrategy, TradeOrder


class EqualGridStrategy(BaseStrategy):
    """等差网格交易策略

    在设定的价格区间内等距划分网格线，
    价格下穿格线买入，上穿格线卖出。

    参数:
        price_upper: 网格上限
        price_lower: 网格下限
        num_grids: 网格数量
        amount_per_grid: 每格交易金额
        initial_position_ratio: 初始仓位比例
    """

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        super().__init__(params)
        self.price_upper = self.params.get("price_upper", 1.5)
        self.price_lower = self.params.get("price_lower", 1.0)
        self.num_grids = self.params.get("num_grids", 10)
        self.amount_per_grid = self.params.get("amount_per_grid", 500.0)
        self.initial_position_ratio = self.params.get("initial_position_ratio", 0.5)

        self._grid_lines: list[float] = []
        self._position_at_grid: dict[int, bool] = {}
        self._prev_price: float | None = None
        self._initialized = False

    @property
    def name(self) -> str:
        return "等差网格"

    @property
    def description(self) -> str:
        return (
            f"价格区间[{self.price_lower}, {self.price_upper}], "
            f"{self.num_grids}格, 每格{self.amount_per_grid}元"
        )

    def reset(self) -> None:
        super().reset()
        self._setup_grids()
        self._prev_price = None
        self._initialized = False

    def _setup_grids(self) -> None:
        """初始化网格线"""
        step = (self.price_upper - self.price_lower) / self.num_grids
        self._grid_lines = [self.price_lower + i * step for i in range(self.num_grids + 1)]
        self._position_at_grid = {}

    def _find_grid_index(self, price: float) -> int:
        """找到价格所在的网格区间"""
        for i, line in enumerate(self._grid_lines):
            if price < line:
                return i - 1
        return len(self._grid_lines) - 1

    def generate_signal(
        self,
        current_date: date,
        price_data: pd.DataFrame,
        **context: Any,
    ) -> TradeOrder | None:
        current_price = price_data["close"].iloc[-1]

        if not self._grid_lines:
            self._setup_grids()

        # 超出网格范围不操作
        if current_price >= self.price_upper or current_price <= self.price_lower:
            self._prev_price = current_price
            return None

        # 首次运行：建立初始仓位
        if not self._initialized:
            self._initialized = True
            self._prev_price = current_price
            grid_idx = self._find_grid_index(current_price)
            # 在当前价格以下的格子都视为已持仓
            for i in range(grid_idx + 1):
                self._position_at_grid[i] = True
            initial_amount = self.amount_per_grid * (grid_idx + 1) * self.initial_position_ratio
            if initial_amount > 0:
                return TradeOrder(
                    trade_date=current_date,
                    direction="buy",
                    amount=initial_amount,
                    price=current_price,
                    reason="网格初始建仓",
                )
            return None

        if self._prev_price is None:
            self._prev_price = current_price
            return None

        # 检查是否穿越了网格线
        prev_idx = self._find_grid_index(self._prev_price)
        curr_idx = self._find_grid_index(current_price)

        self._prev_price = current_price

        if curr_idx < prev_idx:
            # 价格下穿 → 买入
            if not self._position_at_grid.get(curr_idx, False):
                self._position_at_grid[curr_idx] = True
                return TradeOrder(
                    trade_date=current_date,
                    direction="buy",
                    amount=self.amount_per_grid,
                    price=current_price,
                    reason=f"下穿格线{curr_idx}, 买入",
                )

        elif curr_idx > prev_idx:
            # 价格上穿 → 卖出
            if self._position_at_grid.get(prev_idx, False):
                self._position_at_grid[prev_idx] = False
                return TradeOrder(
                    trade_date=current_date,
                    direction="sell",
                    amount=self.amount_per_grid,
                    price=current_price,
                    reason=f"上穿格线{curr_idx}, 卖出",
                )

        return None
