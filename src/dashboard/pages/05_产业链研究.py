"""产业链研究：产业链图谱、企业趋势、重大新闻和横向对比."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from src.dashboard.components import (
    render_empty_state,
    render_metric_cards,
    render_page_header,
    render_page_help,
    render_result_table,
)
from src.dashboard.data_refresh import (
    refresh_industry_chain_companies,
    refresh_industry_chain_fundamental_bundle,
    refresh_industry_chain_news_links,
)
from src.dashboard.styles import configure_dashboard_page, inject_global_styles
from src.dashboard.task_runner import submit_dashboard_task
from src.data.storage import StorageEngine
from src.intelligence.industry_chain_analyzer import IndustryChainAnalyzer

configure_dashboard_page("产业链研究")
inject_global_styles()

render_page_header("产业链研究", "产业链图谱、企业趋势、经营质量、重大新闻与横向对比。")
render_page_help(
    [
        (
            "页面用途",
            "用于围绕人工智能、机器人、商业航天等方向查看产业链结构、供应链企业、趋势表现和重大新闻。",
        ),
        (
            "主要功能",
            [
                "产业链图谱：按上游、中游、下游等环节查看企业、ETF 和指数配置。",
                "企业趋势：比较产业链企业行情、涨跌幅、新闻热度和高影响事件。",
                "经营质量：查看企业财务、估值、业绩预告和覆盖率缺口。",
                "重大新闻：展示与产业链和企业关联的政策、行业、公司新闻。",
                "横向对比：多个产业链之间比较企业数量、新闻热度、趋势和数据覆盖。",
            ],
        ),
        ("数据依赖", "依赖产业链配置、企业行情、企业财务/估值、新闻采集与新闻关联结果。"),
    ]
)


@st.cache_data(ttl=300)
def _load_chains() -> list[dict]:
    storage = StorageEngine()
    try:
        storage.init_schema()
        return IndustryChainAnalyzer(storage).list_chains()
    except Exception:
        return []
    finally:
        storage.close()


@st.cache_data(ttl=300)
def _load_snapshot(chain_id: str) -> dict:
    storage = StorageEngine()
    try:
        storage.init_schema()
        return IndustryChainAnalyzer(storage).build_snapshot(chain_id)
    except Exception:
        return {}
    finally:
        storage.close()


@st.cache_data(ttl=300)
def _load_compare(chain_ids: tuple[str, ...]) -> pd.DataFrame:
    storage = StorageEngine()
    try:
        storage.init_schema()
        return IndustryChainAnalyzer(storage).compare_chains(list(chain_ids))
    except Exception:
        return pd.DataFrame()
    finally:
        storage.close()


def _fmt_pct(value: object) -> str:
    try:
        if value is None or pd.isna(value):
            return "--"
        return f"{float(value):+.2f}%"
    except (TypeError, ValueError):
        return "--"


def _join_aliases(values: object) -> str:
    if isinstance(values, list):
        return "、".join(str(value) for value in values)
    return ""


def _fmt_number(value: object, digits: int = 2) -> str:
    try:
        if value is None or pd.isna(value):
            return "暂无"
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "暂无"


def _fmt_pct_cell(value: object) -> str:
    try:
        if value is None or pd.isna(value):
            return "暂无"
        return f"{float(value):+.2f}%"
    except (TypeError, ValueError):
        return "暂无"


def _fmt_pe(value: object) -> str:
    try:
        if value is None or pd.isna(value):
            return "暂无"
        numeric = float(value)
        if numeric <= 0:
            return "亏损/不可比"
        return f"{numeric:.2f}"
    except (TypeError, ValueError):
        return "暂无"


def _render_data_quality(data_quality: dict) -> None:
    price_coverage = data_quality.get("company_price_coverage", 0)
    fundamental_coverage = data_quality.get("company_fundamental_coverage", 0)
    valuation_coverage = data_quality.get("company_valuation_coverage", 0)
    latest_market_date = data_quality.get("latest_market_date") or "暂无"
    latest_report_date = data_quality.get("latest_report_date") or "暂无"

    render_metric_cards(
        [
            ("行情覆盖率", f"{price_coverage:.0%}"),
            ("财务覆盖率", f"{fundamental_coverage:.0%}"),
            ("估值覆盖率", f"{valuation_coverage:.0%}"),
            ("最新行情", latest_market_date),
            ("最新财报", latest_report_date),
        ]
    )

    if price_coverage >= 1 and fundamental_coverage >= 1 and valuation_coverage >= 1:
        st.caption("当前产业链行情、财务和估值数据覆盖完整。")
        return

    missing_parts = []
    for key, label in [
        ("missing_company_prices", "缺失行情"),
        ("missing_company_fundamentals", "缺失财务"),
        ("missing_company_valuations", "缺失估值"),
    ]:
        missing = data_quality.get(key, [])
        if missing:
            suffix = "等" if len(missing) > 5 else ""
            missing_parts.append(f"{label}：{'、'.join(missing[:5])}{suffix}")
    st.warning("；".join(missing_parts) or "当前产业链存在数据覆盖缺口。")


def _render_chain_refresh_actions(chain_id: str) -> None:
    st.markdown("#### 当前产业链补采")
    col1, col2, col3 = st.columns(3)
    if col1.button("后台补采企业行情", width="stretch"):
        task = submit_dashboard_task(
            f"产业链企业行情补采：{chain_id}",
            refresh_industry_chain_companies,
            chain_id=chain_id,
            task_key=f"industry-chain-companies:{chain_id}",
            task_type="industry_chain",
            tags=["industry_chain", chain_id, "price"],
        )
        st.success(f"已提交后台任务：{task.id}")
    if col2.button("后台补采经营数据", width="stretch"):
        task = submit_dashboard_task(
            f"产业链经营数据补采：{chain_id}",
            refresh_industry_chain_fundamental_bundle,
            chain_id=chain_id,
            task_key=f"industry-chain-fundamentals:{chain_id}",
            task_type="industry_chain",
            tags=["industry_chain", chain_id, "fundamentals"],
        )
        st.success(f"已提交后台任务：{task.id}")
    if col3.button("后台刷新新闻关联", width="stretch"):
        task = submit_dashboard_task(
            "产业链新闻关联刷新",
            refresh_industry_chain_news_links,
            task_key="industry-chain-news-links",
            task_type="industry_chain",
            tags=["industry_chain", "news_links"],
        )
        st.success(f"已提交后台任务：{task.id}")


chains = _load_chains()
if not chains:
    render_empty_state("暂无产业链配置，请检查 config/industry_chains.yaml。")
    st.stop()

chain_name_map = {item["name"]: item["chain_id"] for item in chains}

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

st.caption(f"{snapshot['description']} | 更新时间: {snapshot['generated_at']}")
render_metric_cards(
    [
        ("覆盖企业", overview["company_count"]),
        ("产业环节", overview["segment_count"]),
        ("相关新闻", overview["news_count"]),
        ("高影响新闻", overview["high_impact_news_count"]),
        ("平均情绪", f"{overview['avg_sentiment']:+.2f}", overview["trend_label"]),
    ]
)

analysis = snapshot["analysis"]
st.info(f"{analysis['status']} {analysis['trend']} 风险提示：{analysis['risk']}。")

tabs = st.tabs(["产业链图谱", "企业趋势", "经营质量", "重大新闻", "横向对比", "数据覆盖"])

with tabs[0]:
    seg_df = pd.DataFrame(snapshot["segments"])
    if seg_df.empty:
        render_empty_state("暂无产业链环节配置。")
    else:
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
                title=f"{snapshot['name']} 环节热度",
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
            render_result_table(display, empty_message="暂无环节数据")

        st.markdown("#### 环节企业")
        for segment in snapshot["segments"]:
            with st.expander(segment["segment_name"], expanded=True):
                company_df = pd.DataFrame(segment["companies"])
                if company_df.empty:
                    render_empty_state("暂无企业配置")
                else:
                    company_df["aliases"] = company_df["aliases"].map(_join_aliases)
                    company_df = company_df.rename(
                        columns={
                            "company_code": "代码",
                            "company_name": "企业",
                            "role": "定位",
                            "aliases": "别名",
                        }
                    )
                    render_result_table(company_df, empty_message="暂无企业配置")

    etf_df = pd.DataFrame(snapshot["etfs"])
    index_df = pd.DataFrame(snapshot["indices"])
    ec1, ec2 = st.columns(2)
    with ec1:
        st.markdown("#### 相关 ETF")
        if etf_df.empty:
            render_empty_state("暂无 ETF 配置")
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
            render_result_table(etf_display, empty_message="暂无 ETF 数据")
    with ec2:
        st.markdown("#### 相关指数估值")
        if index_df.empty:
            render_empty_state("暂无指数配置")
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
            for col in ["PE", "PB", "股息率", "PE百分位", "PB百分位"]:
                if col in index_display.columns:
                    index_display[col] = index_display[col].map(_fmt_number)
            if {"PE", "PB", "PE百分位"}.issubset(index_display.columns):
                missing_count = int(
                    (
                        (index_display["PE"] == "暂无")
                        & (index_display["PB"] == "暂无")
                        & (index_display["PE百分位"] == "暂无")
                    ).sum()
                )
                if missing_count:
                    st.caption(
                        f"{missing_count} 个相关指数暂无估值数据，"
                        "请在数据管理页补采或补充指数源映射。"
                    )
            render_result_table(index_display, empty_message="暂无指数估值数据")

with tabs[1]:
    companies_df = pd.DataFrame(snapshot["companies"])
    if companies_df.empty:
        render_empty_state("暂无企业配置")
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
        table["aliases"] = table["aliases"].map(_join_aliases)
        for col in ["return_5d", "return_20d", "return_60d"]:
            table[col] = table[col].map(_fmt_pct_cell)
        table["latest_close"] = table["latest_close"].map(_fmt_number)
        table["pe_ttm"] = table["pe_ttm"].map(_fmt_pe)
        table["pb"] = table["pb"].map(_fmt_number)
        table["avg_sentiment"] = table["avg_sentiment"].map(_fmt_number)
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
        render_result_table(table, empty_message="暂无企业趋势数据")

with tabs[2]:
    fundamentals_df = pd.DataFrame(snapshot["companies"])
    if fundamentals_df.empty:
        render_empty_state("暂无企业基本面数据")
    else:
        available = fundamentals_df[fundamentals_df["latest_report_date"] != ""].copy()
        if available.empty:
            render_empty_state("暂无企业基本面数据，请先执行补采。")
        else:
            render_metric_cards(
                [
                    ("财务覆盖率", f"{data_quality.get('company_fundamental_coverage', 0):.0%}"),
                    ("估值覆盖率", f"{data_quality.get('company_valuation_coverage', 0):.0%}"),
                    ("最新财报日期", data_quality.get("latest_report_date") or "暂无"),
                    ("业绩预告数", data_quality.get("earnings_forecast_count", 0)),
                ]
            )

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
            for col in [
                "revenue",
                "revenue_yoy",
                "net_profit",
                "net_profit_yoy",
                "roe",
                "pb",
                "latest_forecast_change_pct",
            ]:
                quality_table[col] = quality_table[col].map(_fmt_number)
            quality_table["pe_ttm"] = quality_table["pe_ttm"].map(_fmt_pe)
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
            render_result_table(quality_table, empty_message="暂无经营质量数据")

with tabs[3]:
    news_df = pd.DataFrame(snapshot["news"])
    if news_df.empty:
        render_empty_state("暂无关联新闻。请先运行新闻采集任务，或等待调度器更新。")
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

with tabs[4]:
    compare_ids = tuple(chain_name_map[name] for name in compare_names)
    if len(compare_ids) < 2:
        render_empty_state("请至少选择两个产业链进行横向对比。")
    else:
        compare_df = _load_compare(compare_ids)
        render_result_table(
            compare_df.drop(columns=["chain_id"]),
            empty_message="暂无产业链横向对比数据",
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

with tabs[5]:
    _render_data_quality(data_quality)
    _render_chain_refresh_actions(selected_chain_id)

    st.markdown("#### 缺口明细")
    gaps = []
    for key, label in [
        ("missing_company_prices", "行情"),
        ("missing_company_fundamentals", "财务"),
        ("missing_company_valuations", "估值"),
    ]:
        for code in data_quality.get(key, []):
            gaps.append({"类型": label, "代码": code})
    render_result_table(gaps, empty_message="当前产业链暂无数据覆盖缺口。")
