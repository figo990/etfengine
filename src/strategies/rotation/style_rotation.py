"""风格轮动三棱镜策略（复刻 EarlETF 思路）"""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from src.strategies.base_strategy import BaseStrategy, TradeOrder


class StyleRotationStrategy(BaseStrategy):
    """风格轮动三棱镜策略

    使用三个信号维度判断大小盘/价值成长轮动：
    1. 252日布林线突破 — 比值突破上/下轨
    2. 40日收益差的252日均线穿越 — 趋势确认
    3. 比值偏离5年均线 — 长期均值回归

    当三个信号中至少两个一致时，确认轮动方向。
    """

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        super().__init__(params)
        self.bollinger_period = self.params.get("bollinger_period", 252)
        self.bollinger_std = self.params.get("bollinger_std", 2.0)
        self.return_diff_period = self.params.get("return_diff_period", 40)
        self.mean_revert_period = self.params.get("mean_revert_period", 1250)  # 5年
        self.confirmation_threshold = self.params.get("confirmation_threshold", 2)

        self._current_holding: str | None = None  # "asset_a" | "asset_b"

    @property
    def name(self) -> str:
        return "风格轮动三棱镜"

    @property
    def description(self) -> str:
        return "布林线+收益差+均值回归 三维信号确认"

    def reset(self) -> None:
        super().reset()
        self._current_holding = None

    def _calc_bollinger_signal(self, ratio_series: pd.Series) -> int:
        """布林线信号：比值突破上/下轨

        Returns: 1=看多A, -1=看多B, 0=中性
        """
        if len(ratio_series) < self.bollinger_period:
            return 0

        window = ratio_series.tail(self.bollinger_period)
        ma = window.mean()
        std = window.std()

        if std == 0:
            return 0

        upper = ma + self.bollinger_std * std
        lower = ma - self.bollinger_std * std
        current = ratio_series.iloc[-1]

        if current > upper:
            return 1
        elif current < lower:
            return -1
        return 0

    def _calc_return_diff_signal(
        self, prices_a: pd.Series, prices_b: pd.Series
    ) -> int:
        """40日收益差信号：短期动量方向

        计算两资产40日收益差，然后看其252日均线穿越方向。
        Returns: 1=看多A, -1=看多B, 0=中性
        """
        min_len = self.return_diff_period + self.bollinger_period
        if len(prices_a) < min_len or len(prices_b) < min_len:
            return 0

        ret_a = prices_a.pct_change(self.return_diff_period)
        ret_b = prices_b.pct_change(self.return_diff_period)
        diff = ret_a - ret_b

        diff_clean = diff.dropna()
        if len(diff_clean) < self.bollinger_period:
            return 0

        ma = diff_clean.rolling(self.bollinger_period).mean()

        if ma.iloc[-1] is None or pd.isna(ma.iloc[-1]):
            return 0

        current_diff = diff_clean.iloc[-1]

        if current_diff > ma.iloc[-1] and current_diff > 0:
            return 1
        elif current_diff < ma.iloc[-1] and current_diff < 0:
            return -1
        return 0

    def _calc_mean_revert_signal(self, ratio_series: pd.Series) -> int:
        """5年均线均值回归信号

        比值低于5年均线时看多B（被低估的一方），反之看多A。
        Returns: 1=看多A, -1=看多B, 0=中性
        """
        if len(ratio_series) < self.mean_revert_period:
            return 0

        ma_5y = ratio_series.tail(self.mean_revert_period).mean()
        current = ratio_series.iloc[-1]

        deviation = (current - ma_5y) / ma_5y
        if deviation > 0.05:
            return -1  # A相对高估，看多B
        elif deviation < -0.05:
            return 1   # A相对低估，看多A
        return 0

    def generate_signal(
        self,
        current_date: date,
        price_data: pd.DataFrame,
        **context: Any,
    ) -> TradeOrder | None:
        """
        context 需包含:
          - prices_a: pd.Series (资产A价格序列, 如大盘/价值)
          - prices_b: pd.Series (资产B价格序列, 如小盘/成长)
        """
        prices_a: pd.Series | None = context.get("prices_a")
        prices_b: pd.Series | None = context.get("prices_b")

        if prices_a is None or prices_b is None:
            return None

        if len(prices_a) < self.bollinger_period or len(prices_b) < self.bollinger_period:
            return None

        # 计算比值
        ratio = prices_a / prices_b
        ratio = ratio.dropna()

        if ratio.empty:
            return None

        # 三维信号
        sig_bollinger = self._calc_bollinger_signal(ratio)
        sig_return_diff = self._calc_return_diff_signal(prices_a, prices_b)
        sig_mean_revert = self._calc_mean_revert_signal(ratio)

        total_score = sig_bollinger + sig_return_diff + sig_mean_revert

        if total_score >= self.confirmation_threshold:
            target = "asset_a"
        elif total_score <= -self.confirmation_threshold:
            target = "asset_b"
        else:
            return None

        if target == self._current_holding:
            return None

        self._current_holding = target
        current_price = price_data["close"].iloc[-1]
        amount = context.get("position_value", 10000.0)
        target_name = context.get("asset_a_name", "资产A") if target == "asset_a" else context.get("asset_b_name", "资产B")

        return TradeOrder(
            trade_date=current_date,
            direction="buy",
            amount=amount,
            price=current_price,
            reason=(
                f"三棱镜轮动至{target_name}: "
                f"布林={sig_bollinger} 收益差={sig_return_diff} 均值回归={sig_mean_revert}"
            ),
        )
