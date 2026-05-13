"""外盘科技龙头季报：SEC 结构化数据 + 中文解读"""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st
from loguru import logger

from src.dashboard.styles import inject_global_styles

inject_global_styles()

st.title("🌐 外盘科技龙头季报")

with st.expander("💡 使用说明", expanded=False):
    st.markdown("""
    本页展示 **美股科技龙头** 最近财季的 **SEC EDGAR 结构化季报指标**（营收、净利润、稀释 EPS 等）及 **同比变化**，
    并给出面向跨境 ETF 的中文要点/解读（可选 LLM）。

    **数据如何更新**
    - 推荐：每周运行 `python scripts/update_overseas_earnings.py`，或依赖调度器中的「外盘科技龙头季报」周任务。
    - 首次使用若表为空，可点击下方 **「从 SEC 拉取并入库」**。

    **合规与网络**
    - SEC 要求请求携带合规 **User-Agent**（含联系信息）。请在 `config/overseas_earnings.yaml` 中修改 `sec_user_agent`，
      或设置环境变量 `SEC_EDGAR_USER_AGENT`。
    - **LLM 解读**（可选）：与智能资讯共用 `DEEPSEEK_API_KEY`；若未配置，将仅显示规则生成的中文事实摘要。

    **免责声明**：数据来自 SEC 公开接口，仅供研究，不构成投资建议。
    """)

st.divider()

col_a, col_b = st.columns([1, 2])
with col_a:
    do_fetch = st.button("从 SEC 拉取并入库", type="primary")
with col_b:
    st.caption("拉取全部 watchlist 约需数十秒；请避免短时间内重复点击。")

if do_fetch:
    with st.spinner("正在请求 SEC 并写入 DuckDB …"):
        try:
            from src.intelligence.overseas_earnings_monitor import OverseasEarningsMonitor

            r = OverseasEarningsMonitor().run_cycle()
            st.success(f"更新完成: {r}")
        except Exception as e:
            logger.exception("外盘季报更新失败")
            st.error(f"更新失败: {e}")

st.divider()

try:
    from src.data.storage import StorageEngine

    storage = StorageEngine()
    try:
        storage.init_schema()
        dfm = storage.get_overseas_earnings_metrics(limit=5000)
        dfa = storage.get_overseas_earnings_analysis(limit=500)
    finally:
        storage.close()
except Exception as e:
    logger.warning(f"读取外盘季报表失败: {e}")
    dfm = pd.DataFrame()
    dfa = pd.DataFrame()

if dfm.empty:
    st.info("暂无数据。请先运行 `python scripts/update_overseas_earnings.py` 或点击上方按钮。")
    st.stop()

dfm = dfm.sort_values("period_end")
latest_idx = dfm.groupby("ticker")["period_end"].idxmax()
latest = dfm.loc[latest_idx].copy()

if not dfa.empty:
    dfa = dfa.sort_values("analyzed_at", ascending=False)
    dfa_latest = dfa.groupby("ticker").first().reset_index()
    merged = latest.merge(
        dfa_latest,
        on=["ticker", "period_end"],
        how="left",
        suffixes=("", "_a"),
    )
else:
    merged = latest.copy()
    merged["summary_zh"] = None
    merged["sentiment"] = None
    merged["impact_level"] = None
    merged["related_etf_codes"] = None
    merged["fact_brief"] = None

merged = merged.sort_values("ticker")

st.subheader("最新财季一览")
_disp = merged.copy()
for col in ("revenue_usd", "net_income_usd"):
    if col in _disp.columns:
        _disp[col] = _disp[col].apply(
            lambda x: f"{x/1e8:.2f}亿USD" if pd.notna(x) else "—"
        )
if "eps_diluted" in _disp.columns:
    _disp["eps_diluted"] = _disp["eps_diluted"].apply(
        lambda x: f"{x:.2f}" if pd.notna(x) else "—"
    )
for col in ("revenue_yoy_pct", "net_income_yoy_pct"):
    if col in _disp.columns:
        _disp[col] = _disp[col].apply(
            lambda x: f"{x:+.1f}%" if pd.notna(x) else "—"
        )

show_cols = [
    c for c in [
        "ticker", "company_name", "fiscal_year", "fiscal_period", "period_end",
        "revenue_usd", "revenue_yoy_pct", "net_income_usd", "net_income_yoy_pct",
        "eps_diluted", "filed_date", "form",
    ]
    if c in _disp.columns
]
st.dataframe(_disp[show_cols], use_container_width=True, hide_index=True)

st.subheader("要点与 ETF 映射")
for _, row in merged.iterrows():
    h = f"{row.get('company_name', '')} ({row.get('ticker', '')}) · {row.get('fiscal_year', '')}{row.get('fiscal_period', '')}"
    st.markdown(f"#### {h}")
    summ = row.get("summary_zh") or row.get("fact_brief")
    if summ and isinstance(summ, str):
        st.write(summ)
    etf_raw = row.get("related_etf_codes")
    etf_list: list = []
    if isinstance(etf_raw, str) and etf_raw.strip().startswith("["):
        try:
            etf_list = json.loads(etf_raw)
        except json.JSONDecodeError:
            etf_list = []
    elif isinstance(etf_raw, list):
        etf_list = etf_raw
    if etf_list:
        st.caption("关联 ETF: " + ", ".join(str(x) for x in etf_list))
    st.divider()
