"""Streamlit Dashboard 主入口"""

import streamlit as st

st.set_page_config(
    page_title="ETFEngine",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.sidebar.markdown(
    """
    <div style="text-align:center; padding: 0.5rem 0 1rem 0;">
        <span style="font-size:2rem;">📊</span><br>
        <span style="font-size:1.2rem; font-weight:700; letter-spacing:1px;">ETFEngine</span><br>
        <span style="font-size:0.75rem; color:#888;">ETF 投资策略管理工具</span>
    </div>
    """,
    unsafe_allow_html=True,
)
st.sidebar.divider()
st.sidebar.caption("v0.1.0 · 仅供研究，不构成投资建议")

# --- 主页内容 ---
st.markdown(
    """
    <h1 style="text-align:center; padding:1.5rem 0 0.5rem 0;">
        📊 ETFEngine
    </h1>
    <p style="text-align:center; color:#666; font-size:1.1rem; margin-bottom:2rem;">
        一站式 ETF 投资策略研究、回测与管理工具
    </p>
    """,
    unsafe_allow_html=True,
)

st.divider()

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("沪深300 PE百分位", "45.2%", delta="-2.1%")
with col2:
    st.metric("股债性价比(ERP)", "3.12%", delta="0.05%")
with col3:
    st.metric("市场温度", "52.3", delta="-1.8")
with col4:
    st.metric("偏股基金3年收益", "2.5%", delta="-0.3%")

st.divider()

c1, c2, c3 = st.columns(3)

with c1:
    st.markdown(
        """
        #### 📈 估值分析
        - PE/PB 百分位追踪
        - 股债性价比（中美双视角）
        - 五年之锚回归曲线
        - 偏股基金情绪指标
        """
    )

with c2:
    st.markdown(
        """
        #### 💡 策略信号
        - 定投 / 网格 / 轮动信号
        - 新闻情绪预警
        - 政策追踪告警
        - 再平衡提醒
        """
    )

with c3:
    st.markdown(
        """
        #### 🧪 回测与报告
        - 多策略历史回测
        - 参数网格优化
        - 自动周报 / 月报
        - 智能行业资讯
        """
    )

st.divider()

st.info(
    "👈 使用左侧导航栏进入各功能页面。"
    "首次使用请先运行数据初始化：`python scripts/init_data.py`"
)
