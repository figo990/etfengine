"""Streamlit Dashboard 主入口（总览工作台）"""

from __future__ import annotations

from src.dashboard.styles import configure_dashboard_page, inject_global_styles
from src.dashboard.views.home import render_home

configure_dashboard_page("总览")
inject_global_styles()
render_home(title="ETFEngine")
