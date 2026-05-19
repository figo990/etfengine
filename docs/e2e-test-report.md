# ETFEngine 端到端（E2E）测试报告

**执行日期**：2026-05-17  
**环境**：Windows 10，Python 3.12.7（`.venv2`），pytest 9.x，Playwright（Chromium）  
**范围**：全量 `pytest tests/` + Streamlit 实机启动 + `scripts/audit_dashboard_pages.py` 浏览器巡检（可选：`user-playwright` MCP 等价复验）

---

## 1. 测试分层说明

| 层级 | 内容 | 说明 |
| --- | --- | --- |
| A. 单元 / 集成测试 | `pytest tests/` | API（TestClient）、存储、策略、Dashboard 逻辑与 `AppTest` 冒烟等 |
| B. Dashboard 无头冒烟 | `tests/test_dashboard/test_pages_smoke.py` | `streamlit.testing.v1.AppTest` 在无真实库数据路径下跑通 |
| C. 浏览器 E2E（脚本） | `scripts/audit_dashboard_pages.py` | Playwright 访问已启动的 Streamlit，检查 `stException` 与 `BAD_TEXT` |
| D. 浏览器 E2E（MCP） | Cursor `user-playwright` MCP | `browser_navigate` / `browser_wait_for` / `browser_evaluate` 逐页巡检，目标与脚本一致 |

本仓库**未**单独维护 Playwright 的 pytest 插件用例；浏览器巡检以脚本或 MCP 调用执行。

---

## 2. 执行命令（可复现）

### 2.1 全量 Pytest

```powershell
cd E:\code\etfengine
.\.venv2\Scripts\python.exe -m pytest tests/ -v --tb=short
```

`pyproject.toml` 已配置 `addopts = "--assert=plain"`，降低部分 Windows 环境下**收集阶段**与大型依赖同时加载时的内存压力。

### 2.2 浏览器脚本巡检（需本机 Chromium）

```powershell
.\.venv2\Scripts\python.exe -m playwright install chromium

# 终端 1
.\.venv2\Scripts\streamlit.exe run src/dashboard/app.py --server.headless true --server.port 8502

# 终端 2
$env:DASHBOARD_AUDIT_BASE_URL = "http://127.0.0.1:8502"
.\.venv2\Scripts\python.exe scripts/audit_dashboard_pages.py
```

脚本从 `src.dashboard.nav.WORKFLOW_NAV` 生成与侧栏一致的**中文路径**；「产业链研究」使用更长等待与 `inner_text` 超时（见脚本内 `PAGE_WAIT_BUDGETS`）。输出在 `tmp_page_audit/`（已 `.gitignore`）。

### 2.3 MCP 浏览器巡检（IDE）

启动 Streamlit 后，在 Cursor 启用 `user-playwright`，对各页执行导航 → 等待（产业链建议 ≥25s）→ 检查 `stException` 与异常关键词，路径与 §2.2 侧栏名称一致（`urllib.parse.quote(侧栏名)`）。

---

## 3. Pytest 执行结果（本次）

| 指标 | 结果 |
| --- | --- |
| 收集用例数 | **128** |
| 结果 | **128 passed** |
| 耗时（约） | **40.3 s** |

本次未发现失败用例。

---

## 4. 浏览器脚本巡检结果（本次）

| 条件 | 结果 |
| --- | --- |
| Streamlit | `http://127.0.0.1:8502`，`src/dashboard/app.py` |
| 退出码 | **0** |
| 覆盖 | `WORKFLOW_NAV` 展开共 **8** 条：总览、估值与市场、产业链研究、策略实验室、组合中心、资讯事件、报告中心、数据管理 |
| 断言 | 各页 `stException=0`，正文未命中 `BAD_TEXT`（`Traceback` / `AttributeError` / `KeyError` / `更新失败`） |

**本次运行未发现需记入「问题清单」的页面级缺陷**（此前已修复的侧栏 URL 对齐、数据健康缺键、`inner_text` 超时预算等不再单独列出）。

---

## 5. 问题清单（未闭环 / 风险与流程）

以下条目均在 **2026-05-17** 对照本仓库代码与目录结构做过核对：它们**不是**「当前 pytest / 脚本巡检已失败」的缺陷单，而是**仍可能成立的风险或工程缺口**；文中区分「已核实事实」与「历史/边界现象」。

---

### P1 — DuckDB 在单测与临时库上的内存压力（环境 / 可观测风险）

#### 核实结论

| 项 | 结论 |
| --- | --- |
| 当前默认 CI 是否失败？ | **无法从本仓库验证**：根目录**无** `.github/`，无内置流水线日志。 |
| 当前本机全量 pytest | 文档 §3 记录为 **128 passed**；**未在本次**复现 OOM。 |
| 代码上是否存在 OOM 诱因？ | **是**：`StorageEngine` 使用 `duckdb.connect(self._db_path)`（`src/data/storage.py`），**未**设置 `PRAGMA memory_limit` 等；单测在 `tmp_path` 下创建真实 DuckDB 文件并 **批量 `upsert`**。 |

#### 问题说明（便于修复）

1. **机理**：DuckDB 在 Windows 等环境下会按可用内存积极分配；多个用例连续打开临时库并 **批量 `upsert`** 时，在**物理内存偏小或并行度过高**时可能抛出 `_duckdb.OutOfMemoryException`。该风险与当前代码路径**相容**（无 `memory_limit`、存在大窗口写入用例）；**本仓库未提供**用于稳定复现 OOM 的专项脚本或 issue 链接。  
2. **高风险用例（相对更重）**（需改测试或加内存策略时优先看）：  
   - `tests/test_dashboard/test_report_builder.py::test_generate_report_includes_integrated_sections`：约 **80** 个交易日 ETF 日线 + 多表 `upsert`。  
   - `tests/test_intelligence/test_industry_chain_analyzer.py`：`upsert_company_daily` 等同样约 **80** 日窗口 + 基本面/新闻等组合写入。  
3. **与 pytest 收集 MemoryError 的区别**：`pyproject.toml` 中 `addopts = "--assert=plain"` 针对的是 **Python 收集阶段**与 SciPy 等导入链的 **MemoryError**（见同文件注释），**不是** DuckDB OOM；两者修复手段不同。

#### 修复方向（可任选组合）

1. **产品/存储层**：在 `StorageEngine` 连接后执行可配置的 `PRAGMA memory_limit='...'`（从 `settings` 读取，默认关闭或保守值），并在文档中说明对大数据任务的影响。  
2. **测试层**：对上述「80 日」类 fixture 改为更小窗口（如 20～30 个交易日），在断言目标不变的前提下降低峰值内存。  
3. **运行环境**：CI 机器保证足够 RAM；本地并行跑 pytest 时减少 `-n` worker（若使用 xdist）。  
4. **可观测性**：在 CI 落地后（见 P2）对偶发 OOM 保留失败日志与 `duckdb` 版本号，便于对照 DuckDB 发行说明。

---

### P2 — 仓库内无持续集成（CI），浏览器 E2E 与 pytest 均未自动化

#### 核实结论

| 项 | 结论 |
| --- | --- |
| `.github/` 是否存在？ | **当前仓库快照中不存在**（无 `workflows/*.yml` 等 CI 定义时可据此判断）。 |
| 是否「仅缺浏览器 E2E」？ | **否**：在现有结构下，**连默认的 `pytest` 也未由仓库内配置触发**；文档旧表述「默认流水线未配置 Playwright」范围偏窄，应理解为 **无声明式 CI**。 |

#### 问题说明（便于修复）

1. **影响**：合并前无法自动拦截回归；新成员环境差异大；Playwright 巡检依赖人工执行。  
2. **浏览器 E2E 的额外依赖**：需 `playwright install chromium`、后台启动 `streamlit run ...`、再跑 `scripts/audit_dashboard_pages.py`；适合单独 **optional job** 或 nightly，避免阻塞主 job。

#### 修复方向（建议落地顺序）

1. **新增** `.github/workflows/ci.yml`（或等价系统）：  
   - Job A：checkout → 安装 Python 3.12+ → `pip install -e ".[dev]"`（或项目既定方式）→ `pytest tests/ -q`。  
2. **可选** Job B（`workflow_dispatch` 或 `schedule`）：  
   - 安装 Playwright 浏览器 → 启动 Streamlit（`--server.headless true`）→ `python scripts/audit_dashboard_pages.py`；失败时上传 `tmp_page_audit/`。  
3. **文档**：在 `README.md` 中写清「PR 必过」与「夜间 E2E」分别对应哪个 workflow。

---

### P3 — 页面巡检的误报/漏报与 Streamlit `_stcore` 子路径请求

#### 核实结论

| 子项 | 是否真实存在 | 依据 |
| --- | --- | --- |
| `BAD_TEXT` 仅用字符串包含判断 | **是** | `scripts/audit_dashboard_pages.py` 中 `BAD_TEXT = ["Traceback", ...]`，在 `body` 全文上做 `text in body`。 |
| 子路径下 `_stcore` 404 | **在浏览器侧可观察到**（历史 MCP 巡检） | 当页面 URL 为 `http://host/<多字节路径>/...` 时，部分对 `/_stcore/host-config` 的请求会带**页面前缀**，与仅挂载在根路径的静态资源不一致，控制台报 **404**；**脚本的通过条件未校验控制台**，因此「巡检通过 ≠ 无控制台错误」。 |

#### 问题说明（便于修复）

**3.1 巡检启发式（BAD_TEXT）**

- **漏报**：仅渲染图标/组件内文案、或未进入 `inner_text` 的异常，可能逃过正文扫描。  
- **误报**：资讯、报告等页若展示用户可见正文含「Traceback」「KeyError」等词（例如新闻摘录、技术文章），会被判失败。  
- **修复**：  
  - 将断言改为「`stException` 数量 + 可选：限定在 `main` 区域 selector」；  
  - 或对 `BAD_TEXT` 增加上下文规则（例如仅当同段出现 `File "` 才判失败）。

**3.2 `_stcore` 404**

- **机理**：Streamlit 期望部分静态资源从应用根加载；多页应用使用**非根路径**（如中文 segment）时，浏览器可能请求错误前缀，导致 404。  
- **是否阻断功能**：多数情况下**不阻断**主应用脚本已渲染；以实际 UI 与 `stException` 为准。  
- **修复**：  
  - 升级 Streamlit 并查阅对应版本的 multipage / baseUrlPath 说明；  
  - 或在反向代理层将 `/_stcore/` 统一映射到根；  
  - 或在巡检脚本中增加「控制台无 error」的可选严格模式（注意与无害 404 区分）。

---

## 6. 附录：本次未覆盖项

- **真实外网**：未对 AkShare / SEC EDGAR 等做自动化拉数 E2E。  
- **Uvicorn 长驻**：API 以 `TestClient` 为主，未做长时压测。  
- **多用户 / 登录**：Dashboard 无登录态，未测会话隔离。

---

*复测时请更新「执行日期」与 §3、§4 中的数字。*
