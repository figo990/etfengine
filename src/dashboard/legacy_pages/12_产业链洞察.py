"""产业链洞察：方向、环节、企业趋势、重大新闻与横向对比"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from src.dashboard.formatting import format_display_datetime
from src.dashboard.styles import inject_global_styles
from src.data.storage import StorageEngine
from src.intelligence.industry_chain_analyzer import IndustryChainAnalyzer

inject_global_styles()

st.title("产业链洞察")


@st.cache_data(ttl=300)
def _load_chains() -> list[dict]:
    storage = StorageEngine()
    try:
        storage.init_schema()
        return IndustryChainAnalyzer(storage).list_chains()
    finally:
        storage.close()


@st.cache_data(ttl=300)
def _load_snapshot(chain_id: str) -> dict:
    storage = StorageEngine()
    try:
        storage.init_schema()
        return IndustryChainAnalyzer(storage).build_snapshot(chain_id)
    finally:
        storage.close()


@st.cache_data(ttl=300)
def _load_compare(chain_ids: tuple[str, ...]) -> pd.DataFrame:
    storage = StorageEngine()
    try:
        storage.init_schema()
        return IndustryChainAnalyzer(storage).compare_chains(list(chain_ids))
    finally:
        storage.close()


def _fmt_pct(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "--"
    return f"{value:+.2f}%"


def _fmt_num(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "--"
    return f"{value:.2f}"


chains = _load_chains()
if not chains:
    st.info("暂无产业链配置，请检查 config/industry_chains.yaml")
    st.stop()

chain_name_map = {item["name"]: item["chain_id"] for item in chains}
chain_id_to_name = {item["chain_id"]: item["name"] for item in chains}

with st.sidebar:
    st.subheader("产业链筛选")
    selected_name = st.selectbox("产业链方向", list(chain_name_map))
    selected_chain_id = chain_name_map[selected_name]
    compare_names = st.multiselect(
        "横向对比",
        list(chain_name_map),
        default=list(chain_name_map)[: min(3, len(chain_name_map))],
    )

snapshot = _load_snapshot(selected_chain_id)
overview = snapshot["overview"]
data_quality = snapshot.get("data_quality", {})

updated_at = format_display_datetime(snapshot.get("generated_at"))
st.caption(f"{snapshot['description']} | 更新时间: {updated_at}")

metric_cols = st.columns(5)
metric_cols[0].metric("覆盖企业", overview["company_count"])
metric_cols[1].metric("产业环节", overview["segment_count"])
metric_cols[2].metric("相关新闻", overview["news_count"])
metric_cols[3].metric("高影响新闻", overview["high_impact_news_count"])
metric_cols[4].metric("平均情绪", f"{overview['avg_sentiment']:+.2f}", overview["trend_label"])

analysis = snapshot["analysis"]
st.info(f"{analysis['status']} {analysis['trend']} 风险提示：{analysis['risk']}。")

coverage = data_quality.get("company_price_coverage", 0)
latest_market_date = format_display_datetime(
    data_quality.get("latest_market_date") or "暂无",
    date_only=True,
)
fundamental_coverage = data_quality.get("company_fundamental_coverage", 0)
valuation_coverage = data_quality.get("company_valuation_coverage", 0)
latest_report_date = format_display_datetime(
    data_quality.get("latest_report_date") or "暂无",
    date_only=True,
)
if coverage < 1 or fundamental_coverage < 1 or valuation_coverage < 1:
    missing_price = data_quality.get("missing_company_prices", [])
    missing_fundamentals = data_quality.get("missing_company_fundamentals", [])
    missing_valuations = data_quality.get("missing_company_valuations", [])
    missing_parts = []
    if missing_price:
        suffix = "等" if len(missing_price) > 5 else ""
        missing_parts.append(f"缺失行情：{'、'.join(missing_price[:5])}{suffix}")
    if missing_fundamentals:
        suffix = "等" if len(missing_fundamentals) > 5 else ""
        missing_parts.append(f"缺失财务：{'、'.join(missing_fundamentals[:5])}{suffix}")
    if missing_valuations:
        suffix = "等" if len(missing_valuations) > 5 else ""
        missing_parts.append(f"缺失估值：{'、'.join(missing_valuations[:5])}{suffix}")
    st.warning(
        f"企业行情覆盖率 {coverage:.0%}，最新行情日期 {latest_market_date}。"
        f"企业财务覆盖率 {fundamental_coverage:.0%}，最新财报日期 {latest_report_date}。"
        f"企业估值覆盖率 {valuation_coverage:.0%}。"
        f"{'；'.join(missing_parts)}。可在数据管理页补采。"
    )
else:
    st.caption(
        f"企业行情覆盖率 {coverage:.0%}，最新行情日期 {latest_market_date}；"
        f"财务覆盖率 {fundamental_coverage:.0%}，最新财报日期 {latest_report_date}；"
        f"估值覆盖率 {valuation_coverage:.0%}"
    )

tab_overview, tab_companies, tab_fundamentals, tab_news, tab_compare = st.tabs(
    [
        "产业链图谱",
        "企业趋势",
        "经营质量",
        "重大新闻",
        "横向对比",
    ]
)

with tab_overview:
    seg_df = pd.DataFrame(snapshot["segments"])
    if not seg_df.empty:
        c1, c2 = st.columns([3, 2])
        with c1:
            fig = px.bar(
                seg_df,
                x="segment_name",
                y="news_count",
                color="avg_sentiment",
                color_continuous_scale="RdYlGn",
                range_color=[-1, 1],
                text="company_count",
                labels={
                    "segment_name": "环节",
                    "news_count": "相关新闻",
                    "avg_sentiment": "平均情绪",
                    "company_count": "企业数",
                },
                title=f"{snapshot['name']}环节热度",
            )
            fig.update_layout(height=360, showlegend=False)
            st.plotly_chart(fig, width="stretch")

        with c2:
            display = seg_df[
                [
                    "segment_name",
                    "company_count",
                    "news_count",
                    "high_impact_news_count",
                    "avg_sentiment",
                ]
            ].rename(
                columns={
                    "segment_name": "环节",
                    "company_count": "企业数",
                    "news_count": "新闻数",
                    "high_impact_news_count": "高影响",
                    "avg_sentiment": "情绪",
                }
            )
            st.dataframe(display, width="stretch", hide_index=True)

        st.markdown("#### 环节企业")
        for segment in snapshot["segments"]:
            with st.expander(segment["segment_name"], expanded=True):
                company_df = pd.DataFrame(segment["companies"])
                if company_df.empty:
                    st.info("暂无企业配置")
                else:
                    company_df["aliases"] = company_df["aliases"].map(
                        lambda values: "、".join(values) if values else ""
                    )
                    company_df = company_df.rename(
                        columns={
                            "company_code": "代码",
                            "company_name": "企业",
                            "role": "定位",
                            "aliases": "别名",
                        }
                    )
                    st.dataframe(company_df, width="stretch", hide_index=True)

    etf_df = pd.DataFrame(snapshot["etfs"])
    index_df = pd.DataFrame(snapshot["indices"])
    ec1, ec2 = st.columns(2)
    with ec1:
        st.markdown("#### 相关 ETF")
        if etf_df.empty:
            st.info("暂无 ETF 配置")
        else:
            etf_display = etf_df.rename(
                columns={
                    "code": "代码",
                    "latest_date": "日期",
                    "latest_close": "收盘",
                    "return_5d": "5日",
                    "return_20d": "20日",
                    "return_60d": "60日",
                }
            )
            st.dataframe(etf_display, width="stretch", hide_index=True)
    with ec2:
        st.markdown("#### 相关指数估值")
        if index_df.empty:
            st.info("暂无指数配置")
        else:
            index_display = index_df.rename(
                columns={
                    "index_name": "指数",
                    "trade_date": "日期",
                    "pe": "PE",
                    "pb": "PB",
                    "dividend_yield": "股息率",
                    "pe_percentile": "PE百分位",
                    "pb_percentile": "PB百分位",
                }
            )
            st.dataframe(index_display, width="stretch", hide_index=True)

with tab_companies:
    companies_df = pd.DataFrame(snapshot["companies"])
    if companies_df.empty:
        st.info("暂无企业配置")
    else:
        segment_options = ["全部"] + sorted(companies_df["segment_name"].dropna().unique().tolist())
        selected_segment = st.selectbox("环节", segment_options)
        filtered = companies_df
        if selected_segment != "全部":
            filtered = filtered[filtered["segment_name"] == selected_segment]

        chart_df = filtered.copy()
        chart_df["20日涨跌"] = chart_df["return_20d"].fillna(0)
        fig_company = px.bar(
            chart_df,
            x="company_name",
            y="20日涨跌",
            color="avg_sentiment",
            color_continuous_scale="RdYlGn",
            range_color=[-1, 1],
            hover_data=["role", "news_count", "return_5d", "return_60d"],
            labels={
                "company_name": "企业",
                "20日涨跌": "20日涨跌幅(%)",
                "avg_sentiment": "新闻情绪",
            },
            title="企业趋势与新闻情绪",
        )
        fig_company.update_layout(height=380)
        st.plotly_chart(fig_company, width="stretch")

        display_cols = [
            "segment_name",
            "company_code",
            "company_name",
            "aliases",
            "role",
            "news_count",
            "avg_sentiment",
            "latest_close",
            "return_5d",
            "return_20d",
            "return_60d",
            "pe_ttm",
            "pb",
        ]
        table = filtered[display_cols].copy()
        table["aliases"] = table["aliases"].map(lambda values: "、".join(values) if values else "")
        table = table.rename(
            columns={
                "segment_name": "环节",
                "company_code": "代码",
                "company_name": "企业",
                "aliases": "别名",
                "role": "定位",
                "news_count": "新闻数",
                "avg_sentiment": "情绪",
                "latest_close": "最新价",
                "return_5d": "5日",
                "return_20d": "20日",
                "return_60d": "60日",
                "pe_ttm": "PE(TTM)",
                "pb": "PB",
            }
        )
        st.dataframe(table, width="stretch", hide_index=True)

with tab_fundamentals:
    fundamentals_df = pd.DataFrame(snapshot["companies"])
    if fundamentals_df.empty:
        st.info("暂无企业基本面数据")
    else:
        available = fundamentals_df[fundamentals_df["latest_report_date"] != ""].copy()
        if available.empty:
            st.info("暂无企业基本面数据，请先在数据管理页执行更新。")
        else:
            f1, f2, f3, f4 = st.columns(4)
            f1.metric("财务覆盖率", f"{fundamental_coverage:.0%}")
            f2.metric("估值覆盖率", f"{valuation_coverage:.0%}")
            f3.metric("最新财报日期", latest_report_date)
            f4.metric("业绩预告数", data_quality.get("earnings_forecast_count", 0))

            chart_df = available.copy()
            chart_df["营收同比"] = chart_df["revenue_yoy"].fillna(0)
            chart_df["净利同比"] = chart_df["net_profit_yoy"].fillna(0)
            chart_df["营收规模"] = chart_df["revenue"].fillna(0).clip(lower=0)
            fig_quality = px.scatter(
                chart_df,
                x="营收同比",
                y="净利同比",
                size="营收规模",
                color="roe",
                hover_name="company_name",
                hover_data=["segment_name", "pe_ttm", "pb", "latest_report_type"],
                color_continuous_scale="RdYlGn",
                labels={
                    "roe": "ROE",
                    "company_name": "企业",
                    "营收同比": "营收同比(%)",
                    "净利同比": "净利润同比(%)",
                },
                title="经营兑现与估值",
            )
            fig_quality.update_layout(height=420)
            st.plotly_chart(fig_quality, width="stretch")

            quality_cols = [
                "segment_name",
                "company_code",
                "company_name",
                "latest_report_date",
                "latest_report_type",
                "revenue",
                "revenue_yoy",
                "net_profit",
                "net_profit_yoy",
                "roe",
                "pe_ttm",
                "pb",
                "latest_forecast_period",
                "latest_forecast_type",
                "latest_forecast_change_pct",
            ]
            quality_table = available[quality_cols].copy()
            for col in ["revenue", "net_profit"]:
                quality_table[col] = quality_table[col] / 1e8
            quality_table = quality_table.rename(
                columns={
                    "segment_name": "环节",
                    "company_code": "代码",
                    "company_name": "企业",
                    "latest_report_date": "报告期",
                    "latest_report_type": "报告类型",
                    "revenue": "营收(亿元)",
                    "revenue_yoy": "营收同比",
                    "net_profit": "净利润(亿元)",
                    "net_profit_yoy": "净利同比",
                    "roe": "ROE",
                    "pe_ttm": "PE(TTM)",
                    "pb": "PB",
                    "latest_forecast_period": "预告期",
                    "latest_forecast_type": "预告类型",
                    "latest_forecast_change_pct": "预告变动",
                }
            )
            st.dataframe(quality_table, width="stretch", hide_index=True)

with tab_news:
    news_df = pd.DataFrame(snapshot["news"])
    if news_df.empty:
        st.info("暂无关联新闻。请先运行新闻采集任务，或等待调度器更新。")
    else:
        impact = st.radio("新闻类型", ["全部", "政策", "高影响"], horizontal=True)
        filtered_news = news_df
        if impact == "政策":
            filtered_news = filtered_news[filtered_news["is_policy"] == True]  # noqa: E712
        elif impact == "高影响":
            filtered_news = filtered_news[filtered_news["impact_level"] == "high"]

        for _, row in filtered_news.iterrows():
            sentiment = row.get("sentiment") or 0
            badge = "利多" if sentiment > 0.25 else ("利空" if sentiment < -0.25 else "中性")
            with st.container(border=True):
                st.markdown(f"**{row.get('title', '')}**")
                st.caption(
                    f"{row.get('publish_time', '')} | {row.get('source', '')} | "
                    f"{row.get('company_name', '')} | {row.get('impact_level', 'low')} | {badge}"
                )
                if row.get("summary"):
                    st.write(row["summary"])
                if row.get("url"):
                    st.link_button("查看原文", row["url"])

with tab_compare:
    compare_ids = tuple(chain_name_map[name] for name in compare_names)
    if len(compare_ids) < 2:
        st.info("请至少选择两个产业链进行横向对比")
    else:
        compare_df = _load_compare(compare_ids)
        st.dataframe(
            compare_df.drop(columns=["chain_id"]),
            width="stretch",
            hide_index=True,
        )

        fig_compare = px.scatter(
            compare_df,
            x="相关新闻",
            y="平均情绪",
            size="企业数",
            color="趋势",
            text="产业链",
            hover_data=["高影响新闻", "环节数"],
            title="产业链热度/情绪对比",
        )
        fig_compare.update_traces(textposition="top center")
        fig_compare.update_layout(height=420, yaxis_range=[-1, 1])
        st.plotly_chart(fig_compare, width="stretch")
