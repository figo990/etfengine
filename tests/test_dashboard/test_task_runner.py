"""Dashboard background task runner tests."""

from __future__ import annotations

from datetime import datetime, timedelta
from threading import Event

import pytest

import src.dashboard.task_runner as task_runner
from src.data.storage import StorageEngine


@pytest.fixture(autouse=True)
def isolated_task_store(tmp_path, monkeypatch):
    db_path = str(tmp_path / "dashboard_tasks.duckdb")

    class TestStorageEngine(StorageEngine):
        def __init__(self) -> None:
            super().__init__(db_path=db_path)

    monkeypatch.setattr(task_runner, "StorageEngine", TestStorageEngine)
    task_runner._ORPHANS_MARKED = False
    task_runner._TASKS.clear()
    task_runner._FUTURES.clear()
    task_runner._reset_task_store()
    yield
    task_runner._TASKS.clear()
    task_runner._FUTURES.clear()
    task_runner._ORPHANS_MARKED = False
    task_runner._reset_task_store()


def test_dashboard_task_runner_records_success():
    task = task_runner.submit_dashboard_task(
        "测试成功",
        lambda: {"ok": True},
        task_key="test:success",
    )

    finished = task_runner.wait_dashboard_task(task.id, timeout=5)

    assert finished.status == "success"
    assert finished.result == {"ok": True}
    task_runner.clear_finished_dashboard_tasks()


def test_dashboard_task_runner_deduplicates_active_key():
    release = Event()

    def wait_then_return():
        release.wait(timeout=5)
        return 1

    first = task_runner.submit_dashboard_task("测试去重", wait_then_return, task_key="test:dedupe")
    second = task_runner.submit_dashboard_task("测试去重", lambda: 2, task_key="test:dedupe")

    assert second.id == first.id
    release.set()
    task_runner.wait_dashboard_task(first.id, timeout=5)
    task_runner.clear_finished_dashboard_tasks()


def test_dashboard_task_runner_records_failure():
    def fail():
        raise RuntimeError("boom")

    task = task_runner.submit_dashboard_task("测试失败", fail, task_key="test:failure")

    finished = task_runner.wait_dashboard_task(task.id, timeout=5)

    assert finished.status == "failed"
    assert "boom" in finished.error
    task_runner.clear_finished_dashboard_tasks()


def test_dashboard_task_runner_lists_persisted_history_after_memory_clear():
    task = task_runner.submit_dashboard_task(
        "测试持久化",
        lambda: {"rows": 3},
        task_key="test:persisted",
        task_type="test",
        tags=["persisted"],
    )
    task_runner.wait_dashboard_task(task.id, timeout=5)

    task_runner._TASKS.clear()
    task_runner._FUTURES.clear()

    tasks = task_runner.list_dashboard_tasks()

    assert tasks[0].id == task.id
    assert tasks[0].status == "success"
    assert tasks[0].task_type == "test"
    assert tasks[0].tags == ["persisted"]
    assert tasks[0].result == {"rows": 3}


def test_dashboard_task_runner_indexes_success_result():
    task = task_runner.submit_dashboard_task(
        "测试结果索引",
        lambda: {"rows": 3, "files": ["report.md"], "meta": {"ok": True}},
        task_key="test:result-index",
    )
    task_runner.wait_dashboard_task(task.id, timeout=5)

    storage = task_runner.StorageEngine()
    try:
        storage.init_schema()
        results = storage.get_dashboard_task_results(task.id)
    finally:
        storage.close()

    by_key = {row.result_key: row.result_value for row in results.itertuples()}
    assert by_key["rows"] == "3"
    assert by_key["files.__count__"] == "1"
    assert by_key["files.0"] == "report.md"
    assert by_key["meta.ok"] == "true"


def test_dashboard_task_cleanup_keeps_failed_and_interrupted_history():
    old = datetime.now() - timedelta(days=45)
    recent = datetime.now()

    def seed_tasks(storage: StorageEngine) -> None:
        storage.upsert_dashboard_task(
            {
                "id": "old-success",
                "name": "old success",
                "status": "success",
                "task_key": "cleanup:old-success",
                "created_at": old,
                "finished_at": old,
                "result": {"rows": 1},
            }
        )
        storage.upsert_dashboard_task(
            {
                "id": "old-failed",
                "name": "old failed",
                "status": "failed",
                "task_key": "cleanup:old-failed",
                "created_at": old,
                "finished_at": old,
            }
        )
        storage.upsert_dashboard_task(
            {
                "id": "old-interrupted",
                "name": "old interrupted",
                "status": "interrupted",
                "task_key": "cleanup:old-interrupted",
                "created_at": old,
                "finished_at": old,
            }
        )
        storage.upsert_dashboard_task(
            {
                "id": "recent-success",
                "name": "recent success",
                "status": "success",
                "task_key": "cleanup:recent-success",
                "created_at": recent,
                "finished_at": recent,
            }
        )

    task_runner._with_task_store(seed_tasks)

    removed = task_runner.cleanup_old_success_dashboard_tasks(retention_days=30)
    remaining = {task.id for task in task_runner.list_dashboard_tasks(limit=10)}
    deleted_results = task_runner._with_task_store(
        lambda storage: storage.get_dashboard_task_results("old-success")
    )

    assert removed == 1
    assert "old-success" not in remaining
    assert deleted_results.empty
    assert {"old-failed", "old-interrupted", "recent-success"}.issubset(remaining)
