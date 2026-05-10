"""智能资讯页：行业新闻 / 政策追踪 / 基本面分析"""

import streamlit as st
from src.dashboard.styles import inject_global_styles
inject_global_styles()

import json
from datetime import date, timedelta

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.title("🧠 智能资讯中心")
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


def _load_fundamental_snapshot() -> pd.DataFrame:
    """尝试加载基本面对比数据"""
    try:
        from src.analysis.fundamental import FundamentalAnalyzer
        analyzer = FundamentalAnalyzer()
        indices = ["沪深300", "中证500", "创业板指", "中证红利", "上证50"]
        return analyzer.compare_fundamentals(indices)
    except Exception:
        return pd.DataFrame()


def _get_mock_news() -> list[dict]:
    return [
        {
            "时间": "2025-05-10 15:30", "标题": "国务院发布促消费二十条措施",
            "摘要": "涵盖汽车、家电、餐饮等多领域，鼓励以旧换新",
            "情绪": 0.8, "影响": "high", "行业": "消费", "来源": "cctv", "政策": True,
        },
        {
            "时间": "2025-05-10 14:20", "标题": "医保局推进DRG/DIP支付改革",
            "摘要": "全面推行按病种付费，对创新药企影响有限",
            "情绪": -0.3, "影响": "medium", "行业": "医药", "来源": "eastmoney", "政策": True,
        },
        {
            "时间": "2025-05-10 11:00", "标题": "华为发布新一代AI芯片",
            "摘要": "算力提升50%，国产替代加速",
            "情绪": 0.7, "影响": "high", "行业": "半导体", "来源": "cls", "政策": False,
        },
        {
            "时间": "2025-05-10 10:15", "标题": "欧洲光伏反补贴调查终裁落地",
            "摘要": "税率低于预期，市场情绪修复",
            "情绪": 0.4, "影响": "medium", "行业": "新能源", "来源": "eastmoney", "政策": False,
        },
        {
            "时间": "2025-05-09 20:30", "标题": "央行下调MLF利率10个基点",
            "摘要": "宽松信号明确，利好权益资产",
            "情绪": 0.6, "影响": "high", "行业": "金融", "来源": "cctv", "政策": True,
        },
        {
            "时间": "2025-05-09 16:00", "标题": "某军工集团获大额海外订单",
            "摘要": "合同金额超百亿，军贸出口放量",
            "情绪": 0.5, "影响": "medium", "行业": "军工", "来源": "cls", "政策": False,
        },
    ]


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

        rows.append({
            "时间": str(r.get("publish_time", "")),
            "标题": r.get("title", ""),
            "摘要": r.get("summary", ""),
            "情绪": float(r.get("sentiment", 0)),
            "影响": r.get("impact_level", "low"),
            "行业": sector_str,
            "来源": r.get("source", ""),
            "政策": bool(r.get("is_policy", False)),
        })
    return pd.DataFrame(rows)


# --- 加载数据 ---
db_news = _load_news_from_db()
if not db_news.empty:
    news_df = _db_to_display(db_news)
    data_source_label = "实时数据"
else:
    news_df = pd.DataFrame(_get_mock_news())
    data_source_label = "示例数据"

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
        sector_stats.append({
            "行业": sector,
            "新闻数量": len(sub),
            "平均情绪": round(sub["情绪"].mean(), 3) if len(sub) else 0,
            "重大影响": len(sub[sub["影响"] == "high"]) if len(sub) else 0,
        })
    heatmap_data = pd.DataFrame(sector_stats)
else:
    np.random.seed(42)
    heatmap_data = pd.DataFrame({
        "行业": SECTORS,
        "新闻数量": np.random.randint(5, 50, size=len(SECTORS)),
        "平均情绪": np.round(np.random.uniform(-0.5, 0.8, size=len(SECTORS)), 3),
        "重大影响": np.random.randint(0, 5, size=len(SECTORS)),
    })

col_h1, col_h2 = st.columns([2, 3])

with col_h1:
    st.dataframe(
        heatmap_data.style.background_gradient(
            subset=["平均情绪"], cmap="RdYlGn", vmin=-1, vmax=1,
        ),
        use_container_width=True,
        hide_index=True,
    )

with col_h2:
    fig_heat = px.bar(
        heatmap_data, x="行业", y="平均情绪",
        color="平均情绪", color_continuous_scale="RdYlGn", range_color=[-1, 1],
        text=heatmap_data["平均情绪"].apply(lambda x: f"{x:+.2f}"),
    )
    fig_heat.update_layout(title="行业情绪分布", yaxis_range=[-1, 1], height=300, showlegend=False)
    st.plotly_chart(fig_heat, use_container_width=True)

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
    _render_news_table(news_df[news_df["政策"] == True])  # noqa: E712

with tab_high:
    _render_news_table(news_df[news_df["影响"] == "high"])

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
            analyzed_for_tracker.append({
                "title": row["标题"],
                "content": row.get("摘要", ""),
                "source": row["来源"],
                "sentiment": row["情绪"],
                "impact_level": row["影响"],
                "is_policy": row["政策"],
                "category": "policy" if row["政策"] else "finance",
                "related_sectors": [s.strip() for s in str(row["行业"]).split(",") if s.strip()],
                "summary": row.get("摘要", ""),
            })
        alerts = tracker.track(analyzed_for_tracker)
        policy_rows = tracker.get_sector_summary(alerts)
        if policy_rows:
            policy_summary = pd.DataFrame(policy_rows).rename(columns={
                "sector": "行业", "alert_count": "政策条数",
                "avg_sentiment": "平均情绪", "impact_direction": "方向",
                "top_alert_title": "核心政策",
            })
        else:
            policy_summary = None
    else:
        policy_summary = None
except Exception:
    policy_summary = None

if policy_summary is not None and not policy_summary.empty:
    st.dataframe(
        policy_summary.style.background_gradient(
            subset=["平均情绪"], cmap="RdYlGn", vmin=-1, vmax=1,
        ),
        use_container_width=True,
        hide_index=True,
    )
else:
    fallback_policy = pd.DataFrame({
        "行业": ["消费", "医药", "金融", "半导体", "新能源"],
        "政策条数": [3, 2, 2, 1, 1],
        "平均情绪": [0.65, -0.15, 0.45, 0.30, 0.20],
        "方向": ["利多", "中性偏空", "利多", "利多", "中性偏多"],
        "核心政策": ["促消费二十条", "DRG支付改革", "MLF降息10bp", "芯片自主可控政策", "光伏反补贴终裁"],
    })
    st.dataframe(
        fallback_policy.style.background_gradient(
            subset=["平均情绪"], cmap="RdYlGn", vmin=-1, vmax=1,
        ),
        use_container_width=True,
        hide_index=True,
    )

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
except Exception:
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
    dates = pd.date_range(end=date.today(), periods=60, freq="W")
    np.random.seed(hash(selected_idx) % 100)
    fund_df = pd.DataFrame({
        "日期": dates,
        "PE": np.cumsum(np.random.randn(60) * 0.3) + 15,
        "PB": np.cumsum(np.random.randn(60) * 0.05) + 1.5,
        "ROE(推算)": np.cumsum(np.random.randn(60) * 0.2) + 12,
    })

col_f1, col_f2 = st.columns(2)

with col_f1:
    fig_pe = go.Figure()
    fig_pe.add_trace(go.Scatter(
        x=fund_df["日期"], y=fund_df["PE"],
        mode="lines", name="PE", line=dict(color="#1f77b4"),
    ))
    fig_pe.update_layout(title=f"{selected_idx} PE 走势", height=300)
    st.plotly_chart(fig_pe, use_container_width=True)

with col_f2:
    fig_roe = go.Figure()
    fig_roe.add_trace(go.Scatter(
        x=fund_df["日期"], y=fund_df["ROE(推算)"],
        mode="lines", name="ROE", line=dict(color="#2ca02c"),
    ))
    fig_roe.update_layout(title=f"{selected_idx} ROE 推算走势", height=300)
    st.plotly_chart(fig_roe, use_container_width=True)

# 基本面快照对比
st.markdown("#### 多指数基本面对比")

compare_live = _load_fundamental_snapshot()
if not compare_live.empty:
    display_cols = {
        "index_name": "指数", "pe": "PE", "pb": "PB",
        "dividend_yield": "股息率", "roe_trend": "ROE趋势",
        "pe_change_1y": "PE年变化(%)",
    }
    available = [c for c in display_cols if c in compare_live.columns]
    compare_display = compare_live[available].rename(columns=display_cols)
    st.dataframe(compare_display, use_container_width=True, hide_index=True)
else:
    compare_df = pd.DataFrame({
        "指数": ["沪深300", "中证500", "创业板指", "中证红利", "上证50"],
        "PE": [12.5, 22.1, 30.5, 6.8, 10.2],
        "PB": [1.3, 1.8, 3.2, 0.7, 1.1],
        "股息率": ["3.0%", "1.5%", "0.6%", "5.2%", "3.8%"],
        "ROE趋势": ["平稳", "改善", "恶化", "平稳", "改善"],
        "PE年变化": ["-5.2%", "+3.1%", "-12.3%", "+1.8%", "-3.5%"],
    })
    st.dataframe(compare_df, use_container_width=True, hide_index=True)

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
        st.success("中证500: ROE 连续改善，PE 百分位 55%")
        st.success("上证50: 股息率提升至 3.8%")

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
        st.error("医药: 近期政策偏空，连续3条负面新闻")
        st.success("消费: 促消费政策密集出台，情绪显著转多")

with col_w3:
    st.markdown("**政策重大变化**")
    if not news_df.empty:
        policy_news = news_df[(news_df["政策"] == True) & (news_df["影响"] == "high")]  # noqa: E712
        for _, r in policy_news.head(3).iterrows():
            if r["情绪"] > 0.3:
                st.success(f"{r['行业']}: {r['标题'][:20]}...")
            elif r["情绪"] < -0.3:
                st.error(f"{r['行业']}: {r['标题'][:20]}...")
            else:
                st.warning(f"{r['行业']}: {r['标题'][:20]}...")
    else:
        st.warning("金融: MLF降息，关注后续LPR调整")
        st.info("半导体: 自主可控政策持续加码")

if data_source_label == "示例数据":
    st.caption("* 当前展示为示例数据，接入实时数据后将自动更新")
