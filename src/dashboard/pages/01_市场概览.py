"""市场概览页"""

import streamlit as st
from src.dashboard.styles import inject_global_styles
inject_global_styles()
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import date, timedelta

st.title("📊 市场概览")

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
                valuation_rows.append({
                    "指数": idx_name,
                    "PE": round(latest.get("pe", 0), 2),
                    "PE百分位(%)": round(latest.get("pe_percentile", 0), 1),
                    "PB": round(latest.get("pb", 0), 2),
                    "PB百分位(%)": round(latest.get("pb_percentile", 0), 1),
                    "股息率(%)": round(latest.get("dividend_yield", 0), 2),
                })
        except Exception:
            pass

    if valuation_rows:
        val_df = pd.DataFrame(valuation_rows)
        data_source = "实时数据"
    else:
        raise ValueError("无数据")

except Exception:
    val_df = pd.DataFrame({
        "指数": ["上证50", "沪深300", "中证500", "创业板指", "中证红利"],
        "PE": [10.2, 12.5, 22.1, 30.5, 6.8],
        "PE百分位(%)": [35, 45, 55, 38, 25],
        "PB": [1.1, 1.3, 1.8, 3.2, 0.7],
        "PB百分位(%)": [28, 32, 45, 35, 15],
        "股息率(%)": [3.8, 3.0, 1.5, 0.6, 5.2],
    })
    data_source = "示例数据"

st.caption(f"数据来源: {data_source}")
st.divider()

# KPI Metrics
col1, col2, col3, col4 = st.columns(4)

hs300 = val_df[val_df["指数"] == "沪深300"]
zz500 = val_df[val_df["指数"] == "中证500"]
zzhl = val_df[val_df["指数"] == "中证红利"]
cyb = val_df[val_df["指数"] == "创业板指"]

with col1:
    pe_pct = hs300["PE百分位(%)"].values[0] if len(hs300) else 45
    st.metric("沪深300 PE百分位", f"{pe_pct:.1f}%")
with col2:
    pe_pct2 = zz500["PE百分位(%)"].values[0] if len(zz500) else 55
    st.metric("中证500 PE百分位", f"{pe_pct2:.1f}%")
with col3:
    div_yield = zzhl["股息率(%)"].values[0] if len(zzhl) else 5.2
    st.metric("中证红利 股息率", f"{div_yield:.2f}%")
with col4:
    pe_pct3 = cyb["PE百分位(%)"].values[0] if len(cyb) else 38
    st.metric("创业板 PE百分位", f"{pe_pct3:.1f}%")

st.divider()

# 估值速览表
st.subheader("📋 指数估值速览")


def _zone(pe_pct: float) -> str:
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
    use_container_width=True,
    hide_index=True,
    height=250,
)

st.divider()

# PE 百分位柱状图
st.subheader("📊 PE 百分位对比")

fig = go.Figure()
colors = ["#ef5350" if p > 70 else "#66bb6a" if p < 30 else "#ffa726"
          for p in val_df["PE百分位(%)"].values]

fig.add_trace(go.Bar(
    x=val_df["指数"],
    y=val_df["PE百分位(%)"],
    marker_color=colors,
    text=val_df["PE百分位(%)"].apply(lambda x: f"{x:.0f}%"),
    textposition="outside",
))

fig.add_hline(y=30, line_dash="dash", line_color="green",
              annotation_text="低估线 30%")
fig.add_hline(y=70, line_dash="dash", line_color="red",
              annotation_text="高估线 70%")

fig.update_layout(
    yaxis_range=[0, 100],
    yaxis_title="PE百分位(%)",
    height=350,
    margin=dict(t=20, b=20),
    showlegend=False,
)
st.plotly_chart(fig, use_container_width=True)

st.divider()

# 市场温度计
st.subheader("🌡️ 市场温度计")

avg_pe_pct = val_df["PE百分位(%)"].mean()

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
    fig_gauge = go.Figure(go.Indicator(
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
    ))
    fig_gauge.update_layout(height=250, margin=dict(t=30, b=10))
    st.plotly_chart(fig_gauge, use_container_width=True)

if data_source == "示例数据":
    st.caption("* 当前展示为示例数据，运行 `python scripts/init_data.py` 后将显示真实数据")
