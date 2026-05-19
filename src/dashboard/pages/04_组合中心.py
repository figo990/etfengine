"""组合中心：持仓配置、组合概览、再平衡和风险监控"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.dashboard.components import (
    render_empty_state,
    render_page_header,
    render_page_help,
    render_result_table,
)
from src.dashboard.data_refresh import refresh_etf_daily
from src.dashboard.services import load_portfolio_config, save_portfolio_config
from src.dashboard.styles import configure_dashboard_page, inject_global_styles
from src.dashboard.task_runner import submit_dashboard_task
from src.data.storage import StorageEngine

configure_dashboard_page("组合中心")
inject_global_styles()

render_page_header("组合中心", "持仓配置、目标权重、再平衡建议与组合风险。")
render_page_help(
    [
        (
            "页面用途",
            "用于维护 ETF 组合持仓、目标权重和资金规模，并查看偏离度、风险暴露和再平衡建议。",
        ),
        (
            "主要功能",
            [
                "持仓配置：录入组合资产、目标权重和当前持仓。",
                "组合概览：查看市值、权重偏离、近端走势和集中度。",
                "再平衡建议：根据目标权重计算需要买入或卖出的金额。",
                "行情补采：当前价格缺失时可提交后台行情更新。",
            ],
        ),
        ("数据依赖", "依赖 ETF 最新行情和本地组合配置；组合配置会保存在项目数据目录。"),
    ]
)


def _load_config() -> dict:
    return load_portfolio_config()


@st.cache_data(ttl=300)
def _load_prices(codes: tuple[str, ...]) -> dict[str, dict]:
    storage = StorageEngine()
    prices = {}
    try:
        storage.init_schema()
        for code in codes:
            df = storage.get_etf_daily(code)
            if df.empty:
                prices[code] = {"latest_close": None, "trade_date": ""}
                continue
            latest = df.iloc[-1]
            prices[code] = {
                "latest_close": float(latest["close"]),
                "trade_date": str(latest["trade_date"]),
            }
    except Exception:
        return {
            code: {"latest_close": None, "trade_date": ""}
            for code in codes
            if str(code).strip()
        }
    finally:
        storage.close()
    return prices


@st.cache_data(ttl=300)
def _load_history(codes: tuple[str, ...], days: int = 60) -> dict[str, pd.DataFrame]:
    storage = StorageEngine()
    history = {}
    try:
        storage.init_schema()
        for code in codes:
            df = storage.get_etf_daily(code)
            if df.empty:
                continue
            df = df.tail(days).copy()
            df["trade_date"] = pd.to_datetime(df["trade_date"])
            first_close = df["close"].iloc[0]
            df["收益率(%)"] = (df["close"] / first_close - 1) * 100 if first_close else 0
            history[code] = df
    except Exception:
        return {}
    finally:
        storage.close()
    return history


def _portfolio_table(portfolio: dict) -> pd.DataFrame:
    holdings = portfolio.get("holdings", [])
    prices = _load_prices(tuple(h.get("etf", "") for h in holdings))
    rows = []
    total_capital = float(portfolio.get("total_capital", 0))
    for item in holdings:
        code = str(item.get("etf", ""))
        target_weight = float(item.get("target_weight", 0))
        price = prices.get(code, {})
        rows.append(
            {
                "代码": code,
                "名称": item.get("name", code),
                "目标权重": target_weight,
                "目标金额": total_capital * target_weight,
                "最新价格": price.get("latest_close"),
                "数据日期": price.get("trade_date", ""),
            }
        )
    return pd.DataFrame(rows)


def _weight_status(df: pd.DataFrame) -> None:
    total_weight = float(df["目标权重"].sum()) if not df.empty else 0.0
    if abs(total_weight - 1.0) <= 0.01:
        st.success(f"权重总和 {total_weight * 100:.1f}%")
    else:
        st.warning(f"权重总和 {total_weight * 100:.1f}%，建议调整为 100%")


config = _load_config()
portfolio = config.setdefault("portfolio", {})
portfolio.setdefault("holdings", [])
portfolio.setdefault("rebalance", {})
portfolio.setdefault("risk_limits", {})

table = _portfolio_table(portfolio)

tab_overview, tab_settings, tab_rebalance, tab_risk = st.tabs(
    [
        "持仓概览",
        "持仓配置",
        "再平衡",
        "风险监控",
    ]
)

with tab_overview:
    c1, c2, c3 = st.columns(3)
    c1.metric("组合名称", portfolio.get("name", "默认ETF组合"))
    c2.metric("计划总资金", f"¥{float(portfolio.get('total_capital', 0)):,.0f}")
    c3.metric("持仓ETF数", len(portfolio.get("holdings", [])))

    if table.empty:
        render_empty_state("暂无持仓，请在“持仓配置”中添加。")
    else:
        _weight_status(table)
        display = table.copy()
        display["目标权重"] = display["目标权重"].map(lambda x: f"{x * 100:.1f}%")
        display["目标金额"] = display["目标金额"].map(lambda x: f"¥{x:,.0f}")
        display["最新价格"] = display["最新价格"].map(
            lambda x: f"¥{x:.3f}" if pd.notna(x) else "--"
        )
        render_result_table(display, empty_message="暂无持仓数据")

        fig = px.pie(table, values="目标权重", names="名称", title="目标配置权重")
        fig.update_layout(height=360)
        st.plotly_chart(fig, width="stretch")

with tab_settings:
    st.subheader("基本配置")
    col1, col2 = st.columns(2)
    portfolio_name = col1.text_input("组合名称", value=portfolio.get("name", "默认ETF组合"))
    total_capital = col2.number_input(
        "总资金(元)",
        value=int(portfolio.get("total_capital", 100000)),
        step=10000,
        min_value=0,
    )

    st.subheader("持仓列表")
    editor_df = pd.DataFrame(
        [
            {
                "代码": item.get("etf", ""),
                "名称": item.get("name", ""),
                "目标权重(%)": round(float(item.get("target_weight", 0)) * 100, 2),
            }
            for item in portfolio.get("holdings", [])
        ]
    )
    if "portfolio_equalized" in st.session_state:
        editor_df = st.session_state.pop("portfolio_equalized")
    edited = st.data_editor(
        editor_df,
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
        column_config={
            "目标权重(%)": st.column_config.NumberColumn(
                "目标权重(%)",
                min_value=0.0,
                max_value=100.0,
                step=0.5,
            ),
        },
    )

    total_weight_pct = float(edited["目标权重(%)"].sum()) if not edited.empty else 0.0
    if abs(total_weight_pct - 100) <= 1:
        st.success(f"权重总和 {total_weight_pct:.1f}%")
    else:
        st.warning(f"权重总和 {total_weight_pct:.1f}%，建议调整为 100%")

    tool_col1, tool_col2, tool_col3 = st.columns(3)
    if tool_col1.button("均分权重", width="stretch"):
        if not edited.empty:
            equal_weight = round(100 / len(edited), 2)
            edited["目标权重(%)"] = equal_weight
            st.session_state["portfolio_equalized"] = edited
            st.rerun()

    if tool_col2.button("更新持仓ETF行情", width="stretch"):
        codes = [str(code) for code in edited["代码"].dropna().tolist() if str(code).strip()]
        if not codes:
            st.warning("请先填写持仓 ETF 代码。")
        else:
            task_key = "portfolio:etf_daily:" + ",".join(sorted(codes))
            task = submit_dashboard_task(
                "持仓 ETF 行情补采",
                refresh_etf_daily,
                codes=codes,
                task_key=task_key,
                task_type="data_refresh",
                tags=["portfolio", "etf_daily"],
            )
            st.success(f"已提交后台任务：{task.id}")

    if tool_col3.button("保存组合配置", type="primary", width="stretch"):
        new_holdings = []
        for _, row in edited.fillna("").iterrows():
            code = str(row["代码"]).strip()
            if not code:
                continue
            new_holdings.append(
                {
                    "etf": code,
                    "name": str(row["名称"]).strip() or code,
                    "target_weight": round(float(row["目标权重(%)"]) / 100, 4),
                }
            )
        portfolio["name"] = portfolio_name
        portfolio["total_capital"] = int(total_capital)
        portfolio["holdings"] = new_holdings
        config["portfolio"] = portfolio
        save_portfolio_config(config)
        st.success("组合配置已保存")
        st.cache_data.clear()
        st.rerun()

with tab_rebalance:
    if table.empty:
        render_empty_state("暂无持仓，无法计算再平衡。")
    else:
        rebalance_cfg = portfolio.get("rebalance", {})
        drift_threshold = float(rebalance_cfg.get("drift_threshold", 0.05))
        st.caption(
            f"触发方式: {rebalance_cfg.get('trigger', 'drift')} | "
            f"偏离阈值: {drift_threshold * 100:.1f}% | "
            f"检查频率: {rebalance_cfg.get('periodic_frequency', 'monthly')}"
        )

        st.markdown("#### 当前实际市值")
        actual_values = {}
        input_cols = st.columns(min(len(table), 3))
        for idx, row in table.iterrows():
            with input_cols[idx % len(input_cols)]:
                actual_values[row["代码"]] = st.number_input(
                    f"{row['名称']} 市值(元)",
                    value=int(row["目标金额"]),
                    step=1000,
                    min_value=0,
                    key=f"actual_{row['代码']}",
                )

        actual_total = sum(actual_values.values())
        if actual_total > 0:
            rows = []
            for _, row in table.iterrows():
                actual_value = actual_values[row["代码"]]
                target_weight = float(row["目标权重"])
                actual_weight = actual_value / actual_total
                drift = actual_weight - target_weight
                target_value = actual_total * target_weight
                diff = target_value - actual_value
                rows.append(
                    {
                        "代码": row["代码"],
                        "名称": row["名称"],
                        "目标权重": target_weight,
                        "实际权重": actual_weight,
                        "偏离": drift,
                        "建议操作": "买入" if diff > 0 else ("卖出" if diff < 0 else "不动"),
                        "调仓金额": abs(diff),
                        "触发": abs(drift) > drift_threshold,
                    }
                )
            rebal = pd.DataFrame(rows)
            if rebal["触发"].any():
                st.warning("部分持仓偏离超过阈值，建议再平衡。")
            else:
                st.success("持仓偏离在阈值内。")

            display = rebal.copy()
            for col in ["目标权重", "实际权重", "偏离"]:
                display[col] = display[col].map(lambda x: f"{x * 100:+.1f}%")
            display["调仓金额"] = display["调仓金额"].map(lambda x: f"¥{x:,.0f}")
            render_result_table(display, empty_message="暂无再平衡结果")

with tab_risk:
    risk_cfg = portfolio.get("risk_limits", {})
    rebalance_cfg = portfolio.get("rebalance", {})
    col1, col2 = st.columns(2)
    col1.metric("最大回撤预警线", f"{float(risk_cfg.get('max_drawdown_alert', 0.15)) * 100:.0f}%")
    col1.metric("单 ETF 最大仓位", f"{float(risk_cfg.get('max_single_position', 0.40)) * 100:.0f}%")
    col2.metric("单 ETF 最小仓位", f"{float(risk_cfg.get('min_single_position', 0.05)) * 100:.0f}%")
    col2.metric("最小交易金额", f"¥{float(rebalance_cfg.get('min_trade_amount', 1000)):,.0f}")

    st.subheader("风控参数")
    rc1, rc2 = st.columns(2)
    trigger_options = ["drift", "periodic", "both"]
    freq_options = ["monthly", "weekly", "quarterly"]
    trigger = rc1.selectbox(
        "再平衡触发方式",
        trigger_options,
        index=trigger_options.index(rebalance_cfg.get("trigger", "drift")),
    )
    freq = rc1.selectbox(
        "定期检查频率",
        freq_options,
        index=freq_options.index(rebalance_cfg.get("periodic_frequency", "monthly")),
    )
    drift_threshold = rc1.slider(
        "偏离阈值(%)",
        min_value=1,
        max_value=20,
        value=int(float(rebalance_cfg.get("drift_threshold", 0.05)) * 100),
    )
    max_dd = rc2.slider(
        "最大回撤预警(%)",
        min_value=5,
        max_value=50,
        value=int(float(risk_cfg.get("max_drawdown_alert", 0.15)) * 100),
    )
    max_pos = rc2.slider(
        "单 ETF 最大仓位(%)",
        min_value=10,
        max_value=100,
        value=int(float(risk_cfg.get("max_single_position", 0.40)) * 100),
    )
    min_pos = rc2.slider(
        "单 ETF 最小仓位(%)",
        min_value=1,
        max_value=30,
        value=int(float(risk_cfg.get("min_single_position", 0.05)) * 100),
    )

    if st.button("保存风控参数", type="primary"):
        portfolio["rebalance"] = {
            "trigger": trigger,
            "drift_threshold": round(drift_threshold / 100, 4),
            "periodic_frequency": freq,
            "min_trade_amount": rebalance_cfg.get("min_trade_amount", 1000),
        }
        portfolio["risk_limits"] = {
            "max_drawdown_alert": round(max_dd / 100, 4),
            "max_single_position": round(max_pos / 100, 4),
            "min_single_position": round(min_pos / 100, 4),
        }
        config["portfolio"] = portfolio
        save_portfolio_config(config)
        st.success("风控参数已保存")
        st.rerun()

    if not table.empty:
        st.subheader("近 60 日走势")
        history = _load_history(tuple(table["代码"].tolist()))
        if history:
            names = dict(zip(table["代码"], table["名称"]))
            fig = go.Figure()
            for code, df in history.items():
                fig.add_trace(
                    go.Scatter(
                        x=df["trade_date"],
                        y=df["收益率(%)"],
                        mode="lines",
                        name=names.get(code, code),
                    )
                )
            fig.update_layout(height=400, yaxis_title="收益率(%)")
            st.plotly_chart(fig, width="stretch")
