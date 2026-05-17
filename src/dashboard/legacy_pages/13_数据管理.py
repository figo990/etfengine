"""数据管理：手工更新、定时采集配置说明与数据健康检查"""

from __future__ import annotations

import json
from datetime import date

import pandas as pd
import streamlit as st

from src.core.config import settings
from src.dashboard.data_refresh import (
    execute_backfill_plan,
    refresh_bond_yield,
    refresh_etf_daily,
    refresh_index_valuation,
    refresh_industry_chain_companies,
    refresh_industry_chain_fundamental_bundle,
    refresh_industry_chain_news_links,
    refresh_news_monitor,
    refresh_overseas_earnings,
    retry_failed_update,
)
from src.dashboard.data_status import get_data_health_report
from src.dashboard.scheduler_status import get_scheduler_processes
from src.dashboard.task_runner import (
    clear_finished_dashboard_tasks,
    submit_dashboard_task,
    task_status_rows,
)
from src.data.storage import StorageEngine
from src.intelligence.industry_chain_analyzer import IndustryChainAnalyzer

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

tab_manual, tab_schedule, tab_health, tab_logs = st.tabs(
    [
        "手工执行",
        "定时采集",
        "数据健康",
        "更新日志",
    ]
)

with tab_manual:
    st.subheader("手工执行")
    st.caption("手工更新统一进入后台任务队列，页面可继续浏览；结果会写入后台任务状态和更新日志。")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### 基础市场数据")
        if st.button("更新 ETF 行情", width="stretch"):
            _submit_manual_task(
                "ETF 行情补采",
                refresh_etf_daily,
                task_key="manual:etf_daily",
            )

        if st.button("更新指数估值", width="stretch"):
            _submit_manual_task(
                "指数估值补采",
                refresh_index_valuation,
                task_key="manual:index_valuation",
            )

        if st.button("更新国债收益率", width="stretch"):
            _submit_manual_task(
                "国债收益率补采",
                refresh_bond_yield,
                task_key="manual:bond_yield",
            )

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

        if st.button("更新产业链企业行情", type="primary", width="stretch"):
            selected_chain_id = chain_options[chain_name]
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

        if st.button("更新产业链企业基本面", width="stretch"):
            selected_chain_id = chain_options[chain_name]
            _submit_manual_task(
                "产业链企业基本面补采",
                refresh_industry_chain_fundamental_bundle,
                chain_id=selected_chain_id,
                task_key=f"manual:industry_chain_fundamentals:{selected_chain_id}",
            )

        if st.button("刷新产业链新闻关联", width="stretch"):
            _submit_manual_task(
                "产业链新闻关联刷新",
                refresh_industry_chain_news_links,
                task_key="manual:industry_chain_news_links",
            )

with tab_schedule:
    st.subheader("定时采集")
    processes = get_scheduler_processes()
    if processes:
        st.success(f"调度器运行中：{len(processes)} 个进程")
        st.dataframe(pd.DataFrame(processes), width="stretch", hide_index=True)
    else:
        st.warning("未检测到调度器进程。需要常驻定时采集时，请在终端启动。")

    st.markdown(
        f"""
        当前配置来自 `config/settings.yaml`：

        - ETF/指数/债券日更：交易日 `{scheduler_cfg.daily_update_time}`
        - 策略信号生成：交易日 `{scheduler_cfg.signal_generate_time}`
        - 产业链企业行情：交易日 `{industry_time}`
        - 产业链企业基本面：随产业链任务一并刷新
        - 数据健康检查：交易日 `{scheduler_cfg.data_quality_check_time}`
        - 后台成功任务清理：每日 `{scheduler_cfg.dashboard_task_cleanup_time}`
        - 产业链首次历史窗口：`{history_days}` 天
        - 后台成功任务保留：`{scheduler_cfg.dashboard_task_retention_days}` 天
        - 自动周报：`{scheduler_cfg.weekly_report_day}` `{scheduler_cfg.weekly_report_time}`
        - 自动月报：每月最后一天 `{scheduler_cfg.monthly_report_time}`
        - 新闻监控：每小时一次
        - 外盘季报：每周日 `09:05`
        """
    )
    st.code("python -m src.scheduler.runner", language="bash")
    st.info("运行上面的命令后，调度器会常驻执行。页面上的按钮仍可随时手工补采。")

    try:
        from src.scheduler.runner import create_scheduler

        scheduler = create_scheduler()
        jobs = []
        for job in scheduler.get_jobs():
            trigger = str(job.trigger)
            jobs.append({"任务ID": job.id, "名称": job.name, "触发器": trigger})
        st.dataframe(pd.DataFrame(jobs), width="stretch", hide_index=True)
    except Exception as e:
        st.warning(f"无法读取调度任务：{e}")

with tab_health:
    st.subheader("数据健康")

    storage = StorageEngine()
    try:
        storage.init_schema()
        health_report = get_data_health_report(storage)
        chains = IndustryChainAnalyzer(storage).list_chains()
        rows = []
        for chain in chains:
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
                    "缺失ETF数": len(quality.get("missing_etfs", [])),
                    "缺失指数数": len(quality.get("missing_indices", [])),
                }
            )
    except Exception as exc:
        st.warning(f"DuckDB 暂不可用，数据健康详情暂无法加载：{exc}")
        health_report = get_data_health_report()
        rows = []
    finally:
        storage.close()

    if rows:
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    else:
        st.info("暂无产业链配置")

    st.markdown("#### 全局新鲜度")
    st.dataframe(
        health_report["freshness"],
        width="stretch",
        hide_index=True,
    )

    st.markdown("#### 近端断档")
    gaps = health_report["gaps"]
    if gaps.empty:
        st.success("近端日线未发现断档。")
    else:
        st.dataframe(gaps, width="stretch", hide_index=True)

    st.markdown("#### 最近失败")
    recent_failures = health_report["recent_failures"]
    if recent_failures.empty:
        st.success("最近 24 小时未发现失败或部分成功任务。")
    else:
        display_failures = recent_failures.copy()
        display_failures["started_at"] = display_failures["started_at"].astype(str)
        display_failures["finished_at"] = display_failures["finished_at"].astype(str)
        st.dataframe(
            display_failures[
                [
                    "task_name",
                    "status",
                    "finished_at",
                    "failed_count",
                    "rows_written",
                    "error_message",
                ]
            ],
            width="stretch",
            hide_index=True,
        )

    st.markdown("#### 补采建议")
    plan = health_report["backfill_plan"]
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
    st.info(
        "并行查看数据库时优先使用只读连接。若遇到文件锁冲突，请先检查 Dashboard、"
        "API 或调度器是否正在写库；需要写入时再停止其他占用进程。"
    )

with tab_logs:
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
    else:
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
        show_cols = [
            "任务",
            "状态",
            "开始时间",
            "耗时秒",
            "成功",
            "跳过",
            "失败",
            "写入行数",
            "错误",
        ]
        st.dataframe(display[show_cols], width="stretch", hide_index=True)

        st.markdown("#### 日志详情与失败重试")
        options = {
            f"{row.task_name} | {row.started_at} | {row.status}": row.id
            for row in logs.itertuples()
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
