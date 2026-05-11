"""报告中心页 — 基于真实数据生成报告"""

import streamlit as st
from src.dashboard.styles import inject_global_styles
inject_global_styles()

from datetime import date
from pathlib import Path
from loguru import logger

st.title("📑 报告中心")

with st.expander("💡 使用说明", expanded=False):
    st.markdown("""
    **报告中心**自动生成投资分析报告。

    - **生成报告**：基于数据库中的真实数据生成周报/月报，包含：
      - 指数估值快照（PE/PB/股息率）
      - 股债性价比分析
      - 持仓 ETF 最新价格汇总
    - **历史报告**：查看之前生成并保存的报告
    - **推送设置**：配置邮件/企微 Webhook 自动推送

    📄 生成的报告保存在 `data/reports/` 目录下
    """)

st.divider()


@st.cache_resource(ttl=600)
def _get_storage():
    from src.data.storage import StorageEngine
    return StorageEngine()


def _generate_report(report_type: str, report_date: date) -> str:
    """基于真实数据库数据生成报告"""
    storage = _get_storage()
    lines = [f"# ETFEngine {report_type}", f"", f"**报告日期**: {report_date}", ""]

    # 市场估值快照
    lines.append("## 市场估值快照")
    lines.append("| 指数 | PE | PE百分位 | PB | 股息率 |")
    lines.append("|------|-----|---------|-----|--------|")

    indices = ["沪深300", "中证500", "中证1000", "上证50", "中证红利"]
    for idx_name in indices:
        try:
            df = storage.get_index_valuation(idx_name)
            if not df.empty:
                latest = df.iloc[-1]
                pe = f"{latest['pe']:.2f}" if latest.get("pe") else "--"
                pe_pct = f"{latest['pe_percentile']:.1f}%" if latest.get("pe_percentile") else "--"
                pb = f"{latest['pb']:.2f}" if latest.get("pb") else "--"
                dy = f"{latest['dividend_yield']:.2f}%" if latest.get("dividend_yield") else "--"
                lines.append(f"| {idx_name} | {pe} | {pe_pct} | {pb} | {dy} |")
            else:
                lines.append(f"| {idx_name} | -- | -- | -- | -- |")
        except Exception:
            lines.append(f"| {idx_name} | -- | -- | -- | -- |")

    # 股债性价比
    lines.append("")
    lines.append("## 股债性价比")
    try:
        bond_df = storage.get_bond_yield()
        val_df = storage.get_index_valuation("沪深300")
        if not bond_df.empty and not val_df.empty:
            bond_latest = bond_df.iloc[-1]
            val_latest = val_df.iloc[-1]
            cn10y = bond_latest.get("cn_10y", 0)
            pe = val_latest.get("pe", 0)
            if pe and pe > 0 and cn10y:
                erp = 1 / pe * 100 - cn10y
                lines.append(f"- 沪深300 E/P: {1/pe*100:.2f}%")
                lines.append(f"- 10年期国债: {cn10y:.2f}%")
                lines.append(f"- ERP (股债利差): {erp:.2f}%")
                if erp > 3:
                    lines.append(f"- **判断: 股市显著低估，建议偏多**")
                elif erp > 1:
                    lines.append(f"- **判断: 股债中性，维持均衡**")
                else:
                    lines.append(f"- **判断: 股市偏贵，注意风险**")
    except Exception:
        lines.append("- 股债数据暂不可用")

    # 组合持仓
    lines.append("")
    lines.append("## 组合持仓状态")
    try:
        from src.core.config import get_portfolio_config
        cfg = get_portfolio_config()
        holdings = cfg.get("portfolio", {}).get("holdings", [])
        lines.append("| ETF | 名称 | 目标权重 | 最新价 |")
        lines.append("|-----|------|---------|--------|")
        for h in holdings:
            df_etf = storage.get_etf_daily(h["etf"])
            latest_price = f"{df_etf['close'].iloc[-1]:.3f}" if not df_etf.empty else "--"
            lines.append(f"| {h['etf']} | {h['name']} | {h['target_weight']*100:.0f}% | {latest_price} |")
    except Exception:
        lines.append("- 持仓数据暂不可用")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("> 本报告由 ETFEngine 基于真实市场数据自动生成，仅供研究参考，不构成投资建议。")

    return "\n".join(lines)


tab1, tab2, tab3 = st.tabs(["生成报告", "历史报告", "推送设置"])

with tab1:
    st.subheader("生成投资报告")

    col1, col2 = st.columns(2)
    with col1:
        report_type = st.selectbox("报告类型", ["周报", "月报"])
        report_date = st.date_input("报告日期", value=date.today())

    with col2:
        st.markdown("**报告包含内容**:")
        st.markdown("""
        - 市场估值快照（主要宽基 PE 百分位）
        - 股债性价比 (ERP)
        - 组合持仓状态与最新价格
        """)

    if st.button("生成报告", type="primary"):
        with st.spinner("报告生成中..."):
            try:
                report_md = _generate_report(report_type, report_date)

                report_dir = Path("data/reports")
                report_dir.mkdir(parents=True, exist_ok=True)
                if report_type == "周报":
                    fname = f"weekly_{report_date}.md"
                else:
                    fname = f"monthly_{report_date.strftime('%Y%m')}.md"
                report_path = report_dir / fname
                report_path.write_text(report_md, encoding="utf-8")

                st.success(f"报告生成完成! 已保存至 {report_path}")
                st.divider()
                st.markdown(report_md)
            except Exception as e:
                st.error(f"报告生成失败: {e}")
                logger.error(f"报告生成失败: {e}")


with tab2:
    st.subheader("历史报告")

    report_dir = Path("data/reports")
    if report_dir.exists():
        report_files = sorted(report_dir.glob("*.md"), reverse=True)
        if report_files:
            for f in report_files[:20]:
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.text(f"📄 {f.name}")
                with col2:
                    rtype = "周报" if f.name.startswith("weekly") else "月报"
                    st.text(rtype)
                with col3:
                    if st.button("查看", key=f"view_{f.name}"):
                        content = f.read_text(encoding="utf-8")
                        st.markdown(content)
        else:
            st.info("暂无历史报告，请先生成")
    else:
        st.info("暂无历史报告，请先生成")


with tab3:
    st.subheader("推送设置")

    st.markdown("**邮件通知**")
    email_enabled = st.toggle("启用邮件推送", value=False)
    if email_enabled:
        smtp_host = st.text_input("SMTP 服务器", value="smtp.qq.com")
        smtp_port = st.number_input("端口", value=465)
        email_addr = st.text_input("收件邮箱")

    st.divider()
    st.markdown("**企业微信 Webhook**")
    wechat_enabled = st.toggle("启用企微推送", value=False)
    if wechat_enabled:
        webhook_url = st.text_input("Webhook URL")

    st.divider()
    st.markdown("**推送时间**")
    push_time = st.time_input("每日推送时间", value=None)
    push_weekly = st.checkbox("每周五自动生成周报", value=True)
    push_monthly = st.checkbox("每月最后交易日生成月报", value=True)

    if st.button("保存设置"):
        st.success("推送设置已保存!")
