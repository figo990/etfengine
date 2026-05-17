"""Dashboard data refresh task tests."""

from __future__ import annotations

from src.dashboard import data_refresh


def test_execute_backfill_plan_routes_news_and_overseas(monkeypatch):
    calls = []

    monkeypatch.setattr(
        data_refresh,
        "refresh_news_monitor",
        lambda: calls.append("news") or {"articles": 1},
    )
    monkeypatch.setattr(
        data_refresh,
        "refresh_overseas_earnings",
        lambda: calls.append("overseas") or {"metrics_rows": 1},
    )

    result = data_refresh.execute_backfill_plan(
        [
            {"task": "news_monitor", "任务": "新闻监控"},
            {"task": "overseas_earnings", "任务": "外盘季报"},
        ]
    )

    assert calls == ["news", "overseas"]
    assert result[0]["任务"] == "新闻监控"
    assert result[1]["result"]["metrics_rows"] == 1
