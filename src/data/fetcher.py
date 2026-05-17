"""统一数据获取接口：多源容灾、缓存、限速"""

from __future__ import annotations

import time
from datetime import date
from typing import Any

import pandas as pd
from loguru import logger

from src.core.config import settings
from src.data.providers.akshare_provider import AkShareProvider
from src.data.providers.base_provider import BaseDataProvider


class DataFetcher:
    """统一数据获取器，封装多源切换和容错"""

    def __init__(self) -> None:
        self._providers: dict[str, BaseDataProvider] = {
            "akshare": AkShareProvider(),
        }
        cfg = settings().data_source
        self._primary = cfg.primary
        self._fallback = cfg.fallback
        self._rate_limit_interval = 60.0 / cfg.rate_limit.requests_per_minute
        self._last_request_time: float = 0.0

    def _get_provider(self, name: str | None = None) -> BaseDataProvider:
        provider_name = name or self._primary
        if provider_name not in self._providers:
            raise ValueError(f"未注册的数据源: {provider_name}")
        return self._providers[provider_name]

    def _throttle(self) -> None:
        """简单限速"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._rate_limit_interval:
            time.sleep(self._rate_limit_interval - elapsed)
        self._last_request_time = time.time()

    def _fetch_with_fallback(self, method: str, **kwargs: Any) -> pd.DataFrame:
        """带容灾的数据获取"""
        self._throttle()

        try:
            provider = self._get_provider(self._primary)
            func = getattr(provider, method)
            return func(**kwargs)
        except Exception as e:
            logger.warning(f"主数据源 {self._primary} 失败: {e}, 尝试备用源")

        if self._fallback and self._fallback in self._providers:
            try:
                provider = self._get_provider(self._fallback)
                func = getattr(provider, method)
                return func(**kwargs)
            except Exception as e:
                logger.error(f"备用数据源 {self._fallback} 也失败: {e}")
                raise

        raise RuntimeError(f"所有数据源均失败, method={method}")

    def get_etf_daily(
        self,
        code: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """获取 ETF 日线行情"""
        return self._fetch_with_fallback(
            "get_etf_daily", code=code, start_date=start_date, end_date=end_date
        )

    def get_etf_list(self) -> pd.DataFrame:
        """获取 ETF 列表"""
        return self._fetch_with_fallback("get_etf_list")

    def get_index_valuation(
        self,
        index_name: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """获取指数估值"""
        return self._fetch_with_fallback(
            "get_index_valuation",
            index_name=index_name,
            start_date=start_date,
            end_date=end_date,
        )

    def get_bond_yield(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """获取国债收益率"""
        return self._fetch_with_fallback("get_bond_yield", start_date=start_date, end_date=end_date)

    def get_index_daily(
        self,
        index_code: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """获取指数日线"""
        return self._fetch_with_fallback(
            "get_index_daily",
            index_code=index_code,
            start_date=start_date,
            end_date=end_date,
        )

    def get_stock_daily(
        self,
        code: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """获取个股日线行情"""
        return self._fetch_with_fallback(
            "get_stock_daily",
            code=code,
            start_date=start_date,
            end_date=end_date,
        )

    def get_stock_fundamentals(self, code: str) -> pd.DataFrame:
        """获取个股主要财务指标"""
        return self._fetch_with_fallback("get_stock_fundamentals", code=code)

    def get_stock_valuation(self, code: str) -> pd.DataFrame:
        """获取个股估值历史"""
        return self._fetch_with_fallback("get_stock_valuation", code=code)

    def get_stock_earnings_forecasts(self, report_period: date) -> pd.DataFrame:
        """获取某报告期业绩预告"""
        return self._fetch_with_fallback(
            "get_stock_earnings_forecasts",
            report_period=report_period,
        )
