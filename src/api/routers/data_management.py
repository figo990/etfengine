"""数据管理 API 路由."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from src.api.schemas import DataRefreshRequest
from src.dashboard.data_refresh import (
    refresh_bond_yield,
    refresh_etf_daily,
    refresh_index_valuation,
    refresh_industry_chain_companies,
    refresh_industry_chain_fundamental_bundle,
    refresh_industry_chain_news_links,
    refresh_news_monitor,
    refresh_overseas_earnings,
)
from src.dashboard.data_status import get_data_health_report, get_table_freshness
from src.dashboard.task_runner import (
    dashboard_task_to_dict,
    get_dashboard_task,
    list_dashboard_tasks,
    submit_dashboard_task,
)
from src.data.storage import StorageEngine

router = APIRouter(prefix="/api/data-management", tags=["数据管理"])


def _refresh_task_spec(
    request: DataRefreshRequest,
) -> tuple[str, str, Callable[..., Any], tuple[Any, ...], dict[str, Any]]:
    """Map a refresh request to a controlled callable for sync or async execution."""
    codes_key = ",".join(sorted(request.codes))
    if request.task == "etf_daily":
        return (
            "ETF 行情补采",
            f"api:etf_daily:{codes_key}",
            refresh_etf_daily,
            (),
            {"codes": request.codes or None},
        )
    if request.task == "index_valuation":
        return (
            "指数估值补采",
            f"api:index_valuation:{codes_key}",
            refresh_index_valuation,
            (),
            {"indices": request.codes or None},
        )
    if request.task == "bond_yield":
        return ("国债收益率补采", "api:bond_yield", refresh_bond_yield, (), {})
    if request.task == "industry_chain_companies":
        key = (
            f"api:industry_chain_companies:{request.chain_id or 'all'}:"
            f"{request.history_days or 'default'}:{codes_key}"
        )
        return (
            "产业链企业行情补采",
            key,
            refresh_industry_chain_companies,
            (),
            {
                "chain_id": request.chain_id,
                "history_days": request.history_days,
                "company_codes": request.codes or None,
            },
        )
    if request.task == "industry_chain_fundamentals":
        key = f"api:industry_chain_fundamentals:{request.chain_id or 'all'}:{codes_key}"
        return (
            "产业链企业基本面补采",
            key,
            refresh_industry_chain_fundamental_bundle,
            (),
            {"chain_id": request.chain_id, "company_codes": request.codes or None},
        )
    if request.task == "news_monitor":
        return ("新闻监控补采", "api:news_monitor", refresh_news_monitor, (), {})
    if request.task == "overseas_earnings":
        return ("外盘季报补采", "api:overseas_earnings", refresh_overseas_earnings, (), {})
    return (
        "产业链新闻关联刷新",
        "api:industry_chain_news_links",
        refresh_industry_chain_news_links,
        (),
        {},
    )


@router.get("/freshness")
def get_data_freshness():
    """查询关键数据表的新鲜度."""
    df = get_table_freshness()
    return {"count": len(df), "data": df.to_dict("records")}


@router.get("/health")
def get_data_health():
    """查询数据新鲜度、断档、最近失败和补采建议."""
    report = get_data_health_report()
    return {
        "issue_count": report["issue_count"],
        "freshness": report["freshness"].to_dict("records"),
        "gaps": report["gaps"].to_dict("records"),
        "recent_failures": report["recent_failures"].astype(str).to_dict("records"),
        "backfill_plan": report["backfill_plan"],
    }


@router.get("/update-runs")
def list_update_runs(
    task_name: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
):
    """查询最近的数据更新日志."""
    storage = StorageEngine()
    try:
        storage.init_schema()
        df = storage.get_data_update_runs(task_name=task_name, limit=limit)
    finally:
        storage.close()
    if not df.empty:
        for col in ["started_at", "finished_at"]:
            df[col] = df[col].astype(str)
    return {"count": len(df), "data": df.to_dict("records")}


@router.post("/tasks")
def submit_refresh_task(request: DataRefreshRequest):
    """提交后台数据刷新任务，返回任务 ID 供轮询."""
    name, task_key, func, args, kwargs = _refresh_task_spec(request)
    task = submit_dashboard_task(
        name,
        func,
        *args,
        task_key=task_key,
        task_type="data_refresh",
        tags=["api", request.task],
        **kwargs,
    )
    return {
        "task": request.task,
        "task_id": task.id,
        "status": task.status,
        "task_key": task.task_key,
        "task_type": task.task_type,
    }


@router.get("/tasks")
def list_refresh_tasks(
    limit: int = Query(default=50, ge=1, le=500),
    include_result: bool = Query(default=False),
    task_type: str | None = None,
):
    """查询后台任务列表."""
    tasks = [
        dashboard_task_to_dict(task, include_result=include_result)
        for task in list_dashboard_tasks(limit=limit)
        if task_type is None or task.task_type == task_type
    ]
    return {"count": len(tasks), "data": tasks}


@router.get("/tasks/{task_id}")
def get_refresh_task(task_id: str):
    """查询单个后台任务状态与结果."""
    task = get_dashboard_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return dashboard_task_to_dict(task, include_result=True)


@router.post("/refresh")
def trigger_refresh(request: DataRefreshRequest):
    """触发受控的数据刷新任务."""
    _, _, func, args, kwargs = _refresh_task_spec(request)
    result = func(*args, **kwargs)
    return {"task": request.task, "result": result}
