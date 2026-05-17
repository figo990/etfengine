"""Scheduler alerting tests."""

from __future__ import annotations

import pandas as pd

from src.scheduler import runner


def test_scheduler_includes_data_quality_job():
    scheduler = runner.create_scheduler()
    job_ids = {job.id for job in scheduler.get_jobs()}

    assert "data_quality_check" in job_ids
    assert "dashboard_task_cleanup" in job_ids
    assert "weekly_report_generation" in job_ids
    assert "monthly_report_generation" in job_ids


def test_data_quality_check_broadcasts_when_report_has_issues(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        "src.dashboard.data_status.get_data_health_report",
        lambda: {
            "issue_count": 2,
            "freshness": pd.DataFrame(
                [{"数据": "ETF 行情", "状态": "过期", "最新日期": "2026-05-10"}]
            ),
            "gaps": pd.DataFrame([{"数据": "ETF 行情", "代码": "510300", "缺口天数": 2}]),
            "recent_failures": pd.DataFrame(),
        },
    )
    monkeypatch.setattr(
        runner,
        "broadcast_configured",
        lambda title, content: captured.update({"title": title, "content": content}) or True,
    )

    runner.data_quality_check()

    assert captured["title"] == "ETFEngine 数据健康告警"
    assert "ETF 行情" in captured["content"]


def test_run_scheduled_job_notifies_on_failure(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        runner,
        "broadcast_configured",
        lambda title, content: captured.update({"title": title, "content": content}) or True,
    )

    try:
        runner._run_scheduled_job("测试任务", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    except RuntimeError:
        pass

    assert captured["title"] == "ETFEngine 调度失败：测试任务"
    assert "boom" in captured["content"]
