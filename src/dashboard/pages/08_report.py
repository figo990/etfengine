"""报告中心页"""

import streamlit as st
from datetime import date



st.title("📑 报告中心")
st.divider()

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
        - 市场估值快照（主要宽基PE百分位）
        - ETF区间涨跌幅表现
        - 股债性价比 & 市场情绪
        - 本期策略信号汇总
        - 组合持仓状态与偏离
        - 再平衡建议
        """)

    if st.button("生成报告", type="primary"):
        with st.spinner("报告生成中..."):
            st.success("报告生成完成!")
            st.divider()

            st.markdown(f"""
# ETFEngine {report_type}

**报告日期**: {report_date}

## 市场概览
- 沪深300 PE百分位: 45.2% (适中)
- 中证红利 PE百分位: 25.0% (低估)
- 股债性价比(ERP): 3.12% (偏多)
- 偏股基金3年滚动收益: 2.5% (正常)

## 本期信号
- 沪深300: 均线偏离定投 ¥1,000
- 中证红利: 低估加码定投 ¥1,500
- 大小盘轮动: 持有大盘

## 组合状态
- 总市值: ¥108,350
- 最大偏离: 中证红利 +2.1%
- 建议操作: 暂无需再平衡

---

> 本报告由 ETFEngine 自动生成，仅供研究参考，不构成投资建议。
            """)


with tab2:
    st.subheader("历史报告")

    reports = [
        {"日期": "2026-05-04", "类型": "周报", "文件": "weekly_2026-05-04.md"},
        {"日期": "2026-04-27", "类型": "周报", "文件": "weekly_2026-04-27.md"},
        {"日期": "2026-04-30", "类型": "月报", "文件": "monthly_202604.md"},
        {"日期": "2026-04-20", "类型": "周报", "文件": "weekly_2026-04-20.md"},
    ]

    for r in reports:
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            st.text(f"📄 {r['文件']}")
        with col2:
            st.text(f"{r['类型']} | {r['日期']}")
        with col3:
            st.button("查看", key=f"view_{r['文件']}")


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
