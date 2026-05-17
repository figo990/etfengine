"""定时任务调度器"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

from apscheduler.schedulers.blocking import BlockingScheduler
from loguru import logger

from src.core.config import settings
from src.notify.notifier import broadcast_configured


def create_scheduler() -> BlockingScheduler:
    """创建并配置定时任务调度器"""
    scheduler = BlockingScheduler(timezone=settings().app.timezone)

    cfg = settings().scheduler
    hour, minute = map(int, cfg.daily_update_time.split(":"))
    sig_hour, sig_minute = map(int, cfg.signal_generate_time.split(":"))
    chain_hour, chain_minute = map(int, cfg.industry_chain_update_time.split(":"))
    quality_hour, quality_minute = map(int, cfg.data_quality_check_time.split(":"))
    cleanup_hour, cleanup_minute = map(int, cfg.dashboard_task_cleanup_time.split(":"))

    scheduler.add_job(
        daily_data_update,
        "cron",
        hour=hour,
        minute=minute,
        day_of_week="mon-fri",
        id="daily_update",
        name="每日数据更新",
    )

    scheduler.add_job(
        daily_signal_generation,
        "cron",
        hour=sig_hour,
        minute=sig_minute,
        day_of_week="mon-fri",
        id="signal_generation",
        name="每日信号生成",
    )

    scheduler.add_job(
        news_monitor_update,
        "interval",
        hours=1,
        id="news_monitor",
        name="新闻监控更新",
    )

    scheduler.add_job(
        overseas_earnings_update,
        "cron",
        day_of_week="sun",
        hour=9,
        minute=5,
        id="overseas_earnings",
        name="外盘科技龙头季报",
    )

    scheduler.add_job(
        industry_chain_update,
        "cron",
        hour=chain_hour,
        minute=chain_minute,
        day_of_week="mon-fri",
        id="industry_chain_update",
        name="产业链企业行情与新闻关联",
    )

    scheduler.add_job(
        data_quality_check,
        "cron",
        hour=quality_hour,
        minute=quality_minute,
        day_of_week="mon-fri",
        id="data_quality_check",
        name="数据健康检查",
    )

    scheduler.add_job(
        dashboard_task_cleanup,
        "cron",
        hour=cleanup_hour,
        minute=cleanup_minute,
        id="dashboard_task_cleanup",
        name="后台任务成功历史清理",
    )

    if cfg.weekly_report_enabled:
        report_hour, report_minute = map(int, cfg.weekly_report_time.split(":"))
        scheduler.add_job(
            weekly_report_generation,
            "cron",
            hour=report_hour,
            minute=report_minute,
            day_of_week=cfg.weekly_report_day,
            id="weekly_report_generation",
            name="自动生成周报",
        )

    if cfg.monthly_report_enabled:
        report_hour, report_minute = map(int, cfg.monthly_report_time.split(":"))
        scheduler.add_job(
            monthly_report_generation,
            "cron",
            hour=report_hour,
            minute=report_minute,
            day="last",
            id="monthly_report_generation",
            name="自动生成月报",
        )

    return scheduler


def _run_scheduled_job(job_name: str, callback: Callable[[], Any]) -> Any:
    """Run a scheduled job and notify on uncaught failures."""
    try:
        return callback()
    except Exception as exc:
        logger.exception(f"{job_name} 执行失败")
        broadcast_configured(
            f"ETFEngine 调度失败：{job_name}",
            f"- 任务：{job_name}\n- 错误：{exc}",
        )
        raise


def daily_data_update() -> None:
    """每日数据更新任务"""

    def _job() -> None:
        logger.info("执行每日数据更新...")
        from scripts.daily_update import incremental_update

        incremental_update()

    _run_scheduled_job("每日数据更新", _job)


def daily_signal_generation() -> None:
    """每日信号生成任务"""

    def _job() -> None:
        logger.info("执行每日信号生成...")
        from src.signals.signal_engine import SignalEngine

        engine = SignalEngine()
        try:
            signals = engine.generate_daily_signals()
            logger.info(f"生成 {len(signals)} 条信号")
        finally:
            engine.close()

    _run_scheduled_job("每日信号生成", _job)


def overseas_earnings_update() -> None:
    """美股科技龙头季报（SEC companyfacts）周更"""

    def _job() -> None:
        logger.info("执行外盘季报更新...")
        from src.dashboard.data_refresh import refresh_overseas_earnings

        refresh_overseas_earnings()

    _run_scheduled_job("外盘科技龙头季报", _job)


def industry_chain_update() -> None:
    """产业链企业行情与新闻关联更新"""

    def _job() -> None:
        logger.info("执行产业链更新...")
        from src.dashboard.data_refresh import (
            refresh_industry_chain_companies,
            refresh_industry_chain_fundamental_bundle,
            refresh_industry_chain_news_links,
        )

        results = refresh_industry_chain_companies()
        updated = sum(1 for value in results.values() if value > 0)
        failed = sum(1 for value in results.values() if value < 0)
        fundamental_bundle = refresh_industry_chain_fundamental_bundle()
        linked = refresh_industry_chain_news_links()

        logger.info(
            "产业链更新完成: "
            f"companies_updated={updated}, failed={failed}, "
            f"fundamentals={fundamental_bundle}, news_links={linked}"
        )

    _run_scheduled_job("产业链企业行情与新闻关联", _job)


def news_monitor_update() -> None:
    """新闻监控定时更新"""

    def _job() -> None:
        logger.info("执行新闻监控更新...")
        from src.dashboard.data_refresh import refresh_news_monitor

        result = refresh_news_monitor()
        logger.info(f"新闻监控完成: {result}")

    _run_scheduled_job("新闻监控更新", _job)


def _format_data_quality_alert(report: dict[str, Any]) -> str:
    freshness = report["freshness"]
    gaps = report["gaps"]
    failures = report["recent_failures"]
    lines = ["请检查以下数据健康问题："]
    stale = freshness[freshness["状态"] != "新鲜"]
    if not stale.empty:
        lines.append("")
        lines.append("**新鲜度异常**")
        for _, row in stale.iterrows():
            latest = row["最新日期"] or "--"
            lines.append(f"- {row['数据']}: {row['状态']}，最新日期 {latest}")
    if not gaps.empty:
        lines.append("")
        lines.append("**近端断档**")
        for _, row in gaps.head(10).iterrows():
            lines.append(f"- {row['数据']} {row['代码']}: 缺口 {row['缺口天数']} 天")
    if not failures.empty:
        lines.append("")
        lines.append("**最近失败任务**")
        for _, row in failures.head(10).iterrows():
            lines.append(f"- {row['task_name']}: {row['status']} ({row['finished_at']})")
    return "\n".join(lines)


def data_quality_check() -> None:
    """Run scheduled data-health inspection and notify on anomalies."""

    def _job() -> None:
        from src.dashboard.data_status import get_data_health_report

        report = get_data_health_report()
        if report["issue_count"] <= 0:
            logger.info("数据健康检查完成：未发现异常")
            return
        logger.warning(f"数据健康检查发现 {report['issue_count']} 个问题")
        broadcast_configured("ETFEngine 数据健康告警", _format_data_quality_alert(report))

    _run_scheduled_job("数据健康检查", _job)


def dashboard_task_cleanup() -> None:
    """Clean old successful dashboard tasks and retain failed/interrupted history."""

    def _job() -> None:
        from src.dashboard.task_runner import cleanup_old_success_dashboard_tasks

        retention_days = settings().scheduler.dashboard_task_retention_days
        removed = cleanup_old_success_dashboard_tasks(retention_days)
        logger.info(f"后台任务清理完成: retention_days={retention_days}, removed={removed}")

    _run_scheduled_job("后台任务成功历史清理", _job)


def weekly_report_generation() -> None:
    """Generate weekly report and notify configured channels."""

    def _job() -> None:
        _generate_scheduled_report("周报")

    _run_scheduled_job("自动生成周报", _job)


def monthly_report_generation() -> None:
    """Generate monthly report and notify configured channels."""

    def _job() -> None:
        _generate_scheduled_report("月报")

    _run_scheduled_job("自动生成月报", _job)


def _generate_scheduled_report(report_type: str) -> dict[str, Any]:
    from src.dashboard.report_builder import generate_and_save_investment_report
    from src.dashboard.task_runner import submit_dashboard_task, wait_dashboard_task

    report_date = date.today()
    task = submit_dashboard_task(
        f"自动报告生成：{report_type} {report_date}",
        generate_and_save_investment_report,
        report_type,
        report_date,
        task_key=f"report:auto:{report_type}:{report_date.isoformat()}",
        task_type="report",
        tags=["scheduler", report_type],
    )
    finished = wait_dashboard_task(task.id)
    if finished.status == "failed":
        raise RuntimeError(finished.error)
    result = finished.result
    logger.info(f"{report_type} 自动生成完成: {result['report_path']}")
    broadcast_configured(
        f"ETFEngine {report_type} 已生成",
        (
            f"- 报告日期：{result['report_date']}\n"
            f"- 文件：{result['report_path']}\n"
            f"- 大小：{result['size_bytes']} bytes"
        ),
    )
    return result


if __name__ == "__main__":
    from src.core.logging import setup_logging

    setup_logging()
    logger.info("启动定时任务调度器...")
    scheduler = create_scheduler()
    scheduler.start()
