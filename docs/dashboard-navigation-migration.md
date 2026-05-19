# Dashboard 导航架构说明（UX-016）

## 决策

采用 `**st.navigation` 单入口**（`src/dashboard/app.py` → `run_dashboard()`），不再依赖 Streamlit 对 `app.py` 文件名的默认侧栏标签「app」。


| 方案                                                 | 结论                           |
| -------------------------------------------------- | ---------------------------- |
| 保留 `app.py` 作为首页脚本                                 | 侧栏永远显示「app」，不符合产品命名          |
| 仅把首页移到 `pages/01_总览.py` 仍运行 `streamlit run app.py` | 仍会出现「app」+ 子页重复入口            |
| `**st.navigation` 分组 + `st.Page(title=业务名)`**      | **已采用**：侧栏显示「总览 / 估值与市场 / …」 |
| CSS 隐藏默认 multipage 列表                              | 仅作回滚备选，易与 Streamlit 升级冲突     |


## 实现要点

- 首页脚本：`src/dashboard/pages/01_总览.py`
- 入口：`src/dashboard/navigation.py` 的 `build_navigation_pages()` 读取 `WORKFLOW_NAV`
- `configure_dashboard_page()` 在 native 导航模式下不再重复 `set_page_config`
- 自定义「工作流导航」折叠区在 native 导航启用时隐藏，避免与侧栏重复
- 启动命令不变：`streamlit run src/dashboard/app.py`

## 回滚

1. 恢复 `app.py` 为直接 `render_home()` 的旧实现
2. `WORKFLOW_NAV` 将总览改回 `app.py`（不推荐）
3. 删除或停用 `navigation.run_dashboard()`

## 深链与巡检

- 用户书签：`PAGE_URL_BY_LABEL` 仍使用中文路径（如 `/估值与市场`）
- 浏览器巡检：`scripts/audit_dashboard_pages.py` 中「总览」路由为 `/`