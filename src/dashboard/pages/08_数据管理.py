"""数据管理：手工更新、定时采集、数据健康检查与后台任务。"""

from __future__ import annotations

import json
from datetime import date

import pandas as pd
import streamlit as st

from src.core.config import settings
from src.dashboard.components import render_page_header, render_page_help
from src.dashboard.data_refresh import (
    execute_backfill_plan,
    refresh_bond_yield,
    refresh_etf_daily,
    refresh_etf_info,
    refresh_fundamental_data,
    refresh_index_valuation,
    refresh_industry_chain_companies,
    refresh_industry_chain_fundamental_bundle,
    refresh_industry_chain_news_links,
    refresh_news_monitor,
    refresh_overseas_earnings,
    refresh_trade_signals,
    retry_failed_update,
)
from src.dashboard.data_status import get_data_health_report
from src.dashboard.scheduler_status import get_scheduler_processes
from src.dashboard.styles import configure_dashboard_page, inject_global_styles
from src.dashboard.task_runner import (
    clear_finished_dashboard_tasks,
    submit_dashboard_task,
    task_status_rows,
)
from src.data.storage import StorageEngine
from src.intelligence.industry_chain_analyzer import IndustryChainAnalyzer

configure_dashboard_page("数据管理")
inject_global_styles()
render_page_header("数据管理", "手工更新、定时采集、数据健康检查与后台任务。")
render_page_help(
    [
        (
            "页面用途",
            "用于管理全站数据采集、补采、定时任务、数据健康检查、更新日志和后台任务状态。",
        ),
        (
            "主要功能",
            [
                "手工执行：把行情、估值、新闻、产业链等更新提交到后台任务。",
                "定时采集：查看调度器状态、计划时间和启动命令。",
                "数据健康：检查新鲜度、实体覆盖率、历史深度、断档和失败任务。",
                "更新日志：查看数据更新记录，失败任务可按明细重试。",
            ],
        ),
        (
            "推荐使用顺序",
            [
                "打开「数据健康」查看新鲜度、覆盖率与失败任务。",
                "在「手工执行」按建议提交补采；产业链批量任务需先勾选确认。",
                "在「更新日志」核对结果，对失败记录使用重试。",
                "通过侧栏「后台任务」查看运行中/失败摘要。",
            ],
        ),
        (
            "使用建议",
            "并行查看 DuckDB 时优先使用只读连接，避免与后台写入冲突。",
        ),
    ]
)

cfg = settings()
scheduler_cfg = cfg.scheduler
history_days = getattr(scheduler_cfg, "industry_chain_history_days", 183)
industry_time = getattr(scheduler_cfg, "industry_chain_update_time", "20:10")


def _submit_manual_task(name: str, func, *args, task_key: str, **kwargs) -> None:
    task = submit_dashboard_task(
        name,
        func,
        *args,
        task_key=task_key,
        task_type="data_refresh",
        tags=["manual"],
        **kwargs,
    )
    st.success(f"已提交后台任务：{task.id}")


def _render_manual_tab() -> None:
    st.subheader("手工执行")
    st.caption("手工更新统一进入后台任务队列，页面可继续浏览；结果会写入后台任务状态和更新日志。")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### 基础市场数据")
        tasks = [
            ("更新 ETF 行情", "ETF 行情补采", refresh_etf_daily, "manual:etf_daily"),
            ("更新 ETF 基础信息", "ETF 基础信息补采", refresh_etf_info, "manual:etf_info"),
            ("更新指数估值", "指数估值补采", refresh_index_valuation, "manual:index_valuation"),
            (
                "更新指数基本面",
                "指数基本面补采",
                refresh_fundamental_data,
                "manual:fundamental_data",
            ),
            ("更新国债收益率", "国债收益率补采", refresh_bond_yield, "manual:bond_yield"),
        ]
        for button_label, task_name, func, key in tasks:
            if st.button(button_label, width="stretch"):
                _submit_manual_task(task_name, func, task_key=key)

        st.markdown("#### 资讯与海外数据")
        if st.button("后台更新新闻监控", width="stretch"):
            _submit_manual_task(
                "新闻监控补采",
                refresh_news_monitor,
                task_key="manual:news_monitor",
            )
        if st.button("后台更新外盘季报", width="stretch"):
            _submit_manual_task(
                "外盘季报补采",
                refresh_overseas_earnings,
                task_key="manual:overseas_earnings",
            )
        if st.button("生成交易信号", width="stretch"):
            _submit_manual_task(
                "交易信号生成",
                refresh_trade_signals,
                task_key="manual:trade_signals",
            )

    with col2:
        st.markdown("#### 产业链数据")
        chains = IndustryChainAnalyzer().list_chains()
        chain_options = {"全部产业链": None} | {item["name"]: item["chain_id"] for item in chains}
        chain_name = st.selectbox("产业链范围", list(chain_options))
        manual_history_days = st.number_input(
            "首次/补历史天数",
            min_value=30,
            max_value=1000,
            value=int(history_days),
            step=30,
        )
        selected_chain_id = chain_options[chain_name]
        confirm_heavy = st.checkbox(
            "确认提交耗时较长的产业链补采任务",
            value=False,
            key="manual_industry_chain_confirm",
        )

        if st.button(
            "更新产业链企业行情",
            type="primary",
            width="stretch",
            disabled=not confirm_heavy,
        ):
            _submit_manual_task(
                "产业链企业行情补采",
                refresh_industry_chain_companies,
                chain_id=selected_chain_id,
                history_days=int(manual_history_days),
                task_key=(
                    f"manual:industry_chain_companies:{selected_chain_id}:"
                    f"{int(manual_history_days)}"
                ),
            )
        if st.button("更新产业链企业基本面", width="stretch", disabled=not confirm_heavy):
            _submit_manual_task(
                "产业链企业基本面补采",
                refresh_industry_chain_fundamental_bundle,
                chain_id=selected_chain_id,
                task_key=f"manual:industry_chain_fundamentals:{selected_chain_id}",
            )
        if st.button("刷新产业链新闻关联", width="stretch", disabled=not confirm_heavy):
            _submit_manual_task(
                "产业链新闻关联刷新",
                refresh_industry_chain_news_links,
                task_key="manual:industry_chain_news_links",
            )


def _render_schedule_tab() -> None:
    st.subheader("定时采集")
    processes = get_scheduler_processes()
    if processes:
        st.success(f"调度器运行中：{len(processes)} 个进程")
        st.dataframe(pd.DataFrame(processes), width="stretch", hide_index=True)
    else:
        st.warning("未检测到调度器进程。需要常驻定时采集时，请在终端启动。")

    schedule_rows = [
        ("ETF/指数/债券日更", f"交易日 {scheduler_cfg.daily_update_time}"),
        ("策略信号生成", f"交易日 {scheduler_cfg.signal_generate_time}"),
        ("产业链企业行情", f"交易日 {industry_time}"),
        ("产业链企业基本面", "随产业链任务一并刷新"),
        ("数据健康检查", f"交易日 {scheduler_cfg.data_quality_check_time}"),
        ("后台成功任务清理", f"每日 {scheduler_cfg.dashboard_task_cleanup_time}"),
        ("产业链首次历史窗口", f"{history_days} 天"),
        ("后台成功任务保留", f"{scheduler_cfg.dashboard_task_retention_days} 天"),
        ("自动周报", f"{scheduler_cfg.weekly_report_day} {scheduler_cfg.weekly_report_time}"),
        ("自动月报", f"每月最后一天 {scheduler_cfg.monthly_report_time}"),
        ("新闻监控", "每小时一次"),
        ("外盘季报", "每周日 09:05"),
    ]
    st.dataframe(
        pd.DataFrame(schedule_rows, columns=["任务", "计划"]),
        width="stretch",
        hide_index=True,
    )
    st.code("python -m src.scheduler.runner", language="bash")
    st.info("运行上面的命令后，调度器会常驻执行。页面上的按钮仍可随时手工补采。")

    try:
        from src.scheduler.runner import create_scheduler

        scheduler = create_scheduler()
        jobs = [
            {"任务ID": job.id, "名称": job.name, "触发器": str(job.trigger)}
            for job in scheduler.get_jobs()
        ]
        st.dataframe(pd.DataFrame(jobs), width="stretch", hide_index=True)
    except Exception as exc:
        st.warning(f"无法读取调度任务：{exc}")


def _load_health_report() -> tuple[dict, list[dict]]:
    storage = StorageEngine()
    try:
        storage.init_schema()
        report = get_data_health_report(storage)
        rows = []
        for chain in IndustryChainAnalyzer(storage).list_chains():
            snapshot = IndustryChainAnalyzer(storage).build_snapshot(
                chain["chain_id"],
                link_news=False,
            )
            quality = snapshot.get("data_quality", {})
            rows.append(
                {
                    "产业链": snapshot["name"],
                    "企业数": snapshot["overview"]["company_count"],
                    "企业行情覆盖率": f"{quality.get('company_price_coverage', 0):.0%}",
                    "企业财务覆盖率": f"{quality.get('company_fundamental_coverage', 0):.0%}",
                    "企业估值覆盖率": f"{quality.get('company_valuation_coverage', 0):.0%}",
                    "最新行情日期": quality.get("latest_market_date", ""),
                    "最新财报日期": quality.get("latest_report_date", ""),
                    "相关新闻": snapshot["overview"]["news_count"],
                    "业绩预告数": quality.get("earnings_forecast_count", 0),
                    "缺失企业数": len(quality.get("missing_company_prices", [])),
                    "缺失财务数": len(quality.get("missing_company_fundamentals", [])),
                    "缺失估值数": len(quality.get("missing_company_valuations", [])),
                }
            )
        return report, rows
    finally:
        storage.close()


def _health_df(report: dict, key: str) -> pd.DataFrame:
    value = report.get(key)
    return value if isinstance(value, pd.DataFrame) else pd.DataFrame()


def _health_list(report: dict, key: str) -> list:
    value = report.get(key)
    return value if isinstance(value, list) else []


def _render_health_tab() -> None:
    st.subheader("数据健康")
    st.caption("下方表格支持横向滚动、列筛选与 CSV 导出；关键结论请结合各节标题与状态提示。")
    try:
        health_report, rows = _load_health_report()
    except Exception as exc:
        st.warning(f"DuckDB 暂不可用，数据健康详情暂无法加载：{exc}")
        health_report = get_data_health_report()
        rows = []

    if rows:
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    else:
        st.info("暂无产业链配置")

    sections = [
        ("全局新鲜度", _health_df(health_report, "freshness"), "暂无新鲜度数据。"),
        ("实体覆盖率", _health_df(health_report, "coverage"), "暂无可检查的实体覆盖率。"),
        ("历史深度", _health_df(health_report, "history_depth"), "暂无历史深度数据。"),
    ]
    for title, frame, empty_message in sections:
        st.markdown(f"#### {title}")
        if frame.empty:
            st.info(empty_message)
        else:
            st.dataframe(frame, width="stretch", hide_index=True)

    st.markdown("#### 近端断档")
    gaps = _health_df(health_report, "gaps")
    if gaps.empty:
        st.success("近端日线未发现断档。")
    else:
        st.dataframe(gaps, width="stretch", hide_index=True)

    st.markdown("#### 最近失败")
    recent_failures = _health_df(health_report, "recent_failures")
    if recent_failures.empty:
        st.success("最近 24 小时未发现失败或部分成功任务。")
    else:
        display_failures = recent_failures.copy()
        display_failures["started_at"] = display_failures["started_at"].astype(str)
        display_failures["finished_at"] = display_failures["finished_at"].astype(str)
        st.dataframe(display_failures, width="stretch", hide_index=True)

    st.markdown("#### 补采建议")
    plan = _health_list(health_report, "backfill_plan")
    if not plan:
        st.success("当前无需补采。")
    else:
        display_plan = pd.DataFrame(plan).copy()
        display_plan["codes"] = display_plan["codes"].map(
            lambda codes: "全部" if not codes else ", ".join(codes)
        )
        st.dataframe(display_plan, width="stretch", hide_index=True)
        auto_plan = [item for item in plan if item["可自动执行"]]
        if auto_plan and st.button("按建议后台补采", type="primary"):
            task_key = "health-backfill:" + ",".join(item["task"] for item in auto_plan)
            task = submit_dashboard_task(
                "数据健康建议补采",
                execute_backfill_plan,
                auto_plan,
                task_key=task_key,
                task_type="data_refresh",
                tags=["health_backfill"],
            )
            st.success(f"已提交后台补采任务：{task.id}")

    st.caption(f"检查日期：{date.today().isoformat()}")
    st.markdown("#### DuckDB 只读连接")
    db_path = cfg.database.path.replace("\\", "/")
    st.code(f"duckdb -readonly {db_path}", language="bash")
    st.code(
        (
            'python -c "import duckdb; '
            f"con=duckdb.connect(r'{db_path}', read_only=True); "
            "print(con.sql('show tables').df())\""
        ),
        language="powershell",
    )
    st.info("并行查看数据库时优先使用只读连接。写入前请确认 Dashboard、API 或调度器未占用写锁。")


def _render_logs_tab() -> None:
    st.subheader("更新日志")
    st.markdown("#### 后台任务状态")
    task_rows = task_status_rows()
    if task_rows:
        st.dataframe(pd.DataFrame(task_rows), width="stretch", hide_index=True)
        if st.button("清理成功后台任务"):
            removed = clear_finished_dashboard_tasks()
            st.success(f"已清理 {removed} 个成功任务")
            st.rerun()
    else:
        st.caption("暂无后台任务。")

    limit = st.slider("显示条数", min_value=20, max_value=300, value=100, step=20)
    storage = StorageEngine()
    try:
        storage.init_schema()
        logs = storage.get_data_update_runs(limit=limit)
    except Exception as exc:
        st.warning(f"DuckDB 暂不可用，更新日志暂无法加载：{exc}")
        logs = pd.DataFrame()
    finally:
        storage.close()

    if logs.empty:
        st.info("暂无更新日志。执行一次手工更新或启动调度器后会自动记录。")
        return

    display = logs.copy()
    display["started_at"] = display["started_at"].astype(str)
    display["finished_at"] = display["finished_at"].astype(str)
    display = display.rename(
        columns={
            "task_name": "任务",
            "status": "状态",
            "started_at": "开始时间",
            "finished_at": "结束时间",
            "duration_seconds": "耗时秒",
            "success_count": "成功",
            "skipped_count": "跳过",
            "failed_count": "失败",
            "rows_written": "写入行数",
            "error_message": "错误",
        }
    )
    show_cols = ["任务", "状态", "开始时间", "耗时秒", "成功", "跳过", "失败", "写入行数", "错误"]
    st.dataframe(display[show_cols], width="stretch", hide_index=True)

    st.markdown("#### 日志详情与失败重试")
    options = {
        f"{row.task_name} | {row.started_at} | {row.status}": row.id for row in logs.itertuples()
    }
    selected_label = st.selectbox("选择日志", list(options))
    selected = logs[logs["id"] == options[selected_label]].iloc[0]
    try:
        details = json.loads(selected.get("details") or "{}")
    except json.JSONDecodeError:
        details = {"raw": selected.get("details", "")}

    st.json(details)
    failed_count = int(selected.get("failed_count") or 0)
    if failed_count > 0:
        if st.button("只重试失败项", type="primary"):
            _submit_manual_task(
                f"失败项重试：{selected['task_name']}",
                retry_failed_update,
                str(selected["task_name"]),
                details,
                task_key=f"retry:{selected['id']}",
            )
    else:
        st.caption("该任务没有失败项，无需重试。")


tab_manual, tab_schedule, tab_health, tab_logs = st.tabs(
    ["手工执行", "定时采集", "数据健康", "更新日志"]
)
with tab_manual:
    _render_manual_tab()
with tab_schedule:
    _render_schedule_tab()
with tab_health:
    _render_health_tab()
with tab_logs:
    _render_logs_tab()
