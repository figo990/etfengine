"""估值看板页"""

import streamlit as st
from src.dashboard.styles import inject_global_styles
inject_global_styles()
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import date, timedelta



st.title("📈 估值看板")
st.divider()

tab1, tab2, tab3, tab4 = st.tabs(["PE/PB 百分位", "股债性价比", "五年之锚", "情绪指标"])

with tab1:
    st.subheader("PE/PB 百分位追踪")

    lookback = st.selectbox("回看周期", ["3年", "5年", "10年", "全历史"], index=1)

    valuation_df = pd.DataFrame({
        "指数": ["上证50", "沪深300", "中证500", "中证1000", "创业板指", "科创50",
                 "中证红利", "中证消费", "中证医药"],
        "PE": [10.2, 12.5, 22.1, 35.2, 30.5, 48.3, 6.8, 28.5, 25.1],
        "PE百分位(%)": [35, 45, 55, 42, 38, 62, 25, 48, 18],
        "PB": [1.1, 1.3, 1.8, 2.5, 3.2, 4.1, 0.7, 4.5, 2.8],
        "PB百分位(%)": [28, 32, 45, 50, 35, 55, 15, 42, 12],
        "股息率(%)": [3.8, 3.0, 1.5, 0.8, 0.6, 0.3, 5.2, 1.2, 1.0],
        "估值区间": ["低估", "适中", "适中", "适中", "低估", "偏高", "低估", "适中", "极度低估"],
    })

    st.dataframe(
        valuation_df.style.map(
            lambda x: "background-color: #d4edda" if x == "低估" or x == "极度低估"
            else "background-color: #f8d7da" if x == "偏高" or x == "极度高估"
            else "",
            subset=["估值区间"],
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.divider()
    st.subheader("PE 百分位历史走势")

    selected_index = st.selectbox("选择指数", valuation_df["指数"].tolist(), index=1)

    # 模拟历史 PE 百分位数据
    dates = pd.date_range(end=date.today(), periods=1250, freq="B")
    np.random.seed(42)
    pe_pctile = 50 + np.cumsum(np.random.randn(len(dates)) * 0.5)
    pe_pctile = np.clip(pe_pctile, 0, 100)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=pe_pctile, mode="lines", name="PE百分位"))
    fig.add_hline(y=20, line_dash="dash", line_color="green", annotation_text="低估线(20%)")
    fig.add_hline(y=80, line_dash="dash", line_color="red", annotation_text="高估线(80%)")
    fig.add_hrect(y0=0, y1=20, fillcolor="green", opacity=0.05)
    fig.add_hrect(y0=80, y1=100, fillcolor="red", opacity=0.05)
    fig.update_layout(
        title=f"{selected_index} PE百分位历史走势",
        yaxis_title="百分位(%)",
        height=400,
    )
    st.plotly_chart(fig, use_container_width=True)


with tab2:
    st.subheader("股债性价比 (FED 模型)")
    st.markdown("""
    **公式**: ERP = 1/PE(沪深300) - 10年期国债收益率

    - ERP > 4%: 股票极度有吸引力
    - ERP 2~4%: 偏股配置
    - ERP 0~2%: 均衡配置
    - ERP < 0%: 偏债配置
    """)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("沪深300盈利收益率", "8.0%", help="1/PE × 100%")
    with col2:
        st.metric("中国10年国债", "2.35%")
    with col3:
        st.metric("中国视角 ERP", "5.65%", delta="0.12%")

    col4, col5, col6 = st.columns(3)
    with col4:
        st.metric("美国10年国债", "4.28%")
    with col5:
        st.metric("美国视角 ERP", "3.72%", delta="-0.05%")
    with col6:
        st.metric("配置建议", "全仓权益")

    # 模拟 ERP 历史
    dates = pd.date_range(end=date.today(), periods=1250, freq="B")
    np.random.seed(123)
    erp_cn = 3.5 + np.cumsum(np.random.randn(len(dates)) * 0.02)
    erp_us = 2.5 + np.cumsum(np.random.randn(len(dates)) * 0.02)

    fig = make_subplots(specs=[[{"secondary_y": False}]])
    fig.add_trace(go.Scatter(x=dates, y=erp_cn, mode="lines", name="中国视角ERP"))
    fig.add_trace(go.Scatter(x=dates, y=erp_us, mode="lines", name="美国视角ERP"))
    fig.add_hline(y=4, line_dash="dash", line_color="green", annotation_text="强烈看多(4%)")
    fig.add_hline(y=0, line_dash="dash", line_color="red", annotation_text="偏债(0%)")
    fig.update_layout(title="股债性价比(ERP)历史走势", yaxis_title="ERP(%)", height=400)
    st.plotly_chart(fig, use_container_width=True)


with tab3:
    st.subheader("五年之锚 (对数回归通道)")
    st.markdown("对中证全A指数做对数回归，叠加1.5σ置信区间")

    dates = pd.date_range(end=date.today(), periods=2500, freq="B")
    t = np.arange(1, len(dates) + 1, dtype=float)
    np.random.seed(42)
    ln_price = 0.15 * np.log(t) + 7.5 + np.cumsum(np.random.randn(len(dates)) * 0.003)
    price = np.exp(ln_price)

    # 拟合
    from scipy import stats as sp_stats
    slope, intercept, _, _, _ = sp_stats.linregress(np.log(t), ln_price)
    fitted = np.exp(slope * np.log(t) + intercept)
    residual_std = (ln_price - (slope * np.log(t) + intercept)).std()
    upper = np.exp(slope * np.log(t) + intercept + 1.5 * residual_std)
    lower = np.exp(slope * np.log(t) + intercept - 1.5 * residual_std)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=price, mode="lines", name="中证全A", line=dict(width=1.5)))
    fig.add_trace(go.Scatter(x=dates, y=fitted, mode="lines", name="回归中轨",
                             line=dict(dash="dash", color="orange")))
    fig.add_trace(go.Scatter(x=dates, y=upper, mode="lines", name="上轨(+1.5σ)",
                             line=dict(dash="dot", color="red")))
    fig.add_trace(go.Scatter(x=dates, y=lower, mode="lines", name="下轨(-1.5σ)",
                             line=dict(dash="dot", color="green")))
    fig.update_layout(title="五年之锚 - 中证全A对数回归通道", yaxis_title="指数点位", height=450)
    st.plotly_chart(fig, use_container_width=True)

    position = (ln_price[-1] - (slope * np.log(t[-1]) + intercept)) / (1.5 * residual_std)
    st.info(f"当前位置: {position:.2f} (范围 -1 ~ +1, 0=中轨)")


with tab4:
    st.subheader("偏股基金3年滚动年化收益")
    st.markdown("""
    - **> 30%**: 泡沫区域（极度贪婪）
    - **> 15%**: 偏乐观
    - **0% ~ 15%**: 正常
    - **-5% ~ 0%**: 偏悲观
    - **< -10%**: 底部区域（极度恐惧）
    """)

    dates = pd.date_range(end=date.today(), periods=2000, freq="B")
    np.random.seed(88)
    rolling_3y = 5 + np.cumsum(np.random.randn(len(dates)) * 0.15)
    rolling_3y = np.clip(rolling_3y, -20, 40)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=rolling_3y, mode="lines", name="3年滚动年化"))
    fig.add_hline(y=30, line_dash="dash", line_color="red", annotation_text="泡沫线(30%)")
    fig.add_hline(y=-10, line_dash="dash", line_color="green", annotation_text="底部线(-10%)")
    fig.add_hline(y=0, line_dash="dot", line_color="gray")
    fig.add_hrect(y0=30, y1=40, fillcolor="red", opacity=0.05)
    fig.add_hrect(y0=-20, y1=-10, fillcolor="green", opacity=0.05)
    fig.update_layout(title="偏股基金3年滚动年化收益", yaxis_title="年化收益率(%)", height=400)
    st.plotly_chart(fig, use_container_width=True)

    current_val = rolling_3y[-1]
    if current_val > 30:
        st.error(f"当前: {current_val:.1f}% - 泡沫区域，警惕回调")
    elif current_val < -10:
        st.success(f"当前: {current_val:.1f}% - 底部区域，建议逢低布局")
    else:
        st.info(f"当前: {current_val:.1f}%")
