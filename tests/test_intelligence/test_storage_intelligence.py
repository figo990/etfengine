"""DuckDB 新闻和基本面存储测试"""

from datetime import datetime
from types import SimpleNamespace

import pandas as pd
import pytest

import src.data.storage as storage_module
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

    def test_store_news_event_followup(self, storage):
        storage.upsert_news_event_followup("evt-1", "跟踪中", "等待政策细则")

        result = storage.get_news_event_followups(["evt-1"])
        assert len(result) == 1
        assert result["status"].iloc[0] == "跟踪中"
        assert result["note"].iloc[0] == "等待政策细则"


def test_storage_applies_configured_duckdb_memory_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(
        storage_module,
        "settings",
        lambda: SimpleNamespace(
            database=SimpleNamespace(
                path=str(tmp_path / "default.duckdb"),
                duckdb_memory_limit="256MB",
            )
        ),
    )
    engine = StorageEngine(db_path=str(tmp_path / "limited.duckdb"))
    try:
        result = engine.conn.execute(
            "SELECT current_setting('memory_limit') AS memory_limit"
        ).fetchone()
    finally:
        engine.close()

    assert result is not None
    assert "244" in str(result[0]) or "256" in str(result[0])


class TestBacktestScenarioStorage:
    def test_save_backtest_scenario(self, storage):
        scenario_id = storage.save_backtest_scenario(
            {
                "scenario_name": "普通定投基线",
                "etf_code": "510300",
                "strategy_name": "普通定投",
                "params": {"amount": 1000, "frequency": "monthly"},
                "start_date": datetime(2023, 1, 1).date(),
                "end_date": datetime(2025, 12, 31).date(),
                "total_return": 0.12,
                "annual_return": 0.04,
                "max_drawdown": 0.08,
                "sharpe_ratio": 0.9,
                "total_trades": 36,
                "total_invested": 36000,
                "final_value": 40320,
            }
        )

        result = storage.get_backtest_scenarios()
        assert len(result) == 1
        assert result["id"].iloc[0] == scenario_id
        assert result["scenario_name"].iloc[0] == "普通定投基线"


class TestFundamentalStorage:
    def test_upsert_and_query(self, storage):
        df = pd.DataFrame(
            {
                "trade_date": pd.bdate_range("2025-01-01", periods=5).date,
                "pe": [12.0, 12.1, 12.2, 12.3, 12.4],
                "pb": [1.3, 1.31, 1.32, 1.33, 1.34],
                "dividend_yield": [3.0, 3.1, 3.0, 2.9, 3.0],
            }
        )
        count = storage.upsert_fundamental_data(df, "沪深300")
        assert count == 5

        result = storage.get_fundamental_data("沪深300")
        assert len(result) == 5
        assert result["index_name"].iloc[0] == "沪深300"

    def test_upsert_empty(self, storage):
        count = storage.upsert_fundamental_data(pd.DataFrame(), "沪深300")
        assert count == 0

    def test_query_with_date_range(self, storage):
        df = pd.DataFrame(
            {
                "trade_date": pd.bdate_range("2025-01-01", periods=20).date,
                "pe": range(20),
                "pb": [1.0] * 20,
            }
        )
        storage.upsert_fundamental_data(df, "中证500")

        result = storage.get_fundamental_data("中证500", start_date="2025-01-10")
        assert len(result) < 20
        assert len(result) > 0


class TestETFInfoStorage:
    def test_upsert_etf_info_sets_updated_at(self, storage):
        rows = pd.DataFrame(
            [
                {
                    "code": "510300",
                    "name": "沪深300ETF",
                    "index_tracked": "沪深300",
                    "category": "宽基",
                    "fund_size": 100.0,
                    "inception_date": datetime(2012, 5, 4).date(),
                }
            ]
        )

        assert storage.upsert_etf_info(rows) == 1
        result = storage.get_etf_info("510300")

        assert result["name"].iloc[0] == "沪深300ETF"
        assert pd.notna(result["updated_at"].iloc[0])


class TestDataUpdateRuns:
    def test_log_and_query_update_run(self, storage):
        run_id = storage.log_data_update_run(
            {
                "task_name": "产业链企业行情",
                "status": "partial",
                "success_count": 2,
                "skipped_count": 1,
                "failed_count": 1,
                "rows_written": 120,
                "details": {"000001": 60, "000002": -1},
                "error_message": "部分失败",
            }
        )

        result = storage.get_data_update_runs(limit=10)
        assert len(result) == 1
        assert result["id"].iloc[0] == run_id
        assert result["task_name"].iloc[0] == "产业链企业行情"
        assert result["status"].iloc[0] == "partial"
        assert result["rows_written"].iloc[0] == 120

    def test_query_update_run_by_task_name(self, storage):
        storage.log_data_update_run({"task_name": "ETF 行情", "status": "success"})
        storage.log_data_update_run({"task_name": "指数估值", "status": "success"})

        result = storage.get_data_update_runs(task_name="ETF 行情", limit=10)
        assert len(result) == 1
        assert result["task_name"].iloc[0] == "ETF 行情"


class TestIndustryChainCompanyStorage:
    def test_store_aliases(self, storage):
        count = storage.upsert_industry_chain_companies(
            [
                {
                    "chain_id": "ai",
                    "chain_name": "人工智能",
                    "segment_id": "upstream",
                    "segment_name": "上游",
                    "company_code": "000001",
                    "company_name": "测试公司",
                    "role": "AI芯片",
                    "keywords": ["GPU"],
                    "aliases": ["测试简称"],
                }
            ]
        )

        result = storage.get_industry_chain_companies("ai")
        assert count == 1
        assert "aliases" in result.columns
        assert "测试简称" in result["aliases"].iloc[0]


class TestCompanyFundamentalStorage:
    def test_store_company_fundamentals_valuation_and_forecasts(self, storage):
        fundamentals = pd.DataFrame(
            [
                {
                    "report_date": datetime(2025, 12, 31).date(),
                    "report_type": "年报",
                    "revenue": 100.0,
                    "net_profit": 12.0,
                    "roe": 8.5,
                    "revenue_yoy": 15.0,
                    "net_profit_yoy": 20.0,
                    "notice_date": datetime(2026, 3, 28).date(),
                }
            ]
        )
        valuation = pd.DataFrame(
            [
                {
                    "trade_date": datetime(2026, 5, 15).date(),
                    "close": 12.3,
                    "market_cap": 1000.0,
                    "pe_ttm": 22.0,
                    "pe_static": 25.0,
                    "pb": 3.2,
                }
            ]
        )
        forecasts = pd.DataFrame(
            [
                {
                    "company_code": "000001",
                    "company_name": "测试公司",
                    "report_period": datetime(2026, 3, 31).date(),
                    "indicator": "归母净利润",
                    "forecast_value": 13.0,
                    "change_pct": 18.0,
                    "forecast_type": "预增",
                    "reason": "订单增长",
                    "last_year_value": 11.0,
                    "announce_date": datetime(2026, 4, 10).date(),
                }
            ]
        )

        assert storage.upsert_company_fundamentals(fundamentals, "000001") == 1
        assert storage.upsert_company_valuation(valuation, "000001") == 1
        assert storage.upsert_company_earnings_forecasts(forecasts) == 1

        fundamentals_result = storage.get_company_fundamentals("000001")
        valuation_result = storage.get_company_valuation("000001")
        forecasts_result = storage.get_company_earnings_forecasts("000001")
        assert fundamentals_result["roe"].iloc[0] == 8.5
        assert valuation_result["pe_ttm"].iloc[0] == 22.0
        assert forecasts_result["forecast_type"].iloc[0] == "预增"
