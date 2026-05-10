"""组合管理页"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from datetime import date



st.title("📋 组合管理")
st.divider()

tab1, tab2, tab3, tab4 = st.tabs(["持仓概览", "再平衡", "风险监控", "绩效归因"])

with tab1:
    st.subheader("当前持仓")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("总市值", "¥108,350", delta="¥3,520")
    with col2:
        st.metric("总收益", "¥8,350", delta="8.35%")
    with col3:
        st.metric("今日盈亏", "¥285", delta="0.26%")
    with col4:
        st.metric("年化收益", "11.2%")

    holdings = pd.DataFrame({
        "ETF": ["沪深300(510300)", "中证1000(512100)", "中证红利(515080)",
                "纳指100(513100)", "黄金(518880)"],
        "持仓市值": [32505, 21670, 21670, 16253, 16253],
        "目标权重": [30.0, 20.0, 20.0, 15.0, 15.0],
        "实际权重": [30.0, 20.0, 20.0, 15.0, 15.0],
        "偏离度": [0.8, -1.2, 2.1, -0.5, -1.2],
        "持仓盈亏": [1250, -380, 1560, 850, 270],
        "收益率(%)": [4.0, -1.7, 7.8, 5.5, 1.7],
    })
    holdings["实际权重"] = holdings["目标权重"] + holdings["偏离度"]

    st.dataframe(
        holdings.style.map(
            lambda x: "color: red" if isinstance(x, (int, float)) and x > 0
            else "color: green" if isinstance(x, (int, float)) and x < 0
            else "",
            subset=["偏离度", "持仓盈亏", "收益率(%)"],
        ),
        use_container_width=True,
        hide_index=True,
    )

    # 饼图
    col_pie1, col_pie2 = st.columns(2)
    with col_pie1:
        fig = go.Figure(data=[go.Pie(
            labels=holdings["ETF"],
            values=holdings["目标权重"],
            hole=0.4,
        )])
        fig.update_layout(title="目标配置", height=300)
        st.plotly_chart(fig, use_container_width=True)

    with col_pie2:
        fig = go.Figure(data=[go.Pie(
            labels=holdings["ETF"],
            values=holdings["实际权重"],
            hole=0.4,
        )])
        fig.update_layout(title="实际配置", height=300)
        st.plotly_chart(fig, use_container_width=True)


with tab2:
    st.subheader("再平衡建议")

    max_drift = max(abs(d) for d in holdings["偏离度"])
    threshold = st.slider("偏离阈值(%)", 1.0, 10.0, 5.0, 0.5)

    if max_drift > threshold:
        st.warning(f"最大偏离 {max_drift:.1f}% 超过阈值 {threshold}%，建议再平衡")
    else:
        st.success(f"最大偏离 {max_drift:.1f}% 在阈值 {threshold}% 以内，无需操作")

    rebalance_orders = pd.DataFrame({
        "ETF": ["中证红利(515080)", "中证1000(512100)", "黄金(518880)"],
        "操作": ["卖出", "买入", "买入"],
        "调仓金额": [2275, 1300, 1300],
        "目标权重": [20.0, 20.0, 15.0],
        "当前权重": [22.1, 18.8, 13.8],
    })

    st.dataframe(
        rebalance_orders.style.map(
            lambda x: "background-color: #f8d7da" if x == "卖出"
            else "background-color: #d4edda" if x == "买入"
            else "",
            subset=["操作"],
        ),
        use_container_width=True,
        hide_index=True,
    )

    if st.button("确认再平衡", type="primary"):
        st.success("再平衡指令已生成!")


with tab3:
    st.subheader("风险监控")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("年化波动率", "12.5%")
    with col2:
        st.metric("最大回撤", "-8.3%")
    with col3:
        st.metric("夏普比率", "0.89")
    with col4:
        st.metric("VaR(95%)", "-1.2%", help="日度VaR")

    st.divider()
    st.subheader("相关性矩阵")

    etfs = ["沪深300", "中证1000", "中证红利", "纳指100", "黄金"]
    np.random.seed(42)
    n = len(etfs)
    corr = np.eye(n)
    for i in range(n):
        for j in range(i + 1, n):
            c = np.random.uniform(-0.2, 0.8)
            corr[i, j] = c
            corr[j, i] = c

    fig = go.Figure(data=go.Heatmap(
        z=corr,
        x=etfs, y=etfs,
        colorscale="RdBu_r",
        zmin=-1, zmax=1,
        text=np.round(corr, 2),
        texttemplate="%{text}",
    ))
    fig.update_layout(title="持仓相关性矩阵", height=400)
    st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("回撤监控")

    dates = pd.date_range(end=date.today(), periods=500, freq="B")
    np.random.seed(42)
    values = 100000 + np.cumsum(np.random.randn(500) * 300)
    values = np.maximum(values, 80000)
    peak = pd.Series(values).expanding().max()
    drawdown = (pd.Series(values) - peak) / peak * 100

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=drawdown, mode="lines", name="回撤",
                             fill="tozeroy", line=dict(color="red")))
    fig.add_hline(y=-15, line_dash="dash", line_color="darkred",
                 annotation_text="预警线(-15%)")
    fig.update_layout(title="组合回撤曲线", yaxis_title="回撤(%)", height=300)
    st.plotly_chart(fig, use_container_width=True)


with tab4:
    st.subheader("绩效归因")

    attribution = pd.DataFrame({
        "ETF": ["沪深300", "中证1000", "中证红利", "纳指100", "黄金"],
        "权重(%)": [30, 20, 20, 15, 15],
        "区间收益(%)": [4.0, -1.7, 7.8, 5.5, 1.7],
        "贡献度(%)": [1.20, -0.34, 1.56, 0.83, 0.26],
    })
    attribution["贡献占比(%)"] = (attribution["贡献度(%)"] / attribution["贡献度(%)"].sum() * 100).round(1)

    st.dataframe(attribution, use_container_width=True, hide_index=True)

    fig = go.Figure(data=[go.Bar(
        x=attribution["ETF"],
        y=attribution["贡献度(%)"],
        marker_color=["green" if v > 0 else "red" for v in attribution["贡献度(%)"]],
        text=attribution["贡献度(%)"].apply(lambda x: f"{x:.2f}%"),
        textposition="outside",
    )])
    fig.update_layout(title="各ETF收益贡献", yaxis_title="贡献度(%)", height=350)
    st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("对比基准")

    dates = pd.date_range(end=date.today(), periods=500, freq="B")
    np.random.seed(42)
    port_cum = np.cumsum(np.random.randn(500) * 0.004 + 0.0003)
    bench_cum = np.cumsum(np.random.randn(500) * 0.005 + 0.0002)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=port_cum * 100, name="组合",
                             line=dict(color="steelblue", width=2)))
    fig.add_trace(go.Scatter(x=dates, y=bench_cum * 100, name="沪深300(基准)",
                             line=dict(color="gray", dash="dash")))
    fig.update_layout(title="组合 vs 基准", yaxis_title="累计收益(%)", height=350)
    st.plotly_chart(fig, use_container_width=True)
