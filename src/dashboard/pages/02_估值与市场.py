"""估值与市场：市场温度、指数估值、股债性价比和历史走势."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from loguru import logger

from src.dashboard.components import (
    render_empty_state,
    render_metric_cards,
    render_page_header,
    render_result_table,
)
from src.dashboard.styles import configure_dashboard_page, inject_global_styles
from src.data.storage import StorageEngine

configure_dashboard_page("估值与市场")
inject_global_styles()

render_page_header("估值与市场", "统一查看主要宽基估值、市场温度、股债性价比和历史分位变化。")

INDEX_NAMES = ["沪深300", "中证500", "中证1000", "上证50", "创业板指", "中证红利"]
ZONE_COLORS = {
    "极度低估": "background-color: #c8e6c9",
    "低估": "background-color: #e8f5e9",
    "适中": "background-color: #fff9c4",
    "偏高": "background-color: #ffe0b2",
    "高估": "background-color: #ffcdd2",
}


@st.cache_data(ttl=300)
def _load_valuation_data() -> dict[str, pd.DataFrame]:
    storage = StorageEngine()
    try:
        storage.init_schema()
        data = {}
        for index_name in INDEX_NAMES:
            df = storage.get_index_valuation(index_name)
            if not df.empty:
                data[index_name] = df.sort_values("trade_date").reset_index(drop=True)
        return data
    finally:
        storage.close()


@st.cache_data(ttl=300)
def _load_bond_data() -> pd.DataFrame:
    storage = StorageEngine()
    try:
        storage.init_schema()
        return storage.get_bond_yield().sort_values("trade_date").reset_index(drop=True)
    finally:
        storage.close()


def _valuation_zone(pe_percentile: object) -> str:
    if pe_percentile is None or pd.isna(pe_percentile):
        return "--"
    value = float(pe_percentile)
    if value <= 20:
        return "极度低估"
    if value <= 40:
        return "低估"
    if value <= 60:
        return "适中"
    if value <= 80:
        return "偏高"
    return "高估"


def _fmt(value: object, digits: int = 2, suffix: str = "") -> str:
    try:
        if value is None or pd.isna(value):
            return "--"
        return f"{float(value):.{digits}f}{suffix}"
    except (TypeError, ValueError):
        return "--"


def _latest_pe_percentile(df: pd.DataFrame, latest: pd.Series) -> float | None:
    pe_percentile = latest.get("pe_percentile")
    if pe_percentile is not None and pd.notna(pe_percentile):
        return float(pe_percentile)
    pe = latest.get("pe")
    pe_values = df["pe"].dropna() if "pe" in df.columns else pd.Series(dtype=float)
    if pe is None or pd.isna(pe) or pe_values.empty:
        return None
    return float((pe_values < pe).sum() / len(pe_values) * 100)


def _build_snapshot(valuation_data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for index_name, df in valuation_data.items():
        if df.empty:
            continue
        latest = df.iloc[-1]
        pe_percentile = _latest_pe_percentile(df, latest)
        rows.append(
            {
                "指数": index_name,
                "日期": str(latest.get("trade_date", "")),
                "PE": latest.get("pe"),
                "PB": latest.get("pb"),
                "PE百分位": pe_percentile,
                "PB百分位": latest.get("pb_percentile"),
                "股息率": latest.get("dividend_yield"),
                "估值区间": _valuation_zone(pe_percentile),
            }
        )
    return pd.DataFrame(rows)


def _style_zone(value: object) -> str:
    return ZONE_COLORS.get(str(value), "")


def _render_market_temperature(snapshot: pd.DataFrame) -> None:
    valid = snapshot.dropna(subset=["PE百分位"])
    if valid.empty:
        render_empty_state("暂无可计算的 PE 百分位数据。")
        return

    avg_percentile = float(valid["PE百分位"].mean())
    low_count = int((valid["PE百分位"] <= 40).sum())
    high_count = int((valid["PE百分位"] >= 80).sum())
    latest_date = valid["日期"].max()

    render_metric_cards(
        [
            ("综合估值温度", f"{avg_percentile:.0f}/100"),
            ("低估指数数", low_count),
            ("高估指数数", high_count),
            ("最新日期", latest_date),
        ]
    )

    c1, c2 = st.columns([1.1, 1.4])
    with c1:
        if avg_percentile < 30:
            st.success(f"市场偏冷，综合温度 {avg_percentile:.0f}")
            st.caption("估值整体偏低，可重点关注再平衡和分批配置机会。")
        elif avg_percentile < 60:
            st.warning(f"市场中性，综合温度 {avg_percentile:.0f}")
            st.caption("估值处于中间区域，适合维持常规节奏并观察结构分化。")
        else:
            st.error(f"市场偏热，综合温度 {avg_percentile:.0f}")
            st.caption("估值位置偏高，应重点关注仓位约束和止盈纪律。")

        display = snapshot.copy()
        for col in ["PE", "PB", "PE百分位", "PB百分位", "股息率"]:
            display[col] = display[col].map(lambda value: _fmt(value))
        render_result_table(display, empty_message="暂无估值快照")

    with c2:
        gauge = go.Figure(
            go.Indicator(
                mode="gauge+number",
                value=avg_percentile,
                title={"text": "综合估值温度"},
                gauge={
                    "axis": {"range": [0, 100]},
                    "bar": {"color": "#2563eb"},
                    "steps": [
                        {"range": [0, 30], "color": "#c8e6c9"},
                        {"range": [30, 60], "color": "#fff9c4"},
                        {"range": [60, 100], "color": "#ffcdd2"},
                    ],
                },
            )
        )
        gauge.update_layout(height=360, margin=dict(t=30, b=20))
        st.plotly_chart(gauge, width="stretch")


def _render_percentile_compare(snapshot: pd.DataFrame) -> None:
    if snapshot.empty:
        render_empty_state("暂无估值数据。")
        return

    display = snapshot.copy()
    styled = display.copy()
    for col in ["PE", "PB", "PE百分位", "PB百分位", "股息率"]:
        styled[col] = styled[col].map(lambda value: _fmt(value))
    st.dataframe(
        styled.style.map(_style_zone, subset=["估值区间"]),
        width="stretch",
        hide_index=True,
    )

    chart_df = snapshot.dropna(subset=["PE百分位"]).copy()
    if chart_df.empty:
        return

    colors = [
        "#ef4444" if value > 70 else "#16a34a" if value < 30 else "#f59e0b"
        for value in chart_df["PE百分位"]
    ]
    fig = go.Figure(
        go.Bar(
            x=chart_df["指数"],
            y=chart_df["PE百分位"],
            marker_color=colors,
            text=[f"{value:.0f}%" for value in chart_df["PE百分位"]],
            textposition="outside",
        )
    )
    fig.add_hline(y=30, line_dash="dash", line_color="green", annotation_text="低估线 30%")
    fig.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="高估线 70%")
    fig.update_layout(
        height=380,
        yaxis_range=[0, 100],
        yaxis_title="PE 百分位",
        showlegend=False,
        margin=dict(t=20, b=20),
    )
    st.plotly_chart(fig, width="stretch")


def _render_fed_model(valuation_data: dict[str, pd.DataFrame], bond_data: pd.DataFrame) -> None:
    hs300 = valuation_data.get("沪深300", pd.DataFrame())
    if hs300.empty or bond_data.empty:
        render_empty_state("沪深300估值或国债收益率数据不足。")
        return

    latest_pe_series = hs300["pe"].dropna() if "pe" in hs300.columns else pd.Series(dtype=float)
    cn_bond_series = (
        bond_data["cn_10y"].dropna() if "cn_10y" in bond_data.columns else pd.Series(dtype=float)
    )
    if latest_pe_series.empty or cn_bond_series.empty:
        render_empty_state("PE 或中国 10 年国债收益率缺失。")
        return

    latest_pe = float(latest_pe_series.iloc[-1])
    latest_cn_bond = float(cn_bond_series.iloc[-1])
    earnings_yield = 1 / latest_pe * 100 if latest_pe > 0 else None
    cn_erp = earnings_yield - latest_cn_bond if earnings_yield is not None else None
    us_10y = None
    if "us_10y" in bond_data.columns and not bond_data["us_10y"].dropna().empty:
        us_10y = float(bond_data["us_10y"].dropna().iloc[-1])
    us_erp = earnings_yield - us_10y if earnings_yield is not None and us_10y else None

    if cn_erp is None:
        render_empty_state("无法计算股债性价比。")
        return

    if cn_erp > 4:
        advice = "权益吸引力强"
    elif cn_erp > 2:
        advice = "偏股配置"
    elif cn_erp > 0:
        advice = "均衡配置"
    else:
        advice = "偏债配置"

    render_metric_cards(
        [
            ("沪深300盈利收益率", _fmt(earnings_yield, suffix="%")),
            ("中国10年国债", _fmt(latest_cn_bond, suffix="%")),
            ("中国视角 ERP", _fmt(cn_erp, suffix="%")),
            ("美国视角 ERP", _fmt(us_erp, suffix="%")),
            ("配置提示", advice),
        ]
    )

    merged = hs300[["trade_date", "pe"]].dropna().copy()
    merged["trade_date"] = pd.to_datetime(merged["trade_date"])
    merged["盈利收益率"] = 1 / merged["pe"] * 100
    bond = bond_data[["trade_date", "cn_10y"]].dropna().copy()
    bond["trade_date"] = pd.to_datetime(bond["trade_date"])
    merged = merged.merge(bond, on="trade_date", how="left").sort_values("trade_date")
    merged["cn_10y"] = merged["cn_10y"].ffill()
    merged["ERP"] = merged["盈利收益率"] - merged["cn_10y"]
    merged = merged.dropna(subset=["ERP"])

    if len(merged) <= 5:
        render_empty_state("历史数据点不足，暂无法绘制 ERP 趋势。")
        return

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=merged["trade_date"],
            y=merged["ERP"],
            mode="lines",
            name="ERP",
        )
    )
    fig.add_hline(y=4, line_dash="dash", line_color="green", annotation_text="权益强吸引力")
    fig.add_hline(y=0, line_dash="dash", line_color="red", annotation_text="偏债线")
    fig.update_layout(height=420, yaxis_title="ERP(%)", margin=dict(t=20, b=20))
    st.plotly_chart(fig, width="stretch")


def _render_history(valuation_data: dict[str, pd.DataFrame]) -> None:
    available = list(valuation_data)
    if not available:
        render_empty_state("暂无指数估值历史。")
        return

    selected = st.selectbox("指数", available)
    df = valuation_data[selected].copy()
    if df.empty or "trade_date" not in df.columns:
        render_empty_state("该指数暂无历史数据。")
        return

    df["trade_date"] = pd.to_datetime(df["trade_date"])
    c1, c2 = st.columns([2, 1])
    with c1:
        fig = go.Figure()
        if "pe" in df.columns:
            fig.add_trace(go.Scatter(x=df["trade_date"], y=df["pe"], mode="lines", name="PE"))
        if "pb" in df.columns:
            fig.add_trace(go.Scatter(x=df["trade_date"], y=df["pb"], mode="lines", name="PB"))
        fig.update_layout(height=420, yaxis_title="估值", margin=dict(t=20, b=20))
        st.plotly_chart(fig, width="stretch")

    with c2:
        latest = df.iloc[-1]
        pe_values = df["pe"].dropna() if "pe" in df.columns else pd.Series(dtype=float)
        current_pe = latest.get("pe")
        percentile = _latest_pe_percentile(df, latest)
        render_metric_cards(
            [
                ("当前 PE", _fmt(current_pe)),
                ("历史百分位", _fmt(percentile, 1, "%")),
                ("样本点数", len(pe_values)),
            ]
        )
        st.caption(f"当前数据日期：{latest.get('trade_date', '')}")


try:
    valuation_data = _load_valuation_data()
    bond_data = _load_bond_data()
except Exception as exc:
    logger.warning(f"加载估值与市场数据失败: {exc}")
    valuation_data = {}
    bond_data = pd.DataFrame()

snapshot_df = _build_snapshot(valuation_data)

if snapshot_df.empty:
    render_empty_state(
        "尚未初始化估值数据，请先在数据管理页补采指数估值和国债收益率。",
        level="warning",
    )
else:
    tabs = st.tabs(["市场温度", "指数估值", "股债性价比", "历史走势"])
    with tabs[0]:
        _render_market_temperature(snapshot_df)
    with tabs[1]:
        _render_percentile_compare(snapshot_df)
    with tabs[2]:
        _render_fed_model(valuation_data, bond_data)
    with tabs[3]:
        _render_history(valuation_data)
