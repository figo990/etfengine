"""Dashboard data-health tests."""

from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace

import pandas as pd
import pytest

from src.dashboard import data_status
from src.dashboard.data_status import (
    build_backfill_plan,
    get_data_health_report,
    get_recent_market_gaps,
    get_table_freshness,
)
from src.data.storage import StorageEngine


@pytest.fixture
def storage(tmp_path):
    engine = StorageEngine(db_path=str(tmp_path / "health.duckdb"))
    engine.init_schema()
    yield engine
    engine.close()


@pytest.fixture(autouse=True)
def health_settings(monkeypatch):
    config = SimpleNamespace(
        data_health=SimpleNamespace(
            market_data_max_age_days=3,
            news_max_age_days=2,
            company_fundamentals_max_age_days=150,
            company_forecasts_max_age_days=150,
            overseas_earnings_max_age_days=150,
            recent_gap_lookback_days=45,
            recent_gap_tolerance_days=0,
            recent_failure_window_hours=24,
        )
    )
    monkeypatch.setattr(data_status, "settings", lambda: config)
    monkeypatch.setattr(data_status, "_configured_etf_codes", lambda: ["510300", "510500"])


def test_table_freshness_marks_stale_and_missing(storage):
    storage.upsert_etf_daily(
        pd.DataFrame(
            {
                "trade_date": [date(2026, 5, 15)],
                "open": [1.0],
                "high": [1.0],
                "low": [1.0],
                "close": [1.0],
                "volume": [100],
                "amount": [1000],
            }
        ),
        "510300",
    )

    freshness = get_table_freshness(storage, as_of=date(2026, 5, 20))

    etf = freshness[freshness["数据"] == "ETF 行情"].iloc[0]
    bond = freshness[freshness["数据"] == "国债收益率"].iloc[0]
    assert etf["状态"] == "过期"
    assert etf["滞后天数"] == 5
    assert bond["状态"] == "缺失"


def test_recent_market_gaps_detect_missing_codes_and_dates(storage):
    dates = pd.to_datetime(["2026-05-12", "2026-05-13", "2026-05-14"]).date
    base = pd.DataFrame(
        {
            "trade_date": dates,
            "open": [1.0, 1.0, 1.0],
            "high": [1.0, 1.0, 1.0],
            "low": [1.0, 1.0, 1.0],
            "close": [1.0, 1.0, 1.0],
            "volume": [100, 100, 100],
            "amount": [1000, 1000, 1000],
        }
    )
    storage.upsert_etf_daily(base, "510300")
    storage.upsert_etf_daily(base.iloc[[0, 2]], "510500")

    gaps = get_recent_market_gaps(storage, as_of=date(2026, 5, 16))

    row = gaps[(gaps["数据"] == "ETF 行情") & (gaps["代码"] == "510500")].iloc[0]
    assert row["缺口天数"] == 1
    assert "2026-05-13" in row["缺口日期"]


def test_backfill_plan_merges_stale_tables_and_gap_codes(storage):
    freshness = pd.DataFrame(
        [
            {"数据": "ETF 行情", "状态": "过期", "建议动作": "etf_daily"},
            {"数据": "新闻资讯", "状态": "过期", "建议动作": "news_monitor"},
        ]
    )
    gaps = pd.DataFrame(
        [
            {"数据": "ETF 行情", "代码": "510300", "建议动作": "etf_daily"},
            {"数据": "ETF 行情", "代码": "510500", "建议动作": "etf_daily"},
        ]
    )

    plan = build_backfill_plan(freshness, gaps)

    etf_plan = next(item for item in plan if item["task"] == "etf_daily")
    news_plan = next(item for item in plan if item["task"] == "news_monitor")
    assert etf_plan["codes"] == ["510300", "510500"]
    assert etf_plan["可自动执行"] is True
    assert news_plan["可自动执行"] is True


def test_health_report_includes_recent_failures(storage):
    storage.log_data_update_run(
        {
            "task_name": "ETF 行情",
            "status": "partial",
            "finished_at": datetime.now(),
            "failed_count": 1,
        }
    )

    report = get_data_health_report(storage, as_of=date.today())

    assert len(report["recent_failures"]) == 1
    assert report["issue_count"] >= 1
