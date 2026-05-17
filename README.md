# ETFEngine - ETF 投资策略研究与管理工具

面向个人/小型团队的 ETF 投资策略研究、回测与管理工具，覆盖定投、网格交易、轮动策略等主流玩法。

## 功能特性

- **多策略支持**：普通定投、估值定投、均线偏离定投、等差/等比/ATR网格、动量轮动、风格轮动、股债轮动，并支持保存方案横向比较
- **数据采集**：AkShare 为主，多源备份，自动日更
- **回测引擎**：支持交易成本（佣金/印花税/滑点）、T+1 规则，参数网格优化
- **估值分析**：PE/PB 百分位、股债性价比、五年之锚、情绪指标
- **基本面分析**：指数盈利增速、ROE 推算、多指数基本面对比
- **智能资讯**：行业新闻采集、LLM 摘要与情绪评分、政策追踪、事件时间线
- **组合管理**：目标配置、偏离再平衡、风险监控
- **可视化 Dashboard**：Streamlit 总览 + 7 个工作流页面（侧栏分组导航）
- **REST API**：FastAPI 后端，支持数据查询与策略回测
- **投资报告**：周报/月报生成（含数据新鲜度、产业链、组合风险与重大新闻）

## 快速开始

```bash
# 1. 创建虚拟环境
python -m venv .venv

# 2. 激活虚拟环境
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

# 3. 安装依赖（含开发工具）
pip install -e ".[dev]"

# 4. 初始化数据（拉取历史数据至本地 DuckDB）
python scripts/init_data.py

# 5. 启动 Dashboard
streamlit run src/dashboard/app.py

# 6. 启动 API（可选）
uvicorn src.api.main:app --reload
```

### 智能资讯功能（可选）

LLM 新闻分析需设置 DeepSeek API Key：

```bash
# Windows
set DEEPSEEK_API_KEY=your_api_key_here

# Linux/macOS
export DEEPSEEK_API_KEY=your_api_key_here
```

不设置 API Key 时系统会自动降级为关键词匹配模式。

## 项目结构

```
etfengine/
├── config/              # 配置文件（YAML）
│   ├── settings.yaml    # 全局设置
│   ├── etf_universe.yaml# ETF 标的池
│   ├── strategies.yaml  # 策略参数
│   ├── portfolio.yaml   # 组合配置
│   ├── intelligence.yaml# 新闻监控 & LLM 配置
│   └── overseas_earnings.yaml  # 美股科技龙头季报 watchlist
├── src/                 # 源代码
│   ├── analysis/        # 估值/基本面分析
│   ├── api/             # FastAPI 后端
│   ├── backtest/        # 回测引擎 & 优化器
│   ├── core/            # 配置管理 & 日志
│   ├── dashboard/       # Streamlit 可视化（总览 + 7 个工作流页）
│   ├── data/            # 数据采集与存储（DuckDB）
│   ├── intelligence/    # LLM 新闻分析 & 行业追踪
│   ├── notify/          # 通知推送（邮件/企微）
│   ├── scheduler/       # 定时任务（APScheduler）
│   ├── signals/         # 信号引擎
│   └── strategies/      # 策略实现（DCA/Grid/Rotation/Portfolio）
├── data/                # 本地数据（DuckDB + 缓存 + 日志 + 报告）
├── tests/               # 单元测试（75+）
├── scripts/             # 脚本（初始化/日更/报告生成）
└── docs/                # 文档
```

## Dashboard 页面


| 页面      | 功能                   |
| ------- | -------------------- |
| 首页 | 市场指标、数据新鲜度、产业链热度与快捷入口 |
| 估值与市场 | 市场概览、指数估值、股债性价比、估值历史 |
| 策略实验室 | 定投、网格、轮动信号、通用回测与参数优化 |
| 组合中心 | 持仓概览、持仓设置、再平衡建议、风险监控 |
| 产业链研究 | 人工智能/机器人/商业航天图谱、企业趋势、重大新闻与横向对比 |
| 资讯事件 | 行业新闻、政策追踪、智能预警、外盘科技龙头季报 |
| 报告中心 | 周报/月报生成、历史报告、推送设置 |
| 数据管理 | 手工更新、定时采集说明、数据健康检查 |


## 技术栈

- **Python 3.12+** / pip
- **数据**：AkShare + SEC EDGAR（外盘季报）+ DuckDB（嵌入式，零配置）
- **后端**：FastAPI + Uvicorn
- **前端**：Streamlit + Plotly
- **分析**：Pandas + NumPy + SciPy
- **调度**：APScheduler + Loguru
- **LLM**：OpenAI SDK（兼容 DeepSeek API）

## 运行测试

```bash
pytest tests/ -v
```

## 数据更新说明

产业链洞察页依赖本地 DuckDB 中的新闻、ETF、指数估值和产业链企业行情数据：

- 首次点击侧边栏“更新产业链企业”会抓取约半年的企业日线历史数据。
- 运行 `python -m src.scheduler.runner` 后，系统会在交易日收盘后自动更新产业链企业行情。
- 新闻监控每小时运行一次，新增新闻入库后会自动刷新产业链/环节/企业关联。
- 产业链企业基本面包含财务指标、估值历史和业绩预告，可在数据管理页手工补采。
- 产业链方向、环节、企业和关键词维护在 `config/industry_chains.yaml`。

## DuckDB 连接

终端只读查看数据库：

```bash
duckdb -readonly data/db/etfengine.duckdb
```

也可以直接用 Python 只读连接：

```bash
python -c "import duckdb; con=duckdb.connect(r'data/db/etfengine.duckdb', read_only=True); print(con.sql('show tables').df())"
```

Dashboard、API 或调度器正在写库时，外部排查优先使用只读连接；如需写入，请先停止其他占用数据库的进程。

## 免责声明

本工具仅用于投资研究和策略回测，不构成任何投资建议。历史回测结果不代表未来收益。投资有风险，入市需谨慎。
