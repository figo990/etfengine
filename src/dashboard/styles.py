"""Dashboard 全局样式注入"""

import streamlit as st

GLOBAL_CSS = """
<style>
    .stDeployButton { display: none; }
    [data-testid="stToolbar"] { display: none; }
    .block-container { padding-top: 1rem; }
    header[data-testid="stHeader"] { height: 0; }
    [data-testid="stSidebar"] > div:first-child { padding-top: 0.5rem; }
</style>
"""


def inject_global_styles() -> None:
    """在每个页面调用此函数注入全局样式"""
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
