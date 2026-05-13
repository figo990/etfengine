"""定时任务调度器"""

from __future__ import annotations

from apscheduler.schedulers.blocking import BlockingScheduler
from loguru import logger

from src.core.config import settings


def create_scheduler() -> BlockingScheduler:
    """创建并配置定时任务调度器"""
    scheduler = BlockingScheduler(timezone=settings().app.timezone)

    cfg = settings().scheduler
    hour, minute = map(int, cfg.daily_update_time.split(":"))
    sig_hour, sig_minute = map(int, cfg.signal_generate_time.split(":"))

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

    return scheduler


def daily_data_update() -> None:
    """每日数据更新任务"""
    logger.info("执行每日数据更新...")
    from scripts.daily_update import incremental_update
    incremental_update()


def daily_signal_generation() -> None:
    """每日信号生成任务"""
    logger.info("执行每日信号生成...")
    from src.signals.signal_engine import SignalEngine
    engine = SignalEngine()
    try:
        signals = engine.generate_daily_signals()
        logger.info(f"生成 {len(signals)} 条信号")
    finally:
        engine.close()


def overseas_earnings_update() -> None:
    """美股科技龙头季报（SEC companyfacts）周更"""
    logger.info("执行外盘季报更新...")
    from src.intelligence.overseas_earnings_monitor import OverseasEarningsMonitor

    OverseasEarningsMonitor().run_cycle()


def news_monitor_update() -> None:
    """新闻监控定时更新"""
    logger.info("执行新闻监控更新...")
    from src.intelligence.news_monitor import NewsMonitor
    from src.data.storage import StorageEngine

    monitor = NewsMonitor()
    storage = StorageEngine()

    try:
        try:
            analyzed = monitor.run_cycle(use_llm=True)
        except Exception as e:
            logger.warning(f"LLM 分析不可用({e})，使用关键词回退模式")
            analyzed = monitor.run_cycle(use_llm=False)

        if analyzed:
            count = storage.upsert_news_articles(analyzed)
            logger.info(f"新闻监控完成，存储 {count} 条")
        else:
            logger.info("本轮无新增新闻")
    finally:
        storage.close()


if __name__ == "__main__":
    from src.core.logging import setup_logging
    setup_logging()
    logger.info("启动定时任务调度器...")
    scheduler = create_scheduler()
    scheduler.start()
