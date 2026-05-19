"""Streamlit native navigation entry for the dashboard."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.dashboard.nav import WORKFLOW_NAV
from src.dashboard.styles import GLOBAL_CSS, MENU_ITEMS

_DASHBOARD_ROOT = Path(__file__).resolve().parent
_NATIVE_NAV_FLAG = "_ee_use_native_nav"


def iter_navigation_specs() -> list[tuple[str, str, str, bool]]:
    """Return (group, label, relative_path, is_default) without Streamlit runtime."""
    specs: list[tuple[str, str, str, bool]] = []
    for group, links in WORKFLOW_NAV:
        for label, rel_path in links:
            specs.append((group, label, rel_path, label == "总览"))
    return specs


def build_navigation_pages() -> dict[str, list[st.Page]]:
    """Build grouped ``st.Page`` definitions from workflow navigation config."""
    groups: dict[str, list[st.Page]] = {}
    for group, label, rel_path, is_default in iter_navigation_specs():
        groups.setdefault(group, []).append(
            st.Page(
                str(_DASHBOARD_ROOT / rel_path),
                title=label,
                default=is_default,
            )
        )
    return groups


def run_dashboard() -> None:
    """Application entry: native sidebar navigation + shared page scripts."""
    st.set_page_config(
        page_title="ETFEngine",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="auto",
        menu_items=MENU_ITEMS,
    )
    st.session_state[_NATIVE_NAV_FLAG] = True
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
    navigation = st.navigation(build_navigation_pages(), position="sidebar")
    navigation.run()


def using_native_navigation() -> bool:
    return bool(st.session_state.get(_NATIVE_NAV_FLAG))
