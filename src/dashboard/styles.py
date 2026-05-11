"""Dashboard 全局样式注入"""

import streamlit as st

GLOBAL_CSS = """
<style>
    /* 隐藏 Deploy 按钮 */
    .stDeployButton, [data-testid="stAppDeployButton"] { display: none !important; }
    /* 减少顶部空白 */
    .block-container { padding-top: 2rem !important; padding-bottom: 1rem; }
    /* 侧边栏紧凑 */
    [data-testid="stSidebar"] > div:first-child { padding-top: 0.5rem; }
    /* 隐藏 footer */
    footer { visibility: hidden; }
</style>
"""


def inject_global_styles() -> None:
    """在每个页面调用此函数注入全局样式 + 侧栏数据管理面板"""
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
    try:
        from src.dashboard.data_refresh import render_refresh_sidebar
        render_refresh_sidebar()
    except Exception:
        pass
