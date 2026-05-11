"""Streamlit Dashboard 主入口"""

import streamlit as st

st.set_page_config(
    page_title="ETFEngine",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": None,
        "Report a bug": None,
        "About": "### ETFEngine v0.1.0\nETF 投资策略管理工具\n\n仅供研究，不构成投资建议",
    },
)

from src.dashboard.styles import inject_global_styles
inject_global_styles()

st.sidebar.markdown(
    """
    <div style="text-align:center; padding: 0.5rem 0 1rem 0;">
        <span style="font-size:2rem;">📊</span><br>
        <span style="font-size:1.2rem; font-weight:700; letter-spacing:1px;">ETFEngine</span><br>
        <span style="font-size:0.75rem; color:#888;">ETF 投资策略管理工具</span>
    </div>
    """,
    unsafe_allow_html=True,
)
st.sidebar.divider()
st.sidebar.caption("v0.1.0 · 仅供研究，不构成投资建议")

# --- 加载真实数据 ---
_metrics = {}
try:
    import pandas as _pd
    from src.data.storage import StorageEngine
    _storage = StorageEngine()
    for _idx in ["沪深300", "中证500", "创业板指", "中证红利"]:
        _df = _storage.get_index_valuation(_idx)
        if not _df.empty:
            _latest = _df.iloc[-1]
            _pe_pct = _latest.get("pe_percentile")
            _div_y = _latest.get("dividend_yield")

            if _pd.isna(_pe_pct) and not _pd.isna(_latest.get("pe")):
                _all_pe = _df["pe"].dropna()
                _pe_pct = (_all_pe < _latest["pe"]).sum() / len(_all_pe) * 100 if len(_all_pe) > 1 else None

            _metrics[_idx] = {
                "pe_pct": round(float(_pe_pct), 1) if _pe_pct and not _pd.isna(_pe_pct) else None,
                "div_yield": round(float(_div_y), 2) if _div_y and not _pd.isna(_div_y) else None,
            }
except Exception:
    pass

# --- 主页内容 ---
st.markdown(
    """
    <h1 style="text-align:center; padding:0.5rem 0 0.3rem 0;">
        📊 ETFEngine
    </h1>
    <p style="text-align:center; color:#666; font-size:1.05rem; margin-bottom:1rem;">
        一站式 ETF 投资策略研究、回测与管理工具
    </p>
    """,
    unsafe_allow_html=True,
)

st.divider()

col1, col2, col3, col4 = st.columns(4)


def _fmt_pct(val):
    if val == "--" or val is None:
        return "--"
    import math
    if isinstance(val, float) and (math.isnan(val) or val == 0):
        return "--"
    return f"{val}%"


with col1:
    st.metric("沪深300 PE百分位", _fmt_pct(_metrics.get("沪深300", {}).get("pe_pct", "--")))
with col2:
    st.metric("中证500 PE百分位", _fmt_pct(_metrics.get("中证500", {}).get("pe_pct", "--")))
with col3:
    st.metric("中证红利 股息率", _fmt_pct(_metrics.get("中证红利", {}).get("div_yield", "--")))
with col4:
    st.metric("创业板 PE百分位", _fmt_pct(_metrics.get("创业板指", {}).get("pe_pct", "--")))

st.divider()

c1, c2, c3 = st.columns(3)

with c1:
    st.markdown(
        """
        #### 📈 估值分析
        - PE/PB 百分位追踪
        - 股债性价比（中美双视角）
        - 五年之锚回归曲线
        - 偏股基金情绪指标
        """
    )

with c2:
    st.markdown(
        """
        #### 💡 策略信号
        - 定投 / 网格 / 轮动信号
        - 新闻情绪预警
        - 政策追踪告警
        - 再平衡提醒
        """
    )

with c3:
    st.markdown(
        """
        #### 🧪 回测与报告
        - 多策略历史回测
        - 参数网格优化
        - 自动周报 / 月报
        - 智能行业资讯
        """
    )

st.divider()

if not _metrics:
    st.info(
        "👈 使用左侧导航栏进入各功能页面。"
        "首次使用请先运行数据初始化：`python scripts/init_data.py`"
    )
else:
    st.success("✅ 数据已就绪，使用左侧导航栏进入各功能页面")
