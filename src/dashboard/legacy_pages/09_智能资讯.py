"""智能资讯页：行业新闻 / 政策追踪 / 基本面分析"""

import json

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from loguru import logger

from src.dashboard.styles import inject_global_styles

inject_global_styles()

st.title("🧠 智能资讯中心")

with st.expander("💡 使用说明", expanded=False):
    st.markdown("""
    **智能资讯中心**整合行业新闻分析、政策追踪和基本面数据。

    - **行业情绪热力图**：统计各行业新闻的情绪倾向
    - **重大新闻流**：展示全部/政策/高影响新闻，带情绪评分
    - **行业政策追踪**：识别重要政策新闻，评估对各行业的影响
    - **指数基本面**：PE/ROE 走势和多指数对比

    ⚠️ **数据获取**：新闻数据需要运行调度器采集。终端执行：
    ```
    python -m src.scheduler.runner
    ```
    或配置 DeepSeek API Key 后启用 LLM 智能分析。
    """)

st.divider()


def _load_news_from_db() -> pd.DataFrame:
    """尝试从 DuckDB 加载新闻，失败则返回 None"""
    try:
        from src.data.storage import StorageEngine

        storage = StorageEngine()
        df = storage.get_news_articles(limit=100)
        if not df.empty:
            return df
    except Exception as e:
        import logging

        logging.getLogger(__name__).debug(f"加载新闻数据失败（降级为示例）: {e}")
    return pd.DataFrame()


def _get_storage_for_fund():
    from src.data.storage import StorageEngine

    return StorageEngine()


def _load_fundamental_snapshot() -> pd.DataFrame:
    """尝试加载基本面对比数据"""
    try:
        from src.analysis.fundamental import FundamentalAnalyzer

        analyzer = FundamentalAnalyzer()
        indices = ["沪深300", "中证500", "创业板指", "中证红利", "上证50"]
        return analyzer.compare_fundamentals(indices)
    except Exception as e:
        logger.debug(f"基本面数据加载失败: {e}")
        return pd.DataFrame()


def _db_to_display(db_df: pd.DataFrame) -> pd.DataFrame:
    """将 DuckDB 格式转为显示格式"""
    rows = []
    for _, r in db_df.iterrows():
        sectors = r.get("related_sectors", "[]")
        if isinstance(sectors, str):
            try:
                sectors = json.loads(sectors)
            except (json.JSONDecodeError, TypeError):
                sectors = []
        sector_str = ", ".join(sectors) if sectors else ""

        rows.append(
            {
                "时间": str(r.get("publish_time", "")),
                "标题": r.get("title", ""),
                "摘要": r.get("summary", ""),
                "情绪": float(r.get("sentiment", 0)),
                "影响": r.get("impact_level", "low"),
                "行业": sector_str,
                "来源": r.get("source", ""),
                "政策": bool(r.get("is_policy", False)),
            }
        )
    return pd.DataFrame(rows)


# --- 加载数据 ---
db_news = _load_news_from_db()
if not db_news.empty:
    news_df = _db_to_display(db_news)
    data_source_label = "实时数据"
else:
    news_df = pd.DataFrame()
    data_source_label = "暂无数据（请先运行新闻采集任务）"

st.caption(f"数据来源: {data_source_label}")

# ======================================================================
# 行业热度面板
# ======================================================================
st.subheader("🔥 行业情绪热力图")

SECTORS = ["消费", "医药", "半导体", "新能源", "军工", "金融"]

if not news_df.empty:
    sector_stats = []
    for sector in SECTORS:
        mask = news_df["行业"].str.contains(sector, na=False)
        sub = news_df[mask]
        sector_stats.append(
            {
                "行业": sector,
                "新闻数量": len(sub),
                "平均情绪": round(sub["情绪"].mean(), 3) if len(sub) else 0,
                "重大影响": len(sub[sub["影响"] == "high"]) if len(sub) else 0,
            }
        )
    heatmap_data = pd.DataFrame(sector_stats)
else:
    heatmap_data = pd.DataFrame(
        {
            "行业": SECTORS,
            "新闻数量": [0] * len(SECTORS),
            "平均情绪": [0.0] * len(SECTORS),
            "重大影响": [0] * len(SECTORS),
        }
    )

col_h1, col_h2 = st.columns([2, 3])

with col_h1:
    st.dataframe(
        heatmap_data.style.background_gradient(
            subset=["平均情绪"],
            cmap="RdYlGn",
            vmin=-1,
            vmax=1,
        ),
        width="stretch",
        hide_index=True,
    )

with col_h2:
    fig_heat = px.bar(
        heatmap_data,
        x="行业",
        y="平均情绪",
        color="平均情绪",
        color_continuous_scale="RdYlGn",
        range_color=[-1, 1],
        text=heatmap_data["平均情绪"].apply(lambda x: f"{x:+.2f}"),
    )
    fig_heat.update_layout(title="行业情绪分布", yaxis_range=[-1, 1], height=300, showlegend=False)
    st.plotly_chart(fig_heat, width="stretch")

st.divider()

# ======================================================================
# 重大新闻时间线
# ======================================================================
st.subheader("📰 重大新闻流")

tab_all, tab_policy, tab_high = st.tabs(["全部新闻", "政策动态", "高影响"])


def _render_news_table(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("暂无数据")
        return

    for _, row in df.iterrows():
        sent = row["情绪"]
        icon = "🟢" if sent > 0.3 else ("🔴" if sent < -0.3 else "🟡")
        impact_badge = {"high": "🔺高", "medium": "🔸中", "low": "▫️低"}.get(row["影响"], "")

        with st.container():
            c1, c2 = st.columns([5, 1])
            with c1:
                st.markdown(
                    f"**{icon} {row['标题']}** &nbsp; `{row['行业']}` &nbsp; {impact_badge}"
                )
                st.caption(f"{row['时间']} | {row['来源']} — {row['摘要']}")
            with c2:
                st.metric("情绪", f"{sent:+.2f}")


with tab_all:
    _render_news_table(news_df)

with tab_policy:
    if not news_df.empty and "政策" in news_df.columns:
        _render_news_table(news_df[news_df["政策"] == True])  # noqa: E712
    else:
        st.info("暂无政策动态")

with tab_high:
    if not news_df.empty and "影响" in news_df.columns:
        _render_news_table(news_df[news_df["影响"] == "high"])
    else:
        st.info("暂无高影响新闻")

st.divider()

# ======================================================================
# 行业政策追踪
# ======================================================================
st.subheader("📜 行业政策追踪")

try:
    from src.intelligence.sector_tracker import SectorTracker

    tracker = SectorTracker()
    if not news_df.empty:
        analyzed_for_tracker = []
        for _, row in news_df.iterrows():
            analyzed_for_tracker.append(
                {
                    "title": row["标题"],
                    "content": row.get("摘要", ""),
                    "source": row["来源"],
                    "sentiment": row["情绪"],
                    "impact_level": row["影响"],
                    "is_policy": row["政策"],
                    "category": "policy" if row["政策"] else "finance",
                    "related_sectors": [
                        s.strip() for s in str(row["行业"]).split(",") if s.strip()
                    ],
                    "summary": row.get("摘要", ""),
                }
            )
        alerts = tracker.track(analyzed_for_tracker)
        policy_rows = tracker.get_sector_summary(alerts)
        if policy_rows:
            policy_summary = pd.DataFrame(policy_rows).rename(
                columns={
                    "sector": "行业",
                    "alert_count": "政策条数",
                    "avg_sentiment": "平均情绪",
                    "impact_direction": "方向",
                    "top_alert_title": "核心政策",
                }
            )
        else:
            policy_summary = None
    else:
        policy_summary = None
except Exception as e:
    logger.debug(f"政策摘要生成失败: {e}")
    policy_summary = None

if policy_summary is not None and not policy_summary.empty:
    st.dataframe(
        policy_summary.style.background_gradient(
            subset=["平均情绪"],
            cmap="RdYlGn",
            vmin=-1,
            vmax=1,
        ),
        width="stretch",
        hide_index=True,
    )
else:
    st.info("暂无政策追踪数据，请先运行新闻采集任务")

st.divider()

# ======================================================================
# 基本面变化趋势
# ======================================================================
st.subheader("📊 指数基本面变化")

indices = ["沪深300", "中证500", "创业板指", "中证红利"]
selected_idx = st.selectbox("选择指数", indices)

fund_from_db = pd.DataFrame()
try:
    from src.data.storage import StorageEngine

    storage = StorageEngine()
    fund_from_db = storage.get_fundamental_data(selected_idx)
except Exception as e:
    logger.debug(f"基本面数据库查询失败: {e}")
    fund_from_db = pd.DataFrame()

if not fund_from_db.empty and "pe" in fund_from_db.columns:
    fund_df = fund_from_db.copy()
    fund_df["日期"] = pd.to_datetime(fund_df["trade_date"])
    fund_df["PE"] = fund_df["pe"]
    fund_df["PB"] = fund_df["pb"]
    if "roe" in fund_df.columns:
        fund_df["ROE(推算)"] = fund_df["roe"]
    else:
        fund_df["ROE(推算)"] = fund_df["pb"] / fund_df["pe"]
else:
    try:
        storage = _get_storage_for_fund()
        val_df = storage.get_index_valuation(selected_idx)
        if not val_df.empty and "pe" in val_df.columns:
            fund_df = val_df.copy()
            fund_df["日期"] = pd.to_datetime(fund_df["trade_date"])
            fund_df["PE"] = fund_df["pe"]
            fund_df["PB"] = fund_df["pb"]
            fund_df["ROE(推算)"] = fund_df.apply(
                lambda r: r["pb"] / r["pe"] * 100 if r.get("pe") and r["pe"] > 0 else 0, axis=1
            )
        else:
            fund_df = pd.DataFrame()
    except Exception as e:
        logger.debug(f"基本面 DataFrame 处理失败: {e}")
        fund_df = pd.DataFrame()

if not fund_df.empty and "日期" in fund_df.columns and "PE" in fund_df.columns:
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        fig_pe = go.Figure()
        fig_pe.add_trace(
            go.Scatter(
                x=fund_df["日期"],
                y=fund_df["PE"],
                mode="lines",
                name="PE",
                line=dict(color="#1f77b4"),
            )
        )
        fig_pe.update_layout(title=f"{selected_idx} PE 走势", height=300)
        st.plotly_chart(fig_pe, width="stretch")

    with col_f2:
        fig_roe = go.Figure()
        fig_roe.add_trace(
            go.Scatter(
                x=fund_df["日期"],
                y=fund_df["ROE(推算)"],
                mode="lines",
                name="ROE",
                line=dict(color="#2ca02c"),
            )
        )
        fig_roe.update_layout(title=f"{selected_idx} ROE 推算走势", height=300)
        st.plotly_chart(fig_roe, width="stretch")
else:
    st.info(f"暂无 {selected_idx} 的基本面趋势数据")

# 基本面快照对比
st.markdown("#### 多指数基本面对比")

compare_live = _load_fundamental_snapshot()
if not compare_live.empty:
    display_cols = {
        "index_name": "指数",
        "pe": "PE",
        "pb": "PB",
        "dividend_yield": "股息率",
        "roe_trend": "ROE趋势",
        "pe_change_1y": "PE年变化(%)",
    }
    available = [c for c in display_cols if c in compare_live.columns]
    compare_display = compare_live[available].rename(columns=display_cols)
    st.dataframe(compare_display, width="stretch", hide_index=True)
else:
    try:
        storage_cmp = _get_storage_for_fund()
        cmp_rows = []
        for idx_name in ["沪深300", "中证500", "创业板指", "中证红利", "上证50"]:
            val = storage_cmp.get_index_valuation(idx_name)
            if not val.empty:
                latest = val.iloc[-1]
                pe = latest.get("pe")
                pb = latest.get("pb")
                dy = latest.get("dividend_yield")
                cmp_rows.append(
                    {
                        "指数": idx_name,
                        "PE": f"{pe:.2f}" if pe else "--",
                        "PB": f"{pb:.2f}" if pb else "--",
                        "股息率": f"{dy:.2f}%" if dy else "--",
                    }
                )
        if cmp_rows:
            st.dataframe(pd.DataFrame(cmp_rows), width="stretch", hide_index=True)
        else:
            st.info("暂无指数估值数据")
    except Exception as e:
        logger.debug(f"指数估值对比失败: {e}")
        st.info("暂无指数估值数据")

st.divider()

# ======================================================================
# 综合预警信号
# ======================================================================
st.subheader("⚠️ 智能预警")

col_w1, col_w2, col_w3 = st.columns(3)

with col_w1:
    st.markdown("**基本面改善行业**")
    if not compare_live.empty and "roe_trend" in compare_live.columns:
        improving = compare_live[compare_live["roe_trend"] == "改善"]
        for _, r in improving.iterrows():
            st.success(f"{r['index_name']}: ROE 连续改善")
        if improving.empty:
            st.info("暂无 ROE 改善信号")
    else:
        st.info("暂无基本面改善信号数据")

with col_w2:
    st.markdown("**新闻情绪极端**")
    if not news_df.empty:
        for sector in SECTORS:
            mask = news_df["行业"].str.contains(sector, na=False)
            sub = news_df[mask]
            if len(sub) >= 2:
                avg = sub["情绪"].mean()
                if avg < -0.3:
                    st.error(f"{sector}: 近期负面新闻集中，平均情绪 {avg:+.2f}")
                elif avg > 0.5:
                    st.success(f"{sector}: 情绪显著转多，平均情绪 {avg:+.2f}")
    else:
        st.info("暂无新闻情绪预警")

with col_w3:
    st.markdown("**政策重大变化**")
    if not news_df.empty and "政策" in news_df.columns and "影响" in news_df.columns:
        policy_news = news_df[(news_df["政策"] == True) & (news_df["影响"] == "high")]  # noqa: E712
        for _, r in policy_news.head(3).iterrows():
            if r["情绪"] > 0.3:
                st.success(f"{r['行业']}: {r['标题'][:20]}...")
            elif r["情绪"] < -0.3:
                st.error(f"{r['行业']}: {r['标题'][:20]}...")
            else:
                st.warning(f"{r['行业']}: {r['标题'][:20]}...")
    else:
        st.info("暂无政策变化预警")

if news_df.empty:
    st.caption("* 当前暂无新闻数据，请运行 `python -m src.scheduler.runner` 或手动调用新闻采集")
