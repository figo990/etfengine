"""Dashboard data health and freshness helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd

from src.core.config import get_etf_universe, load_yaml_config, settings
from src.data.storage import StorageEngine


@dataclass(frozen=True)
class FreshnessRule:
    label: str
    table: str
    column: str
    threshold_key: str
    refresh_task: str


FRESHNESS_RULES = [
    FreshnessRule("ETF 基础信息", "etf_info", "updated_at", "market_data_max_age_days", "etf_info"),
    FreshnessRule("ETF 行情", "etf_daily", "trade_date", "market_data_max_age_days", "etf_daily"),
    FreshnessRule(
        "指数估值",
        "index_valuation",
        "trade_date",
        "market_data_max_age_days",
        "index_valuation",
    ),
    FreshnessRule(
        "指数基本面",
        "fundamental_data",
        "trade_date",
        "market_data_max_age_days",
        "fundamental_data",
    ),
    FreshnessRule(
        "国债收益率", "bond_yield", "trade_date", "market_data_max_age_days", "bond_yield"
    ),
    FreshnessRule(
        "交易信号",
        "trade_signals",
        "signal_date",
        "market_data_max_age_days",
        "trade_signals",
    ),
    FreshnessRule("新闻资讯", "news_articles", "publish_time", "news_max_age_days", "news_monitor"),
    FreshnessRule(
        "产业链企业",
        "company_daily",
        "trade_date",
        "market_data_max_age_days",
        "industry_chain_companies",
    ),
    FreshnessRule(
        "企业财务",
        "company_fundamentals",
        "report_date",
        "company_fundamentals_max_age_days",
        "industry_chain_fundamentals",
    ),
    FreshnessRule(
        "企业估值",
        "company_valuation",
        "trade_date",
        "market_data_max_age_days",
        "industry_chain_fundamentals",
    ),
    FreshnessRule(
        "业绩预告",
        "company_earnings_forecasts",
        "announce_date",
        "company_forecasts_max_age_days",
        "industry_chain_fundamentals",
    ),
    FreshnessRule(
        "外盘季报",
        "overseas_earnings_metrics",
        "period_end",
        "overseas_earnings_max_age_days",
        "overseas_earnings",
    ),
]

AUTO_BACKFILL_TASKS = {
    "etf_daily": "ETF 行情",
    "etf_info": "ETF 基础信息",
    "index_valuation": "指数估值",
    "fundamental_data": "指数基本面",
    "bond_yield": "国债收益率",
    "trade_signals": "交易信号",
    "industry_chain_companies": "产业链企业行情",
    "industry_chain_fundamentals": "产业链企业基本面",
    "news_monitor": "新闻监控",
    "overseas_earnings": "外盘季报",
}

HISTORY_DEPTH_DAYS = 183


def _as_of_date(as_of: date | None = None) -> date:
    return as_of or date.today()


def _freshness_status(
    latest_value: object,
    count: int,
    threshold_days: int,
    *,
    as_of: date,
) -> tuple[int | None, str]:
    if count <= 0 or not latest_value:
        return None, "缺失"
    latest_ts = pd.to_datetime(latest_value, errors="coerce")
    if pd.isna(latest_ts):
        return None, "待确认"
    lag_days = max((as_of - latest_ts.date()).days, 0)
    return lag_days, "新鲜" if lag_days <= threshold_days else "过期"


def get_table_freshness(
    storage: StorageEngine | None = None,
    *,
    as_of: date | None = None,
) -> pd.DataFrame:
    """Return latest dates and freshness status for key local data tables."""
    as_of = _as_of_date(as_of)
    health_cfg = settings().data_health
    owns_storage = storage is None
    storage = storage or StorageEngine()
    rows = []
    try:
        try:
            storage.init_schema()
        except Exception as exc:
            return pd.DataFrame(
                [
                    {
                        "数据": rule.label,
                        "最新日期": "",
                        "记录数": 0,
                        "滞后天数": None,
                        "阈值天数": int(getattr(health_cfg, rule.threshold_key)),
                        "状态": "不可用",
                        "建议动作": rule.refresh_task,
                        "错误": str(exc),
                    }
                    for rule in FRESHNESS_RULES
                ]
            )
        for rule in FRESHNESS_RULES:
            try:
                latest = storage.conn.execute(
                    f"SELECT MAX({rule.column}) FROM {rule.table}"
                ).fetchone()
                count = storage.conn.execute(f"SELECT COUNT(*) FROM {rule.table}").fetchone()
                threshold_days = int(getattr(health_cfg, rule.threshold_key))
                lag_days, status = _freshness_status(
                    latest[0] if latest else None,
                    int(count[0]) if count else 0,
                    threshold_days,
                    as_of=as_of,
                )
                rows.append(
                    {
                        "数据": rule.label,
                        "最新日期": str(latest[0]) if latest and latest[0] else "",
                        "记录数": int(count[0]) if count else 0,
                        "滞后天数": lag_days,
                        "阈值天数": threshold_days,
                        "状态": status,
                        "建议动作": rule.refresh_task,
                    }
                )
            except Exception:
                rows.append(
                    {
                        "数据": rule.label,
                        "最新日期": "",
                        "记录数": 0,
                        "滞后天数": None,
                        "阈值天数": int(getattr(health_cfg, rule.threshold_key)),
                        "状态": "缺失",
                        "建议动作": rule.refresh_task,
                    }
                )
    finally:
        if owns_storage:
            storage.close()
    return pd.DataFrame(rows)


def _configured_etf_codes() -> list[str]:
    universe = get_etf_universe()
    return [
        item["code"] for category in universe.get("etf_universe", {}).values() for item in category
    ]


def _configured_index_names() -> list[str]:
    return ["沪深300", "中证500", "中证1000", "上证50", "中证红利"]


def _configured_overseas_tickers() -> list[str]:
    try:
        cfg = load_yaml_config("overseas_earnings.yaml")
        return [
            ticker
            for item in cfg.get("watchlist", [])
            if (ticker := str(item.get("ticker", "")).upper()) and item.get("cik") != "skip"
        ]
    except Exception:
        return []


def _industry_company_codes(storage: StorageEngine) -> list[str]:
    rows = storage.conn.execute(
        "SELECT DISTINCT company_code FROM industry_chain_companies ORDER BY company_code"
    ).fetchall()
    return [str(row[0]) for row in rows]


def _entity_codes(storage: StorageEngine, table: str, key_column: str) -> list[str]:
    if table == "etf_daily":
        return _configured_etf_codes()
    if table in {"company_daily", "company_valuation"}:
        rows = storage.conn.execute(
            "SELECT DISTINCT company_code FROM industry_chain_companies ORDER BY company_code"
        ).fetchall()
        return [str(row[0]) for row in rows]
    rows = storage.conn.execute(
        f"SELECT DISTINCT {key_column} FROM {table} ORDER BY {key_column}"
    ).fetchall()
    return [str(row[0]) for row in rows]


def _coverage_row(
    storage: StorageEngine,
    *,
    label: str,
    expected_codes: list[str],
    table: str,
    key_column: str,
    refresh_task: str,
) -> dict[str, Any] | None:
    expected = sorted({str(code) for code in expected_codes if str(code)})
    if not expected:
        return None
    placeholders = ", ".join(["?"] * len(expected))
    rows = storage.conn.execute(
        f"""
        SELECT DISTINCT {key_column}
        FROM {table}
        WHERE {key_column} IN ({placeholders})
        ORDER BY {key_column}
        """,
        expected,
    ).fetchall()
    actual = {str(row[0]) for row in rows}
    missing = [code for code in expected if code not in actual]
    coverage = round((len(expected) - len(missing)) / len(expected), 4)
    return {
        "数据": label,
        "预期数": len(expected),
        "已覆盖数": len(expected) - len(missing),
        "覆盖率": coverage,
        "缺失代码": ", ".join(missing[:20]),
        "建议动作": refresh_task,
        "状态": "完整" if not missing else "缺失",
    }


def get_entity_coverage(
    storage: StorageEngine | None = None,
) -> pd.DataFrame:
    """Return expected-entity coverage for key datasets."""
    owns_storage = storage is None
    storage = storage or StorageEngine()
    try:
        try:
            storage.init_schema()
        except Exception:
            return pd.DataFrame()
        rows = [
            _coverage_row(
                storage,
                label="ETF 基础信息",
                expected_codes=_configured_etf_codes(),
                table="etf_info",
                key_column="code",
                refresh_task="etf_info",
            ),
            _coverage_row(
                storage,
                label="ETF 行情",
                expected_codes=_configured_etf_codes(),
                table="etf_daily",
                key_column="code",
                refresh_task="etf_daily",
            ),
            _coverage_row(
                storage,
                label="指数估值",
                expected_codes=_configured_index_names(),
                table="index_valuation",
                key_column="index_name",
                refresh_task="index_valuation",
            ),
            _coverage_row(
                storage,
                label="指数基本面",
                expected_codes=_configured_index_names(),
                table="fundamental_data",
                key_column="index_name",
                refresh_task="fundamental_data",
            ),
            _coverage_row(
                storage,
                label="产业链企业行情",
                expected_codes=_industry_company_codes(storage),
                table="company_daily",
                key_column="company_code",
                refresh_task="industry_chain_companies",
            ),
            _coverage_row(
                storage,
                label="产业链企业财务",
                expected_codes=_industry_company_codes(storage),
                table="company_fundamentals",
                key_column="company_code",
                refresh_task="industry_chain_fundamentals",
            ),
            _coverage_row(
                storage,
                label="产业链企业估值",
                expected_codes=_industry_company_codes(storage),
                table="company_valuation",
                key_column="company_code",
                refresh_task="industry_chain_fundamentals",
            ),
            _coverage_row(
                storage,
                label="外盘季报",
                expected_codes=_configured_overseas_tickers(),
                table="overseas_earnings_metrics",
                key_column="ticker",
                refresh_task="overseas_earnings",
            ),
        ]
        return pd.DataFrame([row for row in rows if row])
    finally:
        if owns_storage:
            storage.close()


def _recent_gaps_for_table(
    storage: StorageEngine,
    *,
    label: str,
    table: str,
    key_column: str,
    date_column: str,
    refresh_task: str,
    lookback_days: int,
    tolerance_days: int,
    as_of: date,
) -> list[dict[str, Any]]:
    start = as_of - timedelta(days=lookback_days)
    reference_df = storage.conn.execute(
        f"""
        SELECT DISTINCT {date_column} AS trade_date
        FROM {table}
        WHERE {date_column} >= ?
        ORDER BY {date_column}
        """,
        [start],
    ).fetchdf()
    if reference_df.empty:
        return []

    reference_dates = {
        pd.Timestamp(value).date() for value in reference_df["trade_date"].dropna().tolist()
    }
    actual_df = storage.conn.execute(
        f"""
        SELECT {key_column} AS code, {date_column} AS trade_date
        FROM {table}
        WHERE {date_column} >= ?
        """,
        [start],
    ).fetchdf()
    actual_map = {
        str(code): {pd.Timestamp(value).date() for value in group["trade_date"].dropna()}
        for code, group in actual_df.groupby("code")
    }
    rows = []
    for code in _entity_codes(storage, table, key_column):
        actual_dates = actual_map.get(code, set())
        missing_dates = sorted(reference_dates - actual_dates)
        if len(missing_dates) <= tolerance_days:
            continue
        rows.append(
            {
                "数据": label,
                "代码": code,
                "缺口天数": len(missing_dates),
                "缺口日期": ", ".join(value.isoformat() for value in missing_dates[-8:]),
                "最新日期": max(actual_dates).isoformat() if actual_dates else "",
                "建议动作": refresh_task,
            }
        )
    return rows


def get_recent_market_gaps(
    storage: StorageEngine | None = None,
    *,
    as_of: date | None = None,
) -> pd.DataFrame:
    """Return recent daily-series gaps based on locally observed trading dates."""
    as_of = _as_of_date(as_of)
    health_cfg = settings().data_health
    owns_storage = storage is None
    storage = storage or StorageEngine()
    try:
        try:
            storage.init_schema()
        except Exception:
            return pd.DataFrame()
        rows = []
        rows.extend(
            _recent_gaps_for_table(
                storage,
                label="ETF 行情",
                table="etf_daily",
                key_column="code",
                date_column="trade_date",
                refresh_task="etf_daily",
                lookback_days=health_cfg.recent_gap_lookback_days,
                tolerance_days=health_cfg.recent_gap_tolerance_days,
                as_of=as_of,
            )
        )
        rows.extend(
            _recent_gaps_for_table(
                storage,
                label="产业链企业",
                table="company_daily",
                key_column="company_code",
                date_column="trade_date",
                refresh_task="industry_chain_companies",
                lookback_days=health_cfg.recent_gap_lookback_days,
                tolerance_days=health_cfg.recent_gap_tolerance_days,
                as_of=as_of,
            )
        )
        rows.extend(
            _recent_gaps_for_table(
                storage,
                label="企业估值",
                table="company_valuation",
                key_column="company_code",
                date_column="trade_date",
                refresh_task="industry_chain_fundamentals",
                lookback_days=health_cfg.recent_gap_lookback_days,
                tolerance_days=health_cfg.recent_gap_tolerance_days,
                as_of=as_of,
            )
        )
    finally:
        if owns_storage:
            storage.close()
    return pd.DataFrame(rows)


def get_recent_update_failures(
    storage: StorageEngine | None = None,
    *,
    as_of: datetime | None = None,
) -> pd.DataFrame:
    """Return recent failed or partial update runs."""
    as_of = as_of or datetime.now()
    health_cfg = settings().data_health
    owns_storage = storage is None
    storage = storage or StorageEngine()
    try:
        try:
            storage.init_schema()
        except Exception:
            return pd.DataFrame()
        runs = storage.get_data_update_runs(limit=200)
    finally:
        if owns_storage:
            storage.close()
    if runs.empty:
        return runs
    runs = runs.copy()
    runs["finished_at"] = pd.to_datetime(runs["finished_at"], errors="coerce")
    cutoff = as_of - timedelta(hours=health_cfg.recent_failure_window_hours)
    recent = runs[runs["finished_at"] >= cutoff].copy()
    failures = recent[recent["status"].isin(["failed", "partial"])].copy()
    if failures.empty:
        return failures

    success_runs = recent[recent["status"] == "success"][["task_name", "finished_at"]]
    if success_runs.empty:
        return failures

    latest_success = success_runs.groupby("task_name")["finished_at"].max().to_dict()
    return failures[
        failures.apply(
            lambda row: pd.isna(row["finished_at"])
            or row["finished_at"] > latest_success.get(row["task_name"], pd.Timestamp.min),
            axis=1,
        )
    ].copy()


def _history_depth_row(
    storage: StorageEngine,
    *,
    label: str,
    table: str,
    date_column: str,
    refresh_task: str,
    min_days: int,
) -> dict[str, Any]:
    row = storage.conn.execute(
        f"SELECT MIN({date_column}), MAX({date_column}), COUNT(*) FROM {table}"
    ).fetchone()
    earliest, latest, count = row if row else (None, None, 0)
    if not earliest or not latest or not count:
        depth_days = 0
        status = "缺失"
    else:
        earliest_date = pd.Timestamp(earliest).date()
        latest_date = pd.Timestamp(latest).date()
        depth_days = max((latest_date - earliest_date).days, 0)
        status = "充足" if depth_days >= min_days else "不足"
    return {
        "数据": label,
        "最早日期": str(earliest) if earliest else "",
        "最新日期": str(latest) if latest else "",
        "记录数": int(count or 0),
        "历史天数": depth_days,
        "目标天数": min_days,
        "状态": status,
        "建议动作": refresh_task,
    }


def get_history_depth(
    storage: StorageEngine | None = None,
    *,
    min_days: int = HISTORY_DEPTH_DAYS,
) -> pd.DataFrame:
    """Return historical depth for datasets expected to support trend analysis."""
    owns_storage = storage is None
    storage = storage or StorageEngine()
    try:
        try:
            storage.init_schema()
        except Exception:
            return pd.DataFrame()
        rows = [
            _history_depth_row(
                storage,
                label="ETF 行情",
                table="etf_daily",
                date_column="trade_date",
                refresh_task="etf_daily",
                min_days=min_days,
            ),
            _history_depth_row(
                storage,
                label="指数估值",
                table="index_valuation",
                date_column="trade_date",
                refresh_task="index_valuation",
                min_days=min_days,
            ),
            _history_depth_row(
                storage,
                label="指数基本面",
                table="fundamental_data",
                date_column="trade_date",
                refresh_task="fundamental_data",
                min_days=min_days,
            ),
            _history_depth_row(
                storage,
                label="新闻资讯",
                table="news_articles",
                date_column="publish_time",
                refresh_task="news_monitor",
                min_days=min_days,
            ),
            _history_depth_row(
                storage,
                label="产业链企业行情",
                table="company_daily",
                date_column="trade_date",
                refresh_task="industry_chain_companies",
                min_days=min_days,
            ),
            _history_depth_row(
                storage,
                label="企业估值",
                table="company_valuation",
                date_column="trade_date",
                refresh_task="industry_chain_fundamentals",
                min_days=min_days,
            ),
        ]
        return pd.DataFrame(rows)
    finally:
        if owns_storage:
            storage.close()


def build_backfill_plan(
    freshness: pd.DataFrame,
    gaps: pd.DataFrame,
    coverage: pd.DataFrame | None = None,
) -> list[dict[str, Any]]:
    """Build a de-duplicated manual backfill plan from stale tables and gaps."""
    planned: dict[str, dict[str, Any]] = {}

    def add_task(task: str, reason: str, codes: list[str] | None = None) -> None:
        item = planned.setdefault(
            task,
            {
                "task": task,
                "任务": AUTO_BACKFILL_TASKS.get(task, task),
                "原因": [],
                "codes": set(),
                "可自动执行": task in AUTO_BACKFILL_TASKS,
            },
        )
        item["原因"].append(reason)
        item["codes"].update(codes or [])

    for _, row in freshness.iterrows():
        if row.get("状态") in {"缺失", "过期"}:
            add_task(str(row["建议动作"]), f"{row['数据']} {row['状态']}")

    if not gaps.empty:
        for task, sub in gaps.groupby("建议动作"):
            add_task(
                str(task),
                f"{sub['数据'].iloc[0]}存在 {len(sub)} 个标的断档",
                [str(code) for code in sub["代码"].tolist()],
            )

    if coverage is not None and not coverage.empty:
        for task, sub in coverage[coverage["状态"] != "完整"].groupby("建议动作"):
            missing_codes = []
            for value in sub["缺失代码"].dropna().tolist():
                missing_codes.extend(
                    [code.strip() for code in str(value).split(",") if code.strip()]
                )
            add_task(
                str(task),
                f"{sub['数据'].iloc[0]}覆盖不完整",
                missing_codes,
            )

    rows = []
    for item in planned.values():
        rows.append(
            {
                **item,
                "原因": "；".join(dict.fromkeys(item["原因"])),
                "codes": sorted(item["codes"]),
            }
        )
    return sorted(rows, key=lambda row: row["任务"])


def get_data_health_report(
    storage: StorageEngine | None = None,
    *,
    as_of: date | None = None,
) -> dict[str, Any]:
    """Return a consolidated health report for UI, API, and scheduler alerts."""
    owns_storage = storage is None
    storage = storage or StorageEngine()
    try:
        try:
            storage.init_schema()
        except Exception:
            freshness = get_table_freshness(storage, as_of=as_of)
            gaps = pd.DataFrame()
            coverage = pd.DataFrame()
            history_depth = pd.DataFrame()
            failures = pd.DataFrame()
            backfill_plan = []
            return {
                "freshness": freshness,
                "gaps": gaps,
                "coverage": coverage,
                "history_depth": history_depth,
                "recent_failures": failures,
                "backfill_plan": backfill_plan,
                "issue_count": int((freshness["状态"] != "新鲜").sum())
                if not freshness.empty
                else 1,
            }
        freshness = get_table_freshness(storage, as_of=as_of)
        gaps = get_recent_market_gaps(storage, as_of=as_of)
        coverage = get_entity_coverage(storage)
        history_depth = get_history_depth(storage)
        failures = get_recent_update_failures(storage)
    finally:
        if owns_storage:
            storage.close()
    backfill_plan = build_backfill_plan(freshness, gaps, coverage)
    return {
        "freshness": freshness,
        "gaps": gaps,
        "coverage": coverage,
        "history_depth": history_depth,
        "recent_failures": failures,
        "backfill_plan": backfill_plan,
        "issue_count": int((freshness["状态"] != "新鲜").sum())
        + len(gaps)
        + len(coverage[coverage["状态"] != "完整"])
        + len(failures),
    }
