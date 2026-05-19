"""Dashboard 数据刷新工具"""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import streamlit as st
from loguru import logger


def _summarize_mapping_results(results: dict) -> dict:
    success_count = sum(1 for value in results.values() if value > 0)
    skipped_count = sum(1 for value in results.values() if value == 0)
    failed_count = sum(1 for value in results.values() if value < 0)
    rows_written = sum(value for value in results.values() if value > 0)
    status = "success" if failed_count == 0 else ("partial" if success_count else "failed")
    return {
        "status": status,
        "success_count": success_count,
        "skipped_count": skipped_count,
        "failed_count": failed_count,
        "rows_written": rows_written,
    }


def _log_update_run(
    task_name: str,
    started_at: datetime,
    summary: dict,
    details: dict | list | None = None,
    error_message: str = "",
) -> None:
    from src.data.storage import StorageEngine

    finished_at = datetime.now()
    storage = StorageEngine()
    try:
        storage.init_schema()
        storage.log_data_update_run(
            {
                "task_name": task_name,
                "started_at": started_at,
                "finished_at": finished_at,
                "duration_seconds": (finished_at - started_at).total_seconds(),
                "details": details or {},
                "error_message": error_message,
                **summary,
            }
        )
    except Exception as e:
        logger.warning(f"记录数据更新日志失败: {e}")
    finally:
        storage.close()


def refresh_etf_daily(codes: list[str] | None = None) -> dict:
    """增量更新 ETF 日线数据，返回 {code: rows} 结果"""
    from datetime import date, timedelta

    from src.data.fetcher import DataFetcher
    from src.data.storage import StorageEngine

    started_at = datetime.now()
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
    _log_update_run(
        "ETF 行情",
        started_at,
        _summarize_mapping_results(results),
        details=results,
    )
    return results


def refresh_index_valuation(indices: list[str] | None = None) -> dict:
    """更新指数估值数据"""
    from src.data.fetcher import DataFetcher
    from src.data.storage import StorageEngine

    started_at = datetime.now()
    storage = StorageEngine()
    storage.init_schema()
    fetcher = DataFetcher()
    results = {}

    indices = indices or ["沪深300", "中证500", "中证1000", "上证50", "创业板指", "中证红利"]
    for name in indices:
        try:
            df = fetcher.get_index_valuation(name)
            rows = storage.upsert_index_valuation(df, name)
            results[name] = rows
        except Exception as e:
            logger.warning(f"更新 {name} 估值失败: {e}")
            results[name] = -1

    storage.close()
    _log_update_run(
        "指数估值",
        started_at,
        _summarize_mapping_results(results),
        details=results,
    )
    return results


def refresh_bond_yield() -> int:
    """更新国债收益率"""
    from src.data.fetcher import DataFetcher
    from src.data.storage import StorageEngine

    started_at = datetime.now()
    storage = StorageEngine()
    storage.init_schema()
    fetcher = DataFetcher()
    try:
        df = fetcher.get_bond_yield()
        rows = storage.upsert_bond_yield(df)
        storage.close()
        _log_update_run(
            "国债收益率",
            started_at,
            {
                "status": "success",
                "success_count": 1 if rows >= 0 else 0,
                "skipped_count": 1 if rows == 0 else 0,
                "failed_count": 0,
                "rows_written": max(rows, 0),
            },
            details={"rows": rows},
        )
        return rows
    except Exception as e:
        logger.warning(f"更新国债收益率失败: {e}")
        storage.close()
        _log_update_run(
            "国债收益率",
            started_at,
            {
                "status": "failed",
                "success_count": 0,
                "skipped_count": 0,
                "failed_count": 1,
                "rows_written": 0,
            },
            error_message=str(e),
        )
        return -1


def refresh_etf_info() -> int:
    """更新 ETF 基础信息."""
    import pandas as pd

    from src.core.config import get_etf_universe
    from src.data.fetcher import DataFetcher
    from src.data.storage import StorageEngine

    started_at = datetime.now()
    storage = StorageEngine()
    storage.init_schema()
    fetcher = DataFetcher()
    try:
        df = fetcher.get_etf_list()
        universe = get_etf_universe()
        configured_rows = []
        for items in universe.get("etf_universe", {}).values():
            for item in items:
                configured_rows.append(
                    {
                        "code": item.get("code", ""),
                        "name": item.get("name", ""),
                        "index_tracked": item.get("index", ""),
                        "category": item.get("category", ""),
                    }
                )
        if configured_rows:
            configured = pd.DataFrame(configured_rows)
            df = pd.concat([df, configured], ignore_index=True)
            df = df.drop_duplicates(subset=["code"], keep="first")
        rows = storage.upsert_etf_info(df)
        storage.close()
        _log_update_run(
            "ETF 基础信息",
            started_at,
            {
                "status": "success",
                "success_count": 1 if rows > 0 else 0,
                "skipped_count": 1 if rows == 0 else 0,
                "failed_count": 0,
                "rows_written": rows,
            },
            details={"rows": rows},
        )
        return rows
    except Exception as e:
        logger.warning(f"更新 ETF 基础信息失败: {e}")
        storage.close()
        _log_update_run(
            "ETF 基础信息",
            started_at,
            {
                "status": "failed",
                "success_count": 0,
                "skipped_count": 0,
                "failed_count": 1,
                "rows_written": 0,
            },
            error_message=str(e),
        )
        return -1


def refresh_fundamental_data(indices: list[str] | None = None) -> dict[str, int]:
    """更新指数基本面数据."""
    from src.analysis.fundamental import FundamentalAnalyzer
    from src.data.storage import StorageEngine

    started_at = datetime.now()
    storage = StorageEngine()
    storage.init_schema()
    analyzer = FundamentalAnalyzer()
    indices = indices or ["沪深300", "中证500", "中证1000", "上证50", "创业板指", "中证红利"]
    results = {}
    for index_name in indices:
        try:
            df = analyzer.get_index_fundamental(index_name)
            if df.empty:
                df = storage.get_index_valuation(index_name)
                if not df.empty:
                    df = df.copy()
                    if {"pb", "pe"}.issubset(df.columns):
                        df["roe"] = df["pb"] / df["pe"]
                    df["roe_trend"] = "待确认"
            results[index_name] = storage.upsert_fundamental_data(df, index_name)
        except Exception as e:
            logger.warning(f"更新 {index_name} 基本面失败: {e}")
            results[index_name] = -1
    storage.close()
    _log_update_run(
        "指数基本面",
        started_at,
        _summarize_mapping_results(results),
        details=results,
    )
    return results


def refresh_trade_signals() -> int:
    """生成并入库交易信号."""
    from src.signals.signal_engine import SignalEngine

    started_at = datetime.now()
    engine = SignalEngine()
    try:
        engine.storage.init_schema()
        signals = engine.generate_daily_signals()
        rows = len(signals)
        _log_update_run(
            "交易信号",
            started_at,
            {
                "status": "success",
                "success_count": rows,
                "skipped_count": 0 if rows else 1,
                "failed_count": 0,
                "rows_written": rows,
            },
            details=[
                {
                    "strategy_name": signal.strategy_name,
                    "etf_code": signal.etf_code,
                    "direction": signal.direction.value,
                    "reason": signal.reason,
                }
                for signal in signals
            ],
        )
        return rows
    except Exception as e:
        logger.warning(f"生成交易信号失败: {e}")
        _log_update_run(
            "交易信号",
            started_at,
            {
                "status": "failed",
                "success_count": 0,
                "skipped_count": 0,
                "failed_count": 1,
                "rows_written": 0,
            },
            error_message=str(e),
        )
        return -1
    finally:
        engine.close()


def refresh_industry_chain_companies(
    chain_id: str | None = None,
    history_days: int | None = None,
    company_codes: list[str] | None = None,
) -> dict:
    """更新产业链企业日线数据"""
    from datetime import date, timedelta

    from src.core.config import settings
    from src.data.fetcher import DataFetcher
    from src.data.storage import StorageEngine
    from src.intelligence.industry_chain_analyzer import IndustryChainAnalyzer

    started_at = datetime.now()
    scheduler_cfg = settings().scheduler
    default_history_days = getattr(scheduler_cfg, "industry_chain_history_days", 183)
    history_days = history_days or default_history_days
    history_start = date.today() - timedelta(days=history_days)
    storage = StorageEngine()
    storage.init_schema()
    analyzer = IndustryChainAnalyzer(storage)
    analyzer.sync_company_master(chain_id)
    companies = analyzer.flatten_companies(chain_id)
    if company_codes:
        code_set = set(company_codes)
        companies = [company for company in companies if company.company_code in code_set]
    fetcher = DataFetcher()
    results = {}

    for company in companies:
        code = company.company_code
        try:
            latest = storage.get_latest_date("company_daily", "company_code", code)
            start = date.fromisoformat(latest) + timedelta(days=1) if latest else history_start
            end = date.today()
            if start > end:
                results[code] = 0
                continue
            df = fetcher.get_stock_daily(code, start_date=start, end_date=end)
            rows = storage.upsert_company_daily(df, code)
            results[code] = rows
        except Exception as e:
            logger.warning(f"更新产业链企业 {code} 失败: {e}")
            results[code] = -1

    storage.close()
    _log_update_run(
        "产业链企业行情",
        started_at,
        _summarize_mapping_results(results),
        details={
            "chain_id": chain_id,
            "history_days": history_days,
            "company_codes": company_codes or [],
            "results": results,
        },
    )
    return results


def refresh_industry_chain_news_links() -> dict[str, int]:
    """刷新产业链新闻关联并记录运行日志"""
    from src.data.storage import StorageEngine
    from src.intelligence.industry_chain_analyzer import IndustryChainAnalyzer

    started_at = datetime.now()
    storage = StorageEngine()
    try:
        storage.init_schema()
        linked = IndustryChainAnalyzer(storage).link_all_news()
    finally:
        storage.close()

    _log_update_run(
        "产业链新闻关联",
        started_at,
        _summarize_mapping_results(linked),
        details=linked,
    )
    return linked


def _industry_chain_company_codes(
    storage,
    chain_id: str | None,
    company_codes: list[str] | None,
) -> list[str]:
    from src.intelligence.industry_chain_analyzer import IndustryChainAnalyzer

    analyzer = IndustryChainAnalyzer(storage)
    analyzer.sync_company_master(chain_id)
    codes = [company.company_code for company in analyzer.flatten_companies(chain_id)]
    if company_codes:
        allowed = set(company_codes)
        codes = [code for code in codes if code in allowed]
    return codes


def _recent_report_periods(as_of: date | None = None, count: int = 4) -> list[date]:
    """Return the latest completed quarter-end periods."""
    as_of = as_of or date.today()
    quarter_ends = [(3, 31), (6, 30), (9, 30), (12, 31)]
    periods = []
    year = as_of.year
    while len(periods) < count:
        for month, day in reversed(quarter_ends):
            candidate = date(year, month, day)
            if candidate <= as_of:
                periods.append(candidate)
                if len(periods) == count:
                    break
        year -= 1
    return periods


def refresh_industry_chain_fundamentals(
    chain_id: str | None = None,
    company_codes: list[str] | None = None,
) -> dict[str, int]:
    """更新产业链企业财务指标."""
    from src.data.fetcher import DataFetcher
    from src.data.storage import StorageEngine

    started_at = datetime.now()
    storage = StorageEngine()
    storage.init_schema()
    fetcher = DataFetcher()
    codes = _industry_chain_company_codes(storage, chain_id, company_codes)
    results = {}
    for code in codes:
        try:
            df = fetcher.get_stock_fundamentals(code)
            results[code] = storage.upsert_company_fundamentals(df, code)
        except Exception as e:
            logger.warning(f"更新产业链企业财务指标 {code} 失败: {e}")
            results[code] = -1
    storage.close()
    _log_update_run(
        "产业链企业财务指标",
        started_at,
        _summarize_mapping_results(results),
        details={"chain_id": chain_id, "company_codes": company_codes or [], "results": results},
    )
    return results


def refresh_industry_chain_valuations(
    chain_id: str | None = None,
    company_codes: list[str] | None = None,
) -> dict[str, int]:
    """更新产业链企业估值历史."""
    from src.data.fetcher import DataFetcher
    from src.data.storage import StorageEngine

    started_at = datetime.now()
    storage = StorageEngine()
    storage.init_schema()
    fetcher = DataFetcher()
    codes = _industry_chain_company_codes(storage, chain_id, company_codes)
    results = {}
    for code in codes:
        try:
            latest = storage.get_latest_date("company_valuation", "company_code", code)
            df = fetcher.get_stock_valuation(code)
            if latest:
                df = df[df["trade_date"] > date.fromisoformat(latest)]
            results[code] = storage.upsert_company_valuation(df, code)
        except Exception as e:
            logger.warning(f"更新产业链企业估值 {code} 失败: {e}")
            results[code] = -1
    storage.close()
    _log_update_run(
        "产业链企业估值",
        started_at,
        _summarize_mapping_results(results),
        details={"chain_id": chain_id, "company_codes": company_codes or [], "results": results},
    )
    return results


def refresh_industry_chain_forecasts(
    chain_id: str | None = None,
    company_codes: list[str] | None = None,
    report_periods: list[date] | None = None,
) -> dict[str, int]:
    """更新产业链企业业绩预告."""
    from src.data.fetcher import DataFetcher
    from src.data.storage import StorageEngine

    started_at = datetime.now()
    storage = StorageEngine()
    storage.init_schema()
    fetcher = DataFetcher()
    codes = set(_industry_chain_company_codes(storage, chain_id, company_codes))
    periods = report_periods or _recent_report_periods()
    results = {code: 0 for code in codes}
    period_errors = {}

    for period in periods:
        try:
            df = fetcher.get_stock_earnings_forecasts(period)
            if df.empty:
                continue
            filtered = df[df["company_code"].astype(str).isin(codes)]
            if filtered.empty:
                continue
            storage.upsert_company_earnings_forecasts(filtered)
            counts = filtered.groupby("company_code").size()
            for code, rows in counts.items():
                results[str(code)] += int(rows)
        except Exception as e:
            logger.warning(f"更新产业链业绩预告 {period} 失败: {e}")
            period_errors[period.isoformat()] = str(e)

    storage.close()
    summary = _summarize_mapping_results(results)
    if period_errors:
        summary["status"] = "partial" if any(value > 0 for value in results.values()) else "failed"
        summary["failed_count"] = len(period_errors)
    _log_update_run(
        "产业链业绩预告",
        started_at,
        summary,
        details={
            "chain_id": chain_id,
            "company_codes": company_codes or [],
            "report_periods": [period.isoformat() for period in periods],
            "results": results,
            "period_errors": period_errors,
        },
    )
    return results


def refresh_industry_chain_fundamental_bundle(
    chain_id: str | None = None,
    company_codes: list[str] | None = None,
) -> dict[str, dict[str, int]]:
    """更新财务、估值和业绩预告三类经营数据."""
    return {
        "fundamentals": refresh_industry_chain_fundamentals(chain_id, company_codes),
        "valuations": refresh_industry_chain_valuations(chain_id, company_codes),
        "forecasts": refresh_industry_chain_forecasts(chain_id, company_codes),
    }


def refresh_news_monitor(use_llm: bool = True) -> dict:
    """Run news collection, store analyzed articles, and refresh chain links."""
    from src.data.storage import StorageEngine
    from src.intelligence.industry_chain_analyzer import IndustryChainAnalyzer
    from src.intelligence.news_monitor import NewsMonitor

    started_at = datetime.now()
    storage = StorageEngine()
    try:
        storage.init_schema()
        monitor = NewsMonitor()
        mode = "llm" if use_llm else "keyword"
        try:
            analyzed = monitor.run_cycle(use_llm=use_llm)
        except Exception as exc:
            if not use_llm:
                raise
            logger.warning(f"LLM 新闻分析不可用({exc})，使用关键词回退模式")
            mode = "keyword"
            analyzed = monitor.run_cycle(use_llm=False)

        article_count = storage.upsert_news_articles(analyzed) if analyzed else 0
        linked = IndustryChainAnalyzer(storage).link_all_news() if analyzed else {}
        result = {
            "articles": article_count,
            "chain_links": linked,
            "mode": mode,
        }
        _log_update_run(
            "新闻监控",
            started_at,
            {
                "status": "success",
                "success_count": article_count,
                "skipped_count": 0 if article_count else 1,
                "failed_count": 0,
                "rows_written": article_count
                + sum(value for value in linked.values() if value > 0),
            },
            details=result,
        )
        return result
    except Exception as exc:
        _log_update_run(
            "新闻监控",
            started_at,
            {
                "status": "failed",
                "success_count": 0,
                "skipped_count": 0,
                "failed_count": 1,
                "rows_written": 0,
            },
            error_message=str(exc),
        )
        raise
    finally:
        storage.close()


def refresh_overseas_earnings() -> dict:
    """Run overseas earnings refresh and record it in update logs."""
    from src.intelligence.overseas_earnings_monitor import OverseasEarningsMonitor

    started_at = datetime.now()
    try:
        result = OverseasEarningsMonitor().run_cycle()
        rows_written = sum(value for value in result.values() if isinstance(value, int))
        _log_update_run(
            "外盘季报",
            started_at,
            {
                "status": "success",
                "success_count": 1,
                "skipped_count": 0 if rows_written else 1,
                "failed_count": 0,
                "rows_written": rows_written,
            },
            details=result,
        )
        return result
    except Exception as exc:
        _log_update_run(
            "外盘季报",
            started_at,
            {
                "status": "failed",
                "success_count": 0,
                "skipped_count": 0,
                "failed_count": 1,
                "rows_written": 0,
            },
            error_message=str(exc),
        )
        raise


def retry_failed_update(task_name: str, details: dict) -> dict | int | None:
    """Retry failed items from a previous update run."""
    if task_name == "ETF 行情":
        failed = [code for code, rows in details.items() if rows < 0]
        return refresh_etf_daily(codes=failed) if failed else {}

    if task_name == "指数估值":
        failed = [name for name, rows in details.items() if rows < 0]
        return refresh_index_valuation(indices=failed) if failed else {}

    if task_name == "国债收益率":
        return refresh_bond_yield()

        if task_name == "产业链企业行情":
            results = details.get("results", {})
            failed = [code for code, rows in results.items() if rows < 0]
        return (
            refresh_industry_chain_companies(
                chain_id=details.get("chain_id"),
                history_days=details.get("history_days"),
                company_codes=failed,
            )
            if failed
            else {}
        )

    if task_name == "产业链新闻关联":
        failed = {chain_id: rows for chain_id, rows in details.items() if rows < 0}
        return refresh_industry_chain_news_links() if failed else {}

    if task_name == "产业链企业财务指标":
        results = details.get("results", {})
        failed = [code for code, rows in results.items() if rows < 0]
        return (
            refresh_industry_chain_fundamentals(
                chain_id=details.get("chain_id"),
                company_codes=failed,
            )
            if failed
            else {}
        )

    if task_name == "产业链企业估值":
        results = details.get("results", {})
        failed = [code for code, rows in results.items() if rows < 0]
        return (
            refresh_industry_chain_valuations(
                chain_id=details.get("chain_id"),
                company_codes=failed,
            )
            if failed
            else {}
        )

    if task_name == "产业链业绩预告":
        periods = [date.fromisoformat(value) for value in details.get("report_periods", [])]
        return (
            refresh_industry_chain_forecasts(
                chain_id=details.get("chain_id"),
                company_codes=details.get("company_codes") or None,
                report_periods=periods or None,
            )
            if details.get("period_errors")
            else {}
        )

    if task_name == "新闻监控":
        return refresh_news_monitor()

    if task_name == "外盘季报":
        return refresh_overseas_earnings()

    if task_name == "ETF 基础信息":
        return refresh_etf_info()

    if task_name == "指数基本面":
        return refresh_fundamental_data()

    if task_name == "交易信号":
        return refresh_trade_signals()

    return None


def execute_backfill_plan(plan: list[dict]) -> list[dict]:
    """Execute supported health backfill tasks and return task results."""
    results = []
    for item in plan:
        task = item.get("task")
        codes = item.get("codes") or None
        if task == "etf_daily":
            result = refresh_etf_daily(codes=codes)
        elif task == "etf_info":
            result = refresh_etf_info()
        elif task == "index_valuation":
            result = refresh_index_valuation()
        elif task == "fundamental_data":
            result = refresh_fundamental_data()
        elif task == "bond_yield":
            result = refresh_bond_yield()
        elif task == "trade_signals":
            result = refresh_trade_signals()
        elif task == "industry_chain_companies":
            result = refresh_industry_chain_companies(company_codes=codes)
        elif task == "industry_chain_fundamentals":
            result = refresh_industry_chain_fundamental_bundle(company_codes=codes)
        elif task == "news_monitor":
            result = refresh_news_monitor()
        elif task == "overseas_earnings":
            result = refresh_overseas_earnings()
        else:
            continue
        results.append({"task": task, "任务": item.get("任务", task), "result": result})
    return results


def _submit_refresh_task(name: str, func, *args, task_key: str, **kwargs) -> None:
    from src.dashboard.task_runner import submit_dashboard_task

    try:
        task = submit_dashboard_task(
            name,
            func,
            *args,
            task_key=task_key,
            task_type="data_refresh",
            tags=["sidebar"],
            **kwargs,
        )
        st.success(f"已提交后台任务：{task.id}")
    except Exception as exc:
        st.error(f"提交失败: {exc}")


def _render_global_task_status() -> None:
    from src.dashboard.task_runner import clear_finished_dashboard_tasks, task_status_rows

    with st.sidebar.expander("后台任务", expanded=False):
        rows = task_status_rows(limit=8)
        if rows:
            active = sum(1 for row in rows if row["状态"] in {"queued", "running"})
            failed = sum(1 for row in rows if row["状态"] == "failed")
            summary = f"最近任务 {len(rows)} 个，运行中 {active} 个"
            if failed:
                summary += f"，失败 {failed} 个"
            st.caption(summary)
            display = pd.DataFrame(rows)[["任务", "状态", "类型", "创建时间", "结束时间", "错误"]]
            st.dataframe(display, width="stretch", hide_index=True, height=230)
            if st.button("清理成功任务", width="stretch", key="sidebar_clear_success_tasks"):
                removed = clear_finished_dashboard_tasks()
                st.success(f"已清理 {removed} 个任务")
                st.rerun()
        else:
            st.caption("暂无后台任务。")
        st.caption("数据管理入口：左侧主导航 -> 数据管理")


def render_refresh_sidebar() -> None:
    """在侧边栏渲染数据刷新面板"""
    _render_global_task_status()

    with st.sidebar.expander("🔄 数据管理"):
        st.caption("手动刷新数据（从 AkShare 抓取最新数据）")

        if st.button("📊 更新行情数据", width="stretch"):
            _submit_refresh_task(
                "ETF 行情补采",
                refresh_etf_daily,
                task_key="sidebar:etf_daily",
            )

        if st.button("🏷️ 更新 ETF 基础信息", width="stretch"):
            _submit_refresh_task(
                "ETF 基础信息补采",
                refresh_etf_info,
                task_key="sidebar:etf_info",
            )

        if st.button("📈 更新估值数据", width="stretch"):
            _submit_refresh_task(
                "指数估值补采",
                refresh_index_valuation,
                task_key="sidebar:index_valuation",
            )

        if st.button("📚 更新指数基本面", width="stretch"):
            _submit_refresh_task(
                "指数基本面补采",
                refresh_fundamental_data,
                task_key="sidebar:fundamental_data",
            )

        if st.button("🏦 更新国债收益率", width="stretch"):
            _submit_refresh_task(
                "国债收益率补采",
                refresh_bond_yield,
                task_key="sidebar:bond_yield",
            )

        if st.button("🎯 生成交易信号", width="stretch"):
            _submit_refresh_task(
                "交易信号生成",
                refresh_trade_signals,
                task_key="sidebar:trade_signals",
            )

        if st.button("🏭 更新产业链企业", width="stretch"):
            _submit_refresh_task(
                "产业链企业行情补采",
                refresh_industry_chain_companies,
                task_key="sidebar:industry_chain_companies",
            )

        if st.button("🧾 更新企业基本面", width="stretch"):
            _submit_refresh_task(
                "产业链企业基本面补采",
                refresh_industry_chain_fundamental_bundle,
                task_key="sidebar:industry_chain_fundamentals",
            )

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
