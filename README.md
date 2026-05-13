# ETFEngine - ETF 投资策略研究与管理工具

面向个人/小型团队的 ETF 投资策略研究、回测与管理工具，覆盖定投、网格交易、轮动策略等主流玩法。

## 功能特性

- **多策略支持**：普通定投、估值定投、均线偏离定投、等差/等比/ATR网格、动量轮动、风格轮动、股债轮动
- **数据采集**：AkShare 为主，多源备份，自动日更
- **回测引擎**：支持交易成本（佣金/印花税/滑点）、T+1 规则，参数网格优化
- **估值分析**：PE/PB 百分位、股债性价比、五年之锚、情绪指标
- **基本面分析**：指数盈利增速、ROE 推算、多指数基本面对比
- **智能资讯**：行业新闻采集、LLM 摘要与情绪评分、政策追踪预警
- **组合管理**：目标配置、偏离再平衡、风险监控
- **可视化 Dashboard**：Streamlit 驱动的 11 页交互式看板
- **REST API**：FastAPI 后端，支持数据查询与策略回测
- **自动报告**：周报/月报自动生成（含行业动态与基本面板块）

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
│   ├── dashboard/       # Streamlit 可视化（11 页）
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
| 📊 市场概览 | 指数涨跌、估值快照、市场温度计      |
| 📈 估值看板 | PE/PB 百分位、股债性价比、五年之锚 |
| 💰 定投管理 | 定投信号、计划管理、收益追踪       |
| 🔲 网格交易 | 网格参数设计、回测分析、可视化      |
| 🔄 轮动信号 | 大小盘/风格/股债/行业轮动       |
| 📋 组合管理 | 持仓概览、再平衡建议、风险监控      |
| 🧪 策略回测 | 多策略回测、收益曲线、月度热力图     |
| 📄 投资报告 | 周报/月报自动生成            |
| 🧠 智能资讯 | 行业热力图、新闻流、政策追踪       |
| 🌐 外盘季报 | 美股龙头 SEC 季报指标、同比与中文解读   |


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

## 免责声明

本工具仅用于投资研究和策略回测，不构成任何投资建议。历史回测结果不代表未来收益。投资有风险，入市需谨慎。