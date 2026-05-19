"""Dashboard 全局样式注入"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

import streamlit as st

MENU_ITEMS = {
    "Get Help": None,
    "Report a bug": None,
    "About": "### ETFEngine v0.1.0\nETF 投资策略研究与管理工具\n\n仅供研究，不构成投资建议",
}

GLOBAL_CSS = """
<style>
    :root {
        --ee-primary: #2563eb;
        --ee-primary-soft: #eff6ff;
        --ee-accent: #0d9488;
        --ee-text: #0f172a;
        --ee-muted: #64748b;
        --ee-border: #e2e8f0;
        --ee-surface: #ffffff;
        --ee-surface-muted: #f8fafc;
        --ee-radius: 12px;
        --ee-shadow: 0 1px 2px rgba(15, 23, 42, 0.06);
    }

    .stDeployButton, [data-testid="stAppDeployButton"] { display: none !important; }
    footer { visibility: hidden; }

    .block-container {
        max-width: 1760px !important;
        padding-top: 1.25rem !important;
        padding-right: clamp(1rem, 2vw, 2rem) !important;
        padding-bottom: 1.5rem !important;
        padding-left: clamp(1rem, 2vw, 2rem) !important;
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
        border-right: 1px solid var(--ee-border);
    }
    [data-testid="stSidebar"] > div:first-child { padding-top: 0.25rem; }
    [data-testid="stSidebar"] .stCaption { color: var(--ee-muted); }

    .ee-brand-title {
        font-size: 1.15rem;
        font-weight: 700;
        letter-spacing: 0.02em;
        color: var(--ee-text);
        margin: 0;
    }
    .ee-brand-sub {
        font-size: 0.75rem;
        color: var(--ee-muted);
        margin: 0.15rem 0 0 0;
    }

    .ee-page-header {
        margin: 0 0 1.25rem 0;
        padding: 1rem 1.25rem;
        border-radius: var(--ee-radius);
        background: linear-gradient(135deg, var(--ee-primary-soft) 0%, var(--ee-surface) 55%);
        border: 1px solid var(--ee-border);
        box-shadow: var(--ee-shadow);
    }
    .ee-page-title {
        font-size: 1.65rem;
        font-weight: 700;
        color: var(--ee-text);
        margin: 0;
        line-height: 1.25;
    }
    .ee-page-caption {
        font-size: 0.95rem;
        color: var(--ee-muted);
        margin: 0.35rem 0 0 0;
        line-height: 1.5;
    }

    .ee-section-title {
        font-size: 0.95rem;
        font-weight: 600;
        color: var(--ee-text);
        margin: 0 0 0.5rem 0;
        padding-left: 0.5rem;
        border-left: 3px solid var(--ee-primary);
    }

    div[data-testid="stMetric"] {
        background: var(--ee-surface);
        border: 1px solid var(--ee-border);
        border-radius: var(--ee-radius);
        padding: 0.65rem 0.85rem;
        box-shadow: var(--ee-shadow);
    }
    div[data-testid="stMetric"] label {
        color: var(--ee-muted) !important;
        font-size: 0.8rem !important;
    }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: var(--ee-text) !important;
        font-weight: 600 !important;
    }

    [data-testid="stTabs"] [data-baseweb="tab-list"] {
        gap: 0.35rem;
        border-bottom: 1px solid var(--ee-border);
    }
    [data-testid="stTabs"] button[data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
        padding: 0.45rem 0.9rem;
    }

    .ee-nav-group {
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: var(--ee-muted);
        margin: 0.5rem 0 0.15rem 0;
    }

    @media (max-width: 700px) {
        .block-container {
            padding-left: 0.75rem !important;
            padding-right: 0.75rem !important;
            padding-top: 0.75rem !important;
        }
        .ee-page-header {
            padding: 0.75rem 0.9rem;
            margin-bottom: 0.85rem;
        }
        .ee-page-title {
            font-size: 1.35rem;
        }
        .ee-page-caption {
            font-size: 0.85rem;
        }
        [data-testid="stTabs"] button[data-baseweb="tab"] {
            padding: 0.4rem 0.65rem;
        }
    }
</style>
"""

_SUPPRESS_REFRESH_SIDEBAR: ContextVar[bool] = ContextVar(
    "suppress_refresh_sidebar",
    default=False,
)


@contextmanager
def suppress_refresh_sidebar() -> Iterator[None]:
    """Temporarily suppress sidebar refresh widgets for nested legacy pages."""
    token = _SUPPRESS_REFRESH_SIDEBAR.set(True)
    try:
        yield
    finally:
        _SUPPRESS_REFRESH_SIDEBAR.reset(token)


def configure_dashboard_page(page_title: str) -> None:
    """Apply consistent page chrome for every top-level dashboard page."""
    st.set_page_config(
        page_title=f"{page_title} | ETFEngine",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="auto",
        menu_items=MENU_ITEMS,
    )


def inject_global_styles(*, render_refresh_sidebar: bool = True) -> None:
    """在每个页面调用：全局样式 + 侧栏品牌/导航 + 数据管理面板"""
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
    try:
        from src.dashboard.components import render_sidebar_chrome

        render_sidebar_chrome()
    except Exception:
        pass
    if not render_refresh_sidebar or _SUPPRESS_REFRESH_SIDEBAR.get():
        return
    try:
        from src.dashboard.data_refresh import render_refresh_sidebar

        render_refresh_sidebar()
    except Exception as e:
        import logging

        logging.getLogger(__name__).debug(f"侧栏数据面板加载跳过: {e}")
