"""Reusable investment report builder for the dashboard and future jobs."""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
from loguru import logger

from src.core.config import PROJECT_ROOT, get_portfolio_config
from src.dashboard.data_status import get_table_freshness
from src.data.storage import StorageEngine
from src.intelligence.industry_chain_analyzer import IndustryChainAnalyzer

DEFAULT_INDICES = ["沪深300", "中证500", "中证1000", "上证50", "中证红利"]
REPORT_DIR = PROJECT_ROOT / "data" / "reports"


def generate_investment_report(
    report_type: str,
    report_date: date,
    storage: StorageEngine | None = None,
    portfolio_config: dict[str, Any] | None = None,
    include_industry_chains: bool = True,
) -> str:
    """Generate a Markdown investment report from local DuckDB data."""
    owns_storage = storage is None
    storage = storage or StorageEngine()
    if portfolio_config is None:
        portfolio_config = _safe_portfolio_config()

    try:
        storage.init_schema()
        lines = [
            f"# ETFEngine {report_type}",
            "",
            f"**报告日期**: {report_date}",
            "",
        ]
        lines.extend(_data_freshness_section(storage, report_date))
        lines.extend(_valuation_section(storage))
        lines.extend(_bond_section(storage))
        lines.extend(_portfolio_section(storage, portfolio_config))
        if include_industry_chains:
            lines.extend(_industry_chain_section(storage))
        lines.extend(_major_news_section(storage))
        lines.extend(_overseas_earnings_section(storage))
        lines.extend(
            [
                "",
                "---",
                "",
                "> 本报告由 ETFEngine 基于本地数据库生成，仅供研究参考，不构成投资建议。",
            ]
        )
        return "\n".join(lines)
    finally:
        if owns_storage:
            storage.close()


def generate_and_save_investment_report(
    report_type: str,
    report_date: date | str,
    include_industry_chains: bool = True,
) -> dict[str, Any]:
    """Generate an investment report, save it as Markdown, and return task metadata."""
    parsed_date = report_date if isinstance(report_date, date) else date.fromisoformat(report_date)
    report_md = generate_investment_report(
        report_type,
        parsed_date,
        include_industry_chains=include_industry_chains,
    )
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / _report_filename(report_type, parsed_date)
    report_path.write_text(report_md, encoding="utf-8")
    return {
        "type": "investment_report",
        "report_type": report_type,
        "report_date": parsed_date.isoformat(),
        "report_path": str(report_path),
        "file_name": report_path.name,
        "size_bytes": report_path.stat().st_size,
        "preview": report_md[:5000],
    }


def _report_filename(report_type: str, report_date: date) -> str:
    if report_type == "周报":
        return f"weekly_{report_date}.md"
    return f"monthly_{report_date.strftime('%Y%m')}.md"


def _safe_portfolio_config() -> dict[str, Any]:
    try:
        return get_portfolio_config()
    except Exception as exc:
        logger.debug(f"报告: 组合配置加载失败: {exc}")
        return {"portfolio": {"holdings": []}}


def _data_freshness_section(storage: StorageEngine, report_date: date) -> list[str]:
    freshness = get_table_freshness(storage)
    rows = []
    for _, row in freshness.iterrows():
        latest = str(row.get("最新日期", "") or "")
        count = int(row.get("记录数", 0) or 0)
        rows.append(
            [
                row.get("数据", ""),
                latest or "--",
                str(count),
                row.get("状态") or _freshness_label(latest, count, report_date),
            ]
        )
    return [
        "## 数据新鲜度",
        "",
        *_markdown_table(["数据", "最新日期", "记录数", "状态"], rows),
        "",
    ]


def _valuation_section(storage: StorageEngine) -> list[str]:
    rows = []
    for index_name in DEFAULT_INDICES:
        try:
            df = storage.get_index_valuation(index_name)
            latest = df.iloc[-1] if not df.empty else {}
            rows.append(
                [
                    index_name,
                    str(latest.get("trade_date", "--") or "--"),
                    _fmt_num(latest.get("pe")),
                    _fmt_pct(latest.get("pe_percentile"), signed=False),
                    _fmt_num(latest.get("pb")),
                    _fmt_pct(latest.get("dividend_yield"), signed=False),
                ]
            )
        except Exception as exc:
            logger.debug(f"报告: {index_name} 估值获取失败: {exc}")
            rows.append([index_name, "--", "--", "--", "--", "--"])

    return [
        "## 市场估值快照",
        "",
        *_markdown_table(["指数", "日期", "PE", "PE百分位", "PB", "股息率"], rows),
        "",
    ]


def _bond_section(storage: StorageEngine) -> list[str]:
    lines = ["## 股债性价比", ""]
    try:
        bond_df = storage.get_bond_yield()
        val_df = storage.get_index_valuation("沪深300")
        if bond_df.empty or val_df.empty:
            return [*lines, "- 股债数据暂不可用。", ""]

        bond_latest = bond_df.iloc[-1]
        val_latest = val_df.iloc[-1]
        cn10y = _safe_float(bond_latest.get("cn_10y"))
        pe = _safe_float(val_latest.get("pe"))
        if not cn10y or not pe:
            return [*lines, "- 沪深300 PE 或 10年期国债收益率缺失。", ""]

        earnings_yield = 1 / pe * 100
        erp = earnings_yield - cn10y
        lines.extend(
            [
                f"- 沪深300 E/P: {earnings_yield:.2f}%",
                f"- 10年期国债: {cn10y:.2f}%",
                f"- ERP(股债利差): {erp:.2f}%",
                f"- 判断: {_erp_label(erp)}",
                "",
            ]
        )
        return lines
    except Exception as exc:
        logger.debug(f"报告: 股债数据加载失败: {exc}")
        return [*lines, "- 股债数据暂不可用。", ""]


def _portfolio_section(storage: StorageEngine, portfolio_config: dict[str, Any]) -> list[str]:
    portfolio = portfolio_config.get("portfolio", {})
    holdings = portfolio.get("holdings", [])
    lines = ["## 组合持仓与风险", ""]
    if not holdings:
        return [*lines, "- 暂无组合持仓配置。", ""]

    total_capital = float(portfolio.get("total_capital", 0) or 0)
    rows = []
    price_history: dict[str, pd.DataFrame] = {}
    weights: dict[str, float] = {}
    for holding in holdings:
        code = str(holding.get("etf", ""))
        target_weight = float(holding.get("target_weight", 0) or 0)
        weights[code] = target_weight
        latest_price = None
        latest_date = "--"
        try:
            df = storage.get_etf_daily(code)
            price_history[code] = df
            if not df.empty:
                latest = df.iloc[-1]
                latest_price = latest.get("close")
                latest_date = str(latest.get("trade_date", "--") or "--")
        except Exception as exc:
            logger.debug(f"报告: ETF {code} 行情获取失败: {exc}")
        rows.append(
            [
                code,
                str(holding.get("name", code)),
                _fmt_pct(target_weight * 100, signed=False),
                _fmt_money(total_capital * target_weight),
                _fmt_num(latest_price, digits=3),
                latest_date,
            ]
        )

    lines.extend(
        _markdown_table(
            ["ETF", "名称", "目标权重", "目标金额", "最新价", "数据日期"],
            rows,
        )
    )
    total_weight = sum(weights.values())
    risk_cfg = portfolio.get("risk_limits", {})
    max_drawdown_alert = float(risk_cfg.get("max_drawdown_alert", 0.15) or 0.15)
    lines.extend(
        [
            "",
            f"- 权重合计: {total_weight * 100:.1f}%",
            f"- 最大回撤预警线: {max_drawdown_alert * 100:.0f}%",
            f"- 单 ETF 仓位区间: "
            f"{float(risk_cfg.get('min_single_position', 0.05)) * 100:.0f}%"
            f" - {float(risk_cfg.get('max_single_position', 0.40)) * 100:.0f}%",
        ]
    )

    risk = _portfolio_risk(price_history, weights)
    if risk:
        lines.extend(
            [
                f"- 组合近20日收益: {_fmt_pct(risk['return_20d'])}",
                f"- 组合近60日收益: {_fmt_pct(risk['return_60d'])}",
                f"- 区间最大回撤: {_fmt_pct(risk['max_drawdown'])}",
            ]
        )
        if abs(risk["max_drawdown"]) / 100 >= max_drawdown_alert:
            lines.append("- 风险提示: 当前最大回撤已触及或超过预警线。")
    else:
        lines.append("- 组合风险指标暂不可用，需要补齐 ETF 历史行情。")

    if abs(total_weight - 1.0) > 0.01:
        lines.append("- 配置提示: 目标权重合计未等于 100%，建议在组合中心校正。")
    lines.append("")
    return lines


def _industry_chain_section(storage: StorageEngine) -> list[str]:
    lines = ["## 产业链洞察", ""]
    try:
        analyzer = IndustryChainAnalyzer(storage)
        chains = analyzer.list_chains()
        if not chains:
            return [*lines, "- 暂无产业链配置。", ""]

        rows = []
        notes = []
        for chain in chains:
            try:
                snapshot = analyzer.build_snapshot(chain["chain_id"], link_news=False)
            except Exception as exc:
                logger.debug(f"报告: 产业链 {chain['chain_id']} 快照失败: {exc}")
                notes.append(f"- {chain.get('name', chain['chain_id'])}: 快照生成失败。")
                continue
            overview = snapshot["overview"]
            quality = snapshot.get("data_quality", {})
            rows.append(
                [
                    snapshot["name"],
                    overview["trend_label"],
                    str(overview["news_count"]),
                    str(overview["high_impact_news_count"]),
                    _fmt_pct(overview["avg_sentiment"], signed=True, digits=2, suffix=""),
                    f"{float(quality.get('company_price_coverage', 0)) * 100:.0f}%",
                    snapshot["analysis"]["risk"],
                ]
            )
        output = [
            *lines,
            *_markdown_table(
                ["产业链", "趋势", "新闻", "高影响", "情绪", "行情覆盖", "风险"],
                rows,
            ),
        ]
        output.extend(notes)
        output.append("")
        return output
    except Exception as exc:
        logger.debug(f"报告: 产业链洞察加载失败: {exc}")
        return [*lines, "- 产业链数据暂不可用。", ""]


def _major_news_section(storage: StorageEngine) -> list[str]:
    lines = ["## 重大新闻", ""]
    try:
        news = storage.get_news_articles(limit=50)
        if news.empty:
            return [*lines, "- 暂无新闻数据。", ""]
        ranked = news.copy()
        ranked["rank"] = ranked.apply(_news_rank, axis=1)
        ranked = ranked.sort_values(["rank", "publish_time"], ascending=[False, False])
        selected = ranked.head(8)
        for _, row in selected.iterrows():
            title = str(row.get("title", "") or "")
            source = str(row.get("source", "") or "")
            publish_time = str(row.get("publish_time", "") or "")
            impact = str(row.get("impact_level", "low") or "low")
            sentiment = _fmt_pct(row.get("sentiment"), signed=True, digits=2, suffix="")
            lines.append(f"- {publish_time} [{impact}] {title} ({source}, 情绪 {sentiment})")
        lines.append("")
        return lines
    except Exception as exc:
        logger.debug(f"报告: 重大新闻加载失败: {exc}")
        return [*lines, "- 重大新闻暂不可用。", ""]


def _overseas_earnings_section(storage: StorageEngine) -> list[str]:
    lines = ["## 外盘季报观察", ""]
    try:
        metrics = storage.get_overseas_earnings_metrics(limit=5000)
        if metrics.empty:
            return [*lines, "- 暂无海外季报数据。", ""]

        metrics = metrics.sort_values("period_end")
        latest_idx = metrics.groupby("ticker")["period_end"].idxmax()
        latest = metrics.loc[latest_idx].copy()
        analysis = storage.get_overseas_earnings_analysis(limit=1000)
        if not analysis.empty:
            analysis = analysis.sort_values("analyzed_at", ascending=False)
            latest_analysis = analysis.groupby(["ticker", "period_end"]).first().reset_index()
            latest = latest.merge(
                latest_analysis,
                on=["ticker", "period_end"],
                how="left",
                suffixes=("", "_analysis"),
            )
        rows = []
        for _, row in latest.sort_values("ticker").head(10).iterrows():
            rows.append(
                [
                    row.get("ticker", ""),
                    row.get("company_name", ""),
                    str(row.get("period_end", "--") or "--"),
                    _fmt_pct(row.get("revenue_yoy_pct")),
                    _fmt_pct(row.get("net_income_yoy_pct")),
                    row.get("impact_level", "--") or "--",
                ]
            )
        return [
            *lines,
            *_markdown_table(["Ticker", "公司", "期末", "营收YoY", "净利YoY", "影响"], rows),
            "",
        ]
    except Exception as exc:
        logger.debug(f"报告: 外盘季报加载失败: {exc}")
        return [*lines, "- 外盘季报暂不可用。", ""]


def _portfolio_risk(
    price_history: dict[str, pd.DataFrame],
    weights: dict[str, float],
) -> dict[str, float] | None:
    series = {}
    for code, df in price_history.items():
        if df.empty or "close" not in df.columns:
            continue
        data = df[["trade_date", "close"]].dropna().copy()
        if data.empty:
            continue
        data["trade_date"] = pd.to_datetime(data["trade_date"], errors="coerce")
        data = data.dropna(subset=["trade_date"]).sort_values("trade_date")
        series[code] = data.set_index("trade_date")["close"].astype(float)
    if not series:
        return None

    prices = pd.DataFrame(series).sort_index().ffill().dropna()
    if len(prices) < 2:
        return None
    normalized = prices / prices.iloc[0]
    weight_series = pd.Series(weights).reindex(normalized.columns).fillna(0)
    if weight_series.sum() <= 0:
        return None
    weight_series = weight_series / weight_series.sum()
    portfolio = normalized.mul(weight_series, axis=1).sum(axis=1)
    drawdown = portfolio / portfolio.cummax() - 1
    return {
        "return_20d": _period_return(portfolio, 20),
        "return_60d": _period_return(portfolio, 60),
        "max_drawdown": round(float(drawdown.min()) * 100, 2),
    }


def _period_return(series: pd.Series, periods: int) -> float | None:
    if len(series) <= periods:
        return None
    prev = series.iloc[-periods - 1]
    now = series.iloc[-1]
    if pd.isna(prev) or pd.isna(now) or prev == 0:
        return None
    return round((float(now) / float(prev) - 1) * 100, 2)


def _freshness_label(value: str, count: int, as_of: date) -> str:
    if count <= 0 or not value:
        return "缺失"
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return "待确认"
    days = max((as_of - ts.date()).days, 0)
    if days <= 3:
        return "新鲜"
    if days <= 30:
        return "需关注"
    return "过旧"


def _erp_label(erp: float) -> str:
    if erp > 3:
        return "股市性价比较高，适合偏积极跟踪"
    if erp > 1:
        return "股债相对均衡，维持组合纪律"
    return "股市风险补偿偏低，注意估值回撤"


def _news_rank(row: pd.Series) -> float:
    impact_score = {"high": 3, "medium": 2, "low": 1}.get(row.get("impact_level"), 0)
    policy_score = 1 if bool(row.get("is_policy", False)) else 0
    sentiment_score = abs(_safe_float(row.get("sentiment")) or 0)
    return impact_score + policy_score + sentiment_score


def _markdown_table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    if not rows:
        return ["暂无数据。"]
    normalized_headers = [_escape_cell(header) for header in headers]
    lines = [
        "| " + " | ".join(normalized_headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_escape_cell(item) for item in row) + " |")
    return lines


def _escape_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _fmt_money(value: Any) -> str:
    number = _safe_float(value)
    if number is None:
        return "--"
    return f"¥{number:,.0f}"


def _fmt_num(value: Any, digits: int = 2) -> str:
    number = _safe_float(value)
    if number is None:
        return "--"
    return f"{number:.{digits}f}"


def _fmt_pct(
    value: Any,
    signed: bool = True,
    digits: int = 1,
    suffix: str = "%",
) -> str:
    number = _safe_float(value)
    if number is None:
        return "--"
    sign = "+" if signed else ""
    return f"{number:{sign}.{digits}f}{suffix}"


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
