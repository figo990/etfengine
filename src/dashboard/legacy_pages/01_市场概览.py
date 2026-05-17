"""市场概览页"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from loguru import logger

from src.dashboard.styles import inject_global_styles

inject_global_styles()

st.title("📊 市场概览")

with st.expander("💡 使用说明", expanded=False):
    st.markdown("""
    **市场概览**展示主要宽基指数的最新估值快照，帮助你快速判断市场整体冷热。

    - **PE百分位**：当前市盈率在历史中的位置，越低越便宜（<30% 低估，>70% 高估）
    - **股息率**：越高说明分红越多，通常对应低估
    - **市场温度计**：综合所有指数估值，给出冷/中/热判断

    📊 **数据来源**：DuckDB 本地数据库（AkShare 抓取）
    """)

try:
    from src.data.storage import StorageEngine

    storage = StorageEngine()

    indices = ["沪深300", "中证500", "创业板指", "中证红利", "上证50"]
    valuation_rows = []
    for idx_name in indices:
        try:
            df = storage.get_index_valuation(idx_name)
            if not df.empty:
                latest = df.iloc[-1]
                pe_val = latest.get("pe")
                pe_pct = latest.get("pe_percentile")
                div_y = latest.get("dividend_yield")

                # 如果没有百分位，动态计算
                if pd.isna(pe_pct) and not pd.isna(pe_val):
                    all_pe = df["pe"].dropna()
                    pe_pct = (all_pe < pe_val).sum() / len(all_pe) * 100 if len(all_pe) > 1 else 0

                valuation_rows.append(
                    {
                        "指数": idx_name,
                        "PE": f"{float(pe_val):.2f}" if pe_val and not pd.isna(pe_val) else "--",
                        "PE百分位(%)": f"{float(pe_pct):.1f}"
                        if pe_pct and not pd.isna(pe_pct)
                        else "--",
                        "股息率(%)": f"{float(div_y):.2f}"
                        if div_y and not pd.isna(div_y)
                        else "--",
                    }
                )
        except Exception as e:
            logger.warning(f"加载 {idx_name} 估值失败: {e}")

    if valuation_rows:
        val_df = pd.DataFrame(valuation_rows)
        data_source = "实时数据"
    else:
        raise ValueError("无数据")

except Exception as e:
    logger.warning(f"加载估值数据失败: {e}")
    val_df = pd.DataFrame()
    data_source = "无数据"

st.caption(f"数据来源: {data_source}")

if val_df.empty:
    st.warning("尚未初始化数据，请运行 `python scripts/init_data.py`")
    st.stop()

st.divider()

# KPI Metrics
col1, col2, col3, col4 = st.columns(4)


def _get_val(idx_name, col):
    row = val_df[val_df["指数"] == idx_name]
    if len(row) == 0:
        return "--"
    v = row[col].values[0]
    return v if v != "--" else "--"


with col1:
    v = _get_val("沪深300", "PE百分位(%)")
    st.metric("沪深300 PE百分位", f"{v}%" if v != "--" else "--")
with col2:
    v = _get_val("中证500", "PE百分位(%)")
    st.metric("中证500 PE百分位", f"{v}%" if v != "--" else "--")
with col3:
    v = _get_val("中证红利", "股息率(%)")
    st.metric("中证红利 股息率", f"{v}%" if v != "--" else "--")
with col4:
    v = _get_val("创业板指", "PE百分位(%)")
    st.metric("创业板 PE百分位", f"{v}%" if v != "--" else "--")

st.divider()

# 估值速览表
st.subheader("📋 指数估值速览")


def _zone(pe_pct) -> str:
    if pe_pct == "--" or pe_pct is None:
        return "--"
    pe_pct = float(pe_pct)
    if pe_pct <= 20:
        return "极度低估"
    elif pe_pct <= 40:
        return "低估"
    elif pe_pct <= 60:
        return "适中"
    elif pe_pct <= 80:
        return "偏高"
    return "高估"


val_df["估值区间"] = val_df["PE百分位(%)"].apply(_zone)


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
    width="stretch",
    hide_index=True,
    height=250,
)

st.divider()

# PE 百分位柱状图
st.subheader("📊 PE 百分位对比")

chart_df = val_df[val_df["PE百分位(%)"] != "--"].copy()
chart_df["PE百分位(%)"] = chart_df["PE百分位(%)"].astype(float)

if not chart_df.empty:
    fig = go.Figure()
    pe_pcts = chart_df["PE百分位(%)"].values
    colors = ["#ef5350" if p > 70 else "#66bb6a" if p < 30 else "#ffa726" for p in pe_pcts]

    fig.add_trace(
        go.Bar(
            x=chart_df["指数"],
            y=pe_pcts,
            marker_color=colors,
            text=[f"{p:.0f}%" for p in pe_pcts],
            textposition="outside",
        )
    )

    fig.add_hline(y=30, line_dash="dash", line_color="green", annotation_text="低估线 30%")
    fig.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="高估线 70%")

    fig.update_layout(
        yaxis_range=[0, 100],
        yaxis_title="PE百分位(%)",
        height=350,
        margin=dict(t=20, b=20),
        showlegend=False,
    )
    st.plotly_chart(fig, width="stretch")

st.divider()

# 市场温度计
st.subheader("🌡️ 市场温度计")

numeric_pcts = chart_df["PE百分位(%)"] if not chart_df.empty else pd.Series([50])
avg_pe_pct = numeric_pcts.mean()

temp_col1, temp_col2 = st.columns([2, 3])

with temp_col1:
    if avg_pe_pct < 30:
        st.success(f"🟢 市场偏冷 ({avg_pe_pct:.0f})")
        st.markdown("当前估值整体偏低，适合逐步加仓")
    elif avg_pe_pct < 60:
        st.warning(f"🟡 市场中性 ({avg_pe_pct:.0f})")
        st.markdown("估值适中，维持常规定投节奏")
    else:
        st.error(f"🔴 市场偏热 ({avg_pe_pct:.0f})")
        st.markdown("估值偏高，建议减少加仓、适当止盈")

with temp_col2:
    fig_gauge = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=avg_pe_pct,
            title={"text": "综合估值温度"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": "#1976d2"},
                "steps": [
                    {"range": [0, 30], "color": "#c8e6c9"},
                    {"range": [30, 60], "color": "#fff9c4"},
                    {"range": [60, 100], "color": "#ffcdd2"},
                ],
            },
        )
    )
    fig_gauge.update_layout(height=250, margin=dict(t=30, b=10))
    st.plotly_chart(fig_gauge, width="stretch")
