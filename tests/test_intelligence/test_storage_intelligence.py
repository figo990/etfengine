"""DuckDB 新闻和基本面存储测试"""

import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from src.data.storage import StorageEngine


@pytest.fixture
def storage(tmp_path):
    db_path = str(tmp_path / "test.duckdb")
    engine = StorageEngine(db_path=db_path)
    engine.init_schema()
    yield engine
    engine.close()


class TestNewsStorage:
    def test_upsert_and_query(self, storage):
        articles = [
            {
                "title": "消费回暖",
                "summary": "消费数据向好",
                "content": "详细内容",
                "source": "eastmoney",
                "category": "finance",
                "publish_time": datetime(2025, 5, 10, 15, 0),
                "url": "https://example.com/1",
                "sentiment": 0.5,
                "impact_level": "high",
                "is_policy": False,
                "related_sectors": ["消费"],
                "related_etf_codes": ["159928"],
            },
            {
                "title": "芯片政策",
                "summary": "自主可控",
                "content": "半导体政策",
                "source": "cctv",
                "category": "policy",
                "publish_time": datetime(2025, 5, 10, 14, 0),
                "sentiment": 0.7,
                "impact_level": "high",
                "is_policy": True,
                "related_sectors": ["半导体"],
                "related_etf_codes": ["512480"],
            },
        ]
        count = storage.upsert_news_articles(articles)
        assert count == 2

        df = storage.get_news_articles(limit=10)
        assert len(df) == 2
        assert "消费回暖" in df["title"].values or "芯片政策" in df["title"].values

    def test_upsert_empty(self, storage):
        count = storage.upsert_news_articles([])
        assert count == 0

    def test_query_by_sector(self, storage):
        articles = [
            {
                "title": "消费新闻",
                "summary": "摘要",
                "source": "cls",
                "sentiment": 0.3,
                "impact_level": "medium",
                "related_sectors": ["消费"],
                "related_etf_codes": ["159928"],
            },
            {
                "title": "军工新闻",
                "summary": "摘要",
                "source": "cls",
                "sentiment": 0.5,
                "impact_level": "medium",
                "related_sectors": ["军工"],
                "related_etf_codes": ["512660"],
            },
        ]
        storage.upsert_news_articles(articles)

        df = storage.get_news_articles(sector="消费")
        assert len(df) >= 1
        assert all("消费" in str(row) for _, row in df.iterrows())


class TestFundamentalStorage:
    def test_upsert_and_query(self, storage):
        df = pd.DataFrame({
            "trade_date": pd.bdate_range("2025-01-01", periods=5).date,
            "pe": [12.0, 12.1, 12.2, 12.3, 12.4],
            "pb": [1.3, 1.31, 1.32, 1.33, 1.34],
            "dividend_yield": [3.0, 3.1, 3.0, 2.9, 3.0],
        })
        count = storage.upsert_fundamental_data(df, "沪深300")
        assert count == 5

        result = storage.get_fundamental_data("沪深300")
        assert len(result) == 5
        assert result["index_name"].iloc[0] == "沪深300"

    def test_upsert_empty(self, storage):
        count = storage.upsert_fundamental_data(pd.DataFrame(), "沪深300")
        assert count == 0

    def test_query_with_date_range(self, storage):
        df = pd.DataFrame({
            "trade_date": pd.bdate_range("2025-01-01", periods=20).date,
            "pe": range(20),
            "pb": [1.0] * 20,
        })
        storage.upsert_fundamental_data(df, "中证500")

        result = storage.get_fundamental_data("中证500", start_date="2025-01-10")
        assert len(result) < 20
        assert len(result) > 0
