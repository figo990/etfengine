"""每日数据更新脚本"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger

from src.core.config import get_etf_universe
from src.core.logging import setup_logging
from src.dashboard.data_refresh import (
    refresh_etf_info,
    refresh_fundamental_data,
    refresh_index_valuation,
)
from src.data.fetcher import DataFetcher
from src.data.storage import StorageEngine


def incremental_update() -> None:
    """增量更新：只拉取最新数据"""
    try:
        rows = refresh_etf_info()
        logger.info(f"ETF 基础信息更新 {rows} 条")
    except Exception as e:
        logger.error(f"ETF 基础信息更新失败: {e}")

    storage = StorageEngine()
    fetcher = DataFetcher()

    universe = get_etf_universe()
    etf_codes = []
    for category in universe.get("etf_universe", {}).values():
        for item in category:
            etf_codes.append(item["code"])

    today = date.today()

    for code in etf_codes:
        try:
            latest = storage.get_latest_date("etf_daily", "code", code)
            start = (
                date.fromisoformat(latest) + timedelta(days=1)
                if latest
                else date(2018, 1, 1)
            )

            if start > today:
                continue

            logger.info(f"增量更新 {code}: {start} ~ {today}")
            df = fetcher.get_etf_daily(code, start_date=start, end_date=today)
            if not df.empty:
                rows = storage.upsert_etf_daily(df, code)
                logger.info(f"  {code}: 新增 {rows} 条")
        except Exception as e:
            logger.error(f"  {code} 更新失败: {e}")

    # 更新国债收益率
    try:
        latest = storage.get_latest_date("bond_yield", "1", "1")
        start = (
            date.fromisoformat(latest) + timedelta(days=1)
            if latest
            else date(2018, 1, 1)
        )
        df = fetcher.get_bond_yield(start_date=start, end_date=today)
        if not df.empty:
            storage.upsert_bond_yield(df)
            logger.info(f"国债收益率更新 {len(df)} 条")
    except Exception as e:
        logger.error(f"国债收益率更新失败: {e}")

    storage.close()

    try:
        results = refresh_index_valuation()
        logger.info(f"指数估值更新完成: {results}")
    except Exception as e:
        logger.error(f"指数估值更新失败: {e}")

    try:
        results = refresh_fundamental_data()
        logger.info(f"指数基本面更新完成: {results}")
    except Exception as e:
        logger.error(f"指数基本面更新失败: {e}")


def main() -> None:
    setup_logging()
    logger.info("开始每日数据更新...")
    incremental_update()
    logger.info("每日数据更新完成")


if __name__ == "__main__":
    main()
