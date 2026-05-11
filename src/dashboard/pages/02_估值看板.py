"""估值看板页"""

import streamlit as st
from src.dashboard.styles import inject_global_styles
inject_global_styles()

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from loguru import logger
from datetime import date

st.title("📈 估值看板")

with st.expander("💡 使用说明", expanded=False):
    st.markdown("""
    **估值看板**是深度估值分析工具，包含三个维度：

    1. **PE/PB 百分位**：各指数当前估值在历史中的位置
    2. **股债性价比 (FED模型)**：对比股票盈利收益率与国债利率
       - ERP > 4%：股市极度有吸引力
       - ERP 2~4%：偏股配置
       - ERP < 0%：偏债配置
    3. **估值历史走势**：查看单个指数 PE 的长期变化趋势

    📊 数据基于 AkShare 抓取的指数估值和国债收益率
    """)

st.divider()

# --- 加载真实数据 ---
@st.cache_data(ttl=300)
def _load_valuation_data():
    """从 DuckDB 加载所有指数估值"""
    from src.data.storage import StorageEngine
    storage = StorageEngine()
    indices = ["沪深300", "中证500", "中证1000", "上证50", "创业板指", "中证红利"]
    result = {}
    for idx in indices:
        df = storage.get_index_valuation(idx)
        if not df.empty:
            result[idx] = df
    storage.close()
    return result


@st.cache_data(ttl=300)
def _load_bond_data():
    """加载国债收益率"""
    from src.data.storage import StorageEngine
    storage = StorageEngine()
    df = storage.get_bond_yield()
    storage.close()
    return df


try:
    valuation_data = _load_valuation_data()
    bond_data = _load_bond_data()
    has_data = bool(valuation_data)
except Exception as e:
    logger.warning(f"加载估值/国债数据失败: {e}")
    valuation_data = {}
    bond_data = pd.DataFrame()
    has_data = False

if not has_data:
    st.warning("尚未初始化数据，请运行 `python scripts/init_data.py`")
    st.stop()

# --- Tab 1: PE/PB 百分位 ---
tab1, tab2, tab3 = st.tabs(["PE/PB 百分位", "股债性价比", "估值历史走势"])

with tab1:
    st.subheader("指数估值速览")

    rows = []
    for idx_name, df in valuation_data.items():
        if df.empty:
            continue
        latest = df.iloc[-1]
        pe_val = latest.get("pe")
        pe_pct = latest.get("pe_percentile")
        div_y = latest.get("dividend_yield")

        # 如果没有 pe_percentile，手动计算
        if pd.isna(pe_pct) and not pd.isna(pe_val):
            all_pe = df["pe"].dropna()
            pe_pct = (all_pe < pe_val).sum() / len(all_pe) * 100 if len(all_pe) > 0 else None

        zone = "适中"
        if pe_pct is not None:
            if pe_pct <= 20:
                zone = "极度低估"
            elif pe_pct <= 40:
                zone = "低估"
            elif pe_pct <= 60:
                zone = "适中"
            elif pe_pct <= 80:
                zone = "偏高"
            else:
                zone = "高估"

        rows.append({
            "指数": idx_name,
            "PE": round(pe_val, 2) if pe_val and not pd.isna(pe_val) else "--",
            "PE百分位(%)": round(pe_pct, 1) if pe_pct and not pd.isna(pe_pct) else "--",
            "股息率(%)": round(div_y, 2) if div_y and not pd.isna(div_y) else "--",
            "估值区间": zone,
            "数据日期": str(latest.get("trade_date", "")),
        })

    if rows:
        val_df = pd.DataFrame(rows)

        def _color_zone(val):
            colors = {
                "极度低估": "background-color: #c8e6c9",
                "低估": "background-color: #e8f5e9",
                "适中": "background-color: #fff9c4",
                "偏高": "background-color: #ffe0b2",
                "高估": "background-color: #ffcdd2",
            }
            return colors.get(val, "")

        st.dataframe(
            val_df.style.map(_color_zone, subset=["估值区间"]),
            use_container_width=True, hide_index=True,
        )

        # PE百分位柱状图
        pe_pcts = [r["PE百分位(%)"] for r in rows if r["PE百分位(%)"] != "--"]
        idx_names = [r["指数"] for r in rows if r["PE百分位(%)"] != "--"]
        if pe_pcts:
            colors = ["#ef5350" if p > 70 else "#66bb6a" if p < 30 else "#ffa726" for p in pe_pcts]
            fig = go.Figure(go.Bar(
                x=idx_names, y=pe_pcts, marker_color=colors,
                text=[f"{p:.0f}%" for p in pe_pcts], textposition="outside",
            ))
            fig.add_hline(y=30, line_dash="dash", line_color="green", annotation_text="低估线30%")
            fig.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="高估线70%")
            fig.update_layout(yaxis_range=[0, 100], yaxis_title="PE百分位(%)",
                              height=350, margin=dict(t=20, b=20), showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("股债性价比 (FED 模型)")
    st.markdown("""
    **公式**: ERP = 1/PE(沪深300) - 10年期国债收益率

    - ERP > 4%: 股票极度有吸引力
    - ERP 2~4%: 偏股配置
    - ERP 0~2%: 均衡配置
    - ERP < 0%: 偏债配置
    """)

    hs300_df = valuation_data.get("沪深300", pd.DataFrame())
    if not hs300_df.empty and not bond_data.empty:
        latest_pe = hs300_df["pe"].dropna().iloc[-1] if "pe" in hs300_df.columns else None
        latest_bond = bond_data["cn_10y"].dropna().iloc[-1] if "cn_10y" in bond_data.columns else None
        us_10y = bond_data["us_10y"].dropna().iloc[-1] if "us_10y" in bond_data.columns else None

        if latest_pe and latest_pe > 0 and latest_bond:
            earnings_yield = (1 / latest_pe) * 100
            cn_erp = earnings_yield - latest_bond
            us_erp = (earnings_yield - us_10y) if us_10y and not pd.isna(us_10y) else None

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("沪深300盈利收益率", f"{earnings_yield:.2f}%")
            with col2:
                st.metric("中国10年国债", f"{latest_bond:.2f}%")
            with col3:
                st.metric("中国视角 ERP", f"{cn_erp:.2f}%")

            col4, col5, col6 = st.columns(3)
            with col4:
                st.metric("美国10年国债", f"{us_10y:.2f}%" if us_10y and not pd.isna(us_10y) else "--")
            with col5:
                st.metric("美国视角 ERP", f"{us_erp:.2f}%" if us_erp else "--")
            with col6:
                if cn_erp > 4:
                    advice = "全仓权益"
                elif cn_erp > 2:
                    advice = "偏股配置"
                elif cn_erp > 0:
                    advice = "均衡配置"
                else:
                    advice = "偏债配置"
                st.metric("配置建议", advice)

            # ERP 历史走势（基于真实数据拼接）
            if "pe" in hs300_df.columns and "trade_date" in hs300_df.columns:
                merged = hs300_df[["trade_date", "pe"]].copy()
                merged["trade_date"] = pd.to_datetime(merged["trade_date"])
                merged = merged.dropna(subset=["pe"])
                merged["earnings_yield"] = 1 / merged["pe"] * 100

                bond_copy = bond_data[["trade_date", "cn_10y"]].copy()
                bond_copy["trade_date"] = pd.to_datetime(bond_copy["trade_date"])
                merged = merged.merge(bond_copy, on="trade_date", how="left")
                merged["cn_10y"] = merged["cn_10y"].ffill()
                merged["erp"] = merged["earnings_yield"] - merged["cn_10y"]
                merged = merged.dropna(subset=["erp"])

                if len(merged) > 5:
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=merged["trade_date"], y=merged["erp"],
                        mode="lines", name="ERP (中国视角)",
                    ))
                    fig.add_hline(y=4, line_dash="dash", line_color="green", annotation_text="强烈看多(4%)")
                    fig.add_hline(y=0, line_dash="dash", line_color="red", annotation_text="偏债(0%)")
                    fig.update_layout(title="沪深300 股债性价比历史", yaxis_title="ERP(%)", height=380)
                    st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("PE 或国债收益率数据缺失")
    else:
        st.info("请先初始化数据")

with tab3:
    st.subheader("指数 PE 历史走势")

    available_indices = list(valuation_data.keys())
    if available_indices:
        selected = st.selectbox("选择指数", available_indices)
        sel_df = valuation_data[selected]

        if "pe" in sel_df.columns and "trade_date" in sel_df.columns:
            chart_df = sel_df[["trade_date", "pe"]].dropna()
            chart_df["trade_date"] = pd.to_datetime(chart_df["trade_date"])

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=chart_df["trade_date"], y=chart_df["pe"],
                mode="lines", name="PE",
            ))
            fig.update_layout(
                title=f"{selected} PE 历史走势",
                yaxis_title="PE", height=400,
            )
            st.plotly_chart(fig, use_container_width=True)

            # 当前位置分析
            pe_vals = sel_df["pe"].dropna()
            if len(pe_vals) > 1:
                current_pe = pe_vals.iloc[-1]
                pct = (pe_vals < current_pe).sum() / len(pe_vals) * 100
                st.info(f"当前 PE = {current_pe:.2f}，历史百分位 = {pct:.1f}%（基于 {len(pe_vals)} 个数据点）")
    else:
        st.info("无可用数据")
