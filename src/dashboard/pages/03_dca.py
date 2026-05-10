"""定投管理页"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import date, timedelta



st.title("💰 定投管理")
st.divider()

tab1, tab2, tab3 = st.tabs(["定投信号", "收益追踪", "策略回测"])

with tab1:
    st.subheader("今日定投信号")

    signals = pd.DataFrame({
        "ETF": ["沪深300ETF(510300)", "中证红利(515080)", "纳指100(513100)"],
        "策略": ["均线偏离定投", "估值定投", "普通定投"],
        "信号": ["正常定投", "低估加码", "正常定投"],
        "建议金额": [1000, 1500, 1000],
        "触发条件": ["MA250偏离-3.2%", "PE百分位25%", "月度定投日"],
    })

    st.dataframe(signals, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("定投计划管理")

    with st.expander("➕ 新建定投计划"):
        col1, col2 = st.columns(2)
        with col1:
            etf_code = st.text_input("ETF代码", value="510300")
            strategy_type = st.selectbox("策略类型", ["普通定投", "估值定投", "均线偏离定投"])
            base_amount = st.number_input("基础金额(元)", value=1000, step=100)
        with col2:
            frequency = st.selectbox("定投频率", ["每月", "每周", "每两周"])
            day = st.number_input("每月第几个交易日", value=1, min_value=1, max_value=22)
            st.button("创建计划", type="primary")


with tab2:
    st.subheader("定投收益追踪")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("累计投入", "¥36,000")
    with col2:
        st.metric("当前市值", "¥41,520")
    with col3:
        st.metric("累计收益", "¥5,520", delta="15.3%")
    with col4:
        st.metric("年化收益(XIRR)", "8.6%")

    # 定投微笑曲线
    dates = pd.date_range(start="2022-01-01", end=date.today(), freq="B")
    np.random.seed(42)
    prices = 4.0 + np.cumsum(np.random.randn(len(dates)) * 0.02)
    prices = np.maximum(prices, 2.5)

    invest_dates = dates[::22]  # 约每月
    avg_costs = []
    cumulative_cost = 0
    cumulative_shares = 0
    for i, d in enumerate(invest_dates):
        idx = np.searchsorted(dates, d)
        if idx < len(prices):
            cumulative_shares += 1000 / prices[idx]
            cumulative_cost += 1000
            avg_costs.append(cumulative_cost / cumulative_shares)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=prices, mode="lines", name="ETF价格",
                             line=dict(color="steelblue")))
    fig.add_trace(go.Scatter(x=invest_dates[:len(avg_costs)], y=avg_costs,
                             mode="lines", name="平均成本",
                             line=dict(color="orange", dash="dash")))
    fig.update_layout(title="定投微笑曲线", yaxis_title="价格/成本", height=400)
    st.plotly_chart(fig, use_container_width=True)


with tab3:
    st.subheader("定投策略回测")

    col1, col2 = st.columns(2)
    with col1:
        bt_etf = st.selectbox("选择ETF", ["510300 沪深300", "515080 中证红利", "513100 纳指100"])
        bt_strategy = st.selectbox("选择策略", ["普通定投", "估值定投", "均线偏离定投", "策略对比"])
    with col2:
        bt_start = st.date_input("开始日期", value=date(2020, 1, 1))
        bt_end = st.date_input("结束日期", value=date.today())
        bt_amount = st.number_input("月投金额", value=1000)

    if st.button("运行回测", type="primary"):
        with st.spinner("回测中..."):
            # 模拟回测结果
            st.success("回测完成!")

            rcol1, rcol2, rcol3, rcol4 = st.columns(4)
            with rcol1:
                st.metric("总收益率", "32.5%")
            with rcol2:
                st.metric("年化收益", "9.2%")
            with rcol3:
                st.metric("最大回撤", "-15.3%")
            with rcol4:
                st.metric("夏普比率", "0.85")

            dates = pd.date_range(start=bt_start, end=bt_end, freq="B")
            np.random.seed(55)
            cumulative = np.cumsum(np.random.randn(len(dates)) * 0.003) + np.linspace(0, 0.3, len(dates))

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=dates, y=cumulative * 100, mode="lines", name="策略收益"))
            fig.add_trace(go.Scatter(x=dates, y=np.linspace(0, 25, len(dates)),
                                     mode="lines", name="一次性投入",
                                     line=dict(dash="dash")))
            fig.update_layout(title="累计收益曲线", yaxis_title="收益率(%)", height=350)
            st.plotly_chart(fig, use_container_width=True)
