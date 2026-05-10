"""策略回测页"""

import streamlit as st
from src.dashboard.styles import inject_global_styles
inject_global_styles()

from datetime import date

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.title("🧪 策略回测")
st.divider()

STRATEGY_MAP = {
    "普通定投(DCA)": "simple_dca",
    "估值定投": "valuation_dca",
    "均线偏离定投": "ma_deviation_dca",
    "等差网格": "equal_grid",
    "等比网格": "geometric_grid",
    "大小盘动量轮动": "momentum_rotation",
    "股债轮动": "bond_equity",
}

col_config, col_result = st.columns([1, 2])

with col_config:
    st.subheader("回测配置")

    etf_code = st.text_input("ETF代码", value="510300")
    strategy_name = st.selectbox("策略类型", list(STRATEGY_MAP.keys()))

    st.markdown("**时间范围**")
    start_date = st.date_input("开始", value=date(2019, 1, 1))
    end_date = st.date_input("结束", value=date.today())

    st.markdown("**策略参数**")
    if "定投" in strategy_name:
        amount = st.number_input("每期金额", value=1000, step=100)
        freq = st.selectbox("频率", ["每月", "每周"])
    elif "网格" in strategy_name:
        upper = st.number_input("价格上限", value=5.0)
        lower = st.number_input("价格下限", value=3.0)
        grids = st.number_input("网格数量", value=10, min_value=3)
        grid_amount = st.number_input("每格金额", value=500)
    else:
        amount = st.number_input("单次金额", value=10000, step=1000)

    st.markdown("**交易成本**")
    commission = st.number_input("佣金率(万)", value=3.0) / 10000
    include_slippage = st.checkbox("计入滑点", value=True)

    run_btn = st.button("🚀 运行回测", type="primary", use_container_width=True)


def _run_backtest(
    etf_code: str,
    strategy_key: str,
    start: date,
    end: date,
    commission_rate: float,
    slippage: bool,
    **params,
) -> dict | None:
    """调用真实回测引擎"""
    try:
        from src.backtest.engine import BacktestEngine, BacktestConfig
        from src.data.storage import StorageEngine

        storage = StorageEngine()
        price_df = storage.get_etf_daily(etf_code, str(start), str(end))

        if price_df.empty or len(price_df) < 30:
            return None

        config = BacktestConfig(
            initial_cash=100000.0,
            commission_rate=commission_rate,
            stamp_tax_rate=0.001,
            slippage_rate=0.0001 if slippage else 0.0,
        )

        if strategy_key == "simple_dca":
            from src.strategies.dca.simple_dca import SimpleDCAStrategy
            strategy = SimpleDCAStrategy({
                "base_amount": params.get("amount", 1000),
                "frequency": "monthly" if params.get("freq") == "每月" else "weekly",
            })
        elif strategy_key == "valuation_dca":
            from src.strategies.dca.valuation_dca import ValuationDCAStrategy
            strategy = ValuationDCAStrategy({
                "base_amount": params.get("amount", 1000),
            })
        elif strategy_key == "ma_deviation_dca":
            from src.strategies.dca.ma_deviation_dca import MADeviationDCAStrategy
            strategy = MADeviationDCAStrategy({
                "base_amount": params.get("amount", 1000),
            })
        elif strategy_key == "equal_grid":
            from src.strategies.grid.equal_grid import EqualGridStrategy
            strategy = EqualGridStrategy({
                "upper_price": params.get("upper", 5.0),
                "lower_price": params.get("lower", 3.0),
                "num_grids": params.get("grids", 10),
                "amount_per_grid": params.get("grid_amount", 500),
            })
        elif strategy_key == "geometric_grid":
            from src.strategies.grid.geometric_grid import GeometricGridStrategy
            strategy = GeometricGridStrategy({
                "upper_price": params.get("upper", 5.0),
                "lower_price": params.get("lower", 3.0),
                "num_grids": params.get("grids", 10),
                "amount_per_grid": params.get("grid_amount", 500),
            })
        else:
            return None

        engine = BacktestEngine(config)
        result = engine.run(strategy, price_df)
        return result

    except Exception as e:
        st.error(f"回测引擎异常: {e}")
        return None


with col_result:
    if run_btn:
        st.subheader("回测结果")

        strategy_key = STRATEGY_MAP[strategy_name]
        local_params = {}
        if "定投" in strategy_name:
            local_params = {"amount": amount, "freq": freq}
        elif "网格" in strategy_name:
            local_params = {"upper": upper, "lower": lower, "grids": grids, "grid_amount": grid_amount}
        else:
            local_params = {"amount": amount}

        with st.spinner("策略回测中..."):
            result = _run_backtest(
                etf_code, strategy_key, start_date, end_date,
                commission, include_slippage, **local_params,
            )

        if result is not None and "daily_values" in result:
            metrics = result.get("metrics", {})

            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.metric("总收益率", f"{metrics.get('total_return', 0)*100:.1f}%")
            with m2:
                st.metric("年化收益", f"{metrics.get('annual_return', 0)*100:.1f}%")
            with m3:
                st.metric("最大回撤", f"{metrics.get('max_drawdown', 0)*100:.1f}%")
            with m4:
                st.metric("夏普比率", f"{metrics.get('sharpe_ratio', 0):.2f}")

            m5, m6, m7, m8 = st.columns(4)
            with m5:
                st.metric("索提诺比率", f"{metrics.get('sortino_ratio', 0):.2f}")
            with m6:
                st.metric("卡玛比率", f"{metrics.get('calmar_ratio', 0):.2f}")
            with m7:
                st.metric("交易次数", f"{metrics.get('total_trades', 0)}")
            with m8:
                total_inv = metrics.get('total_investment', 0)
                st.metric("累计投入", f"¥{total_inv:,.0f}")

            st.divider()

            daily = result["daily_values"]
            dates_arr = daily.get("dates", [])
            values = daily.get("values", [])

            if dates_arr and values:
                val_series = pd.Series(values, index=pd.to_datetime(dates_arr))
                cumulative = val_series / val_series.iloc[0] - 1
                cummax = (1 + cumulative).cummax()
                drawdown = ((1 + cumulative) - cummax) / cummax

                fig = make_subplots(
                    rows=2, cols=1, shared_xaxes=True,
                    row_heights=[0.7, 0.3], vertical_spacing=0.05,
                )
                fig.add_trace(
                    go.Scatter(x=cumulative.index, y=cumulative * 100,
                               mode="lines", name="策略收益", line=dict(color="steelblue")),
                    row=1, col=1,
                )
                fig.add_trace(
                    go.Scatter(x=drawdown.index, y=drawdown * 100,
                               mode="lines", name="回撤", fill="tozeroy", line=dict(color="red")),
                    row=2, col=1,
                )
                fig.update_layout(height=500, title="收益曲线 & 回撤")
                fig.update_yaxes(title_text="收益率(%)", row=1, col=1)
                fig.update_yaxes(title_text="回撤(%)", row=2, col=1)
                st.plotly_chart(fig, use_container_width=True)

        else:
            st.warning(
                "无法运行真实回测（可能数据未初始化），展示模拟结果。\n\n"
                "请先运行 `python scripts/init_data.py` 初始化数据。"
            )

            dates_mock = pd.date_range(start=start_date, end=end_date, freq="B")
            np.random.seed(42)
            returns = np.random.randn(len(dates_mock)) * 0.008 + 0.0003
            cumulative = (1 + pd.Series(returns)).cumprod() - 1
            cummax = (1 + cumulative).cummax()
            drawdown = ((1 + cumulative) - cummax) / cummax

            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.metric("总收益率", "45.2%")
            with m2:
                st.metric("年化收益", "8.9%")
            with m3:
                st.metric("最大回撤", "-18.5%")
            with m4:
                st.metric("夏普比率", "0.72")

            fig = make_subplots(
                rows=2, cols=1, shared_xaxes=True,
                row_heights=[0.7, 0.3], vertical_spacing=0.05,
            )
            fig.add_trace(
                go.Scatter(x=dates_mock, y=cumulative * 100, mode="lines",
                           name="策略收益(模拟)", line=dict(color="steelblue")),
                row=1, col=1,
            )
            fig.add_trace(
                go.Scatter(x=dates_mock, y=drawdown * 100, mode="lines",
                           name="回撤", fill="tozeroy", line=dict(color="red")),
                row=2, col=1,
            )
            fig.update_layout(height=500, title="收益曲线 & 回撤 (模拟数据)")
            fig.update_yaxes(title_text="收益率(%)", row=1, col=1)
            fig.update_yaxes(title_text="回撤(%)", row=2, col=1)
            st.plotly_chart(fig, use_container_width=True)

    else:
        st.info("👈 请配置回测参数后点击「运行回测」")
