"""数据源基类：定义统一的数据获取接口"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

import pandas as pd


class BaseDataProvider(ABC):
    """数据源抽象基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """数据源名称"""
        ...

    @abstractmethod
    def get_etf_daily(
        self,
        code: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """获取 ETF 日线行情

        Returns:
            DataFrame columns: [trade_date, open, high, low, close, volume, amount]
        """
        ...

    @abstractmethod
    def get_etf_list(self) -> pd.DataFrame:
        """获取 ETF 列表

        Returns:
            DataFrame columns: [code, name, index_tracked, fund_size, inception_date]
        """
        ...

    @abstractmethod
    def get_index_valuation(
        self,
        index_name: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """获取指数估值数据

        Returns:
            DataFrame columns: [trade_date, pe, pe_ttm, pb, dividend_yield]
        """
        ...

    @abstractmethod
    def get_bond_yield(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """获取国债收益率

        Returns:
            DataFrame columns: [trade_date, cn_10y, cn_5y, cn_1y, us_10y]
        """
        ...

    def get_index_daily(
        self,
        index_code: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """获取指数日线行情（部分数据源可能不支持）"""
        raise NotImplementedError(f"{self.name} 不支持指数日线数据")

    def get_fund_index(
        self,
        index_name: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """获取基金指数数据"""
        raise NotImplementedError(f"{self.name} 不支持基金指数数据")
