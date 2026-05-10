"""组合再平衡策略"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from loguru import logger


@dataclass
class RebalanceOrder:
    """再平衡调仓指令"""
    etf_code: str
    etf_name: str
    direction: str  # "buy" | "sell"
    target_weight: float
    current_weight: float
    drift: float
    trade_amount: float
    trade_shares: float


class PortfolioRebalancer:
    """组合再平衡管理器

    支持两种触发模式：
    1. 偏离触发：任一持仓偏离目标超过阈值时触发
    2. 定期触发：按固定频率（月/季）检查并再平衡
    """

    def __init__(
        self,
        drift_threshold: float = 0.05,
        min_trade_amount: float = 1000.0,
    ) -> None:
        self.drift_threshold = drift_threshold
        self.min_trade_amount = min_trade_amount

    def check_drift(
        self,
        holdings: list[dict],
        total_value: float,
    ) -> list[dict]:
        """检查各持仓偏离度

        Args:
            holdings: [{etf_code, etf_name, market_value, target_weight}, ...]
            total_value: 组合总市值

        Returns:
            带偏离度信息的列表
        """
        result = []
        for h in holdings:
            actual_weight = h["market_value"] / total_value if total_value > 0 else 0
            drift = actual_weight - h["target_weight"]
            result.append({
                **h,
                "actual_weight": round(actual_weight, 4),
                "drift": round(drift, 4),
                "abs_drift": round(abs(drift), 4),
                "needs_rebalance": abs(drift) > self.drift_threshold,
            })
        return result

    def should_rebalance(self, holdings: list[dict], total_value: float) -> bool:
        """是否需要触发再平衡"""
        drift_info = self.check_drift(holdings, total_value)
        return any(h["needs_rebalance"] for h in drift_info)

    def calc_rebalance_orders(
        self,
        holdings: list[dict],
        total_value: float,
        current_prices: dict[str, float],
    ) -> list[RebalanceOrder]:
        """计算再平衡调仓指令

        Args:
            holdings: 当前持仓
            total_value: 组合总市值
            current_prices: {etf_code: 当前价格}

        Returns:
            调仓指令列表
        """
        orders: list[RebalanceOrder] = []
        drift_info = self.check_drift(holdings, total_value)

        for h in drift_info:
            target_value = total_value * h["target_weight"]
            current_value = h["market_value"]
            diff = target_value - current_value

            if abs(diff) < self.min_trade_amount:
                continue

            price = current_prices.get(h["etf_code"], 0)
            if price <= 0:
                continue

            direction = "buy" if diff > 0 else "sell"
            trade_amount = abs(diff)
            trade_shares = trade_amount / price

            orders.append(RebalanceOrder(
                etf_code=h["etf_code"],
                etf_name=h.get("etf_name", ""),
                direction=direction,
                target_weight=h["target_weight"],
                current_weight=h["actual_weight"],
                drift=h["drift"],
                trade_amount=round(trade_amount, 2),
                trade_shares=round(trade_shares, 2),
            ))

        # 先卖后买，避免资金不足
        orders.sort(key=lambda o: (o.direction != "sell", -o.trade_amount))
        return orders

    def calc_contribution(
        self,
        holdings: list[dict],
        returns_dict: dict[str, float],
    ) -> list[dict]:
        """计算各持仓对组合收益的贡献度

        Args:
            holdings: [{etf_code, target_weight}, ...]
            returns_dict: {etf_code: 区间收益率}

        Returns:
            [{etf_code, weight, return, contribution}, ...]
        """
        result = []
        total_contribution = 0.0
        for h in holdings:
            code = h["etf_code"]
            weight = h["target_weight"]
            ret = returns_dict.get(code, 0.0)
            contribution = weight * ret
            total_contribution += contribution
            result.append({
                "etf_code": code,
                "etf_name": h.get("etf_name", ""),
                "weight": weight,
                "return": round(ret * 100, 2),
                "contribution": round(contribution * 100, 4),
            })

        for r in result:
            r["contribution_pct"] = (
                round(r["contribution"] / (total_contribution * 100) * 100, 1)
                if total_contribution != 0 else 0
            )

        return result
