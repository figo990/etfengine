"""Data management API tests."""

from datetime import datetime
from types import SimpleNamespace

import pandas as pd
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.routers import data_management
from src.dashboard.task_runner import DashboardTask

client = TestClient(app)


def test_freshness_endpoint(monkeypatch):
    monkeypatch.setattr(
        data_management,
        "get_table_freshness",
        lambda: pd.DataFrame([{"数据": "ETF 行情", "最新日期": "2026-05-15", "记录数": 10}]),
    )

    response = client.get("/api/data-management/freshness")

    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["data"][0]["数据"] == "ETF 行情"


def test_refresh_endpoint_routes_industry_chain_task(monkeypatch):
    captured = {}

    def fake_refresh(chain_id=None, history_days=None, company_codes=None):
        captured["chain_id"] = chain_id
        captured["history_days"] = history_days
        captured["company_codes"] = company_codes
        return {"000001": 12}

    monkeypatch.setattr(
        data_management,
        "refresh_industry_chain_companies",
        fake_refresh,
    )

    response = client.post(
        "/api/data-management/refresh",
        json={
            "task": "industry_chain_companies",
            "chain_id": "ai",
            "history_days": 183,
            "codes": ["000001"],
        },
    )

    assert response.status_code == 200
    assert response.json()["result"] == {"000001": 12}
    assert captured == {
        "chain_id": "ai",
        "history_days": 183,
        "company_codes": ["000001"],
    }


def test_health_endpoint_returns_report(monkeypatch):
    monkeypatch.setattr(
        data_management,
        "get_data_health_report",
        lambda: {
            "issue_count": 1,
            "freshness": pd.DataFrame([{"数据": "ETF 行情", "状态": "过期"}]),
            "gaps": pd.DataFrame([{"数据": "ETF 行情", "代码": "510300"}]),
            "recent_failures": pd.DataFrame(),
            "backfill_plan": [{"task": "etf_daily"}],
        },
    )

    response = client.get("/api/data-management/health")

    assert response.status_code == 200
    assert response.json()["issue_count"] == 1
    assert response.json()["backfill_plan"][0]["task"] == "etf_daily"


def test_refresh_endpoint_routes_industry_chain_fundamentals(monkeypatch):
    captured = {}

    def fake_refresh(chain_id=None, company_codes=None):
        captured["chain_id"] = chain_id
        captured["company_codes"] = company_codes
        return {"fundamentals": {"000001": 1}}

    monkeypatch.setattr(
        data_management,
        "refresh_industry_chain_fundamental_bundle",
        fake_refresh,
    )

    response = client.post(
        "/api/data-management/refresh",
        json={
            "task": "industry_chain_fundamentals",
            "chain_id": "ai",
            "codes": ["000001"],
        },
    )

    assert response.status_code == 200
    assert response.json()["result"] == {"fundamentals": {"000001": 1}}
    assert captured == {"chain_id": "ai", "company_codes": ["000001"]}


def test_refresh_endpoint_routes_news_monitor(monkeypatch):
    monkeypatch.setattr(
        data_management,
        "refresh_news_monitor",
        lambda: {"articles": 2, "chain_links": {"ai": 1}, "mode": "keyword"},
    )

    response = client.post(
        "/api/data-management/refresh",
        json={"task": "news_monitor"},
    )

    assert response.status_code == 200
    assert response.json()["result"]["articles"] == 2


def test_refresh_endpoint_routes_overseas_earnings(monkeypatch):
    monkeypatch.setattr(
        data_management,
        "refresh_overseas_earnings",
        lambda: {"metrics_rows": 3, "analysis_rows": 1},
    )

    response = client.post(
        "/api/data-management/refresh",
        json={"task": "overseas_earnings"},
    )

    assert response.status_code == 200
    assert response.json()["result"]["metrics_rows"] == 3


def test_update_runs_endpoint_serializes_timestamps(monkeypatch):
    class FakeStorage:
        def init_schema(self):
            return None

        def get_data_update_runs(self, task_name=None, limit=100):
            assert task_name == "ETF 行情"
            assert limit == 20
            return pd.DataFrame(
                [
                    {
                        "task_name": "ETF 行情",
                        "started_at": datetime(2026, 5, 16, 9, 0),
                        "finished_at": datetime(2026, 5, 16, 9, 5),
                    }
                ]
            )

        def close(self):
            return None

    monkeypatch.setattr(data_management, "StorageEngine", FakeStorage)

    response = client.get(
        "/api/data-management/update-runs",
        params={"task_name": "ETF 行情", "limit": 20},
    )

    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["data"][0]["started_at"] == "2026-05-16 09:00:00"


def test_submit_refresh_task_endpoint_returns_task_id(monkeypatch):
    captured = {}

    def fake_submit(name, func, *args, task_key=None, task_type=None, tags=None, **kwargs):
        captured["name"] = name
        captured["task_key"] = task_key
        captured["task_type"] = task_type
        captured["tags"] = tags
        captured["kwargs"] = kwargs
        return SimpleNamespace(
            id="task-1",
            status="queued",
            task_key=task_key,
            task_type=task_type,
        )

    monkeypatch.setattr(data_management, "submit_dashboard_task", fake_submit)

    response = client.post(
        "/api/data-management/tasks",
        json={"task": "etf_daily", "codes": ["510300"]},
    )

    assert response.status_code == 200
    assert response.json()["task_id"] == "task-1"
    assert response.json()["status"] == "queued"
    assert captured["name"] == "ETF 行情补采"
    assert captured["task_key"] == "api:etf_daily:510300"
    assert captured["task_type"] == "data_refresh"
    assert captured["tags"] == ["api", "etf_daily"]
    assert captured["kwargs"] == {"codes": ["510300"]}


def test_list_refresh_tasks_endpoint(monkeypatch):
    monkeypatch.setattr(
        data_management,
        "list_dashboard_tasks",
        lambda limit=50: [
            DashboardTask(
                id="task-1",
                name="ETF 行情补采",
                status="success",
                task_key="api:etf_daily:510300",
                task_type="data_refresh",
                result={"510300": 2},
            )
        ],
    )

    response = client.get("/api/data-management/tasks", params={"include_result": True})

    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["data"][0]["result"] == {"510300": 2}


def test_get_refresh_task_endpoint_404(monkeypatch):
    monkeypatch.setattr(data_management, "get_dashboard_task", lambda task_id: None)

    response = client.get("/api/data-management/tasks/missing")

    assert response.status_code == 404
