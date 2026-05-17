"""数据管理：手工更新、定时采集和数据健康检查"""

from __future__ import annotations

from src.dashboard.components import render_page_header
from src.dashboard.page_loader import run_legacy_page
from src.dashboard.styles import configure_dashboard_page, inject_global_styles

configure_dashboard_page("数据管理")
inject_global_styles()
render_page_header("数据管理", "手工更新、定时采集、数据健康检查与后台任务。")
run_legacy_page("13_数据管理.py")
