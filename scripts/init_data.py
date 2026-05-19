"""数据初始化脚本：首次运行时拉取历史数据"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger

from src.core.config import get_etf_universe
from src.core.logging import setup_logging
from src.data.fetcher import DataFetcher
from src.data.storage import StorageEngine


def init_database() -> StorageEngine:
    """初始化数据库"""
    storage = StorageEngine()
    storage.init_schema()
    logger.info("数据库初始化完成")
    return storage


def fetch_etf_daily(fetcher: DataFetcher, storage: StorageEngine, codes: list[str]) -> None:
    """拉取 ETF 日线数据"""
    start = date(2018, 1, 1)
    end = date.today()

    for code in codes:
        try:
            logger.info(f"正在获取 ETF 日线: {code}")
            df = fetcher.get_etf_daily(code, start_date=start, end_date=end)
            rows = storage.upsert_etf_daily(df, code)
            logger.info(f"  {code}: 写入 {rows} 条记录")
        except Exception as e:
            logger.error(f"  {code} 获取失败: {e}")


def fetch_index_valuation(fetcher: DataFetcher, storage: StorageEngine) -> None:
    """拉取指数估值数据"""
    index_names = ["沪深300", "中证500", "中证1000", "上证50", "创业板指", "中证红利"]

    for name in index_names:
        try:
            logger.info(f"正在获取指数估值: {name}")
            df = fetcher.get_index_valuation(name)
            rows = storage.upsert_index_valuation(df, name)
            logger.info(f"  {name}: 写入 {rows} 条记录")
        except Exception as e:
            logger.error(f"  {name} 获取失败: {e}")


def fetch_bond_yield(fetcher: DataFetcher, storage: StorageEngine) -> None:
    """拉取国债收益率"""
    try:
        logger.info("正在获取国债收益率...")
        df = fetcher.get_bond_yield()
        rows = storage.upsert_bond_yield(df)
        logger.info(f"  国债收益率: 写入 {rows} 条记录")
    except Exception as e:
        logger.error(f"  国债收益率获取失败: {e}")


def main() -> None:
    setup_logging()
    logger.info("=" * 60)
    logger.info("ETFEngine 数据初始化开始")
    logger.info("=" * 60)

    storage = init_database()
    fetcher = DataFetcher()

    universe = get_etf_universe()
    etf_codes = []
    for category in universe.get("etf_universe", {}).values():
        for item in category:
            etf_codes.append(item["code"])

    logger.info(f"共 {len(etf_codes)} 只 ETF 待拉取")

    fetch_etf_daily(fetcher, storage, etf_codes)
    fetch_index_valuation(fetcher, storage)
    fetch_bond_yield(fetcher, storage)

    storage.close()
    logger.info("=" * 60)
    logger.info("数据初始化完成!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
