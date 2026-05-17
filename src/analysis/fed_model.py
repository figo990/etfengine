"""股债性价比（FED 模型）分析"""

from __future__ import annotations

import pandas as pd


class FEDModelAnalyzer:
    """股债性价比分析器

    FED Model: 股票收益率 (1/PE) - 国债收益率
    - 值越高 → 股票越有吸引力（低估）
    - 值越低 → 债券越有吸引力（高估）
    """

    def calc_equity_risk_premium(
        self,
        pe_series: pd.Series,
        bond_yield_series: pd.Series,
    ) -> pd.Series:
        """计算股权风险溢价 (ERP)

        ERP = 1/PE - 国债收益率

        Args:
            pe_series: PE 时间序列
            bond_yield_series: 国债收益率序列 (如 2.5 表示 2.5%)

        Returns:
            ERP 时间序列 (百分比)
        """
        earnings_yield = 100.0 / pe_series  # 转为百分比
        erp = earnings_yield - bond_yield_series
        return erp

    def get_fed_snapshot(
        self,
        pe: float,
        cn_10y_yield: float,
        us_10y_yield: float | None = None,
    ) -> dict:
        """获取当前股债性价比快照

        Args:
            pe: 沪深300等宽基指数当前PE
            cn_10y_yield: 中国10年期国债收益率(%)
            us_10y_yield: 美国10年期国债收益率(%)

        Returns:
            dict: {earnings_yield, cn_erp, us_erp, cn_signal, us_signal}
        """
        earnings_yield = 100.0 / pe if pe > 0 else 0.0

        cn_erp = earnings_yield - cn_10y_yield
        cn_signal = self._classify_signal(cn_erp)

        result = {
            "earnings_yield": round(earnings_yield, 2),
            "cn_10y_yield": cn_10y_yield,
            "cn_erp": round(cn_erp, 2),
            "cn_signal": cn_signal,
        }

        if us_10y_yield is not None:
            us_erp = earnings_yield - us_10y_yield
            us_signal = self._classify_signal(us_erp)
            result.update(
                {
                    "us_10y_yield": us_10y_yield,
                    "us_erp": round(us_erp, 2),
                    "us_signal": us_signal,
                }
            )

        return result

    def _classify_signal(self, erp: float) -> str:
        """根据 ERP 值判断信号

        标准参考（沪深300 历史均值约 3-4%）:
        - ERP > 4%: 股票极度有吸引力
        - ERP > 2%: 偏股配置
        - ERP > 0%: 均衡配置
        - ERP < 0%: 偏债配置
        """
        if erp > 4:
            return "强烈看多"
        elif erp > 2:
            return "偏多"
        elif erp > 0:
            return "中性"
        elif erp > -2:
            return "偏空"
        else:
            return "强烈看空"

    def calc_historical_quantile(
        self,
        erp_series: pd.Series,
        lookback_years: int = 5,
    ) -> float | None:
        """计算当前 ERP 在历史中的分位数"""
        window = lookback_years * 252
        recent = erp_series.dropna().tail(window)
        if recent.empty:
            return None

        current = recent.iloc[-1]
        percentile = (recent < current).mean() * 100
        return round(percentile, 1)

    def get_allocation_suggestion(
        self,
        cn_erp: float,
        thresholds: dict | None = None,
    ) -> dict:
        """基于股债性价比给出配置建议

        Returns:
            dict: {equity_weight, bond_weight, suggestion}
        """
        if thresholds is None:
            thresholds = {
                "high": 3.0,
                "mid": 1.0,
                "low": -1.0,
            }

        if cn_erp > thresholds["high"]:
            return {"equity_weight": 1.0, "bond_weight": 0.0, "suggestion": "全仓权益"}
        elif cn_erp > thresholds["mid"]:
            return {"equity_weight": 0.7, "bond_weight": 0.3, "suggestion": "70%权益+30%债券"}
        elif cn_erp > thresholds["low"]:
            return {"equity_weight": 0.3, "bond_weight": 0.7, "suggestion": "30%权益+70%债券"}
        else:
            return {"equity_weight": 0.0, "bond_weight": 1.0, "suggestion": "全仓债券"}
