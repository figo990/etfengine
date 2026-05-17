"""Dashboard data health and freshness helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd

from src.core.config import get_etf_universe, settings
from src.data.storage import StorageEngine


@dataclass(frozen=True)
class FreshnessRule:
    label: str
    table: str
    column: str
    threshold_key: str
    refresh_task: str


FRESHNESS_RULES = [
    FreshnessRule("ETF 行情", "etf_daily", "trade_date", "market_data_max_age_days", "etf_daily"),
    FreshnessRule(
        "指数估值",
        "index_valuation",
        "trade_date",
        "market_data_max_age_days",
        "index_valuation",
    ),
    FreshnessRule(
        "国债收益率", "bond_yield", "trade_date", "market_data_max_age_days", "bond_yield"
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
    "index_valuation": "指数估值",
    "bond_yield": "国债收益率",
    "industry_chain_companies": "产业链企业行情",
    "industry_chain_fundamentals": "产业链企业基本面",
    "news_monitor": "新闻监控",
    "overseas_earnings": "外盘季报",
}


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
    return runs[runs["status"].isin(["failed", "partial"]) & (runs["finished_at"] >= cutoff)].copy()


def build_backfill_plan(
    freshness: pd.DataFrame,
    gaps: pd.DataFrame,
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
            failures = pd.DataFrame()
            backfill_plan = []
            return {
                "freshness": freshness,
                "gaps": gaps,
                "recent_failures": failures,
                "backfill_plan": backfill_plan,
                "issue_count": int((freshness["状态"] != "新鲜").sum())
                if not freshness.empty
                else 1,
            }
        freshness = get_table_freshness(storage, as_of=as_of)
        gaps = get_recent_market_gaps(storage, as_of=as_of)
        failures = get_recent_update_failures(storage)
    finally:
        if owns_storage:
            storage.close()
    backfill_plan = build_backfill_plan(freshness, gaps)
    return {
        "freshness": freshness,
        "gaps": gaps,
        "recent_failures": failures,
        "backfill_plan": backfill_plan,
        "issue_count": int((freshness["状态"] != "新鲜").sum()) + len(gaps) + len(failures),
    }
