"""产业链分析器测试"""

from datetime import datetime
from unittest.mock import patch

import pandas as pd
import pytest

from src.data.storage import StorageEngine
from src.intelligence.industry_chain_analyzer import IndustryChainAnalyzer


@pytest.fixture
def chain_config():
    return {
        "industry_chains": {
            "ai": {
                "name": "人工智能",
                "description": "测试产业链",
                "trend_keywords": ["算力"],
                "etf_codes": ["515980"],
                "index_names": ["中证人工智能"],
                "segments": {
                    "upstream": {
                        "name": "上游",
                        "keywords": ["芯片", "算力"],
                        "companies": [
                            {
                                "code": "000001",
                                "name": "测试芯片",
                                "aliases": ["芯片龙头"],
                                "role": "AI芯片",
                            },
                        ],
                    },
                    "downstream": {
                        "name": "下游",
                        "keywords": ["应用"],
                        "companies": [
                            {"code": "000002", "name": "测试应用", "role": "AI应用"},
                        ],
                    },
                },
            }
        }
    }


@pytest.fixture
def storage(tmp_path):
    engine = StorageEngine(db_path=str(tmp_path / "chain.duckdb"))
    engine.init_schema()
    yield engine
    engine.close()


def test_list_and_flatten_chains(storage, chain_config):
    with patch(
        "src.intelligence.industry_chain_analyzer.get_industry_chain_config",
        return_value=chain_config,
    ):
        analyzer = IndustryChainAnalyzer(storage)
        chains = analyzer.list_chains()
        companies = analyzer.flatten_companies("ai")

    assert chains[0]["chain_id"] == "ai"
    assert chains[0]["company_count"] == 2
    assert companies[0].company_name == "测试芯片"
    assert "芯片龙头" in companies[0].aliases
    assert "AI芯片" in companies[0].keywords


def test_sync_company_master(storage, chain_config):
    with patch(
        "src.intelligence.industry_chain_analyzer.get_industry_chain_config",
        return_value=chain_config,
    ):
        analyzer = IndustryChainAnalyzer(storage)
        count = analyzer.sync_company_master("ai")

    df = storage.get_industry_chain_companies("ai")
    assert count == 2
    assert len(df) == 2


def test_link_news_and_snapshot(storage, chain_config):
    storage.upsert_news_articles(
        [
            {
                "title": "测试芯片带动算力产业链升温",
                "summary": "芯片需求改善",
                "content": "测试芯片公司订单增长",
                "source": "cls",
                "category": "finance",
                "publish_time": datetime(2026, 5, 1, 9, 30),
                "sentiment": 0.6,
                "impact_level": "high",
                "is_policy": False,
                "related_sectors": ["半导体"],
                "related_etf_codes": ["512480"],
            }
        ]
    )
    storage.upsert_company_daily(
        pd.DataFrame(
            {
                "trade_date": pd.bdate_range("2026-01-01", periods=80).date,
                "open": range(80),
                "high": range(1, 81),
                "low": range(80),
                "close": [10 + i * 0.1 for i in range(80)],
                "volume": [1000] * 80,
                "amount": [10000] * 80,
            }
        ),
        "000001",
    )
    storage.upsert_company_fundamentals(
        pd.DataFrame(
            [
                {
                    "report_date": datetime(2025, 12, 31).date(),
                    "report_type": "年报",
                    "revenue": 120.0,
                    "net_profit": 18.0,
                    "roe": 12.5,
                    "revenue_yoy": 20.0,
                    "net_profit_yoy": 30.0,
                    "notice_date": datetime(2026, 3, 30).date(),
                }
            ]
        ),
        "000001",
    )
    storage.upsert_company_valuation(
        pd.DataFrame(
            [
                {
                    "trade_date": datetime(2026, 5, 15).date(),
                    "close": 18.0,
                    "market_cap": 1000.0,
                    "pe_ttm": 22.5,
                    "pe_static": 25.0,
                    "pb": 3.2,
                }
            ]
        ),
        "000001",
    )
    storage.upsert_company_earnings_forecasts(
        pd.DataFrame(
            [
                {
                    "company_code": "000001",
                    "company_name": "测试芯片",
                    "report_period": datetime(2026, 3, 31).date(),
                    "indicator": "归母净利润",
                    "forecast_value": 20.0,
                    "change_pct": 15.0,
                    "forecast_type": "预增",
                    "reason": "订单增长",
                    "last_year_value": 17.0,
                    "announce_date": datetime(2026, 4, 20).date(),
                }
            ]
        )
    )

    with patch(
        "src.intelligence.industry_chain_analyzer.get_industry_chain_config",
        return_value=chain_config,
    ):
        analyzer = IndustryChainAnalyzer(storage)
        linked = analyzer.link_news("ai")
        snapshot = analyzer.build_snapshot("ai", link_news=False)

    assert linked >= 1
    assert snapshot["overview"]["news_count"] >= 1
    assert snapshot["overview"]["high_impact_news_count"] >= 1
    assert snapshot["data_quality"]["company_price_coverage"] == 0.5
    assert snapshot["data_quality"]["company_fundamental_coverage"] == 0.5
    assert snapshot["data_quality"]["company_valuation_coverage"] == 0.5
    chip = next(c for c in snapshot["companies"] if c["company_code"] == "000001")
    assert chip["return_20d"] is not None
    assert chip["roe"] == 12.5
    assert chip["pe_ttm"] == 22.5
    assert chip["latest_forecast_type"] == "预增"


def test_segment_keyword_does_not_attach_to_every_company(storage, chain_config):
    storage.upsert_news_articles(
        [
            {
                "title": "算力基础设施需求提升",
                "summary": "上游环节受关注",
                "content": "算力产业链持续升温",
                "source": "cls",
                "category": "finance",
                "publish_time": datetime(2026, 5, 2, 9, 30),
                "sentiment": 0.2,
                "impact_level": "medium",
                "is_policy": False,
                "related_sectors": ["半导体"],
                "related_etf_codes": ["512480"],
            }
        ]
    )

    with patch(
        "src.intelligence.industry_chain_analyzer.get_industry_chain_config",
        return_value=chain_config,
    ):
        analyzer = IndustryChainAnalyzer(storage)
        analyzer.link_news("ai")
        snapshot = analyzer.build_snapshot("ai", link_news=False)

    upstream = next(s for s in snapshot["segments"] if s["segment_id"] == "upstream")
    assert upstream["news_count"] == 1
    assert all(company["news_count"] == 0 for company in snapshot["companies"])


def test_alias_match_attaches_news_to_company(storage, chain_config):
    storage.upsert_news_articles(
        [
            {
                "title": "芯片龙头订单增长",
                "summary": "别名命中",
                "content": "芯片龙头新增服务器订单",
                "source": "cls",
                "category": "finance",
                "publish_time": datetime(2026, 5, 3, 9, 30),
                "sentiment": 0.5,
                "impact_level": "high",
                "is_policy": False,
                "related_sectors": ["半导体"],
                "related_etf_codes": ["512480"],
            }
        ]
    )

    with patch(
        "src.intelligence.industry_chain_analyzer.get_industry_chain_config",
        return_value=chain_config,
    ):
        analyzer = IndustryChainAnalyzer(storage)
        analyzer.link_news("ai")
        snapshot = analyzer.build_snapshot("ai", link_news=False)

    chip = next(company for company in snapshot["companies"] if company["company_code"] == "000001")
    assert chip["news_count"] == 1
