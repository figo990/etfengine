# Dashboard 页面报错巡检记录

巡检时间：2026-05-17

## 巡检范围

本轮使用浏览器自动化逐个访问 8 个一级页面：

- 首页
- 估值与市场
- 策略实验室
- 组合中心
- 产业链研究
- 资讯事件
- 报告中心
- 数据管理

## 问题清单与处理状态

| 问题 | 影响页面 | 根因 | 修复/处理 | 状态 |
| --- | --- | --- | --- | --- |
| `Settings` 缺少 `data_health` 属性 | 多个页面 | 8501 端口由旧 Anaconda Streamlit 进程占用，浏览器访问的不是最新代码 | 停止旧进程，重新启动服务；当前代码已包含 `Settings.data_health` 与配置项 | 已处理 |
| DuckDB 文件锁导致页面读取失败 | 首页、数据管理、策略、组合、产业链、资讯、报告 | Streamlit/后台任务/外部连接可能同时持有写锁 | 页面读取层增加只读失败降级，显示“不可用/暂无数据”而不是崩溃 | 已处理 |
| `st.page_link` 在当前运行环境下兼容性不稳定 | 首页、侧栏入口 | Streamlit 版本或页面路径变化后容易触发导航异常 | 改为稳定的导航提示和原生页面入口 | 已处理 |
| 页面 404 控制台噪声 | 全部页面 | 在子路径页面访问 `_stcore/health` 与 `_stcore/host-config` 时返回 404 | 未影响页面渲染或 Streamlit 异常；后续可通过固定 base path/升级 Streamlit 再复核 | 观察 |
| 页面数据为空时主体偏瘦 | 资讯事件、数据管理部分 tab | 当前本地库缺少新闻、产业链新闻关联等数据 | 已保留空状态提示；后续重点是补齐定时采集和真实数据覆盖 | 待数据补齐 |

## 浏览器巡检结果

| 页面 | Streamlit 异常块 | 关键错误文本 | 主体渲染 |
| --- | ---: | --- | --- |
| 首页 | 0 | 无 | 正常 |
| 估值与市场 | 0 | 无 | 正常 |
| 策略实验室 | 0 | 无 | 正常 |
| 组合中心 | 0 | 无 | 正常 |
| 产业链研究 | 0 | 无 | 正常 |
| 资讯事件 | 0 | 无 | 正常 |
| 报告中心 | 0 | 无 | 正常 |
| 数据管理 | 0 | 无 | 正常 |

截图与页面文本已输出到 `tmp_page_audit/`，用于人工复核页面主体内容。

## 验证命令

```powershell
.\.venv2\Scripts\python.exe -m pytest tests\test_dashboard -q
.\.venv2\Scripts\python.exe -m ruff check src\dashboard tests\test_dashboard --ignore N999
```

验证结果：

- `tests/test_dashboard`：17 passed
- `ruff check src\dashboard tests\test_dashboard --ignore N999`：passed

## 后续建议

- 固化本地启动脚本，避免误用旧 Anaconda Streamlit 进程占用 8501。
- 为浏览器巡检脚本增加 CI/本地一键命令，自动打开全部页面并检查 `stException`。
- 对交互按钮继续做二阶段巡检：数据刷新、报告生成、回测提交、组合保存等按钮需分别验证后台任务落库。
- 补齐本地新闻、产业链新闻关联、外盘季报数据后，再做一次“有数据状态”的视觉和业务校验。
