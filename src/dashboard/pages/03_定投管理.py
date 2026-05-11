"""定投管理页 — 基于真实ETF行情数据"""

import streamlit as st
from src.dashboard.styles import inject_global_styles
inject_global_styles()

import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import date
from loguru import logger

st.title("💰 定投管理")

with st.expander("💡 使用说明", expanded=False):
    st.markdown("""
    **定投管理**帮助你制定和追踪 ETF 定投策略。

    - **定投信号**：根据 MA250 均线偏离度自动计算今日定投建议
      - 偏离 < -10%：深度低估加码（建议 2x）
      - 偏离 < -5%：低估加码（建议 1.5x）
      - 偏离 > 10%：暂停定投
    - **收益追踪**：选择 ETF 查看定投微笑曲线（价格 vs 平均成本）
    - **策略回测**：用真实历史数据回测不同定投策略的收益表现

    📌 定投信号基于你在「持仓设置」中配置的 ETF 列表
    """)

st.divider()


@st.cache_resource(ttl=600)
def _get_storage():
    from src.data.storage import StorageEngine
    return StorageEngine()


def _load_portfolio_etfs() -> list[dict]:
    """从 portfolio.yaml 加载持仓列表"""
    try:
        from src.core.config import get_portfolio_config
        cfg = get_portfolio_config()
        return cfg.get("portfolio", {}).get("holdings", [])
    except Exception as e:
        logger.warning(f"加载组合配置失败: {e}")
        return []


def _load_etf_daily(code: str) -> pd.DataFrame:
    try:
        storage = _get_storage()
        return storage.get_etf_daily(code)
    except Exception as e:
        logger.warning(f"加载 {code} 日线失败: {e}")
        return pd.DataFrame()


holdings = _load_portfolio_etfs()
etf_options = {f"{h['etf']} {h['name']}": h["etf"] for h in holdings}

if not etf_options:
    st.warning("未配置组合持仓，请编辑 config/portfolio.yaml")
    st.stop()

tab1, tab2, tab3 = st.tabs(["定投信号", "收益追踪", "策略回测"])

with tab1:
    st.subheader("今日定投信号")

    signals = []
    for h in holdings:
        df = _load_etf_daily(h["etf"])
        if df.empty or len(df) < 250:
            signals.append({
                "ETF": f"{h['name']}({h['etf']})",
                "策略": "普通定投",
                "信号": "正常定投",
                "建议金额": 1000,
                "触发条件": "数据不足，按默认",
            })
            continue

        close = df["close"].values
        ma250 = np.mean(close[-250:])
        deviation = (close[-1] - ma250) / ma250

        if deviation < -0.10:
            strategy, signal, amount, cond = "均线偏离定投", "深度低估加码", 2000, f"MA250偏离{deviation*100:.1f}%"
        elif deviation < -0.05:
            strategy, signal, amount, cond = "均线偏离定投", "低估加码", 1500, f"MA250偏离{deviation*100:.1f}%"
        elif deviation > 0.10:
            strategy, signal, amount, cond = "均线偏离定投", "暂停定投", 0, f"MA250偏离{deviation*100:.1f}%"
        else:
            strategy, signal, amount, cond = "普通定投", "正常定投", 1000, f"MA250偏离{deviation*100:.1f}%"

        signals.append({
            "ETF": f"{h['name']}({h['etf']})",
            "策略": strategy,
            "信号": signal,
            "建议金额": amount,
            "触发条件": cond,
        })

    sig_df = pd.DataFrame(signals)
    st.dataframe(sig_df, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("定投计划管理")
    with st.expander("➕ 新建定投计划"):
        col1, col2 = st.columns(2)
        with col1:
            etf_code = st.selectbox("选择ETF", list(etf_options.keys()), key="plan_etf")
            strategy_type = st.selectbox("策略类型", ["普通定投", "估值定投", "均线偏离定投"])
            base_amount = st.number_input("基础金额(元)", value=1000, step=100)
        with col2:
            frequency = st.selectbox("定投频率", ["每月", "每周", "每两周"])
            day = st.number_input("每月第几个交易日", value=1, min_value=1, max_value=22)
            st.button("创建计划", type="primary")

with tab2:
    st.subheader("定投收益追踪")

    selected_label = st.selectbox("选择ETF", list(etf_options.keys()), key="track_etf")
    selected_code = etf_options[selected_label]
    df = _load_etf_daily(selected_code)

    if df.empty or len(df) < 30:
        st.info("该ETF数据不足，无法生成追踪曲线")
    else:
        prices = df["close"].values
        dates = pd.to_datetime(df["trade_date"])

        invest_dates_idx = list(range(0, len(prices), 22))
        cumulative_cost = 0.0
        cumulative_shares = 0.0
        avg_costs = []
        invest_dates_list = []

        for idx in invest_dates_idx:
            p = prices[idx]
            if p > 0:
                cumulative_shares += 1000 / p
                cumulative_cost += 1000
                avg_costs.append(cumulative_cost / cumulative_shares)
                invest_dates_list.append(dates.iloc[idx])

        market_value = cumulative_shares * prices[-1]
        total_return_val = market_value - cumulative_cost
        return_pct = (total_return_val / cumulative_cost * 100) if cumulative_cost > 0 else 0

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("累计投入", f"¥{cumulative_cost:,.0f}")
        with col2:
            st.metric("当前市值", f"¥{market_value:,.0f}")
        with col3:
            st.metric("累计收益", f"¥{total_return_val:,.0f}", delta=f"{return_pct:.1f}%")
        with col4:
            years = len(prices) / 252 if len(prices) > 252 else 1
            annual_ret = ((market_value / cumulative_cost) ** (1 / years) - 1) * 100 if cumulative_cost > 0 else 0
            st.metric("年化收益(估)", f"{annual_ret:.1f}%")

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=dates, y=prices, mode="lines", name="ETF价格",
                                 line=dict(color="steelblue")))
        if avg_costs:
            fig.add_trace(go.Scatter(x=invest_dates_list, y=avg_costs,
                                     mode="lines", name="平均成本",
                                     line=dict(color="orange", dash="dash")))
        fig.update_layout(title="定投微笑曲线（真实行情）", yaxis_title="价格/成本", height=400)
        st.plotly_chart(fig, use_container_width=True)

with tab3:
    st.subheader("定投策略回测")

    col1, col2 = st.columns(2)
    with col1:
        bt_label = st.selectbox("选择ETF", list(etf_options.keys()), key="bt_etf")
        bt_code = etf_options[bt_label]
        bt_strategy = st.selectbox("选择策略", ["普通定投", "估值定投(低PE加码)", "均线偏离定投"])
    with col2:
        bt_start = st.date_input("开始日期", value=date(2020, 1, 1))
        bt_end = st.date_input("结束日期", value=date.today())
        bt_amount = st.number_input("月投金额", value=1000)

    if st.button("运行回测", type="primary"):
        df = _load_etf_daily(bt_code)
        if df.empty:
            st.error("无法加载ETF数据")
        else:
            with st.spinner("回测中..."):
                df["trade_date"] = pd.to_datetime(df["trade_date"])
                mask = (df["trade_date"].dt.date >= bt_start) & (df["trade_date"].dt.date <= bt_end)
                bt_df = df[mask].reset_index(drop=True)

                if len(bt_df) < 22:
                    st.error("回测区间内数据不足")
                else:
                    prices = bt_df["close"].values
                    dates_bt = bt_df["trade_date"]

                    total_invested = 0.0
                    total_shares = 0.0
                    invest_records = []
                    peak = 0.0
                    max_dd = 0.0

                    for idx in range(0, len(prices), 22):
                        p = prices[idx]
                        amount = bt_amount
                        if bt_strategy == "估值定投(低PE加码)" and idx > 252:
                            ma = np.mean(prices[max(0, idx - 252):idx])
                            if p < ma * 0.9:
                                amount = bt_amount * 1.5
                            elif p > ma * 1.1:
                                amount = bt_amount * 0.5
                        elif bt_strategy == "均线偏离定投" and idx > 252:
                            ma = np.mean(prices[max(0, idx - 250):idx])
                            dev = (p - ma) / ma
                            if dev < -0.10:
                                amount = bt_amount * 2
                            elif dev < -0.05:
                                amount = bt_amount * 1.5
                            elif dev > 0.10:
                                amount = 0

                        if amount > 0 and p > 0:
                            total_shares += amount / p
                            total_invested += amount

                        current_val = total_shares * prices[idx]
                        peak = max(peak, current_val)
                        if peak > 0:
                            dd = (peak - current_val) / peak
                            max_dd = max(max_dd, dd)

                        invest_records.append({
                            "date": dates_bt.iloc[idx],
                            "value": current_val,
                            "invested": total_invested,
                        })

                    final_value = total_shares * prices[-1]
                    total_return_pct = (final_value / total_invested - 1) * 100 if total_invested > 0 else 0
                    years = len(bt_df) / 252
                    annual_ret = ((final_value / total_invested) ** (1 / max(years, 0.1)) - 1) * 100 if total_invested > 0 else 0

                    st.success("回测完成!")
                    rcol1, rcol2, rcol3, rcol4 = st.columns(4)
                    with rcol1:
                        st.metric("总收益率", f"{total_return_pct:.1f}%")
                    with rcol2:
                        st.metric("年化收益", f"{annual_ret:.1f}%")
                    with rcol3:
                        st.metric("最大回撤", f"-{max_dd * 100:.1f}%")
                    with rcol4:
                        st.metric("累计投入", f"¥{total_invested:,.0f}")

                    rec_df = pd.DataFrame(invest_records)
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=rec_df["date"], y=rec_df["value"],
                                             mode="lines", name="组合市值"))
                    fig.add_trace(go.Scatter(x=rec_df["date"], y=rec_df["invested"],
                                             mode="lines", name="累计投入",
                                             line=dict(dash="dash", color="gray")))
                    fig.update_layout(title="定投回测曲线（真实行情）", yaxis_title="金额(元)", height=350)
                    st.plotly_chart(fig, use_container_width=True)
