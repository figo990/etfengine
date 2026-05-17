"""市场情绪指标"""

from __future__ import annotations

import numpy as np
import pandas as pd


class SentimentAnalyzer:
    """市场情绪分析器

    核心指标：偏股基金3年滚动年化收益
    - > 30%: 泡沫区域（贪婪）
    - > 15%: 偏乐观
    - < -5%: 偏悲观
    - < -10%: 底部区域（恐惧）
    """

    def calc_rolling_annual_return(
        self,
        nav_series: pd.Series,
        years: int = 3,
        trading_days_per_year: int = 252,
    ) -> pd.Series:
        """计算滚动年化收益率

        Args:
            nav_series: 基金净值序列
            years: 滚动年数
            trading_days_per_year: 年交易日

        Returns:
            滚动年化收益率序列（小数形式，如 0.15 = 15%）
        """
        window = years * trading_days_per_year
        rolling_return = nav_series / nav_series.shift(window) - 1
        annual_return = (1 + rolling_return) ** (1 / years) - 1
        return annual_return

    def get_sentiment_snapshot(
        self,
        rolling_return: float | None,
    ) -> dict:
        """获取市场情绪快照

        Args:
            rolling_return: 偏股基金3年滚动年化收益（小数）

        Returns:
            dict: {value, zone, signal, description}
        """
        if rolling_return is None:
            return {"value": None, "zone": "未知", "signal": "中性", "description": "数据不足"}

        value_pct = rolling_return * 100

        if value_pct > 30:
            zone = "泡沫"
            signal = "强烈看空"
            desc = "市场极度贪婪，警惕泡沫破裂"
        elif value_pct > 15:
            zone = "乐观"
            signal = "偏空"
            desc = "市场情绪偏热，注意控制仓位"
        elif value_pct > 0:
            zone = "正常"
            signal = "中性"
            desc = "市场情绪正常"
        elif value_pct > -5:
            zone = "偏冷"
            signal = "偏多"
            desc = "市场情绪偏冷，可适度加仓"
        elif value_pct > -10:
            zone = "悲观"
            signal = "看多"
            desc = "市场悲观，逢低布局"
        else:
            zone = "底部"
            signal = "强烈看多"
            desc = "极度恐惧，历史底部区域"

        return {
            "value": round(value_pct, 2),
            "zone": zone,
            "signal": signal,
            "description": desc,
        }

    def calc_market_temperature(
        self,
        pe_percentile: float | None = None,
        erp: float | None = None,
        sentiment_value: float | None = None,
    ) -> dict:
        """综合市场温度计

        综合 PE百分位 + 股债性价比 + 情绪指标，给出 0-100 的温度值：
        - 0~20: 极冷（底部）
        - 20~40: 偏冷
        - 40~60: 适中
        - 60~80: 偏热
        - 80~100: 极热（顶部）
        """
        scores = []

        if pe_percentile is not None:
            scores.append(pe_percentile)

        if erp is not None:
            # ERP 正常范围 -2% ~ 6%，映射到 100~0
            erp_score = max(0, min(100, (6 - erp) / 8 * 100))
            scores.append(erp_score)

        if sentiment_value is not None:
            # 3年滚动收益 -15% ~ 35%，映射到 0~100
            sent_score = max(0, min(100, (sentiment_value + 15) / 50 * 100))
            scores.append(sent_score)

        if not scores:
            return {"temperature": 50, "zone": "未知", "factors_count": 0}

        temperature = np.mean(scores)
        zone = self._temp_zone(temperature)

        return {
            "temperature": round(temperature, 1),
            "zone": zone,
            "factors_count": len(scores),
        }

    def _temp_zone(self, temp: float) -> str:
        if temp < 20:
            return "极冷"
        elif temp < 40:
            return "偏冷"
        elif temp < 60:
            return "适中"
        elif temp < 80:
            return "偏热"
        else:
            return "极热"
