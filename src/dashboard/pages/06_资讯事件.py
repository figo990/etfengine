"""资讯事件：行业新闻、政策追踪、智能预警和外盘季报"""

from __future__ import annotations

import json

import pandas as pd
import plotly.express as px
import streamlit as st

from src.core.config import load_yaml_config
from src.dashboard.components import (
    render_empty_state,
    render_page_header,
    render_page_help,
    render_result_table,
)
from src.dashboard.data_refresh import refresh_overseas_earnings
from src.dashboard.formatting import format_display_datetime
from src.dashboard.services import update_news_event_followup
from src.dashboard.styles import configure_dashboard_page, inject_global_styles
from src.dashboard.task_runner import submit_dashboard_task
from src.data.storage import StorageEngine
from src.intelligence.sector_tracker import SectorTracker

configure_dashboard_page("资讯事件")
inject_global_styles()

render_page_header("资讯事件", "行业新闻、政策追踪、预警事件与海外科技龙头季报。")
render_page_help(
    [
        (
            "页面用途",
            "用于跟踪行业新闻、政策事件、情绪变化、重点事件跟进和海外科技龙头季报影响。",
        ),
        (
            "主要功能",
            [
                "新闻总览：按行业、情绪、影响等级筛选新闻。",
                "政策追踪：聚合政策类新闻并支持后续跟进状态。",
                "事件预警：发现高影响或情绪极端事件。",
                "外盘季报：查看海外科技龙头财报指标和 ETF 关联影响。",
            ],
        ),
        ("数据依赖", "依赖新闻监控、LLM/关键词分析、海外季报采集和事件跟进记录。"),
    ]
)


def _parse_json_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if not isinstance(value, str) or not value.strip():
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    if isinstance(parsed, list):
        return [str(item) for item in parsed]
    return []


@st.cache_data(ttl=300)
def _load_news(limit: int = 300) -> pd.DataFrame:
    storage = StorageEngine()
    try:
        storage.init_schema()
        df = storage.get_news_articles(limit=limit)
    except Exception:
        return pd.DataFrame()
    finally:
        storage.close()
    if df.empty:
        return df

    rows = []
    for _, row in df.iterrows():
        sectors = _parse_json_list(row.get("related_sectors"))
        etfs = _parse_json_list(row.get("related_etf_codes"))
        rows.append(
            {
                "id": row.get("id", ""),
                "时间": format_display_datetime(row.get("publish_time", "")),
                "标题": row.get("title", ""),
                "摘要": row.get("summary", ""),
                "来源": row.get("source", ""),
                "类别": row.get("category", ""),
                "情绪": float(row.get("sentiment", 0) or 0),
                "影响": row.get("impact_level", "low"),
                "政策": bool(row.get("is_policy", False)),
                "行业列表": sectors,
                "行业": ", ".join(sectors),
                "ETF": ", ".join(etfs),
                "链接": row.get("url", ""),
            }
        )
    return pd.DataFrame(rows)


@st.cache_data(ttl=300)
def _load_overseas_earnings() -> pd.DataFrame:
    storage = StorageEngine()
    try:
        storage.init_schema()
        metrics = storage.get_overseas_earnings_metrics(limit=5000)
        analysis = storage.get_overseas_earnings_analysis(limit=1000)
    except Exception:
        return pd.DataFrame()
    finally:
        storage.close()

    if metrics.empty:
        return pd.DataFrame()

    metrics = metrics.sort_values("period_end")
    latest_idx = metrics.groupby("ticker")["period_end"].idxmax()
    latest = metrics.loc[latest_idx].copy()

    if analysis.empty:
        latest["summary_zh"] = ""
        latest["sentiment"] = None
        latest["impact_level"] = ""
        latest["related_etf_codes"] = ""
        return latest.sort_values("ticker")

    analysis = analysis.sort_values("analyzed_at", ascending=False)
    latest_analysis = analysis.groupby(["ticker", "period_end"]).first().reset_index()
    merged = latest.merge(
        latest_analysis,
        on=["ticker", "period_end"],
        how="left",
        suffixes=("", "_analysis"),
    )
    return merged.sort_values("ticker")


def _load_followups(article_ids: list[str]) -> pd.DataFrame:
    storage = StorageEngine()
    try:
        storage.init_schema()
        return storage.get_news_event_followups(article_ids)
    except Exception:
        return pd.DataFrame()
    finally:
        storage.close()


def _sector_heatmap(news: pd.DataFrame) -> pd.DataFrame:
    sectors_config = load_yaml_config("intelligence.yaml").get("sectors", {})
    sector_names = list(sectors_config) or sorted(
        {sector for sectors in news.get("行业列表", []) for sector in sectors}
    )
    rows = []
    for sector in sector_names:
        mask = news["行业"].str.contains(sector, na=False) if not news.empty else pd.Series()
        sub = news[mask] if not news.empty else pd.DataFrame()
        rows.append(
            {
                "行业": sector,
                "新闻数": len(sub),
                "平均情绪": round(sub["情绪"].mean(), 3) if len(sub) else 0.0,
                "高影响": int((sub["影响"] == "high").sum()) if len(sub) else 0,
            }
        )
    return pd.DataFrame(rows)


def _render_news_cards(news: pd.DataFrame, *, page_size: int = 15) -> None:
    if news.empty:
        render_empty_state("暂无新闻数据，请先运行调度器或在数据管理页补采。")
        return

    total = len(news)
    page_count = max((total + page_size - 1) // page_size, 1)
    page = st.number_input(
        "新闻列表页码",
        min_value=1,
        max_value=page_count,
        value=1,
        step=1,
        key=f"news_page_{id(news)}",
    )
    start = (int(page) - 1) * page_size
    page_rows = news.iloc[start : start + page_size]
    st.caption(f"共 {total} 条，当前第 {int(page)}/{page_count} 页（每页 {page_size} 条）")

    for _, row in page_rows.iterrows():
        sentiment = float(row["情绪"])
        badge = "利多" if sentiment > 0.25 else ("利空" if sentiment < -0.25 else "中性")
        meta_parts = [
            str(value).strip()
            for value in [
                row.get("时间"),
                row.get("来源"),
                row.get("行业"),
                row.get("影响"),
                f"{badge} {sentiment:+.2f}",
            ]
            if str(value or "").strip()
        ]
        meta_line = " · ".join(meta_parts)
        summary = str(row.get("摘要") or "").strip()
        body_parts = [f"**{row['标题']}**", meta_line]
        if summary and summary != str(row.get("标题", "")).strip():
            body_parts.append(f"_{summary}_")
        if row.get("ETF"):
            body_parts.append(f"关联 ETF: {row['ETF']}")
        with st.container(border=True):
            st.markdown("\n\n".join(body_parts))
            if row.get("链接"):
                st.link_button("查看原文", row["链接"])


def _fmt_usd(value: object) -> str:
    try:
        if pd.isna(value):
            return "--"
        return f"{float(value) / 1e8:.2f}亿"
    except (TypeError, ValueError):
        return "--"


def _fmt_pct(value: object) -> str:
    try:
        if pd.isna(value):
            return "--"
        return f"{float(value):+.1f}%"
    except (TypeError, ValueError):
        return "--"


news_df = _load_news()
earnings_df = _load_overseas_earnings()

tab_news, tab_policy, tab_timeline, tab_overseas, tab_alerts = st.tabs(
    [
        "新闻总览",
        "政策追踪",
        "事件时间线",
        "外盘季报",
        "预警事件",
    ]
)

with tab_news:
    total_news = len(news_df)
    policy_count = int(news_df["政策"].sum()) if not news_df.empty else 0
    high_count = int((news_df["影响"] == "high").sum()) if not news_df.empty else 0
    avg_sentiment = float(news_df["情绪"].mean()) if not news_df.empty else 0.0

    cols = st.columns(4)
    cols[0].metric("新闻数", total_news)
    cols[1].metric("政策新闻", policy_count)
    cols[2].metric("高影响", high_count)
    cols[3].metric("平均情绪", f"{avg_sentiment:+.2f}")

    heatmap = _sector_heatmap(news_df)
    if not heatmap.empty:
        c1, c2 = st.columns([2, 3])
        with c1:
            st.dataframe(heatmap, width="stretch", hide_index=True)
        with c2:
            fig = px.bar(
                heatmap,
                x="行业",
                y="新闻数",
                color="平均情绪",
                color_continuous_scale="RdYlGn",
                range_color=[-1, 1],
                title="行业新闻热度与情绪",
            )
            fig.update_layout(height=340)
            st.plotly_chart(fig, width="stretch")

    st.divider()
    filters = st.columns(3)
    sectors = sorted({sector for items in news_df.get("行业列表", []) for sector in items})
    selected_sector = filters[0].selectbox("行业", ["全部"] + sectors)
    selected_impact = filters[1].selectbox("影响等级", ["全部", "high", "medium", "low"])
    only_policy = filters[2].checkbox("仅政策")

    filtered = news_df.copy()
    if selected_sector != "全部":
        filtered = filtered[filtered["行业"].str.contains(selected_sector, na=False)]
    if selected_impact != "全部":
        filtered = filtered[filtered["影响"] == selected_impact]
    if only_policy:
        filtered = filtered[filtered["政策"]]
    _render_news_cards(filtered.head(30))

with tab_policy:
    st.subheader("政策追踪")
    if news_df.empty:
        render_empty_state("暂无新闻数据")
    else:
        tracker = SectorTracker()
        analyzed = [
            {
                "title": row["标题"],
                "content": row["摘要"],
                "source": row["来源"],
                "sentiment": row["情绪"],
                "impact_level": row["影响"],
                "is_policy": row["政策"],
                "category": "policy" if row["政策"] else row["类别"],
                "related_sectors": row["行业列表"],
                "summary": row["摘要"],
            }
            for _, row in news_df.iterrows()
        ]
        alerts = tracker.track(analyzed)
        summary = pd.DataFrame(tracker.get_sector_summary(alerts))
        if summary.empty:
            render_empty_state("暂无政策追踪数据")
        else:
            summary = summary.rename(
                columns={
                    "sector": "行业",
                    "alert_count": "政策条数",
                    "avg_sentiment": "平均情绪",
                    "top_alert_title": "核心政策",
                    "impact_direction": "方向",
                }
            )
            render_result_table(summary, empty_message="暂无政策追踪数据")

        st.markdown("#### 政策与高影响新闻")
        policy_news = news_df[(news_df["政策"]) | (news_df["影响"] == "high")]
        _render_news_cards(policy_news.head(20))

with tab_timeline:
    st.subheader("事件时间线")
    if news_df.empty:
        render_empty_state("暂无新闻数据")
    else:
        timeline = news_df[(news_df["政策"]) | (news_df["影响"] == "high")].copy()
        if timeline.empty:
            render_empty_state("暂无需要重点跟踪的事件")
        else:
            followups = _load_followups(timeline["id"].tolist())
            if followups.empty:
                timeline["跟踪状态"] = "待跟踪"
                timeline["跟踪备注"] = ""
                timeline["更新时间"] = ""
            else:
                timeline = timeline.merge(
                    followups.rename(
                        columns={
                            "article_id": "id",
                            "status": "跟踪状态",
                            "note": "跟踪备注",
                            "updated_at": "更新时间",
                        }
                    ),
                    on="id",
                    how="left",
                )
                timeline["跟踪状态"] = timeline["跟踪状态"].fillna("待跟踪")
                timeline["跟踪备注"] = timeline["跟踪备注"].fillna("")
                timeline["更新时间"] = timeline["更新时间"].fillna("")

            t1, t2, t3 = st.columns(3)
            t1.metric("待跟踪", int((timeline["跟踪状态"] == "待跟踪").sum()))
            t2.metric("跟踪中", int((timeline["跟踪状态"] == "跟踪中").sum()))
            t3.metric("已收敛", int((timeline["跟踪状态"] == "已收敛").sum()))

            display = timeline[
                [
                    "时间",
                    "标题",
                    "行业",
                    "影响",
                    "情绪",
                    "跟踪状态",
                    "更新时间",
                ]
            ].copy()
            render_result_table(display, empty_message="暂无事件时间线")

            st.markdown("#### 跟踪更新")
            options = {
                f"{row['时间']} | {row['标题']}": row["id"] for _, row in timeline.iterrows()
            }
            selected_label = st.selectbox("选择事件", list(options))
            selected_id = options[selected_label]
            selected_row = timeline[timeline["id"] == selected_id].iloc[0]
            status_options = ["待跟踪", "跟踪中", "已收敛"]
            current_status = selected_row["跟踪状态"]
            selected_status = st.selectbox(
                "跟踪状态",
                status_options,
                index=status_options.index(current_status),
            )
            note = st.text_area("跟踪备注", value=str(selected_row["跟踪备注"]))
            if st.button("保存跟踪状态", type="primary"):
                update_news_event_followup(selected_id, selected_status, note)
                st.success("跟踪状态已保存")
                st.rerun()

with tab_overseas:
    st.subheader("外盘科技龙头季报")
    col1, col2 = st.columns([1, 3])
    if col1.button("从 SEC 拉取并入库", type="primary"):
        task = submit_dashboard_task(
            "外盘季报补采",
            refresh_overseas_earnings,
            task_key="events:overseas_earnings",
            task_type="news",
            tags=["events", "overseas_earnings"],
        )
        st.success(f"已提交后台任务：{task.id}")
    col2.caption("首次使用或数据过旧时可手工拉取；定时任务每周日自动更新。")

    if earnings_df.empty:
        render_empty_state("暂无外盘季报数据。")
    else:
        display = earnings_df.copy()
        for col in ["revenue_usd", "net_income_usd"]:
            if col in display.columns:
                display[col] = display[col].map(_fmt_usd)
        for col in ["revenue_yoy_pct", "net_income_yoy_pct"]:
            if col in display.columns:
                display[col] = display[col].map(_fmt_pct)
        show_cols = [
            col
            for col in [
                "ticker",
                "company_name",
                "fiscal_year",
                "fiscal_period",
                "period_end",
                "revenue_usd",
                "revenue_yoy_pct",
                "net_income_usd",
                "net_income_yoy_pct",
                "eps_diluted",
                "filed_date",
                "impact_level",
            ]
            if col in display.columns
        ]
        st.dataframe(display[show_cols], width="stretch", hide_index=True)

        st.markdown("#### 季报要点")
        for _, row in earnings_df.iterrows():
            title = (
                f"{row.get('company_name', '')} ({row.get('ticker', '')}) "
                f"{row.get('fiscal_year', '')}{row.get('fiscal_period', '')}"
            )
            with st.container(border=True):
                st.markdown(f"**{title}**")
                summary = row.get("summary_zh") or row.get("fact_brief") or ""
                if isinstance(summary, str) and summary:
                    st.write(summary)
                etf_raw = row.get("related_etf_codes", "")
                etfs = _parse_json_list(etf_raw)
                if etfs:
                    st.caption("关联 ETF: " + ", ".join(etfs))

with tab_alerts:
    st.subheader("预警事件")
    if news_df.empty and earnings_df.empty:
        render_empty_state("暂无可用事件数据")
    else:
        a1, a2 = st.columns(2)
        with a1:
            st.markdown("#### 高影响新闻")
            high_news = news_df[news_df["影响"] == "high"] if not news_df.empty else pd.DataFrame()
            _render_news_cards(high_news.head(10))

        with a2:
            st.markdown("#### 情绪极端行业")
            heatmap = _sector_heatmap(news_df)
            extreme = heatmap[
                (heatmap["新闻数"] >= 2)
                & ((heatmap["平均情绪"] >= 0.5) | (heatmap["平均情绪"] <= -0.3))
            ]
            if extreme.empty:
                render_empty_state("暂无情绪极端行业")
            else:
                st.dataframe(extreme, width="stretch", hide_index=True)

            st.markdown("#### 外盘季报影响")
            if earnings_df.empty or "impact_level" not in earnings_df.columns:
                render_empty_state("暂无外盘季报影响评级")
            else:
                impactful = earnings_df[earnings_df["impact_level"].isin(["high", "medium"])]
                if impactful.empty:
                    render_empty_state("暂无中高影响季报")
                else:
                    impact_cols = ["ticker", "company_name", "period_end", "impact_level"]
                    st.dataframe(
                        impactful[impact_cols].head(20),
                        width="stretch",
                        hide_index=True,
                    )
