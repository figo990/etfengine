"""Dashboard report builder tests."""

from datetime import date, datetime
from unittest.mock import patch

import pandas as pd
import pytest

from src.dashboard.report_builder import generate_investment_report
from src.data.storage import StorageEngine


@pytest.fixture
def storage(tmp_path):
    engine = StorageEngine(db_path=str(tmp_path / "report.duckdb"))
    engine.init_schema()
    yield engine
    engine.close()


def _chain_config():
    return {
        "industry_chains": {
            "ai": {
                "name": "人工智能",
                "description": "测试产业链",
                "trend_keywords": ["算力"],
                "etf_codes": ["159915"],
                "index_names": ["沪深300"],
                "segments": {
                    "compute": {
                        "name": "算力",
                        "keywords": ["算力"],
                        "companies": [
                            {"code": "000001", "name": "算力公司", "role": "服务器"},
                        ],
                    },
                },
            }
        }
    }


def test_generate_report_includes_integrated_sections(storage):
    trade_dates = pd.bdate_range("2026-01-01", periods=80).date
    storage.upsert_index_valuation(
        pd.DataFrame(
            {
                "trade_date": trade_dates[-3:],
                "pe": [11.8, 12.0, 12.2],
                "pb": [1.2, 1.21, 1.22],
                "dividend_yield": [3.1, 3.0, 2.9],
                "pe_percentile": [25.0, 26.0, 27.0],
            }
        ),
        "沪深300",
    )
    storage.upsert_bond_yield(
        pd.DataFrame(
            {
                "trade_date": [trade_dates[-1]],
                "cn_10y": [2.3],
                "cn_5y": [2.1],
                "cn_1y": [1.5],
                "us_10y": [4.1],
            }
        )
    )
    storage.upsert_etf_daily(
        pd.DataFrame(
            {
                "trade_date": trade_dates,
                "open": [1.0] * 80,
                "high": [1.1] * 80,
                "low": [0.9] * 80,
                "close": [1 + i * 0.01 for i in range(80)],
                "volume": [1000] * 80,
                "amount": [10000] * 80,
            }
        ),
        "159915",
    )
    storage.upsert_company_daily(
        pd.DataFrame(
            {
                "trade_date": trade_dates,
                "open": [10.0] * 80,
                "high": [11.0] * 80,
                "low": [9.0] * 80,
                "close": [10 + i * 0.1 for i in range(80)],
                "volume": [1000] * 80,
                "amount": [10000] * 80,
            }
        ),
        "000001",
    )
    storage.upsert_news_articles(
        [
            {
                "title": "人工智能算力产业链订单增长",
                "summary": "服务器需求改善",
                "content": "算力公司订单增长",
                "source": "测试来源",
                "category": "finance",
                "publish_time": datetime(2026, 5, 14, 9, 30),
                "sentiment": 0.6,
                "impact_level": "high",
                "is_policy": False,
                "related_sectors": ["人工智能"],
                "related_etf_codes": ["159915"],
            }
        ]
    )
    portfolio_config = {
        "portfolio": {
            "name": "测试组合",
            "total_capital": 100000,
            "holdings": [{"etf": "159915", "name": "创业板ETF", "target_weight": 1.0}],
            "risk_limits": {"max_drawdown_alert": 0.15},
        }
    }

    with patch(
        "src.intelligence.industry_chain_analyzer.get_industry_chain_config",
        return_value=_chain_config(),
    ):
        report = generate_investment_report(
            "周报",
            date(2026, 5, 16),
            storage=storage,
            portfolio_config=portfolio_config,
        )

    assert "## 数据新鲜度" in report
    assert "## 市场估值快照" in report
    assert "## 组合持仓与风险" in report
    assert "## 产业链洞察" in report
    assert "人工智能" in report
    assert "人工智能算力产业链订单增长" in report


def test_generate_report_handles_empty_database(storage):
    report = generate_investment_report(
        "月报",
        date(2026, 5, 16),
        storage=storage,
        portfolio_config={"portfolio": {"holdings": []}},
        include_industry_chains=False,
    )

    assert "暂无组合持仓配置" in report
    assert "暂无新闻数据" in report
