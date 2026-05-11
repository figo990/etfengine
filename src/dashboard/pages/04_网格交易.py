"""网格交易页 — 基于真实ETF行情数据"""

import streamlit as st
from src.dashboard.styles import inject_global_styles
inject_global_styles()

import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import date
from loguru import logger

st.title("🔲 网格交易")

with st.expander("💡 使用说明", expanded=False):
    st.markdown("""
    **网格交易**适合震荡市场，通过在固定价格区间内低买高卖赚取波动利润。

    - **网格设计**：设置价格上下限和网格数量，叠加真实行情可视化网格线
      - 等差网格：网格间距固定
      - 等比网格：网格间距按比例递增（适合价格波动大的标的）
    - **回测分析**：基于真实行情模拟网格交易，查看买卖点和收益
    - **参数优化**：扫描不同网格数，寻找历史最优参数

    ⚡ 页面会根据选择的 ETF 自动推荐价格上下限（近 60 日高低点 ±5%）
    """)

st.divider()


@st.cache_resource(ttl=600)
def _get_storage():
    from src.data.storage import StorageEngine
    return StorageEngine()


def _load_portfolio_etfs() -> list[dict]:
    try:
        from src.core.config import get_portfolio_config
        cfg = get_portfolio_config()
        return cfg.get("portfolio", {}).get("holdings", [])
    except Exception as e:
        logger.warning(f"加载组合配置失败: {e}")
        return []


def _load_etf_daily(code: str) -> pd.DataFrame:
    try:
        return _get_storage().get_etf_daily(code)
    except Exception as e:
        logger.warning(f"加载 {code} 日线失败: {e}")
        return pd.DataFrame()


holdings = _load_portfolio_etfs()
etf_options = {f"{h['etf']} {h['name']}": h["etf"] for h in holdings}

tab1, tab2, tab3 = st.tabs(["网格设计", "回测分析", "参数优化"])

with tab1:
    st.subheader("网格参数设计器")

    col1, col2 = st.columns([1, 2])

    with col1:
        grid_type = st.selectbox("网格类型", ["等差网格", "等比网格"])
        if etf_options:
            selected_label = st.selectbox("选择ETF", list(etf_options.keys()), key="grid_etf")
            etf_code = etf_options[selected_label]
        else:
            etf_code = st.text_input("ETF代码", value="159915")

        df_price = _load_etf_daily(etf_code)
        if not df_price.empty and len(df_price) > 60:
            recent = df_price["close"].values[-60:]
            default_upper = float(np.max(recent) * 1.05)
            default_lower = float(np.min(recent) * 0.95)
        else:
            default_upper, default_lower = 2.0, 1.0

        price_upper = st.number_input("价格上限", value=round(default_upper, 3), step=0.01, format="%.3f")
        price_lower = st.number_input("价格下限", value=round(default_lower, 3), step=0.01, format="%.3f")
        num_grids = st.slider("网格数量", min_value=3, max_value=30, value=10)
        amount_per_grid = st.number_input("每格金额(元)", value=500, step=100)
        init_ratio = st.slider("初始仓位比例", 0.0, 1.0, 0.5)

    with col2:
        if grid_type == "等差网格":
            step = (price_upper - price_lower) / num_grids
            grid_lines = [price_lower + i * step for i in range(num_grids + 1)]
        else:
            ratio = price_upper / price_lower if price_lower > 0 else 2
            grid_lines = [price_lower * (ratio ** (i / num_grids)) for i in range(num_grids + 1)]

        fig = go.Figure()
        if not df_price.empty:
            dates = pd.to_datetime(df_price["trade_date"])
            prices = df_price["close"].values
            fig.add_trace(go.Scatter(x=dates, y=prices, mode="lines", name="ETF真实价格",
                                     line=dict(color="steelblue", width=1.5)))
        else:
            st.info("无法加载真实行情，仅显示网格线")

        for i, line in enumerate(grid_lines):
            fig.add_hline(y=line, line_dash="dot",
                         line_color="rgba(255,165,0,0.4)",
                         annotation_text=f"G{i}: {line:.3f}" if i % 2 == 0 else None)

        fig.add_hline(y=price_upper, line_color="red", line_dash="dash", annotation_text="上限")
        fig.add_hline(y=price_lower, line_color="green", line_dash="dash", annotation_text="下限")

        fig.update_layout(title=f"{grid_type}可视化 ({num_grids}格)", yaxis_title="价格", height=450)
        st.plotly_chart(fig, use_container_width=True)

        total_investment = amount_per_grid * num_grids
        step_size = (price_upper - price_lower) / num_grids if num_grids > 0 else 0
        mid_price = (price_upper + price_lower) / 2 if price_lower > 0 else 1
        st.markdown(f"""
        **参数汇总**:
        - 网格间距: {step_size:.4f}
        - 满仓投入: ¥{total_investment:,.0f}
        - 初始投入: ¥{total_investment * init_ratio:,.0f}
        - 每格收益率: {step_size / mid_price * 100:.2f}%
        """)

with tab2:
    st.subheader("网格回测")

    if etf_options:
        bt_label = st.selectbox("选择ETF", list(etf_options.keys()), key="grid_bt_etf")
        bt_code = etf_options[bt_label]
    else:
        bt_code = st.text_input("ETF代码", value="159915", key="grid_bt_code")

    col_p1, col_p2 = st.columns(2)
    with col_p1:
        bt_grids = st.slider("网格数", 3, 30, 10, key="bt_grids")
        bt_amount = st.number_input("每格金额", value=500, step=100, key="bt_grid_amt")
    with col_p2:
        bt_start = st.date_input("开始日期", value=date(2024, 1, 1), key="grid_bt_start")
        bt_end = st.date_input("结束日期", value=date.today(), key="grid_bt_end")

    if st.button("运行网格回测", type="primary"):
        df_bt = _load_etf_daily(bt_code)
        if df_bt.empty:
            st.error("无法加载ETF数据")
        else:
            with st.spinner("回测中..."):
                df_bt["trade_date"] = pd.to_datetime(df_bt["trade_date"])
                mask = (df_bt["trade_date"].dt.date >= bt_start) & (df_bt["trade_date"].dt.date <= bt_end)
                bt_df = df_bt[mask].reset_index(drop=True)

                if len(bt_df) < 10:
                    st.error("数据不足")
                else:
                    prices = bt_df["close"].values
                    dates_bt = bt_df["trade_date"]
                    p_upper = float(np.max(prices))
                    p_lower = float(np.min(prices))
                    grid_step = (p_upper - p_lower) / bt_grids if bt_grids > 0 else 1

                    cash = bt_amount * bt_grids * 0.5
                    shares = 0.0
                    trades = 0
                    buy_points, sell_points = [], []
                    buy_prices, sell_prices = [], []
                    grid_profit = 0.0
                    invested = cash

                    last_grid = int((prices[0] - p_lower) / grid_step) if grid_step > 0 else 0

                    values = []
                    for i, p in enumerate(prices):
                        current_grid = int((p - p_lower) / grid_step) if grid_step > 0 else 0
                        current_grid = max(0, min(current_grid, bt_grids))

                        if current_grid < last_grid and cash >= bt_amount:
                            buy_shares = bt_amount / p
                            shares += buy_shares
                            cash -= bt_amount
                            trades += 1
                            buy_points.append(i)
                            buy_prices.append(p)
                        elif current_grid > last_grid and shares * p >= bt_amount:
                            sell_shares = bt_amount / p
                            shares -= sell_shares
                            cash += bt_amount
                            grid_profit += (p - prices[max(0, i - 1)]) * sell_shares
                            trades += 1
                            sell_points.append(i)
                            sell_prices.append(p)

                        last_grid = current_grid
                        values.append(cash + shares * p)

                    final_val = values[-1] if values else invested
                    total_ret = (final_val / invested - 1) * 100 if invested > 0 else 0
                    days = len(bt_df)
                    annual_ret = ((final_val / invested) ** (252 / max(days, 1)) - 1) * 100 if invested > 0 else 0

                    peak = np.maximum.accumulate(values) if values else [1]
                    dd = (np.array(peak) - np.array(values)) / np.array(peak)
                    max_dd = float(np.max(dd)) * 100 if len(dd) > 0 else 0

                    st.success("回测完成!")
                    col_r1, col_r2, col_r3, col_r4 = st.columns(4)
                    with col_r1:
                        st.metric("总收益率", f"{total_ret:.1f}%")
                    with col_r2:
                        st.metric("年化收益", f"{annual_ret:.1f}%")
                    with col_r3:
                        st.metric("交易次数", f"{trades}次")
                    with col_r4:
                        st.metric("最大回撤", f"-{max_dd:.1f}%")

                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=dates_bt, y=prices, mode="lines", name="价格"))
                    if buy_points:
                        fig.add_trace(go.Scatter(
                            x=dates_bt.iloc[buy_points], y=buy_prices,
                            mode="markers", name="买入",
                            marker=dict(color="green", size=8, symbol="triangle-up"),
                        ))
                    if sell_points:
                        fig.add_trace(go.Scatter(
                            x=dates_bt.iloc[sell_points], y=sell_prices,
                            mode="markers", name="卖出",
                            marker=dict(color="red", size=8, symbol="triangle-down"),
                        ))
                    fig.update_layout(title="网格交易买卖点（真实行情）", height=400)
                    st.plotly_chart(fig, use_container_width=True)

with tab3:
    st.subheader("参数优化器")
    st.markdown("扫描不同参数组合，基于真实行情寻找最优配置")

    if etf_options:
        opt_label = st.selectbox("选择ETF", list(etf_options.keys()), key="grid_opt_etf")
        opt_code = etf_options[opt_label]
    else:
        opt_code = "159915"

    col_o1, col_o2 = st.columns(2)
    with col_o1:
        grids_range = st.slider("网格数量范围", 3, 30, (5, 20))
    with col_o2:
        optimize_target = st.selectbox("优化目标", ["总收益率", "年化收益率"])

    if st.button("开始优化", type="primary"):
        df_opt = _load_etf_daily(opt_code)
        if df_opt.empty or len(df_opt) < 60:
            st.error("数据不足，无法优化")
        else:
            with st.spinner("参数扫描中..."):
                prices = df_opt["close"].values[-252:]
                p_max = float(np.max(prices))
                p_min = float(np.min(prices))

                results = []
                for g in range(grids_range[0], grids_range[1] + 1):
                    grid_s = (p_max - p_min) / g if g > 0 else 1
                    c = 5000.0
                    s = 0.0
                    lg = int((prices[0] - p_min) / grid_s) if grid_s > 0 else 0
                    init_c = c
                    for p in prices:
                        cg = max(0, min(int((p - p_min) / grid_s), g)) if grid_s > 0 else 0
                        if cg < lg and c >= 500:
                            s += 500 / p
                            c -= 500
                        elif cg > lg and s * p >= 500:
                            s -= 500 / p
                            c += 500
                        lg = cg
                    final = c + s * prices[-1]
                    ret = (final / init_c - 1) * 100
                    results.append({"网格数": g, "总收益率(%)": round(ret, 2)})

                res_df = pd.DataFrame(results).sort_values("总收益率(%)", ascending=False)
                best = res_df.iloc[0]
                st.success(f"最优参数: 网格数={int(best['网格数'])}, 收益率={best['总收益率(%)']:.2f}%")

                fig = go.Figure(data=[
                    go.Bar(x=res_df["网格数"].astype(str), y=res_df["总收益率(%)"],
                           marker_color=["green" if v > 0 else "red" for v in res_df["总收益率(%)"]])
                ])
                fig.update_layout(title="不同网格数收益对比", xaxis_title="网格数", yaxis_title="收益率(%)", height=350)
                st.plotly_chart(fig, use_container_width=True)
