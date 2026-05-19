"""报告中心：生成、查看和配置投资报告"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from src.core.config import settings
from src.dashboard.components import (
    render_data_status_bar,
    render_empty_state,
    render_metric_cards,
    render_page_header,
    render_page_help,
    render_result_table,
)
from src.dashboard.data_status import get_table_freshness
from src.dashboard.nav import PAGE_URL_BY_LABEL
from src.dashboard.report_builder import REPORT_DIR, generate_and_save_investment_report
from src.dashboard.styles import configure_dashboard_page, inject_global_styles
from src.dashboard.task_runner import (
    dashboard_task_to_dict,
    list_dashboard_tasks,
    submit_dashboard_task,
)
from src.data.storage import StorageEngine

configure_dashboard_page("报告中心")
inject_global_styles()

render_page_header("报告中心", "周报/月报生成，整合估值、组合、产业链、资讯与数据状态。")
render_page_help(
    [
        (
            "页面用途",
            "用于生成投资周报/月报，回看历史报告，并检查报告生成所需的数据状态。",
        ),
        (
            "主要功能",
            [
                "生成报告：选择周报或月报后提交后台生成任务。",
                "生成任务：查看报告任务状态、结果和可下载文件。",
                "历史报告：浏览已生成的 Markdown 报告内容。",
                "推送设置：查看自动周报/月报和任务清理配置。",
            ],
        ),
        ("数据依赖", "报告会整合估值、组合、产业链、资讯事件和数据健康信息。"),
    ]
)


@st.cache_data(ttl=300)
def _load_freshness() -> pd.DataFrame:
    return get_table_freshness()


@st.cache_data(ttl=300)
def _load_report_stats() -> dict[str, int]:
    storage = StorageEngine()
    try:
        storage.init_schema()
        news = storage.get_news_articles(limit=200)
        update_runs = storage.get_data_update_runs(limit=50)
    except Exception:
        return {
            "news_count": 0,
            "high_news": 0,
            "failed_runs": 0,
            "partial_runs": 0,
        }
    finally:
        storage.close()

    high_news = int((news["impact_level"] == "high").sum()) if not news.empty else 0
    failed_runs = int((update_runs["status"] == "failed").sum()) if not update_runs.empty else 0
    partial_runs = int((update_runs["status"] == "partial").sum()) if not update_runs.empty else 0
    return {
        "news_count": len(news),
        "high_news": high_news,
        "failed_runs": failed_runs,
        "partial_runs": partial_runs,
    }


def _load_report_files() -> list[Path]:
    if not REPORT_DIR.exists():
        return []
    return sorted(REPORT_DIR.glob("*.md"), key=lambda item: item.stat().st_mtime, reverse=True)


def _format_mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")


def _render_report_preview(content: str) -> None:
    """Keep long-form report prose readable inside the wider workspace shell."""
    _, preview_col, _ = st.columns([1, 5, 1])
    with preview_col:
        st.markdown(content)


def _report_task_rows(limit: int = 100) -> list[dict]:
    return [
        dashboard_task_to_dict(task)
        for task in list_dashboard_tasks(limit)
        if task.task_type == "report"
    ]


tab_generate, tab_tasks, tab_history, tab_push = st.tabs(
    ["生成报告", "生成任务", "历史报告", "推送设置"]
)

with tab_generate:
    stats = _load_report_stats()
    render_metric_cards(
        [
            ("近200条新闻素材", stats["news_count"]),
            ("高影响新闻", stats["high_news"]),
            ("失败更新任务", stats["failed_runs"]),
            ("部分成功任务", stats["partial_runs"]),
        ]
    )
    if stats["failed_runs"] > 0:
        st.warning(
            f"检测到 {stats['failed_runs']} 次失败的数据更新。"
            f"请前往 [数据管理]({PAGE_URL_BY_LABEL['数据管理']}) 查看「更新日志」并重试。"
        )

    st.subheader("报告参数")
    st.caption("报告日期为周报/月报的锚定日期（非区间选择）。")
    form_cols = st.columns(2)
    report_type = form_cols[0].selectbox("报告类型", ["周报", "月报"])
    report_date_value = form_cols[1].date_input("报告日期", value=date.today())
    if not isinstance(report_date_value, date):
        report_date_value = date.today()

    st.markdown("#### 数据新鲜度")
    freshness = _load_freshness()
    render_data_status_bar(freshness)
    render_result_table(freshness, empty_message="暂无数据新鲜度")

    if st.button("生成并保存报告", type="primary"):
        task = submit_dashboard_task(
            f"报告生成：{report_type} {report_date_value}",
            generate_and_save_investment_report,
            report_type,
            report_date_value,
            task_key=f"report:{report_type}:{report_date_value.isoformat()}",
            task_type="report",
            tags=["report_center", report_type],
        )
        st.success(f"已提交后台报告任务：{task.id}，可在“生成任务”查看和下载。")

with tab_tasks:
    st.subheader("生成任务")
    task_rows = _report_task_rows()
    if not task_rows:
        render_empty_state("暂无报告生成任务，请先提交一次报告生成。")
    else:
        task_display = pd.DataFrame(
            [
                {
                    "任务ID": row["id"],
                    "任务": row["name"],
                    "状态": row["status"],
                    "创建时间": row["created_at"],
                    "结束时间": row["finished_at"] or "",
                    "错误": row["error"],
                }
                for row in task_rows
            ]
        )
        render_result_table(task_display, empty_message="暂无报告生成任务")
        options = {
            f"{row['created_at']} | {row['name']} | {row['status']}": row for row in task_rows
        }
        selected_label = st.selectbox("选择报告任务", list(options))
        selected_task = options[selected_label]
        if selected_task["status"] != "success":
            if selected_task["error"]:
                st.error(selected_task["error"])
            else:
                st.info("任务尚未完成，稍后刷新查看结果。")
        else:
            result = selected_task.get("result") or {}
            path_value = result.get("report_path")
            report_path = Path(path_value) if path_value else None
            if report_path is None or not report_path.exists():
                st.warning("报告任务已完成，但文件不存在。请重新生成。")
            else:
                content = report_path.read_text(encoding="utf-8")
                c1, c2, c3 = st.columns(3)
                c1.metric("文件名", report_path.name)
                c2.metric("大小", f"{report_path.stat().st_size / 1024:.1f} KB")
                c3.metric("报告日期", result.get("report_date", "--"))
                st.download_button(
                    "下载 Markdown",
                    data=content,
                    file_name=report_path.name,
                    mime="text/markdown",
                )
                _render_report_preview(content)

with tab_history:
    st.subheader("历史报告")
    files = _load_report_files()
    if not files:
        render_empty_state("暂无历史报告，请先生成。")
    else:
        options = {f"{path.name} | {_format_mtime(path)}": path for path in files[:50]}
        selected = st.selectbox("选择报告", list(options))
        selected_path = options[selected]
        content = selected_path.read_text(encoding="utf-8")
        h1, h2, h3 = st.columns([2, 1, 1])
        h1.metric("文件名", selected_path.name)
        h2.metric("大小", f"{selected_path.stat().st_size / 1024:.1f} KB")
        h3.metric("更新时间", _format_mtime(selected_path))
        st.download_button(
            "下载 Markdown",
            data=content,
            file_name=selected_path.name,
            mime="text/markdown",
        )
        _render_report_preview(content)

with tab_push:
    st.subheader("推送设置")
    cfg = settings()
    notify = cfg.notify
    channels = []
    for name, channel in notify.channels.items():
        channels.append(
            {
                "渠道": name,
                "启用": "是" if channel.enabled else "否",
                "SMTP": channel.smtp_host or "--",
                "Webhook": "已配置" if channel.webhook_url else "--",
            }
        )
    render_result_table(pd.DataFrame(channels), empty_message="暂无通知渠道配置。")

    st.markdown("#### 自动报告")
    schedule_rows = [
        {"任务": "数据采集", "时间": cfg.scheduler.daily_update_time, "状态": "已配置"},
        {"任务": "信号生成", "时间": cfg.scheduler.signal_generate_time, "状态": "已配置"},
        {
            "任务": "产业链行情",
            "时间": cfg.scheduler.industry_chain_update_time,
            "状态": "已配置",
        },
        {
            "任务": "数据健康检查",
            "时间": cfg.scheduler.data_quality_check_time,
            "状态": "已配置",
        },
        {
            "任务": "后台成功任务清理",
            "时间": cfg.scheduler.dashboard_task_cleanup_time,
            "状态": f"保留 {cfg.scheduler.dashboard_task_retention_days} 天",
        },
        {
            "任务": "自动周报",
            "时间": f"{cfg.scheduler.weekly_report_day} {cfg.scheduler.weekly_report_time}",
            "状态": "启用" if cfg.scheduler.weekly_report_enabled else "关闭",
        },
        {
            "任务": "自动月报",
            "时间": f"每月最后一天 {cfg.scheduler.monthly_report_time}",
            "状态": "启用" if cfg.scheduler.monthly_report_enabled else "关闭",
        },
    ]
    render_result_table(pd.DataFrame(schedule_rows), empty_message="暂无自动报告配置")
