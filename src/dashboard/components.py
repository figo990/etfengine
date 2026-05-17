"""Reusable Streamlit building blocks for dashboard pages."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

import pandas as pd
import streamlit as st

from src.dashboard.data_status import get_table_freshness
from src.dashboard.nav import WORKFLOW_NAV

MetricSpec = tuple[str, Any] | tuple[str, Any, Any]


def render_sidebar_chrome() -> None:
    """Brand block + grouped workflow navigation in the sidebar."""
    st.sidebar.markdown(
        """
        <div style="text-align:center; padding: 0.35rem 0 0.85rem 0;">
            <span style="font-size:1.85rem;">📊</span>
            <p class="ee-brand-title">ETFEngine</p>
            <p class="ee-brand-sub">ETF 投资研究工作台</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.sidebar.caption("v0.1.0 · 仅供研究，不构成投资建议")
    st.sidebar.divider()
    with st.sidebar.expander("工作流导航", expanded=True):
        render_workflow_nav(compact=True)
    st.sidebar.divider()


def render_workflow_nav(*, compact: bool = False) -> None:
    """Grouped page links aligned with consolidated menu structure."""
    for group, links in WORKFLOW_NAV:
        st.markdown(f'<p class="ee-nav-group">{group}</p>', unsafe_allow_html=True)
        for label, path in links:
            if compact:
                st.page_link(path, label=label)
            else:
                st.page_link(path, label=label)


def render_workflow_quick_links() -> None:
    """Quick links column on the home page."""
    st.markdown('<div class="ee-section-title">工作流入口</div>', unsafe_allow_html=True)
    for group, links in WORKFLOW_NAV:
        if group == "系统":
            continue
        st.caption(group)
        for label, path in links:
            if path == "app.py":
                continue
            st.page_link(path, label=label)


def render_page_header(title: str, caption: str = "") -> None:
    """Unified page title block."""
    cap_html = f'<p class="ee-page-caption">{caption}</p>' if caption else ""
    st.markdown(
        f'<div class="ee-page-header">'
        f'<h1 class="ee-page-title">{title}</h1>{cap_html}</div>',
        unsafe_allow_html=True,
    )


def render_metric_cards(metrics: Sequence[MetricSpec]) -> None:
    """Render one compact row of metric cards."""
    if not metrics:
        return
    columns = st.columns(len(metrics))
    for column, metric in zip(columns, metrics):
        if len(metric) == 2:
            label, value = metric
            column.metric(label, value)
        else:
            label, value, delta = metric
            column.metric(label, value, delta)


def render_data_status_bar(freshness: pd.DataFrame | None = None) -> pd.DataFrame:
    """Render a compact freshness summary and return the underlying table."""
    freshness = freshness.copy() if freshness is not None else get_table_freshness()
    if freshness.empty:
        render_metric_cards(
            [
                ("已覆盖数据表", "0"),
                ("最新数据日期", "--"),
                ("总记录数", "0"),
            ]
        )
        return freshness

    available = freshness[freshness["记录数"] > 0]
    latest_date = available["最新日期"].replace("", pd.NA).dropna()
    render_metric_cards(
        [
            ("已覆盖数据表", f"{len(available)}/{len(freshness)}"),
            ("最新数据日期", latest_date.max() if not latest_date.empty else "--"),
            ("总记录数", f"{int(freshness['记录数'].sum()):,}"),
        ]
    )
    return freshness


def render_empty_state(message: str, *, level: str = "info") -> None:
    """Render a consistent empty-state message."""
    renderer = getattr(st, level, st.info)
    renderer(message)


def render_result_table(
    data: pd.DataFrame | Iterable[dict[str, Any]],
    *,
    empty_message: str,
    hide_index: bool = True,
    width: str | int = "stretch",
    **kwargs: Any,
) -> bool:
    """Render a table or a consistent empty state. Return whether data existed."""
    frame = data if isinstance(data, pd.DataFrame) else pd.DataFrame(data)
    if frame.empty:
        render_empty_state(empty_message)
        return False
    st.dataframe(
        frame,
        hide_index=hide_index,
        width=width,
        **kwargs,
    )
    return True
