"""AkShare 数据源实现"""

# ruff: noqa: E402,I001

from __future__ import annotations

import os
from datetime import date

os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"
for _k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
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
                symbol=code,
                period="daily",
                start_date=start_str,
                end_date=end_str,
                adjust="qfq",
            )
            df = df.rename(
                columns={
                    "日期": "trade_date",
                    "开盘": "open",
                    "最高": "high",
                    "最低": "low",
                    "收盘": "close",
                    "成交量": "volume",
                    "成交额": "amount",
                }
            )
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
        df = df.rename(
            columns={
                "代码": "code",
                "名称": "name",
            }
        )

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
            # csindex 返回: 日期(0), 代码(1), 全称(2), 简称(3),
            # 英文全称(4), 英文简称(5), PE1(6), PE2(7), 股息率1(8), 股息率2(9), PB(10+)
            rename_map = {cols[0]: "trade_date"}
            if len(cols) > 6:
                rename_map[cols[6]] = "pe"
            if len(cols) > 8:
                rename_map[cols[8]] = "dividend_yield"
            if len(cols) > 10:
                rename_map[cols[10]] = "pb"
            df = df.rename(columns=rename_map)
        except Exception as e:
            logger.warning(f"csindex 接口失败: {e}, 尝试 funddb 接口")
            df = ak.index_value_name_funddb(symbol=index_name)
            df = df.rename(
                columns={
                    "日期": "trade_date",
                    "市盈率": "pe",
                    "市净率": "pb",
                    "股息率": "dividend_yield",
                }
            )

        if "trade_date" in df.columns:
            df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce").dt.date
        for col in ["pe", "pb", "dividend_yield"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        if start_date and "trade_date" in df.columns:
            df = df[df["trade_date"] >= start_date]
        if end_date and "trade_date" in df.columns:
            df = df[df["trade_date"] <= end_date]

        valuation_cols = ["trade_date", "pe", "pb", "dividend_yield"]
        cols_available = [c for c in valuation_cols if c in df.columns]
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
        # bond_zh_us_rate 列: 0=日期, 1=中国国债收益率2年, 2=中国国债收益率5年,
        # 3=中国国债收益率10年, ..., 9=美国国债收益率10年
        # 字段映射: cn_1y 存储短期(2年), cn_5y 存储5年, cn_10y 存储10年
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

        df = df.rename(
            columns={
                "date": "trade_date",
                "open": "open",
                "high": "high",
                "low": "low",
                "close": "close",
                "volume": "volume",
            }
        )

        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date

        return (
            df[["trade_date", "open", "high", "low", "close", "volume"]]
            .sort_values("trade_date")
            .reset_index(drop=True)
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    def get_stock_daily(
        self,
        code: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        logger.debug(f"[AkShare] 获取个股日线: {code}")

        start_str = start_date.strftime("%Y%m%d") if start_date else "20100101"
        end_str = end_date.strftime("%Y%m%d") if end_date else date.today().strftime("%Y%m%d")
        try:
            df = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start_str,
                end_date=end_str,
                adjust="qfq",
            )
        except Exception as exc:
            logger.warning(f"东方财富个股日线失败: {code}, 尝试新浪源: {exc}")
            prefix = "sh" if code.startswith(("6", "9")) else "sz"
            df = ak.stock_zh_a_daily(
                symbol=f"{prefix}{code}",
                start_date=start_str,
                end_date=end_str,
                adjust="qfq",
            )
        if df is None or df.empty:
            return pd.DataFrame()

        df = df.rename(
            columns={
                "日期": "trade_date",
                "date": "trade_date",
                "开盘": "open",
                "最高": "high",
                "最低": "low",
                "收盘": "close",
                "成交量": "volume",
                "成交额": "amount",
                "涨跌幅": "pct_change",
            }
        )
        df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce").dt.date
        for col in ["open", "high", "low", "close", "volume", "amount", "pct_change"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        stock_cols = [
            "trade_date",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "amount",
            "pct_change",
        ]
        cols = [c for c in stock_cols if c in df.columns]
        return (
            df[cols].dropna(subset=["trade_date"]).sort_values("trade_date").reset_index(drop=True)
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    def get_stock_fundamentals(self, code: str) -> pd.DataFrame:
        """获取个股主要财务指标."""
        logger.debug(f"[AkShare] 获取个股财务指标: {code}")
        symbol = f"{code}.{'SH' if code.startswith('6') else 'SZ'}"
        df = ak.stock_financial_analysis_indicator_em(symbol=symbol)
        if df is None or df.empty:
            return pd.DataFrame()

        rename_map = {
            "REPORT_DATE": "report_date",
            "REPORT_TYPE": "report_type",
            "TOTALOPERATEREVE": "revenue",
            "PARENTNETPROFIT": "net_profit",
            "ROEJQ": "roe",
            "TOTALOPERATEREVETZ": "revenue_yoy",
            "PARENTNETPROFITTZ": "net_profit_yoy",
            "NOTICE_DATE": "notice_date",
        }
        df = df.rename(columns=rename_map)
        df["report_date"] = pd.to_datetime(df["report_date"], errors="coerce").dt.date
        df["notice_date"] = pd.to_datetime(df["notice_date"], errors="coerce").dt.date
        numeric_cols = ["revenue", "net_profit", "roe", "revenue_yoy", "net_profit_yoy"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        cols = [
            "report_date",
            "report_type",
            "revenue",
            "net_profit",
            "roe",
            "revenue_yoy",
            "net_profit_yoy",
            "notice_date",
        ]
        return (
            df[[col for col in cols if col in df.columns]]
            .dropna(subset=["report_date"])
            .sort_values("report_date")
            .reset_index(drop=True)
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    def get_stock_valuation(self, code: str) -> pd.DataFrame:
        """获取个股估值历史."""
        logger.debug(f"[AkShare] 获取个股估值: {code}")
        df = ak.stock_value_em(symbol=code)
        if df is None or df.empty:
            return pd.DataFrame()

        df = df.rename(
            columns={
                "数据日期": "trade_date",
                "当日收盘价": "close",
                "总市值": "market_cap",
                "PE(TTM)": "pe_ttm",
                "PE(静)": "pe_static",
                "市净率": "pb",
            }
        )
        df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce").dt.date
        for col in ["close", "market_cap", "pe_ttm", "pe_static", "pb"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        cols = ["trade_date", "close", "market_cap", "pe_ttm", "pe_static", "pb"]
        return (
            df[[col for col in cols if col in df.columns]]
            .dropna(subset=["trade_date"])
            .sort_values("trade_date")
            .reset_index(drop=True)
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    def get_stock_earnings_forecasts(self, report_period: date) -> pd.DataFrame:
        """获取某报告期业绩预告."""
        logger.debug(f"[AkShare] 获取业绩预告: {report_period}")
        df = ak.stock_yjyg_em(date=report_period.strftime("%Y%m%d"))
        if df is None or df.empty:
            return pd.DataFrame()

        df = df.rename(
            columns={
                "股票代码": "company_code",
                "股票简称": "company_name",
                "预测指标": "indicator",
                "预测数值": "forecast_value",
                "业绩变动幅度": "change_pct",
                "业绩变动原因": "reason",
                "预告类型": "forecast_type",
                "上年同期值": "last_year_value",
                "公告日期": "announce_date",
            }
        )
        df["report_period"] = report_period
        df["announce_date"] = pd.to_datetime(df["announce_date"], errors="coerce").dt.date
        for col in ["forecast_value", "change_pct", "last_year_value"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        cols = [
            "company_code",
            "company_name",
            "report_period",
            "indicator",
            "forecast_value",
            "change_pct",
            "forecast_type",
            "reason",
            "last_year_value",
            "announce_date",
        ]
        return (
            df[[col for col in cols if col in df.columns]]
            .dropna(subset=["company_code", "announce_date"])
            .reset_index(drop=True)
        )
