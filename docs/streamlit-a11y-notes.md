# Streamlit 可访问性说明（UX-034）

**验证环境**：Streamlit 1.57.0（`.venv2`）  
**范围**：Dashboard 表格、侧栏控件、Tab/Expander 的辅助技术树表现

## 框架限制（应用层不强行改造）


| 组件                        | 现象                                         | 缓解措施                                                 |
| ------------------------- | ------------------------------------------ | ---------------------------------------------------- |
| `st.dataframe` / DataGrid | 读屏对列语义依赖 Canvas，横向滚动时次要列不易感知               | 表前增加 `accessibility_hint` 文案；关键 KPI 用 `st.metric` 摘要 |
| `st.expander`             | 标签含 Material 图标英文（如 `keyboard_arrow_down`） | 接受；升级 Streamlit 时复测                                  |
| 侧栏收起按钮                    | 无中文 aria 名称                                | 接受                                                   |
| `st.number_input` 加减按钮    | 无独立可读名称                                    | 保留可见 label；不改为 text_input 降级                         |
| `st.date_input`           | 单日期场景可能出现「请选择第二日期」辅助文案                     | 报告中心已加业务说明 caption                                   |


## 已落地的应用层改进

- KPI/日期：`format_display_datetime()` 避免时间被拆成多段 StaticText
- 资讯列表：单块 markdown + 分页，减少标题重复节点
- 数据表：`render_result_table(..., accessibility_hint=...)` 提示可横向滚动/导出
- 后台任务：侧栏表格外增加运行中/失败计数摘要

## 验收口径（UX-006）

审计时同时检查：

1. **可见 UI**：截图与正文是否含 Traceback、更新失败等业务错误
2. **辅助技术树**：仅作参考；隐藏 Tab/折叠内容可能仍出现在树中
3. **控制台**：区分可忽略的深度链接 404 与真实错误（见 `audit_dashboard_pages._is_ignorable_console_error`）
4. **用户路径**：侧栏能否以业务名进入各页（native navigation）

## 升级评估清单

升级 Streamlit 小版本前：

- 跑 `scripts/check_all.ps1`（Ruff + pytest）  
- 跑 `scripts/check_all.ps1 -BrowserAudit`（需先启动 Dashboard）  
- 抽查总览 KPI 日期、资讯列表、数据管理任务表