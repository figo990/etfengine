"""Dashboard 全局样式注入"""

import streamlit as st

GLOBAL_CSS = """
<style>
    /* 隐藏右上角 Deploy/Menu 按钮 */
    .stDeployButton { display: none !important; }
    [data-testid="stToolbar"] { visibility: hidden; height: 0; }
    /* 减少顶部空白但不隐藏 header（避免遮盖内容） */
    .block-container { padding-top: 2rem !important; padding-bottom: 1rem; }
    /* 侧边栏紧凑 */
    [data-testid="stSidebar"] > div:first-child { padding-top: 0.5rem; }
    /* 隐藏 footer */
    footer { visibility: hidden; }
</style>
"""


def inject_global_styles() -> None:
    """在每个页面调用此函数注入全局样式"""
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
