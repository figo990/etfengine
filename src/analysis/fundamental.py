"""指数基本面分析：盈利增速、ROE、营收等宏观指标"""

from __future__ import annotations

import akshare as ak
import numpy as np
import pandas as pd
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential


class FundamentalAnalyzer:
    """指数层面基本面分析器

    获取并分析指数整体的：
    - 盈利增速（净利润同比增长率）
    - ROE 走势
    - 营收增速
    - 股息率变化
    """

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15))
    def get_index_fundamental(self, index_name: str) -> pd.DataFrame:
        """获取指数基本面历史数据（通过韭圈儿/funddb）"""
        logger.debug(f"获取指数基本面: {index_name}")
        try:
            df = ak.index_value_name_funddb(symbol=index_name)
            rename_map = {}
            for col in df.columns:
                col_lower = col.lower()
                if "日期" in col or "date" in col_lower:
                    rename_map[col] = "trade_date"
                elif "市盈" in col or "pe" in col_lower:
                    rename_map[col] = "pe"
                elif "市净" in col or "pb" in col_lower:
                    rename_map[col] = "pb"
                elif "股息" in col or "dividend" in col_lower:
                    rename_map[col] = "dividend_yield"
                elif "roe" in col_lower:
                    rename_map[col] = "roe"

            df = df.rename(columns=rename_map)
            if "trade_date" in df.columns:
                df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
            return df.sort_values("trade_date").reset_index(drop=True)
        except Exception as e:
            logger.warning(f"获取 {index_name} 基本面数据失败: {e}")
            return pd.DataFrame()

    def calc_earnings_growth(
        self,
        pe_series: pd.Series,
        price_series: pd.Series,
    ) -> pd.Series:
        """通过PE和价格反推盈利增速

        EPS = Price / PE
        盈利增速 = EPS同比变化
        """
        eps = price_series / pe_series
        eps = eps.replace([np.inf, -np.inf], np.nan)
        growth = eps.pct_change(252)  # 年化同比
        return growth

    def calc_roe_trend(self, pb_series: pd.Series, pe_series: pd.Series) -> pd.Series:
        """通过PB和PE推算ROE趋势

        ROE = PB / PE (杜邦分解简化)
        """
        roe = pb_series / pe_series
        roe = roe.replace([np.inf, -np.inf], np.nan)
        return roe

    def get_fundamental_snapshot(
        self,
        index_name: str,
        valuation_df: pd.DataFrame | None = None,
    ) -> dict:
        """获取基本面快照

        Returns:
            {pe, pb, roe, dividend_yield, pe_change_1y, roe_direction, ...}
        """
        if valuation_df is None:
            valuation_df = self.get_index_fundamental(index_name)

        if valuation_df.empty:
            return {"index_name": index_name, "status": "no_data"}

        latest = valuation_df.iloc[-1]
        result = {
            "index_name": index_name,
            "trade_date": str(latest.get("trade_date", "")),
        }

        for field in ["pe", "pb", "dividend_yield", "roe"]:
            if field in valuation_df.columns:
                result[field] = (
                    round(float(latest[field]), 4) if pd.notna(latest.get(field)) else None
                )

        # PE 变化方向（年化）
        if "pe" in valuation_df.columns and len(valuation_df) > 252:
            pe_now = valuation_df["pe"].iloc[-1]
            pe_1y = valuation_df["pe"].iloc[-252]
            if pd.notna(pe_now) and pd.notna(pe_1y) and pe_1y != 0:
                result["pe_change_1y"] = round((pe_now / pe_1y - 1) * 100, 2)

        # PB 变化
        if "pb" in valuation_df.columns and len(valuation_df) > 252:
            pb_now = valuation_df["pb"].iloc[-1]
            pb_1y = valuation_df["pb"].iloc[-252]
            if pd.notna(pb_now) and pd.notna(pb_1y) and pb_1y != 0:
                result["pb_change_1y"] = round((pb_now / pb_1y - 1) * 100, 2)

        # ROE 推算方向
        if "pe" in valuation_df.columns and "pb" in valuation_df.columns:
            roe_series = self.calc_roe_trend(valuation_df["pb"], valuation_df["pe"])
            roe_clean = roe_series.dropna()
            if len(roe_clean) > 60:
                roe_recent = roe_clean.tail(60).mean()
                roe_prev = (
                    roe_clean.iloc[-120:-60].mean() if len(roe_clean) > 120 else roe_clean.mean()
                )
                result["roe_trend"] = (
                    "改善"
                    if roe_recent > roe_prev * 1.02
                    else ("恶化" if roe_recent < roe_prev * 0.98 else "平稳")
                )

        return result

    def compare_fundamentals(
        self,
        indices: list[str],
    ) -> pd.DataFrame:
        """多指数基本面对比"""
        rows = []
        for idx in indices:
            snapshot = self.get_fundamental_snapshot(idx)
            if snapshot.get("status") != "no_data":
                rows.append(snapshot)

        if not rows:
            return pd.DataFrame()

        return pd.DataFrame(rows)
