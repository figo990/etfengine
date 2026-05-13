"""美股季报指标加工：同比、简报文本"""

from __future__ import annotations

from src.data.providers.us_sec_earnings_provider import QuarterlyFactPoint


def attach_yoy_metrics(
    ticker: str,
    company_name: str,
    points: list[QuarterlyFactPoint],
) -> list[dict]:
    """将 SEC 季报点转为可入库行，并计算同比（同财季 fy-1）。"""
    idx = {(p.fiscal_year, p.fiscal_period): p for p in points}
    rows: list[dict] = []
    for p in sorted(points, key=lambda x: (x.period_end, x.fiscal_year, x.fiscal_period)):
        prev = idx.get((p.fiscal_year - 1, p.fiscal_period))
        rev_yoy = None
        ni_yoy = None
        if prev and prev.revenue and p.revenue and prev.revenue != 0:
            rev_yoy = (p.revenue / prev.revenue - 1) * 100
        if prev and prev.net_income is not None and p.net_income is not None and prev.net_income != 0:
            ni_yoy = (p.net_income / prev.net_income - 1) * 100

        rows.append({
            "ticker": ticker.upper(),
            "company_name": company_name,
            "period_end": p.period_end,
            "fiscal_year": p.fiscal_year,
            "fiscal_period": p.fiscal_period,
            "form": p.form,
            "filed_date": p.filed,
            "revenue_usd": p.revenue,
            "net_income_usd": p.net_income,
            "eps_diluted": p.eps_diluted,
            "revenue_yoy_pct": rev_yoy,
            "net_income_yoy_pct": ni_yoy,
            "revenue_tag": p.revenue_tag,
            "net_income_tag": p.net_income_tag,
            "eps_tag": p.eps_tag,
        })
    return rows


def build_fact_brief_cn(
    ticker: str,
    company_name: str,
    row: dict,
) -> str:
    """基于结构化字段生成中文事实简报（不依赖 LLM）。"""
    fy = row.get("fiscal_year")
    fp = row.get("fiscal_period")
    rev = row.get("revenue_usd")
    ni = row.get("net_income_usd")
    eps = row.get("eps_diluted")
    ry = row.get("revenue_yoy_pct")
    ny = row.get("net_income_yoy_pct")

    parts = [f"{company_name}（{ticker}）{fy}{fp} 财报要点（SEC XBRL 汇总）："]
    if rev is not None:
        parts.append(f"营收约 {rev/1e8:.2f} 亿美元。")
    if ry is not None:
        parts.append(f"营收同比约 {ry:+.1f}%。")
    if ni is not None:
        parts.append(f"净利润约 {ni/1e8:.2f} 亿美元。")
    if ny is not None:
        parts.append(f"净利润同比约 {ny:+.1f}%。")
    if eps is not None:
        parts.append(f"稀释 EPS 约 {eps:.2f} 美元。")
    parts.append("数据来源：SEC EDGAR companyfacts；仅供研究，不构成投资建议。")
    return "".join(parts)
