"""持仓设置页 — 可视化管理 ETF 持仓配置"""

import streamlit as st

from src.dashboard.services import load_portfolio_config, save_portfolio_config
from src.dashboard.styles import inject_global_styles

inject_global_styles()

st.title("⚙️ 持仓设置")

with st.expander("💡 使用说明", expanded=False):
    st.markdown("""
    本页面用于管理你的 **ETF 持仓组合**配置，修改后会直接保存到 `config/portfolio.yaml`。

    - **添加持仓**：在下方输入 ETF 代码和名称，点击添加
    - **调整权重**：拖动滑块调整各 ETF 的目标配置权重（总和应为 100%）
    - **删除持仓**：勾选要移除的 ETF 后点击删除
    - **修改后**需要运行数据更新来拉取新 ETF 的历史行情
    """)

st.divider()


def _load_config() -> dict:
    return load_portfolio_config()


def _save_config(cfg: dict) -> None:
    save_portfolio_config(cfg)


cfg = _load_config()
portfolio = cfg.get("portfolio", {})
holdings = portfolio.get("holdings", [])

# ─── 基本信息 ───
st.subheader("📋 组合基本信息")
col1, col2 = st.columns(2)
with col1:
    portfolio_name = st.text_input("组合名称", value=portfolio.get("name", "默认ETF组合"))
with col2:
    total_capital = st.number_input(
        "总资金(元)", value=portfolio.get("total_capital", 100000), step=10000, min_value=0
    )

st.divider()

# ─── 当前持仓列表 ───
st.subheader("📊 当前持仓")

if not holdings:
    st.info("暂无持仓，请在下方添加")
else:
    total_weight = sum(h.get("target_weight", 0) for h in holdings)
    if abs(total_weight - 1.0) > 0.01:
        st.warning(f"⚠️ 权重总和为 {total_weight * 100:.1f}%，建议调整为 100%")
    else:
        st.success(f"✅ 权重总和: {total_weight * 100:.1f}%")

    to_delete = []
    updated_holdings = []

    for i, h in enumerate(holdings):
        with st.container():
            cols = st.columns([1.5, 3, 3, 1])
            with cols[0]:
                st.markdown(f"**{h.get('etf', '')}**")
            with cols[1]:
                new_name = st.text_input(
                    "名称", value=h.get("name", ""), key=f"name_{i}", label_visibility="collapsed"
                )
            with cols[2]:
                new_weight = st.slider(
                    f"权重 {h.get('etf', '')}",
                    min_value=0,
                    max_value=100,
                    value=int(h.get("target_weight", 0.1) * 100),
                    key=f"weight_{i}",
                    format="%d%%",
                    label_visibility="collapsed",
                )
            with cols[3]:
                if st.checkbox("删除", key=f"del_{i}", label_visibility="collapsed"):
                    to_delete.append(i)

            updated_holdings.append(
                {
                    "etf": h.get("etf", ""),
                    "name": new_name,
                    "target_weight": round(new_weight / 100, 2),
                }
            )

    # 删除确认
    if to_delete:
        st.warning(f"已勾选 {len(to_delete)} 只 ETF 待删除")
        if st.button("确认删除所选", type="secondary"):
            updated_holdings = [h for i, h in enumerate(updated_holdings) if i not in to_delete]
            portfolio["holdings"] = updated_holdings
            portfolio["name"] = portfolio_name
            portfolio["total_capital"] = total_capital
            cfg["portfolio"] = portfolio
            _save_config(cfg)
            st.success("已删除并保存!")
            st.rerun()

    # 保存权重变更
    if st.button("💾 保存修改", type="primary"):
        portfolio["holdings"] = updated_holdings
        portfolio["name"] = portfolio_name
        portfolio["total_capital"] = total_capital
        cfg["portfolio"] = portfolio
        _save_config(cfg)
        st.success("配置已保存!")
        st.rerun()

st.divider()

# ─── 添加新持仓 ───
st.subheader("➕ 添加新 ETF")

add_col1, add_col2, add_col3 = st.columns([2, 3, 2])
with add_col1:
    new_code = st.text_input("ETF代码", placeholder="如 510300")
with add_col2:
    new_etf_name = st.text_input("ETF名称", placeholder="如 沪深300ETF")
with add_col3:
    new_weight_pct = st.number_input("目标权重(%)", value=10, min_value=1, max_value=100)

if st.button("➕ 添加到组合"):
    if not new_code or not new_etf_name:
        st.error("请填写 ETF 代码和名称")
    elif any(h.get("etf") == new_code for h in holdings):
        st.error(f"ETF {new_code} 已存在于组合中")
    else:
        holdings.append(
            {
                "etf": new_code,
                "name": new_etf_name,
                "target_weight": round(new_weight_pct / 100, 2),
            }
        )
        portfolio["holdings"] = holdings
        portfolio["name"] = portfolio_name
        portfolio["total_capital"] = total_capital
        cfg["portfolio"] = portfolio
        _save_config(cfg)
        st.success(f"已添加 {new_etf_name}({new_code})，权重 {new_weight_pct}%")
        st.balloons()
        st.rerun()

st.divider()

# ─── 均分权重工具 ───
st.subheader("🔧 快捷工具")

col_t1, col_t2 = st.columns(2)

with col_t1:
    if st.button("均分所有权重"):
        if holdings:
            equal_w = round(1.0 / len(holdings), 2)
            remainder = round(1.0 - equal_w * len(holdings), 2)
            for i, h in enumerate(holdings):
                h["target_weight"] = equal_w + (remainder if i == 0 else 0)
            portfolio["holdings"] = holdings
            cfg["portfolio"] = portfolio
            _save_config(cfg)
            st.success(f"已均分权重: 每只 {equal_w * 100:.0f}%")
            st.rerun()

with col_t2:
    if holdings:
        need_data = st.button("🔄 拉取新增ETF数据")
        if need_data:
            st.info("请在终端运行: `python scripts/init_data.py`")
            st.code("python scripts/init_data.py", language="bash")

st.divider()

# ─── 风控参数 ───
st.subheader("🛡️ 风控参数")

rebalance = portfolio.get("rebalance", {})
risk_limits = portfolio.get("risk_limits", {})

rc1, rc2 = st.columns(2)
with rc1:
    trigger = st.selectbox(
        "再平衡触发方式",
        ["drift", "periodic", "both"],
        index=["drift", "periodic", "both"].index(rebalance.get("trigger", "drift")),
    )
    drift_threshold = st.slider(
        "偏离阈值(%)", 1, 20, int(rebalance.get("drift_threshold", 0.05) * 100)
    )
    freq = st.selectbox(
        "定期检查频率",
        ["monthly", "weekly", "quarterly"],
        index=["monthly", "weekly", "quarterly"].index(
            rebalance.get("periodic_frequency", "monthly")
        ),
    )

with rc2:
    max_dd = st.slider(
        "最大回撤预警(%)", 5, 50, int(risk_limits.get("max_drawdown_alert", 0.15) * 100)
    )
    max_pos = st.slider(
        "单ETF最大仓位(%)", 10, 100, int(risk_limits.get("max_single_position", 0.40) * 100)
    )
    min_pos = st.slider(
        "单ETF最小仓位(%)", 1, 30, int(risk_limits.get("min_single_position", 0.05) * 100)
    )

if st.button("💾 保存风控设置"):
    portfolio["rebalance"] = {
        "trigger": trigger,
        "drift_threshold": round(drift_threshold / 100, 2),
        "periodic_frequency": freq,
        "min_trade_amount": rebalance.get("min_trade_amount", 1000),
    }
    portfolio["risk_limits"] = {
        "max_drawdown_alert": round(max_dd / 100, 2),
        "max_single_position": round(max_pos / 100, 2),
        "min_single_position": round(min_pos / 100, 2),
    }
    cfg["portfolio"] = portfolio
    _save_config(cfg)
    st.success("风控参数已保存!")
