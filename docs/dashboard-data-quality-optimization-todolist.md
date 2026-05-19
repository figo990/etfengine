# Dashboard 数据质量优化 TodoList

## P0：本轮执行

- [x] 为 `etf_info` 增加 `updated_at`，让 ETF 基础信息可以纳入新鲜度检查。
- [x] 增加实体覆盖率检查，覆盖 ETF 行情、ETF 基础信息、指数估值、指数基本面、产业链行情、企业财务、企业估值、外盘季报。
- [x] 交易信号按 `strategy_name + etf_code + signal_date` 幂等写入，避免重复生成。
- [x] 清理残留 `st.page_link` 导航，降低 Streamlit 版本兼容风险。
- [x] 增加数据健康与信号幂等测试。
- [x] 清理 `scripts/` 目录 Ruff 遗留问题，保证全仓 Ruff 可通过。
- [x] 为数据管理 API 的健康覆盖率返回与新增任务类型补充测试。
- [x] 新增 `scripts/audit_dashboard_pages.py`，支持一键浏览器巡检 8 个 Streamlit 页面。

## P1：后续增强

- [x] 继续寻找可稳定回溯半年以上的指数估值/基本面历史源；当前先增加历史深度检查，明确标出数据源不足。
- [x] 为新闻源增加历史深度可观测能力，持续增量积累；历史分页源仍作为后续数据源增强项保留。
- [x] 将数据管理页从 legacy 嵌套改为完全原生页面。
- [x] 将浏览器逐页巡检脚本接入本地 `scripts/check_all.ps1 -BrowserAudit` 检查命令。

## P2：工程体验

- [x] 启动脚本增加监听进程环境校验；若 Streamlit 派生到非预期 Python，会输出明确警告。
- [x] 为远程 API 的新增任务类型补充接口级测试。
- [x] 为 Streamlit/巡检运行环境增加 `.venv2` 重建脚本，并把 Playwright 纳入 dev 依赖。
- [x] 为后台任务结果增加索引表，减少大 JSON 单行存储。

## 后续仍需外部数据源增强

- [x] 建立新闻源稳定性登记与历史补采判断规则，见 `docs/data-source-stability-plan.md`。
- [x] 建立指数估值/基本面源稳定性登记，明确当前基本面为过渡派生源。
- [x] 提供 `.venv2` 重建入口：`powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\rebuild_env.ps1 -InstallBrowsers`。
- [x] 如仍需使用 conda，建议另建独立 environment 并禁用 base 自动激活；项目命令统一推荐 `powershell -NoProfile`。

## 新增后续观察项

- [ ] 接入真实可授权的半年以上产业链新闻分页源后，将 `stable_for_backfill` 调整为 true 并实现历史补采。
- [ ] 接入正式指数基本面源后，替换当前由估值序列派生的过渡实现。
