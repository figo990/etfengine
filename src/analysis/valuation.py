"""估值分析模块：PE/PB 百分位计算与追踪"""

from __future__ import annotations

import numpy as np
import pandas as pd


class ValuationAnalyzer:
    """指数估值分析器"""

    def calc_percentile(
        self,
        series: pd.Series,
        lookback_years: int = 5,
        trading_days_per_year: int = 252,
    ) -> pd.Series:
        """计算滚动百分位数

        Args:
            series: PE/PB 时间序列
            lookback_years: 回看年数
            trading_days_per_year: 每年交易日数

        Returns:
            百分位数序列 (0~100)
        """
        window = lookback_years * trading_days_per_year
        result = series.rolling(window=window, min_periods=max(window // 2, 60)).apply(
            lambda x: (x.iloc[:-1] < x.iloc[-1]).mean() * 100 if len(x) > 1 else 50.0,
            raw=False,
        )
        return result

    def get_valuation_snapshot(
        self,
        valuation_df: pd.DataFrame,
        lookback_years: int = 5,
    ) -> dict:
        """获取当前估值快照

        Args:
            valuation_df: 包含 [trade_date, pe, pb, dividend_yield] 的 DataFrame

        Returns:
            dict: {pe, pb, pe_percentile, pb_percentile, dividend_yield, zone}
        """
        if valuation_df.empty:
            return {}

        latest = valuation_df.iloc[-1]
        pe_pctile = self.calc_percentile(valuation_df["pe"].dropna(), lookback_years)
        pb_pctile = self.calc_percentile(valuation_df["pb"].dropna(), lookback_years)

        pe_percentile = pe_pctile.iloc[-1] if not pe_pctile.empty else None
        pb_percentile = pb_pctile.iloc[-1] if not pb_pctile.empty else None

        zone = self._classify_zone(pe_percentile)

        return {
            "pe": latest.get("pe"),
            "pb": latest.get("pb"),
            "dividend_yield": latest.get("dividend_yield"),
            "pe_percentile": pe_percentile,
            "pb_percentile": pb_percentile,
            "zone": zone,
        }

    def _classify_zone(self, pe_percentile: float | None) -> str:
        """根据 PE 百分位划分估值区间"""
        if pe_percentile is None:
            return "未知"
        if pe_percentile < 20:
            return "极度低估"
        elif pe_percentile < 40:
            return "低估"
        elif pe_percentile < 60:
            return "适中"
        elif pe_percentile < 80:
            return "高估"
        else:
            return "极度高估"

    def calc_pe_band(
        self,
        price_series: pd.Series,
        pe_series: pd.Series,
    ) -> pd.DataFrame:
        """计算 PE Band（不同PE水平对应的价格）

        用于判断当前价格在历史估值中的相对位置
        """
        if price_series.empty or pe_series.empty:
            return pd.DataFrame()

        eps = price_series / pe_series
        eps_latest = eps.iloc[-1]

        percentiles = [10, 25, 50, 75, 90]
        pe_values = np.percentile(pe_series.dropna(), percentiles)

        bands = {}
        for p, pe_val in zip(percentiles, pe_values):
            bands[f"PE_{p}%"] = eps_latest * pe_val

        result = pd.DataFrame(bands, index=[0])
        result["current_price"] = price_series.iloc[-1]
        result["current_pe"] = pe_series.iloc[-1]
        return result

    def calc_graham_number(self, eps: float, bps: float) -> float:
        """格雷厄姆数（估值参考）

        Graham Number = sqrt(22.5 * EPS * BPS)
        """
        if eps <= 0 or bps <= 0:
            return 0.0
        return np.sqrt(22.5 * eps * bps)
