"""首页 / 总览工作台内容."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.dashboard.components import (
    render_data_status_bar,
    render_metric_cards,
    render_page_header,
    render_page_help,
    render_result_table,
    render_workflow_quick_links,
)
from src.dashboard.data_status import get_table_freshness
from src.data.storage import StorageEngine
from src.intelligence.industry_chain_analyzer import IndustryChainAnalyzer


def _load_market_metrics() -> dict:
    storage = StorageEngine()
    metrics: dict = {}
    try:
        storage.init_schema()
        for idx in ["沪深300", "中证500", "创业板指", "中证红利"]:
            df = storage.get_index_valuation(idx)
            if df.empty:
                continue
            latest = df.iloc[-1]
            pe_pct = latest.get("pe_percentile")
            if pd.isna(pe_pct) and not pd.isna(latest.get("pe")):
                pe_vals = df["pe"].dropna()
                pe_pct = (
                    (pe_vals < latest["pe"]).sum() / len(pe_vals) * 100 if len(pe_vals) else None
                )
            metrics[idx] = {
                "pe_percentile": pe_pct,
                "dividend_yield": latest.get("dividend_yield"),
            }
    except Exception:
        return {}
    finally:
        storage.close()
    return metrics


def _fmt_pct(value: object) -> str:
    try:
        if value is None or pd.isna(value):
            return "--"
        return f"{float(value):.1f}%"
    except (TypeError, ValueError):
        return "--"


def render_home(*, title: str = "总览") -> None:
    """Render the dashboard home / overview workspace."""
    render_page_header(
        title,
        "市场状态、数据新鲜度、产业链热度与研究工作流入口。",
    )
    render_page_help(
        [
            (
                "页面用途",
                "作为研究工作台总览，用于快速确认市场估值位置、数据是否新鲜、产业链热度和后续工作入口。",
            ),
            (
                "使用建议",
                [
                    "先看顶部宽基指标，判断市场整体估值温度。",
                    "再看数据状态，发现过期或缺失后进入数据管理补采。",
                    "通过产业链热度和工作流入口跳转到更细页面继续分析。",
                ],
            ),
        ]
    )

    metrics = _load_market_metrics()
    metric_cards = []
    for idx in ["沪深300", "中证500", "创业板指", "中证红利"]:
        item = metrics.get(idx, {})
        value = item.get("dividend_yield") if idx == "中证红利" else item.get("pe_percentile")
        label = "股息率" if idx == "中证红利" else "PE百分位"
        metric_cards.append((f"{idx} {label}", _fmt_pct(value)))
    render_metric_cards(metric_cards)

    st.divider()

    q1, q2, q3 = st.columns(3)
    with q1:
        st.markdown('<div class="ee-section-title">数据状态</div>', unsafe_allow_html=True)
        freshness = render_data_status_bar(get_table_freshness())
        render_result_table(freshness, empty_message="暂无数据状态")

    with q2:
        st.markdown('<div class="ee-section-title">产业链热度</div>', unsafe_allow_html=True)
        storage = StorageEngine()
        rows = []
        try:
            storage.init_schema()
            analyzer = IndustryChainAnalyzer(storage)
            for chain in analyzer.list_chains():
                snapshot = analyzer.build_snapshot(chain["chain_id"], link_news=False)
                rows.append(
                    {
                        "产业链": snapshot["name"],
                        "新闻": snapshot["overview"]["news_count"],
                        "情绪": snapshot["overview"]["avg_sentiment"],
                        "趋势": snapshot["overview"]["trend_label"],
                    }
                )
        except Exception:
            rows = []
        finally:
            storage.close()
        render_result_table(pd.DataFrame(rows), empty_message="暂无产业链数据")

    with q3:
        render_workflow_quick_links()

    if not metrics:
        st.warning("尚未检测到指数估值数据，请先在「数据管理」中初始化或更新行情与估值。")
