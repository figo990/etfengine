"""轮动信号页"""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import date



st.title("🔄 轮动信号")
st.divider()

tab1, tab2, tab3, tab4 = st.tabs(["大小盘轮动", "风格三棱镜", "红利轮动", "行业轮动"])

with tab1:
    st.subheader("大小盘动量轮动")
    st.markdown("**上证50 vs 中证1000** | ROC20日动量比较")

    dates = pd.date_range(end=date.today(), periods=500, freq="B")
    np.random.seed(42)
    large_prices = 2800 + np.cumsum(np.random.randn(500) * 15)
    small_prices = 6500 + np.cumsum(np.random.randn(500) * 30)

    col1, col2, col3 = st.columns(3)
    roc_large = (large_prices[-1] / large_prices[-21] - 1) * 100
    roc_small = (small_prices[-1] / small_prices[-21] - 1) * 100
    with col1:
        st.metric("上证50 ROC20", f"{roc_large:.1f}%")
    with col2:
        st.metric("中证1000 ROC20", f"{roc_small:.1f}%")
    with col3:
        holding = "上证50(大盘)" if roc_large > roc_small else "中证1000(小盘)"
        st.metric("当前持有", holding)

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.6, 0.4],
                        vertical_spacing=0.08)
    fig.add_trace(go.Scatter(x=dates, y=large_prices, name="上证50", line=dict(color="blue")), row=1, col=1)
    fig.add_trace(go.Scatter(x=dates, y=small_prices, name="中证1000", line=dict(color="orange")), row=1, col=1)

    roc_diff = pd.Series(large_prices).pct_change(20) - pd.Series(small_prices).pct_change(20)
    colors = ["green" if v > 0 else "red" for v in roc_diff.dropna()]
    fig.add_trace(go.Bar(x=dates[20:], y=roc_diff.dropna() * 100, name="ROC差值",
                         marker_color=colors), row=2, col=1)

    fig.update_layout(title="大小盘轮动", height=500)
    fig.update_yaxes(title_text="点位", row=1, col=1)
    fig.update_yaxes(title_text="ROC差(%)", row=2, col=1)
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("风格轮动三棱镜")
    st.markdown("**三维信号**: 252日布林线 + 40日收益差 + 5年均线回归")

    dates = pd.date_range(end=date.today(), periods=1260, freq="B")
    np.random.seed(123)
    ratio = 1.0 + np.cumsum(np.random.randn(1260) * 0.002)

    ma252 = pd.Series(ratio).rolling(252).mean()
    std252 = pd.Series(ratio).rolling(252).std()
    upper = ma252 + 2 * std252
    lower = ma252 - 2 * std252
    ma1250 = pd.Series(ratio).rolling(1250).mean()

    # 信号面板
    latest_ratio = ratio[-1]
    sig1 = "看多价值" if latest_ratio > upper.iloc[-1] else ("看多成长" if latest_ratio < lower.iloc[-1] else "中性")
    sig2 = "看多价值" if ratio[-1] > ratio[-41] else "看多成长"
    sig3 = "看多成长" if not np.isnan(ma1250.iloc[-1]) and latest_ratio > ma1250.iloc[-1] else "看多价值"

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("布林线信号", sig1)
    with col2:
        st.metric("收益差信号", sig2)
    with col3:
        st.metric("均值回归信号", sig3)
    with col4:
        st.metric("综合判断", "偏价值" if [sig1, sig2, sig3].count("看多价值") >= 2 else "偏成长")

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=ratio, name="价值/成长比值", line=dict(width=1.5)))
    fig.add_trace(go.Scatter(x=dates, y=ma252, name="252日均线", line=dict(dash="dash", color="orange")))
    fig.add_trace(go.Scatter(x=dates, y=upper, name="布林上轨", line=dict(dash="dot", color="red")))
    fig.add_trace(go.Scatter(x=dates, y=lower, name="布林下轨", line=dict(dash="dot", color="green")))
    if not ma1250.isna().all():
        fig.add_trace(go.Scatter(x=dates, y=ma1250, name="5年均线", line=dict(dash="dashdot", color="purple")))

    fig.update_layout(title="风格轮动三棱镜 (价值/成长比值)", height=450)
    st.plotly_chart(fig, use_container_width=True)

with tab3:
    st.subheader("红利轮动")
    st.markdown("**A股红利 vs 港股红利** | 40日收益差驱动")

    dates = pd.date_range(end=date.today(), periods=500, freq="B")
    np.random.seed(88)
    a_dividend = 1000 + np.cumsum(np.random.randn(500) * 3)
    hk_dividend = 800 + np.cumsum(np.random.randn(500) * 4)

    ret_a_40 = (pd.Series(a_dividend).pct_change(40) * 100).dropna()
    ret_hk_40 = (pd.Series(hk_dividend).pct_change(40) * 100).dropna()
    diff_40 = ret_a_40 - ret_hk_40

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("A股红利40日收益", f"{ret_a_40.iloc[-1]:.1f}%")
    with col2:
        st.metric("港股红利40日收益", f"{ret_hk_40.iloc[-1]:.1f}%")
    with col3:
        holding = "港股红利" if diff_40.iloc[-1] > 5 else ("A股红利" if diff_40.iloc[-1] < -5 else "均衡")
        st.metric("建议持有", holding)

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.5, 0.5],
                        vertical_spacing=0.08)
    fig.add_trace(go.Scatter(x=dates, y=a_dividend, name="A股红利"), row=1, col=1)
    fig.add_trace(go.Scatter(x=dates, y=hk_dividend, name="港股红利"), row=1, col=1)

    diff_colors = ["red" if d > 5 else ("green" if d < -5 else "gray") for d in diff_40]
    fig.add_trace(go.Bar(x=dates[40:], y=diff_40, name="收益差",
                         marker_color=diff_colors), row=2, col=1)
    fig.add_hline(y=5, line_dash="dash", line_color="red", row=2, col=1)
    fig.add_hline(y=-5, line_dash="dash", line_color="green", row=2, col=1)

    fig.update_layout(title="红利轮动", height=500)
    st.plotly_chart(fig, use_container_width=True)

with tab4:
    st.subheader("行业动量轮动")
    st.markdown("**多周期动量打分** | 选择Top-3行业ETF持有")

    sectors = ["消费", "医药", "半导体", "新能源", "军工", "金融", "地产", "有色"]
    np.random.seed(42)
    scores = pd.DataFrame({
        "行业": sectors,
        "1月动量": np.random.randn(len(sectors)) * 5 + 2,
        "3月动量": np.random.randn(len(sectors)) * 8 + 3,
        "6月动量": np.random.randn(len(sectors)) * 12 + 5,
        "综合得分": np.random.randn(len(sectors)) * 6 + 4,
    }).round(2)

    scores = scores.sort_values("综合得分", ascending=False).reset_index(drop=True)

    st.dataframe(
        scores.style.background_gradient(cmap="RdYlGn", subset=["综合得分"]),
        use_container_width=True,
        hide_index=True,
    )

    top3 = scores.head(3)["行业"].tolist()
    st.success(f"当前Top-3持仓建议: **{', '.join(top3)}**")

    fig = go.Figure(data=[
        go.Bar(name="1月", x=scores["行业"], y=scores["1月动量"]),
        go.Bar(name="3月", x=scores["行业"], y=scores["3月动量"]),
        go.Bar(name="6月", x=scores["行业"], y=scores["6月动量"]),
    ])
    fig.update_layout(barmode="group", title="行业多周期动量", height=350)
    st.plotly_chart(fig, use_container_width=True)
