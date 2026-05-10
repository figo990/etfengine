"""网格交易页"""

import streamlit as st
from src.dashboard.styles import inject_global_styles
inject_global_styles()
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import date



st.title("🔲 网格交易")
st.divider()

tab1, tab2, tab3 = st.tabs(["网格设计", "回测分析", "参数优化"])

with tab1:
    st.subheader("网格参数设计器")

    col1, col2 = st.columns([1, 2])

    with col1:
        grid_type = st.selectbox("网格类型", ["等差网格", "等比网格", "ATR动态网格"])
        etf_code = st.text_input("ETF代码", value="510300")
        price_upper = st.number_input("价格上限", value=4.5, step=0.1)
        price_lower = st.number_input("价格下限", value=3.0, step=0.1)
        num_grids = st.slider("网格数量", min_value=3, max_value=30, value=10)
        amount_per_grid = st.number_input("每格金额(元)", value=500, step=100)
        init_ratio = st.slider("初始仓位比例", 0.0, 1.0, 0.5)

    with col2:
        # 可视化网格线
        if grid_type == "等差网格":
            step = (price_upper - price_lower) / num_grids
            grid_lines = [price_lower + i * step for i in range(num_grids + 1)]
        else:
            ratio = price_upper / price_lower
            grid_lines = [price_lower * (ratio ** (i / num_grids)) for i in range(num_grids + 1)]

        # 模拟价格走势
        dates = pd.date_range(start="2024-01-01", end=date.today(), freq="B")
        np.random.seed(42)
        mid = (price_upper + price_lower) / 2
        prices = mid + np.cumsum(np.random.randn(len(dates)) * 0.01)
        prices = np.clip(prices, price_lower * 0.95, price_upper * 1.05)

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=dates, y=prices, mode="lines", name="ETF价格",
                                 line=dict(color="steelblue", width=1.5)))

        for i, line in enumerate(grid_lines):
            fig.add_hline(y=line, line_dash="dot",
                         line_color="rgba(255,165,0,0.4)",
                         annotation_text=f"G{i}: {line:.3f}" if i % 2 == 0 else None)

        fig.add_hline(y=price_upper, line_color="red", line_dash="dash",
                     annotation_text="上限")
        fig.add_hline(y=price_lower, line_color="green", line_dash="dash",
                     annotation_text="下限")

        fig.update_layout(
            title=f"{grid_type}可视化 ({num_grids}格)",
            yaxis_title="价格",
            height=450,
        )
        st.plotly_chart(fig, use_container_width=True)

        # 网格参数汇总
        total_investment = amount_per_grid * num_grids
        st.markdown(f"""
        **参数汇总**:
        - 网格间距: {(price_upper-price_lower)/num_grids:.4f} (等差) / {(price_upper/price_lower)**(1/num_grids):.4f}x (等比)
        - 满仓投入: ¥{total_investment:,.0f}
        - 初始投入: ¥{total_investment * init_ratio:,.0f}
        - 每格收益率: {(price_upper-price_lower)/num_grids/((price_upper+price_lower)/2)*100:.2f}%
        """)

with tab2:
    st.subheader("网格回测")

    if st.button("运行网格回测", type="primary"):
        with st.spinner("回测中..."):
            # 模拟结果
            col_r1, col_r2, col_r3, col_r4 = st.columns(4)
            with col_r1:
                st.metric("总收益率", "18.6%")
            with col_r2:
                st.metric("年化收益", "12.3%")
            with col_r3:
                st.metric("交易次数", "86次")
            with col_r4:
                st.metric("最大回撤", "-8.2%")

            col_r5, col_r6, col_r7, col_r8 = st.columns(4)
            with col_r5:
                st.metric("网格利润", "¥9,300")
            with col_r6:
                st.metric("持仓盈亏", "¥2,100")
            with col_r7:
                st.metric("交易成本", "¥430")
            with col_r8:
                st.metric("胜率", "62.8%")

            # 买卖点标注
            np.random.seed(42)
            dates = pd.date_range(start="2024-01-01", periods=250, freq="B")
            prices = 3.8 + np.cumsum(np.random.randn(250) * 0.02)
            prices = np.clip(prices, 3.0, 4.5)

            buy_mask = np.random.random(250) < 0.06
            sell_mask = np.random.random(250) < 0.06

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=dates, y=prices, mode="lines", name="价格"))
            fig.add_trace(go.Scatter(
                x=dates[buy_mask], y=prices[buy_mask],
                mode="markers", name="买入",
                marker=dict(color="green", size=8, symbol="triangle-up"),
            ))
            fig.add_trace(go.Scatter(
                x=dates[sell_mask], y=prices[sell_mask],
                mode="markers", name="卖出",
                marker=dict(color="red", size=8, symbol="triangle-down"),
            ))
            fig.update_layout(title="网格交易买卖点", height=400)
            st.plotly_chart(fig, use_container_width=True)

with tab3:
    st.subheader("参数优化器")
    st.markdown("扫描不同参数组合，寻找最优网格配置")

    col_o1, col_o2 = st.columns(2)
    with col_o1:
        grids_range = st.slider("网格数量范围", 3, 30, (5, 20))
        amount_range = st.slider("每格金额范围", 200, 2000, (300, 1000), step=100)
    with col_o2:
        optimize_target = st.selectbox("优化目标", ["夏普比率", "年化收益率", "卡玛比率"])

    if st.button("开始优化", type="primary"):
        with st.spinner("参数扫描中..."):
            np.random.seed(42)
            grid_nums = range(grids_range[0], grids_range[1] + 1, 2)
            amounts = range(amount_range[0], amount_range[1] + 1, 200)

            results = []
            for g in grid_nums:
                for a in amounts:
                    sharpe = np.random.uniform(0.3, 1.5) - abs(g - 12) * 0.03
                    results.append({"网格数": g, "每格金额": a, "夏普比率": round(sharpe, 3)})

            df = pd.DataFrame(results)
            best = df.loc[df["夏普比率"].idxmax()]
            st.success(f"最优参数: 网格数={int(best['网格数'])}, 每格金额=¥{int(best['每格金额'])}, 夏普={best['夏普比率']}")

            pivot = df.pivot_table(index="网格数", columns="每格金额", values="夏普比率")
            fig = go.Figure(data=go.Heatmap(
                z=pivot.values,
                x=[str(c) for c in pivot.columns],
                y=[str(i) for i in pivot.index],
                colorscale="RdYlGn",
                text=np.round(pivot.values, 2),
                texttemplate="%{text}",
            ))
            fig.update_layout(
                title="参数空间热力图 (夏普比率)",
                xaxis_title="每格金额", yaxis_title="网格数",
                height=400,
            )
            st.plotly_chart(fig, use_container_width=True)
