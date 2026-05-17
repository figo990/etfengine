"""轮动信号页 — 基于真实ETF行情数据"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from loguru import logger
from plotly.subplots import make_subplots

from src.dashboard.styles import inject_global_styles

inject_global_styles()

st.title("🔄 轮动信号")

with st.expander("💡 使用说明", expanded=False):
    st.markdown("""
    **轮动信号**通过动量指标判断不同资产/风格之间的强弱，帮助决定持有哪个方向。

    - **大小盘轮动**：上证50 vs 中证1000 的 20 日 ROC 动量对比
    - **风格三棱镜**：价值/成长比值 + 布林线信号，判断风格偏向
    - **红利轮动**：红利ETF vs 中证红利 的 40 日收益差驱动
    - **行业轮动**：对消费/医药/半导体等行业ETF计算多周期动量综合打分，选 Top-3

    📊 所有信号基于真实 ETF 行情数据计算，每次打开页面自动更新
    """)

st.divider()


@st.cache_resource(ttl=600)
def _get_storage():
    from src.data.storage import StorageEngine

    return StorageEngine()


def _load_etf_daily(code: str) -> pd.DataFrame:
    try:
        return _get_storage().get_etf_daily(code)
    except Exception as e:
        logger.warning(f"加载 {code} 日线失败: {e}")
        return pd.DataFrame()


def _calc_roc(prices: np.ndarray, period: int = 20) -> float:
    if len(prices) <= period:
        return 0.0
    return (prices[-1] / prices[-period - 1] - 1) * 100


ROTATION_PAIRS = {
    "大小盘轮动": {
        "大盘": {"code": "510050", "name": "上证50ETF"},
        "小盘": {"code": "512100", "name": "中证1000ETF"},
    },
    "红利轮动": {
        "A股红利": {"code": "510880", "name": "红利ETF"},
        "中证红利": {"code": "515080", "name": "中证红利ETF"},
    },
}

SECTOR_ETFS = {
    "消费": "159928",
    "医药": "512010",
    "半导体": "512480",
    "新能源": "516160",
    "军工": "512660",
    "金融": "510230",
}

tab1, tab2, tab3, tab4 = st.tabs(["大小盘轮动", "风格三棱镜", "红利轮动", "行业轮动"])

with tab1:
    st.subheader("大小盘动量轮动")
    st.markdown("**上证50 vs 中证1000** | ROC20日动量比较")

    pair = ROTATION_PAIRS["大小盘轮动"]
    df_large = _load_etf_daily(pair["大盘"]["code"])
    df_small = _load_etf_daily(pair["小盘"]["code"])

    if df_large.empty or df_small.empty:
        st.warning("无法加载行情数据")
    else:
        min_len = min(len(df_large), len(df_small))
        large_prices = df_large["close"].values[-min_len:]
        small_prices = df_small["close"].values[-min_len:]
        dates_large = pd.to_datetime(df_large["trade_date"]).values[-min_len:]

        roc_large = _calc_roc(large_prices, 20)
        roc_small = _calc_roc(small_prices, 20)

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(f"{pair['大盘']['name']} ROC20", f"{roc_large:.1f}%")
        with col2:
            st.metric(f"{pair['小盘']['name']} ROC20", f"{roc_small:.1f}%")
        with col3:
            holding = (
                f"{pair['大盘']['name']}(大盘)"
                if roc_large > roc_small
                else f"{pair['小盘']['name']}(小盘)"
            )
            st.metric("当前持有", holding)

        show_n = min(500, min_len)
        fig = make_subplots(
            rows=2, cols=1, shared_xaxes=True, row_heights=[0.6, 0.4], vertical_spacing=0.08
        )
        fig.add_trace(
            go.Scatter(
                x=dates_large[-show_n:],
                y=large_prices[-show_n:],
                name=pair["大盘"]["name"],
                line=dict(color="blue"),
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=dates_large[-show_n:],
                y=small_prices[-show_n:],
                name=pair["小盘"]["name"],
                line=dict(color="orange"),
            ),
            row=1,
            col=1,
        )

        roc_diff_series = pd.Series(large_prices[-show_n:]).pct_change(20) - pd.Series(
            small_prices[-show_n:]
        ).pct_change(20)
        roc_vals = roc_diff_series.dropna() * 100
        colors = ["green" if v > 0 else "red" for v in roc_vals]
        fig.add_trace(
            go.Bar(
                x=dates_large[-show_n + 20 :],
                y=roc_vals.values,
                name="ROC差值",
                marker_color=colors,
            ),
            row=2,
            col=1,
        )

        fig.update_layout(title="大小盘轮动（真实行情）", height=500)
        fig.update_yaxes(title_text="价格", row=1, col=1)
        fig.update_yaxes(title_text="ROC差(%)", row=2, col=1)
        st.plotly_chart(fig, width="stretch")

with tab2:
    st.subheader("风格轮动三棱镜")
    st.markdown("**价值/成长比值** | 使用上证50 vs 创业板指")

    df_value = _load_etf_daily("510050")
    df_growth = _load_etf_daily("159915")

    if df_value.empty or df_growth.empty:
        st.warning("无法加载行情数据")
    else:
        min_len = min(len(df_value), len(df_growth))
        val_prices = df_value["close"].values[-min_len:]
        gro_prices = df_growth["close"].values[-min_len:]
        dates_v = pd.to_datetime(df_value["trade_date"]).values[-min_len:]

        ratio = val_prices / gro_prices
        ratio_s = pd.Series(ratio)
        ma252 = ratio_s.rolling(min(252, len(ratio_s))).mean()
        std252 = ratio_s.rolling(min(252, len(ratio_s))).std()
        upper = ma252 + 2 * std252
        lower = ma252 - 2 * std252

        latest_ratio = ratio[-1]
        sig1 = (
            "看多价值"
            if not pd.isna(upper.iloc[-1]) and latest_ratio > upper.iloc[-1]
            else (
                "看多成长"
                if not pd.isna(lower.iloc[-1]) and latest_ratio < lower.iloc[-1]
                else "中性"
            )
        )
        sig2 = "看多价值" if len(ratio) > 41 and ratio[-1] > ratio[-41] else "看多成长"

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("布林线信号", sig1)
        with col2:
            st.metric("收益差信号", sig2)
        with col3:
            combined = "偏价值" if [sig1, sig2].count("看多价值") >= 1 else "偏成长"
            st.metric("综合判断", combined)

        show_n = min(len(ratio), 1000)
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=dates_v[-show_n:], y=ratio[-show_n:], name="价值/成长比值", line=dict(width=1.5)
            )
        )
        fig.add_trace(
            go.Scatter(
                x=dates_v[-show_n:],
                y=ma252.values[-show_n:],
                name="均线",
                line=dict(dash="dash", color="orange"),
            )
        )
        fig.add_trace(
            go.Scatter(
                x=dates_v[-show_n:],
                y=upper.values[-show_n:],
                name="布林上轨",
                line=dict(dash="dot", color="red"),
            )
        )
        fig.add_trace(
            go.Scatter(
                x=dates_v[-show_n:],
                y=lower.values[-show_n:],
                name="布林下轨",
                line=dict(dash="dot", color="green"),
            )
        )
        fig.update_layout(title="风格轮动三棱镜（上证50/创业板ETF）", height=450)
        st.plotly_chart(fig, width="stretch")

with tab3:
    st.subheader("红利轮动")
    st.markdown("**红利ETF vs 中证红利ETF** | 40日收益差驱动")

    pair = ROTATION_PAIRS["红利轮动"]
    df_a = _load_etf_daily(pair["A股红利"]["code"])
    df_b = _load_etf_daily(pair["中证红利"]["code"])

    if df_a.empty or df_b.empty:
        st.warning("无法加载行情数据")
    else:
        min_len = min(len(df_a), len(df_b))
        a_prices = df_a["close"].values[-min_len:]
        b_prices = df_b["close"].values[-min_len:]
        dates_r = pd.to_datetime(df_a["trade_date"]).values[-min_len:]

        ret_a = pd.Series(a_prices).pct_change(40) * 100
        ret_b = pd.Series(b_prices).pct_change(40) * 100
        diff_40 = (ret_a - ret_b).dropna()

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(
                f"{pair['A股红利']['name']} 40日收益",
                f"{ret_a.iloc[-1]:.1f}%" if not pd.isna(ret_a.iloc[-1]) else "--",
            )
        with col2:
            st.metric(
                f"{pair['中证红利']['name']} 40日收益",
                f"{ret_b.iloc[-1]:.1f}%" if not pd.isna(ret_b.iloc[-1]) else "--",
            )
        with col3:
            d = diff_40.iloc[-1] if len(diff_40) > 0 else 0
            holding = (
                pair["中证红利"]["name"]
                if d > 5
                else (pair["A股红利"]["name"] if d < -5 else "均衡")
            )
            st.metric("建议持有", holding)

        show_n = min(500, min_len)
        fig = make_subplots(
            rows=2, cols=1, shared_xaxes=True, row_heights=[0.5, 0.5], vertical_spacing=0.08
        )
        fig.add_trace(
            go.Scatter(x=dates_r[-show_n:], y=a_prices[-show_n:], name=pair["A股红利"]["name"]),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(x=dates_r[-show_n:], y=b_prices[-show_n:], name=pair["中证红利"]["name"]),
            row=1,
            col=1,
        )

        diff_vals = diff_40.values[-show_n + 40 :] if len(diff_40) > 0 else []
        if len(diff_vals) > 0:
            diff_colors = ["red" if d > 5 else ("green" if d < -5 else "gray") for d in diff_vals]
            fig.add_trace(
                go.Bar(
                    x=dates_r[-len(diff_vals) :],
                    y=diff_vals,
                    name="收益差",
                    marker_color=diff_colors,
                ),
                row=2,
                col=1,
            )
            fig.add_hline(y=5, line_dash="dash", line_color="red", row=2, col=1)
            fig.add_hline(y=-5, line_dash="dash", line_color="green", row=2, col=1)

        fig.update_layout(title="红利轮动（真实行情）", height=500)
        st.plotly_chart(fig, width="stretch")

with tab4:
    st.subheader("行业动量轮动")
    st.markdown("**多周期动量打分** | 基于真实行情选择Top-3行业ETF")

    sector_scores = []
    for name, code in SECTOR_ETFS.items():
        df_sec = _load_etf_daily(code)
        if df_sec.empty or len(df_sec) < 130:
            sector_scores.append(
                {"行业": name, "1月动量": 0, "3月动量": 0, "6月动量": 0, "综合得分": 0}
            )
            continue

        prices = df_sec["close"].values
        m1 = _calc_roc(prices, 22)
        m3 = _calc_roc(prices, 66)
        m6 = _calc_roc(prices, 130)
        composite = m1 * 0.4 + m3 * 0.35 + m6 * 0.25

        sector_scores.append(
            {
                "行业": name,
                "1月动量": round(m1, 2),
                "3月动量": round(m3, 2),
                "6月动量": round(m6, 2),
                "综合得分": round(composite, 2),
            }
        )

    scores_df = (
        pd.DataFrame(sector_scores).sort_values("综合得分", ascending=False).reset_index(drop=True)
    )

    st.dataframe(
        scores_df.style.background_gradient(cmap="RdYlGn", subset=["综合得分"]),
        width="stretch",
        hide_index=True,
    )

    top3 = scores_df.head(3)["行业"].tolist()
    st.success(f"当前Top-3持仓建议: **{', '.join(top3)}**")

    fig = go.Figure(
        data=[
            go.Bar(name="1月", x=scores_df["行业"], y=scores_df["1月动量"]),
            go.Bar(name="3月", x=scores_df["行业"], y=scores_df["3月动量"]),
            go.Bar(name="6月", x=scores_df["行业"], y=scores_df["6月动量"]),
        ]
    )
    fig.update_layout(barmode="group", title="行业多周期动量（真实数据）", height=350)
    st.plotly_chart(fig, width="stretch")
