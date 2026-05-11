"""Dashboard 数据刷新工具"""

from __future__ import annotations
import streamlit as st
from loguru import logger


def refresh_etf_daily(codes: list[str] | None = None) -> dict:
    """增量更新 ETF 日线数据，返回 {code: rows} 结果"""
    from datetime import date, timedelta
    from src.data.fetcher import DataFetcher
    from src.data.storage import StorageEngine

    storage = StorageEngine()
    storage.init_schema()
    fetcher = DataFetcher()
    results = {}

    if codes is None:
        from src.core.config import get_etf_universe
        universe = get_etf_universe()
        codes = []
        for category in universe.get("etf_universe", {}).values():
            for item in category:
                codes.append(item["code"])

    for code in codes:
        try:
            latest = storage.get_latest_date("etf_daily", "code", code)
            start = date.fromisoformat(latest) + timedelta(days=1) if latest else date(2018, 1, 1)
            end = date.today()
            if start > end:
                results[code] = 0
                continue
            df = fetcher.get_etf_daily(code, start_date=start, end_date=end)
            rows = storage.upsert_etf_daily(df, code)
            results[code] = rows
        except Exception as e:
            logger.warning(f"更新 {code} 失败: {e}")
            results[code] = -1

    storage.close()
    return results


def refresh_index_valuation() -> dict:
    """更新指数估值数据"""
    from src.data.fetcher import DataFetcher
    from src.data.storage import StorageEngine

    storage = StorageEngine()
    storage.init_schema()
    fetcher = DataFetcher()
    results = {}

    indices = ["沪深300", "中证500", "中证1000", "上证50", "创业板指", "中证红利"]
    for name in indices:
        try:
            df = fetcher.get_index_valuation(name)
            rows = storage.upsert_index_valuation(df, name)
            results[name] = rows
        except Exception as e:
            logger.warning(f"更新 {name} 估值失败: {e}")
            results[name] = -1

    storage.close()
    return results


def refresh_bond_yield() -> int:
    """更新国债收益率"""
    from src.data.fetcher import DataFetcher
    from src.data.storage import StorageEngine

    storage = StorageEngine()
    storage.init_schema()
    fetcher = DataFetcher()
    try:
        df = fetcher.get_bond_yield()
        rows = storage.upsert_bond_yield(df)
        storage.close()
        return rows
    except Exception as e:
        logger.warning(f"更新国债收益率失败: {e}")
        storage.close()
        return -1


def render_refresh_sidebar() -> None:
    """在侧边栏渲染数据刷新面板"""
    with st.sidebar.expander("🔄 数据管理"):
        st.caption("手动刷新数据（从 AkShare 抓取最新数据）")

        if st.button("📊 更新行情数据", use_container_width=True):
            with st.spinner("正在更新 ETF 行情..."):
                try:
                    results = refresh_etf_daily()
                    updated = sum(1 for v in results.values() if v > 0)
                    st.success(f"✅ 更新完成: {updated}/{len(results)} 只ETF有新数据")
                except Exception as e:
                    st.error(f"更新失败: {e}")

        if st.button("📈 更新估值数据", use_container_width=True):
            with st.spinner("正在更新指数估值..."):
                try:
                    results = refresh_index_valuation()
                    st.success(f"✅ 估值更新完成: {len(results)} 个指数")
                except Exception as e:
                    st.error(f"更新失败: {e}")

        if st.button("🏦 更新国债收益率", use_container_width=True):
            with st.spinner("正在更新国债收益率..."):
                try:
                    rows = refresh_bond_yield()
                    if rows > 0:
                        st.success(f"✅ 国债收益率: {rows} 条")
                    else:
                        st.warning("无新数据或更新失败")
                except Exception as e:
                    st.error(f"更新失败: {e}")

        st.divider()
        st.caption("""
        **定时任务说明**

        系统支持自动定时更新，在终端运行：
        ```
        python -m src.scheduler.runner
        ```
        将自动执行：
        - 每交易日 18:30 更新行情
        - 每交易日 19:00 生成信号
        - 每小时采集新闻资讯
        """)
