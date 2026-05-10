"""AkShare 数据源实现"""

from __future__ import annotations

from datetime import date

import akshare as ak
import pandas as pd
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from src.data.providers.base_provider import BaseDataProvider


class AkShareProvider(BaseDataProvider):
    """AkShare 数据源"""

    @property
    def name(self) -> str:
        return "akshare"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    def get_etf_daily(
        self,
        code: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        logger.debug(f"[AkShare] 获取 ETF 日线: {code}")

        start_str = start_date.strftime("%Y%m%d") if start_date else "20100101"
        end_str = end_date.strftime("%Y%m%d") if end_date else date.today().strftime("%Y%m%d")

        df = ak.fund_etf_hist_em(
            symbol=code,
            period="daily",
            start_date=start_str,
            end_date=end_str,
            adjust="qfq",
        )

        df = df.rename(columns={
            "日期": "trade_date",
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "收盘": "close",
            "成交量": "volume",
            "成交额": "amount",
            "换手率": "turnover_rate",
        })

        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        numeric_cols = ["open", "high", "low", "close", "volume", "amount"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df[["trade_date", "open", "high", "low", "close", "volume", "amount"]].sort_values(
            "trade_date"
        ).reset_index(drop=True)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    def get_etf_list(self) -> pd.DataFrame:
        logger.debug("[AkShare] 获取 ETF 列表")

        df = ak.fund_etf_spot_em()
        df = df.rename(columns={
            "代码": "code",
            "名称": "name",
        })

        result = df[["code", "name"]].copy()
        result["index_tracked"] = ""
        result["fund_size"] = None
        result["inception_date"] = None

        return result

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    def get_index_valuation(
        self,
        index_name: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        logger.debug(f"[AkShare] 获取指数估值: {index_name}")

        df = ak.index_value_name_funddb(symbol=index_name)

        df = df.rename(columns={
            "日期": "trade_date",
            "市盈率": "pe",
            "市净率": "pb",
            "股息率": "dividend_yield",
        })

        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date

        if start_date:
            df = df[df["trade_date"] >= start_date]
        if end_date:
            df = df[df["trade_date"] <= end_date]

        cols_available = [c for c in ["trade_date", "pe", "pb", "dividend_yield"] if c in df.columns]
        return df[cols_available].sort_values("trade_date").reset_index(drop=True)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    def get_bond_yield(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        logger.debug("[AkShare] 获取国债收益率")

        df_cn = ak.bond_zh_us_rate(start_date="2010-01-01")
        df_cn = df_cn.rename(columns={
            "日期": "trade_date",
            "中国国债收益率10年": "cn_10y",
            "中国国债收益率5年": "cn_5y",
            "中国国债收益率1年": "cn_1y",
            "美国国债收益率10年": "us_10y",
        })

        df_cn["trade_date"] = pd.to_datetime(df_cn["trade_date"]).dt.date

        if start_date:
            df_cn = df_cn[df_cn["trade_date"] >= start_date]
        if end_date:
            df_cn = df_cn[df_cn["trade_date"] <= end_date]

        cols = ["trade_date", "cn_10y", "cn_5y", "cn_1y", "us_10y"]
        cols_available = [c for c in cols if c in df_cn.columns]
        return df_cn[cols_available].sort_values("trade_date").reset_index(drop=True)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    def get_index_daily(
        self,
        index_code: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        logger.debug(f"[AkShare] 获取指数日线: {index_code}")

        start_str = start_date.strftime("%Y%m%d") if start_date else "20100101"
        end_str = end_date.strftime("%Y%m%d") if end_date else date.today().strftime("%Y%m%d")

        df = ak.stock_zh_index_daily_em(
            symbol=index_code,
            start_date=start_str,
            end_date=end_str,
        )

        df = df.rename(columns={
            "date": "trade_date",
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "volume": "volume",
        })

        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date

        return df[["trade_date", "open", "high", "low", "close", "volume"]].sort_values(
            "trade_date"
        ).reset_index(drop=True)
