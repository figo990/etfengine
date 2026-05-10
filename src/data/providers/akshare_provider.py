"""AkShare 数据源实现"""

from __future__ import annotations

import os
from datetime import date

os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"
for _k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
           "ALL_PROXY", "all_proxy"):
    os.environ.pop(_k, None)

import akshare as ak
import requests
requests.Session.trust_env = False
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

        # 使用新浪源（更稳定），需要加市场前缀
        prefix = "sh" if code.startswith(("5", "6")) else "sz"
        symbol = f"{prefix}{code}"

        try:
            df = ak.fund_etf_hist_sina(symbol=symbol)
        except Exception:
            # 回退到东方财富源
            start_str = start_date.strftime("%Y%m%d") if start_date else "20100101"
            end_str = end_date.strftime("%Y%m%d") if end_date else date.today().strftime("%Y%m%d")
            df = ak.fund_etf_hist_em(
                symbol=code, period="daily",
                start_date=start_str, end_date=end_str, adjust="qfq",
            )
            df = df.rename(columns={
                "日期": "trade_date", "开盘": "open", "最高": "high",
                "最低": "low", "收盘": "close", "成交量": "volume", "成交额": "amount",
            })
            df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
            numeric_cols = ["open", "high", "low", "close", "volume", "amount"]
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            result = df[["trade_date", "open", "high", "low", "close", "volume", "amount"]]
            if start_date:
                result = result[result["trade_date"] >= start_date]
            if end_date:
                result = result[result["trade_date"] <= end_date]
            return result.sort_values("trade_date").reset_index(drop=True)

        df = df.rename(columns={"date": "trade_date"})
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        numeric_cols = ["open", "high", "low", "close", "volume", "amount"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        result = df[["trade_date", "open", "high", "low", "close", "volume", "amount"]].copy()
        if start_date:
            result = result[result["trade_date"] >= start_date]
        if end_date:
            result = result[result["trade_date"] <= end_date]
        return result.sort_values("trade_date").reset_index(drop=True)

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

    INDEX_CODE_MAP = {
        "沪深300": "000300",
        "中证500": "000905",
        "中证1000": "000852",
        "上证50": "000016",
        "创业板指": "399006",
        "中证红利": "000922",
        "科创50": "000688",
    }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    def get_index_valuation(
        self,
        index_name: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        logger.debug(f"[AkShare] 获取指数估值: {index_name}")

        index_code = self.INDEX_CODE_MAP.get(index_name, index_name)

        try:
            df = ak.stock_zh_index_value_csindex(symbol=index_code)
            cols = df.columns.tolist()
            # csindex 返回固定格式: 日期(0), 代码(1), 中文全称(2), 简称(3),
            # 英文全称(4), 英文简称(5), 市盈率1(6), 市盈率2(7), 股息率1(8), 股息率2(9)
            if len(cols) >= 9:
                df = df.rename(columns={
                    cols[0]: "trade_date",
                    cols[6]: "pe",
                    cols[8]: "dividend_yield",
                })
            else:
                df = df.rename(columns={cols[0]: "trade_date"})
                if len(cols) > 6:
                    df = df.rename(columns={cols[6]: "pe"})
        except Exception as e:
            logger.warning(f"csindex 接口失败: {e}, 尝试 funddb 接口")
            df = ak.index_value_name_funddb(symbol=index_name)
            df = df.rename(columns={
                "日期": "trade_date",
                "市盈率": "pe",
                "市净率": "pb",
                "股息率": "dividend_yield",
            })

        if "trade_date" in df.columns:
            df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce").dt.date
        for col in ["pe", "pb", "dividend_yield"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        if start_date and "trade_date" in df.columns:
            df = df[df["trade_date"] >= start_date]
        if end_date and "trade_date" in df.columns:
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
        cols = df_cn.columns.tolist()
        # 固定位置: 0=日期, 1=中国2年, 2=中国5年, 3=中国10年, 9=美国10年
        rename_map = {cols[0]: "trade_date"}
        if len(cols) > 3:
            rename_map[cols[3]] = "cn_10y"
        if len(cols) > 2:
            rename_map[cols[2]] = "cn_5y"
        if len(cols) > 1:
            rename_map[cols[1]] = "cn_1y"
        if len(cols) > 9:
            rename_map[cols[9]] = "us_10y"
        df_cn = df_cn.rename(columns=rename_map)

        df_cn["trade_date"] = pd.to_datetime(df_cn["trade_date"]).dt.date

        if start_date:
            df_cn = df_cn[df_cn["trade_date"] >= start_date]
        if end_date:
            df_cn = df_cn[df_cn["trade_date"] <= end_date]

        cols_need = ["trade_date", "cn_10y", "cn_5y", "cn_1y", "us_10y"]
        cols_available = [c for c in cols_need if c in df_cn.columns]
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
