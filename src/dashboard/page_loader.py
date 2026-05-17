"""Utilities for loading legacy Streamlit pages inside consolidated pages."""

from __future__ import annotations

import runpy
from pathlib import Path

import streamlit as st

from src.dashboard.styles import suppress_refresh_sidebar

LEGACY_PAGE_DIR = Path(__file__).resolve().parent / "legacy_pages"


def run_legacy_page(filename: str) -> None:
    """Execute a legacy page file by filename."""
    path = LEGACY_PAGE_DIR / filename
    if not path.exists():
        st.error(f"页面文件不存在: {filename}")
        return
    with suppress_refresh_sidebar():
        runpy.run_path(str(path), run_name=f"__legacy_{path.stem}__")


def legacy_page_selector(label: str, options: dict[str, str], key: str) -> str:
    """Render a page selector and return the selected legacy filename."""
    selected = st.radio(label, list(options), horizontal=True, key=key)
    st.divider()
    return options[selected]
