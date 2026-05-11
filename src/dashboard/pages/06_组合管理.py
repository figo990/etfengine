"""组合管理页"""

import streamlit as st
from src.dashboard.styles import inject_global_styles
inject_global_styles()

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from datetime import date

st.title("📋 组合管理")

with st.expander("💡 使用说明", expanded=False):
    st.markdown("""
    **组合管理**展示你的 ETF 持仓组合状态，并提供再平衡分析。

    - **持仓概览**：展示各 ETF 目标权重、最新价格、资金分配饼图
    - **再平衡分析**：输入当前实际市值，计算偏离度，给出调仓建议
    - **风险监控**：展示风控参数（回撤预警/仓位限制），以及近 60 日收益率对比图

    📌 持仓配置来自 `config/portfolio.yaml`，可在「持仓设置」页面修改
    """)

st.divider()


@st.cache_data(ttl=300)
def _load_portfolio_config():
    """加载组合配置"""
    from src.core.config import get_portfolio_config
    return get_portfolio_config()


@st.cache_data(ttl=300)
def _load_holdings_data(holdings):
    """获取各 ETF 最新价格"""
    from src.data.storage import StorageEngine
    storage = StorageEngine()
    results = []
    for h in holdings:
        code = h["etf"]
        name = h.get("name", code)
        target_w = h["target_weight"]
        df = storage.get_etf_daily(code)
        if not df.empty:
            latest = df.iloc[-1]
            results.append({
                "code": code,
                "name": name,
                "target_weight": target_w,
                "latest_close": float(latest["close"]),
                "trade_date": str(latest["trade_date"]),
            })
        else:
            results.append({
                "code": code,
                "name": name,
                "target_weight": target_w,
                "latest_close": None,
                "trade_date": None,
            })
    storage.close()
    return results


try:
    portfolio_cfg = _load_portfolio_config()
    p = portfolio_cfg.get("portfolio", {})
    holdings_cfg = p.get("holdings", [])
    total_capital = p.get("total_capital", 100000)
    rebalance_cfg = p.get("rebalance", {})
    risk_cfg = p.get("risk_limits", {})
    holdings_data = _load_holdings_data(holdings_cfg)
    has_data = any(h["latest_close"] is not None for h in holdings_data)
except Exception as e:
    st.error(f"加载组合配置失败: {e}")
    st.info("请检查 `config/portfolio.yaml` 配置文件")
    st.stop()

if not has_data:
    st.warning("尚未获取到 ETF 价格数据，请先运行 `python scripts/init_data.py`")
    st.stop()

tab1, tab2, tab3 = st.tabs(["持仓概览", "再平衡分析", "风险监控"])

with tab1:
    st.subheader("当前组合持仓")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("组合名称", p.get("name", "默认组合"))
    with col2:
        st.metric("计划总资金", f"¥{total_capital:,.0f}")
    with col3:
        st.metric("持仓ETF数", f"{len(holdings_data)} 只")

    st.divider()

    display_rows = []
    for h in holdings_data:
        target_amount = total_capital * h["target_weight"]
        display_rows.append({
            "ETF代码": h["code"],
            "名称": h["name"],
            "目标权重": f"{h['target_weight']*100:.0f}%",
            "目标金额": f"¥{target_amount:,.0f}",
            "最新价格": f"¥{h['latest_close']:.3f}" if h["latest_close"] else "--",
            "数据日期": h["trade_date"] or "--",
        })

    st.dataframe(pd.DataFrame(display_rows), use_container_width=True, hide_index=True)

    # 饼图
    labels = [h["name"] for h in holdings_data]
    values = [h["target_weight"] for h in holdings_data]
    fig = px.pie(values=values, names=labels, title="目标配置权重")
    fig.update_layout(height=350)
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("再平衡分析")

    drift_threshold = rebalance_cfg.get("drift_threshold", 0.05)
    st.info(f"再平衡触发条件: 偏离度 > {drift_threshold*100:.0f}% | "
            f"检查频率: {rebalance_cfg.get('periodic_frequency', 'monthly')}")

    st.markdown("#### 调仓建议")
    st.markdown("当前系统记录目标权重，实际持仓需手动输入后计算偏离。")

    st.divider()
    st.markdown("#### 手动输入当前持仓市值")

    actual_values = {}
    cols = st.columns(min(len(holdings_data), 3))
    for i, h in enumerate(holdings_data):
        with cols[i % len(cols)]:
            val = st.number_input(
                f"{h['name']} 市值(元)",
                value=int(total_capital * h["target_weight"]),
                step=1000, key=f"hold_{h['code']}"
            )
            actual_values[h["code"]] = val

    actual_total = sum(actual_values.values())
    if actual_total > 0 and st.button("计算再平衡"):
        rebal_rows = []
        for h in holdings_data:
            actual_w = actual_values[h["code"]] / actual_total
            target_w = h["target_weight"]
            drift = actual_w - target_w
            target_val = actual_total * target_w
            diff = target_val - actual_values[h["code"]]
            action = "买入" if diff > 0 else "卖出" if diff < 0 else "不动"
            rebal_rows.append({
                "ETF": h["name"],
                "目标权重": f"{target_w*100:.1f}%",
                "实际权重": f"{actual_w*100:.1f}%",
                "偏离": f"{drift*100:+.1f}%",
                "操作": action,
                "调仓金额": f"¥{abs(diff):,.0f}",
            })
        rebal_df = pd.DataFrame(rebal_rows)
        needs_rebal = any(abs(float(r["偏离"].strip("%+")) / 100) > drift_threshold for r in rebal_rows)
        if needs_rebal:
            st.warning("⚠️ 部分持仓偏离超过阈值，建议再平衡")
        else:
            st.success("✅ 持仓偏离在合理范围内")
        st.dataframe(rebal_df, use_container_width=True, hide_index=True)

with tab3:
    st.subheader("风险监控")

    col1, col2 = st.columns(2)
    with col1:
        st.metric("最大回撤预警线", f"{risk_cfg.get('max_drawdown_alert', 0.15)*100:.0f}%")
        st.metric("单只ETF最大仓位", f"{risk_cfg.get('max_single_position', 0.40)*100:.0f}%")
    with col2:
        st.metric("单只ETF最小仓位", f"{risk_cfg.get('min_single_position', 0.05)*100:.0f}%")
        st.metric("最小交易金额", f"¥{rebalance_cfg.get('min_trade_amount', 1000):,.0f}")

    st.divider()
    st.markdown("#### ETF 近期走势对比")

    @st.cache_data(ttl=300)
    def _load_etf_history(codes, days=60):
        from src.data.storage import StorageEngine
        storage = StorageEngine()
        all_data = {}
        for code in codes:
            df = storage.get_etf_daily(code)
            if not df.empty:
                df = df.tail(days).copy()
                df["trade_date"] = pd.to_datetime(df["trade_date"])
                first_close = df["close"].iloc[0]
                df["收益率(%)"] = (df["close"] / first_close - 1) * 100
                all_data[code] = df
        storage.close()
        return all_data

    codes = [h["code"] for h in holdings_data]
    names_map = {h["code"]: h["name"] for h in holdings_data}
    history = _load_etf_history(codes)

    if history:
        fig = go.Figure()
        for code, df in history.items():
            fig.add_trace(go.Scatter(
                x=df["trade_date"], y=df["收益率(%)"],
                mode="lines", name=names_map.get(code, code),
            ))
        fig.update_layout(
            title="近60日收益率对比",
            yaxis_title="收益率(%)", height=400,
        )
        st.plotly_chart(fig, use_container_width=True)
