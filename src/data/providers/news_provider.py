"""新闻数据源：AkShare 财经新闻 + 东方财富公告"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

import akshare as ak
import pandas as pd
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential


@dataclass
class NewsArticle:
    """新闻文章"""

    title: str
    content: str = ""
    source: str = ""
    publish_time: datetime | None = None
    url: str = ""
    category: str = ""  # finance | policy | industry | announcement
    raw_data: dict = field(default_factory=dict)


class NewsProvider:
    """新闻数据采集器"""

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=10))
    def fetch_eastmoney_news(self, max_items: int = 50) -> list[NewsArticle]:
        """东方财富财经新闻"""
        logger.debug("[NewsProvider] 采集东方财富新闻")
        articles = []
        try:
            df = ak.stock_info_global_em()
            if df.empty:
                return articles

            for _, row in df.head(max_items).iterrows():
                articles.append(
                    NewsArticle(
                        title=str(row.get("标题", "")),
                        content=str(row.get("摘要", "")),
                        source="eastmoney",
                        publish_time=self._parse_time(row.get("发布时间")),
                        url=str(row.get("链接", "")),
                        category="finance",
                    )
                )
        except Exception as e:
            logger.warning(f"东方财富新闻采集失败: {e}")

        return articles

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=10))
    def fetch_cls_telegraph(self, max_items: int = 50) -> list[NewsArticle]:
        """财联社快讯"""
        logger.debug("[NewsProvider] 采集财联社快讯")
        articles = []
        try:
            df = ak.stock_info_global_cls()
            if df is None or df.empty:
                return articles

            for _, row in df.head(max_items).iterrows():
                title = str(row.get("标题", ""))
                content = str(row.get("内容", title))
                articles.append(
                    NewsArticle(
                        title=title,
                        content=content,
                        source="cls",
                        publish_time=self._parse_time(row.get("发布时间", row.get("发布日期"))),
                        category="finance",
                    )
                )
        except Exception as e:
            logger.warning(f"财联社快讯采集失败: {e}")

        return articles

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=10))
    def fetch_eastmoney_breakfast(self, max_items: int = 30) -> list[NewsArticle]:
        """东方财富财经早餐/政经资讯."""
        logger.debug("[NewsProvider] 采集东方财富财经早餐")
        articles = []
        try:
            df = ak.stock_info_cjzc_em()
            if df is None or df.empty:
                return articles

            for _, row in df.head(max_items).iterrows():
                articles.append(
                    NewsArticle(
                        title=str(row.get("标题", "")),
                        content=str(row.get("摘要", "")),
                        source="eastmoney_breakfast",
                        publish_time=self._parse_time(row.get("发布时间")),
                        url=str(row.get("链接", "")),
                        category="policy",
                    )
                )
        except Exception as e:
            logger.warning(f"东方财富财经早餐采集失败: {e}")

        return articles

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=10))
    def fetch_cctv_news(self, max_items: int = 30) -> list[NewsArticle]:
        """央视新闻（政策类）"""
        logger.debug("[NewsProvider] 采集央视新闻")
        articles = []
        try:
            today = date.today().strftime("%Y%m%d")
            df = ak.news_cctv(date=today)
            if df is None or df.empty:
                return articles

            for _, row in df.head(max_items).iterrows():
                articles.append(
                    NewsArticle(
                        title=str(row.get("title", "")),
                        content=str(row.get("content", "")),
                        source="cctv",
                        publish_time=self._parse_time(row.get("date")),
                        category="policy",
                    )
                )
        except Exception as e:
            logger.warning(f"央视新闻采集失败: {e}")

        return articles

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=10))
    def fetch_stock_news(self, stock_code: str, max_items: int = 20) -> list[NewsArticle]:
        """个股新闻（用于重仓股监控）"""
        logger.debug(f"[NewsProvider] 采集个股新闻: {stock_code}")
        articles = []
        try:
            df = ak.stock_news_em(symbol=stock_code)
            if df is None or df.empty:
                return articles

            for _, row in df.head(max_items).iterrows():
                articles.append(
                    NewsArticle(
                        title=str(row.get("新闻标题", "")),
                        content=str(row.get("新闻内容", "")),
                        source="eastmoney",
                        publish_time=self._parse_time(row.get("发布时间")),
                        url=str(row.get("新闻链接", "")),
                        category="industry",
                    )
                )
        except Exception as e:
            logger.warning(f"个股 {stock_code} 新闻采集失败: {e}")

        return articles

    def fetch_all(
        self, sources: list[str] | None = None, max_per_source: int = 50
    ) -> list[NewsArticle]:
        """采集所有配置的新闻源"""
        sources = sources or ["eastmoney", "cls", "eastmoney_breakfast", "cctv"]
        all_articles: list[NewsArticle] = []

        fetchers = {
            "eastmoney": lambda: self.fetch_eastmoney_news(max_per_source),
            "cls": lambda: self.fetch_cls_telegraph(max_per_source),
            "eastmoney_breakfast": lambda: self.fetch_eastmoney_breakfast(max_per_source),
            "cctv": lambda: self.fetch_cctv_news(max_per_source),
        }

        for source in sources:
            if source in fetchers:
                try:
                    articles = fetchers[source]()
                    all_articles.extend(articles)
                    logger.info(f"[NewsProvider] {source}: 采集 {len(articles)} 条")
                except Exception as e:
                    logger.error(f"[NewsProvider] {source} 采集异常: {e}")

        return all_articles

    def _parse_time(self, raw: object) -> datetime | None:
        if raw is None or (isinstance(raw, float) and pd.isna(raw)):
            return None
        raw_str = str(raw).strip()
        if not raw_str:
            return None
        for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y%m%d", "%Y/%m/%d %H:%M"]:
            try:
                return datetime.strptime(raw_str, fmt)
            except ValueError:
                continue
        try:
            return pd.to_datetime(raw_str).to_pydatetime()
        except Exception:
            return None
