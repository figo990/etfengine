"""Lightweight in-process task runner for Dashboard-triggered jobs."""

from __future__ import annotations

import json
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from threading import Lock
from typing import Any
from uuid import uuid4

from loguru import logger

from src.core.config import settings
from src.data.storage import StorageEngine


@dataclass
class DashboardTask:
    id: str
    name: str
    status: str = "queued"
    task_key: str = ""
    task_type: str = "general"
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result: Any = None
    error: str = ""


_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="dashboard-task")
_TASKS: dict[str, DashboardTask] = {}
_FUTURES: dict[str, Future] = {}
_LOCK = Lock()
_ORPHANS_MARKED = False
_ACTIVE_STATUSES = {"queued", "running"}
_CLEARABLE_STATUSES = {"success"}


def _is_active(task: DashboardTask) -> bool:
    return task.status in _ACTIVE_STATUSES


def _normalize_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if str(value) in {"", "NaT", "None"}:
        return None
    if hasattr(value, "to_pydatetime"):
        converted = value.to_pydatetime()
        return converted if isinstance(converted, datetime) else None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _parse_result(value: Any) -> Any:
    if value is None or str(value) == "":
        return None
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _parse_tags(value: Any) -> list[str]:
    if value is None or str(value) == "":
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    return [str(value)]


def _infer_task_type(task_key: str) -> str:
    if task_key.startswith("backtest:"):
        return "backtest"
    if task_key.startswith("report:"):
        return "report"
    if "news" in task_key:
        return "news"
    if "industry_chain" in task_key:
        return "industry_chain"
    if task_key.startswith(("api:", "manual:", "sidebar:", "health-backfill:", "portfolio:")):
        return "data_refresh"
    return "general"


def _task_from_record(record: dict[str, Any]) -> DashboardTask:
    task_key = str(record.get("task_key", ""))
    task_type = str(record.get("task_type") or "")
    return DashboardTask(
        id=str(record.get("id", "")),
        name=str(record.get("name", "")),
        status=str(record.get("status", "unknown")),
        task_key=task_key,
        task_type=task_type if task_type and task_type != "None" else _infer_task_type(task_key),
        tags=_parse_tags(record.get("tags")),
        created_at=_normalize_datetime(record.get("created_at")) or datetime.now(),
        started_at=_normalize_datetime(record.get("started_at")),
        finished_at=_normalize_datetime(record.get("finished_at")),
        result=_parse_result(record.get("result")),
        error=str(record.get("error") or ""),
    )


def _persist_task(task: DashboardTask) -> None:
    storage = StorageEngine()
    try:
        storage.init_schema()
        storage.upsert_dashboard_task(
            {
                "id": task.id,
                "name": task.name,
                "status": task.status,
                "task_key": task.task_key,
                "task_type": task.task_type,
                "tags": task.tags,
                "created_at": task.created_at,
                "started_at": task.started_at,
                "finished_at": task.finished_at,
                "result": task.result,
                "error": task.error,
            }
        )
    except Exception as exc:
        logger.warning(f"持久化后台任务状态失败: {exc}")
    finally:
        storage.close()


def _ensure_task_store() -> None:
    global _ORPHANS_MARKED
    storage = StorageEngine()
    try:
        storage.init_schema()
        if not _ORPHANS_MARKED:
            interrupted = storage.mark_orphaned_dashboard_tasks()
            if interrupted:
                logger.info(f"已标记 {interrupted} 个重启前未完成的后台任务为中断")
            _ORPHANS_MARKED = True
    except Exception as exc:
        logger.warning(f"初始化后台任务持久化表失败: {exc}")
    finally:
        storage.close()


def _load_persisted_task(task_id: str) -> DashboardTask | None:
    _ensure_task_store()
    storage = StorageEngine()
    try:
        storage.init_schema()
        df = storage.get_dashboard_task(task_id)
    except Exception as exc:
        logger.warning(f"读取后台任务状态失败: {exc}")
        return None
    finally:
        storage.close()
    if df.empty:
        return None
    return _task_from_record(df.iloc[0].to_dict())


def _load_persisted_tasks(limit: int) -> list[DashboardTask]:
    _ensure_task_store()
    storage = StorageEngine()
    try:
        storage.init_schema()
        df = storage.get_dashboard_tasks(limit=limit)
    except Exception as exc:
        logger.warning(f"读取后台任务列表失败: {exc}")
        return []
    finally:
        storage.close()
    return [_task_from_record(row.to_dict()) for _, row in df.iterrows()]


def submit_dashboard_task(
    name: str,
    func: Callable[..., Any],
    *args: Any,
    task_key: str | None = None,
    task_type: str | None = None,
    tags: list[str] | None = None,
    **kwargs: Any,
) -> DashboardTask:
    """Submit a background task, de-duplicating active tasks with the same key."""
    _ensure_task_store()
    dedupe_key = task_key or name
    with _LOCK:
        for task in _TASKS.values():
            if task.task_key == dedupe_key and _is_active(task):
                return task

        task = DashboardTask(
            id=str(uuid4()),
            name=name,
            task_key=dedupe_key,
            task_type=task_type or _infer_task_type(dedupe_key),
            tags=tags or [],
        )
        _TASKS[task.id] = task
        _persist_task(task)

    def _run() -> Any:
        with _LOCK:
            task.status = "running"
            task.started_at = datetime.now()
            _persist_task(task)
        try:
            result = func(*args, **kwargs)
        except Exception as exc:
            logger.exception(f"后台任务失败: {name}")
            with _LOCK:
                task.status = "failed"
                task.error = str(exc)
                task.finished_at = datetime.now()
                _persist_task(task)
            raise
        with _LOCK:
            task.status = "success"
            task.result = result
            task.finished_at = datetime.now()
            _persist_task(task)
        return result

    future = _EXECUTOR.submit(_run)
    with _LOCK:
        _FUTURES[task.id] = future
    return task


def get_dashboard_task(task_id: str) -> DashboardTask | None:
    with _LOCK:
        task = _TASKS.get(task_id)
    return task or _load_persisted_task(task_id)


def list_dashboard_tasks(limit: int = 50) -> list[DashboardTask]:
    persisted = {task.id: task for task in _load_persisted_tasks(limit=limit)}
    with _LOCK:
        for task in _TASKS.values():
            persisted[task.id] = task
        tasks = sorted(persisted.values(), key=lambda item: item.created_at, reverse=True)
    return tasks[:limit]


def wait_dashboard_task(task_id: str, timeout: float | None = None) -> DashboardTask:
    future = _FUTURES.get(task_id)
    if future is not None:
        try:
            future.result(timeout=timeout)
        except Exception:
            pass
    task = get_dashboard_task(task_id)
    if task is None:
        raise KeyError(task_id)
    return task


def task_status_rows(limit: int = 20) -> list[dict[str, Any]]:
    """Return task state rows suitable for st.dataframe."""
    rows = []
    for task in list_dashboard_tasks(limit):
        rows.append(
            {
                "任务ID": task.id,
                "任务": task.name,
                "状态": task.status,
                "类型": task.task_type,
                "任务Key": task.task_key,
                "创建时间": task.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "开始时间": task.started_at.strftime("%Y-%m-%d %H:%M:%S")
                if task.started_at
                else "",
                "结束时间": task.finished_at.strftime("%Y-%m-%d %H:%M:%S")
                if task.finished_at
                else "",
                "错误": task.error,
            }
        )
    return rows


def dashboard_task_to_dict(task: DashboardTask, *, include_result: bool = True) -> dict[str, Any]:
    """Serialize a dashboard task for API responses and generic result views."""
    row: dict[str, Any] = {
        "id": task.id,
        "name": task.name,
        "status": task.status,
        "task_key": task.task_key,
        "task_type": task.task_type,
        "tags": task.tags,
        "created_at": task.created_at.isoformat(sep=" "),
        "started_at": task.started_at.isoformat(sep=" ") if task.started_at else None,
        "finished_at": task.finished_at.isoformat(sep=" ") if task.finished_at else None,
        "error": task.error,
    }
    if include_result:
        row["result"] = task.result
    return row


def clear_finished_dashboard_tasks() -> int:
    """Remove successful tasks from the in-memory registry and persisted history."""
    with _LOCK:
        finished_ids = [
            task_id for task_id, task in _TASKS.items() if task.status in _CLEARABLE_STATUSES
        ]
        for task_id in finished_ids:
            _TASKS.pop(task_id, None)
            _FUTURES.pop(task_id, None)
    _ensure_task_store()
    storage = StorageEngine()
    try:
        storage.init_schema()
        persisted_removed = storage.delete_finished_dashboard_tasks()
    finally:
        storage.close()
    return max(len(finished_ids), persisted_removed)


def cleanup_old_success_dashboard_tasks(retention_days: int | None = None) -> int:
    """Delete successful tasks older than the configured retention window."""
    if retention_days is None:
        try:
            retention_days = settings().scheduler.dashboard_task_retention_days
        except Exception:
            retention_days = 30
    cutoff = datetime.now() - timedelta(days=max(retention_days, 0))
    with _LOCK:
        removable = [
            task_id
            for task_id, task in _TASKS.items()
            if task.status == "success" and (task.finished_at or task.created_at) < cutoff
        ]
        for task_id in removable:
            _TASKS.pop(task_id, None)
            _FUTURES.pop(task_id, None)

    _ensure_task_store()
    storage = StorageEngine()
    try:
        storage.init_schema()
        persisted_removed = storage.delete_success_dashboard_tasks_older_than(retention_days)
    finally:
        storage.close()
    return max(len(removable), persisted_removed)
