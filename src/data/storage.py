"""数据存储模块：DuckDB / SQLite 统一存储引擎"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
from loguru import logger

from src.core.config import settings


class StorageEngine:
    """DuckDB 数据存储引擎"""

    def __init__(self, db_path: str | None = None) -> None:
        cfg = settings().database
        if db_path is not None:
            self._db_path = db_path
        else:
            self._db_path = cfg.path
        self._duckdb_memory_limit = getattr(cfg, "duckdb_memory_limit", None)
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn: duckdb.DuckDBPyConnection | None = None

    @property
    def conn(self) -> duckdb.DuckDBPyConnection:
        if self._conn is None:
            self._conn = duckdb.connect(self._db_path)
            self._apply_connection_pragmas()
        return self._conn

    def _apply_connection_pragmas(self) -> None:
        """Apply optional DuckDB connection settings from config."""
        if not self._duckdb_memory_limit:
            return
        escaped_limit = str(self._duckdb_memory_limit).replace("'", "''")
        self._conn.execute(f"PRAGMA memory_limit='{escaped_limit}'")

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def init_schema(self) -> None:
        """初始化数据库表结构"""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS etf_daily (
                code VARCHAR,
                trade_date DATE,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume DOUBLE,
                amount DOUBLE,
                PRIMARY KEY (code, trade_date)
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS index_valuation (
                index_name VARCHAR,
                trade_date DATE,
                pe DOUBLE,
                pb DOUBLE,
                dividend_yield DOUBLE,
                pe_percentile DOUBLE,
                pb_percentile DOUBLE,
                PRIMARY KEY (index_name, trade_date)
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS bond_yield (
                trade_date DATE PRIMARY KEY,
                cn_10y DOUBLE,
                cn_5y DOUBLE,
                cn_1y DOUBLE,
                us_10y DOUBLE
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS etf_info (
                code VARCHAR PRIMARY KEY,
                name VARCHAR,
                index_tracked VARCHAR,
                category VARCHAR,
                fund_size DOUBLE,
                inception_date DATE,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self._ensure_column("etf_info", "updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS trade_signals (
                id INTEGER PRIMARY KEY,
                strategy_name VARCHAR,
                etf_code VARCHAR,
                signal_date DATE,
                direction VARCHAR,
                amount DOUBLE,
                reason VARCHAR,
                confidence DOUBLE,
                generated_at TIMESTAMP
            )
        """)
        self.conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_trade_signals_natural_key
            ON trade_signals(strategy_name, etf_code, signal_date)
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS backtest_scenarios (
                id VARCHAR PRIMARY KEY,
                scenario_name VARCHAR,
                etf_code VARCHAR,
                strategy_name VARCHAR,
                params VARCHAR,
                start_date DATE,
                end_date DATE,
                total_return DOUBLE,
                annual_return DOUBLE,
                max_drawdown DOUBLE,
                sharpe_ratio DOUBLE,
                sortino_ratio DOUBLE,
                calmar_ratio DOUBLE,
                total_trades INTEGER,
                total_invested DOUBLE,
                final_value DOUBLE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS news_articles (
                id VARCHAR PRIMARY KEY,
                title VARCHAR,
                summary VARCHAR,
                content VARCHAR,
                source VARCHAR,
                category VARCHAR,
                publish_time TIMESTAMP,
                url VARCHAR,
                sentiment DOUBLE,
                impact_level VARCHAR,
                is_policy BOOLEAN,
                related_sectors VARCHAR,
                related_etf_codes VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS news_event_followups (
                article_id VARCHAR PRIMARY KEY,
                status VARCHAR,
                note VARCHAR,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS fundamental_data (
                index_name VARCHAR,
                trade_date DATE,
                pe DOUBLE,
                pb DOUBLE,
                dividend_yield DOUBLE,
                roe DOUBLE,
                pe_percentile DOUBLE,
                pb_percentile DOUBLE,
                roe_trend VARCHAR,
                PRIMARY KEY (index_name, trade_date)
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS overseas_earnings_metrics (
                ticker VARCHAR,
                company_name VARCHAR,
                period_end DATE,
                fiscal_year INTEGER,
                fiscal_period VARCHAR,
                form VARCHAR,
                filed_date DATE,
                revenue_usd DOUBLE,
                net_income_usd DOUBLE,
                eps_diluted DOUBLE,
                revenue_yoy_pct DOUBLE,
                net_income_yoy_pct DOUBLE,
                revenue_tag VARCHAR,
                net_income_tag VARCHAR,
                eps_tag VARCHAR,
                updated_at TIMESTAMP,
                PRIMARY KEY (ticker, period_end)
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS overseas_earnings_analysis (
                ticker VARCHAR,
                period_end DATE,
                summary_zh VARCHAR,
                sentiment DOUBLE,
                impact_level VARCHAR,
                related_etf_codes VARCHAR,
                fact_brief VARCHAR,
                analyzed_at TIMESTAMP,
                PRIMARY KEY (ticker, period_end)
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS industry_chain_companies (
                chain_id VARCHAR,
                chain_name VARCHAR,
                segment_id VARCHAR,
                segment_name VARCHAR,
                company_code VARCHAR,
                company_name VARCHAR,
                role VARCHAR,
                keywords VARCHAR,
                aliases VARCHAR DEFAULT '[]',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (chain_id, segment_id, company_code)
            )
        """)
        self._ensure_column("industry_chain_companies", "aliases", "VARCHAR DEFAULT '[]'")

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS company_daily (
                company_code VARCHAR,
                trade_date DATE,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume DOUBLE,
                amount DOUBLE,
                pct_change DOUBLE,
                PRIMARY KEY (company_code, trade_date)
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS company_fundamentals (
                company_code VARCHAR,
                report_date DATE,
                report_type VARCHAR,
                revenue DOUBLE,
                net_profit DOUBLE,
                roe DOUBLE,
                revenue_yoy DOUBLE,
                net_profit_yoy DOUBLE,
                notice_date DATE,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (company_code, report_date)
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS company_valuation (
                company_code VARCHAR,
                trade_date DATE,
                close DOUBLE,
                market_cap DOUBLE,
                pe_ttm DOUBLE,
                pe_static DOUBLE,
                pb DOUBLE,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (company_code, trade_date)
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS company_earnings_forecasts (
                company_code VARCHAR,
                company_name VARCHAR,
                report_period DATE,
                indicator VARCHAR,
                forecast_value DOUBLE,
                change_pct DOUBLE,
                forecast_type VARCHAR,
                reason VARCHAR,
                last_year_value DOUBLE,
                announce_date DATE,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (company_code, report_period, indicator, announce_date)
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS company_news_links (
                article_id VARCHAR,
                chain_id VARCHAR,
                segment_id VARCHAR,
                company_code VARCHAR,
                company_name VARCHAR,
                match_score DOUBLE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (article_id, chain_id, segment_id, company_code)
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS data_update_runs (
                id VARCHAR PRIMARY KEY,
                task_name VARCHAR,
                status VARCHAR,
                started_at TIMESTAMP,
                finished_at TIMESTAMP,
                duration_seconds DOUBLE,
                success_count INTEGER,
                skipped_count INTEGER,
                failed_count INTEGER,
                rows_written INTEGER,
                details VARCHAR,
                error_message VARCHAR
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS dashboard_tasks (
                id VARCHAR PRIMARY KEY,
                name VARCHAR,
                status VARCHAR,
                task_key VARCHAR,
                task_type VARCHAR DEFAULT 'general',
                tags VARCHAR DEFAULT '[]',
                created_at TIMESTAMP,
                started_at TIMESTAMP,
                finished_at TIMESTAMP,
                result VARCHAR,
                error VARCHAR,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS dashboard_task_results (
                task_id VARCHAR,
                result_key VARCHAR,
                result_value VARCHAR,
                value_type VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (task_id, result_key)
            )
        """)
        self._ensure_column("dashboard_tasks", "task_type", "VARCHAR DEFAULT 'general'")
        self._ensure_column("dashboard_tasks", "tags", "VARCHAR DEFAULT '[]'")

        logger.info("数据库表结构初始化完成")

    def _ensure_column(self, table: str, column: str, definition: str) -> None:
        """Add a nullable column for lightweight DuckDB migrations."""
        columns = self.conn.execute(f"PRAGMA table_info('{table}')").fetchdf()
        if column not in columns["name"].tolist():
            self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def upsert_etf_daily(self, df: pd.DataFrame, code: str) -> int:
        """插入/更新 ETF 日线数据"""
        if df.empty:
            return 0

        df = df.copy()
        df["code"] = code

        self.conn.execute("""
            INSERT OR REPLACE INTO etf_daily
            SELECT code, trade_date, open, high, low, close, volume, amount
            FROM df
        """)
        return len(df)

    def upsert_index_valuation(self, df: pd.DataFrame, index_name: str) -> int:
        """插入/更新指数估值"""
        if df.empty:
            return 0

        df = df.copy()
        df["index_name"] = index_name

        for col in ["pe", "pb", "dividend_yield", "pe_percentile", "pb_percentile"]:
            if col not in df.columns:
                df[col] = None

        self.conn.execute("""
            INSERT OR REPLACE INTO index_valuation
            SELECT index_name, trade_date, pe, pb, dividend_yield,
                   pe_percentile, pb_percentile
            FROM df
        """)
        return len(df)

    def upsert_bond_yield(self, df: pd.DataFrame) -> int:
        """插入/更新国债收益率"""
        if df.empty:
            return 0

        df = df.copy()
        for col in ["cn_10y", "cn_5y", "cn_1y", "us_10y"]:
            if col not in df.columns:
                df[col] = None

        self.conn.execute("""
            INSERT OR REPLACE INTO bond_yield
            SELECT trade_date, cn_10y, cn_5y, cn_1y, us_10y
            FROM df
        """)
        return len(df)

    def upsert_etf_info(self, df: pd.DataFrame) -> int:
        """插入/更新 ETF 基础信息."""
        if df.empty:
            return 0

        df = df.copy()
        for col in ["index_tracked", "category", "fund_size", "inception_date"]:
            if col not in df.columns:
                df[col] = None
        df["inception_date"] = pd.to_datetime(df["inception_date"], errors="coerce").dt.date

        self.conn.execute("""
            INSERT OR REPLACE INTO etf_info
            SELECT code, name, index_tracked, category, fund_size, inception_date,
                   CURRENT_TIMESTAMP
            FROM df
        """)
        return len(df)

    def get_etf_info(self, code: str | None = None, limit: int = 5000) -> pd.DataFrame:
        """查询 ETF 基础信息."""
        if code:
            return self.conn.execute("SELECT * FROM etf_info WHERE code = ?", [code]).fetchdf()
        return self.conn.execute(
            "SELECT * FROM etf_info ORDER BY code LIMIT ?",
            [limit],
        ).fetchdf()

    def get_etf_daily(
        self,
        code: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """查询 ETF 日线"""
        query = "SELECT * FROM etf_daily WHERE code = ?"
        params: list = [code]

        if start_date:
            query += " AND trade_date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND trade_date <= ?"
            params.append(end_date)

        query += " ORDER BY trade_date"
        return self.conn.execute(query, params).fetchdf()

    def get_index_valuation(
        self,
        index_name: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """查询指数估值"""
        query = "SELECT * FROM index_valuation WHERE index_name = ?"
        params: list = [index_name]

        if start_date:
            query += " AND trade_date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND trade_date <= ?"
            params.append(end_date)

        query += " ORDER BY trade_date"
        return self.conn.execute(query, params).fetchdf()

    def get_bond_yield(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """查询国债收益率"""
        query = "SELECT * FROM bond_yield WHERE 1=1"
        params: list = []

        if start_date:
            query += " AND trade_date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND trade_date <= ?"
            params.append(end_date)

        query += " ORDER BY trade_date"
        return self.conn.execute(query, params).fetchdf()

    def upsert_news_articles(self, articles: list[dict]) -> int:
        """插入/更新新闻文章"""
        if not articles:
            return 0

        import hashlib
        import json
        from datetime import datetime

        rows = []
        for art in articles:
            title = art.get("title", "")
            article_id = hashlib.md5(title.encode("utf-8")).hexdigest()[:16]
            rows.append(
                {
                    "id": article_id,
                    "title": title,
                    "summary": art.get("summary", ""),
                    "content": art.get("content", "")[:2000],
                    "source": art.get("source", ""),
                    "category": art.get("category", ""),
                    "publish_time": art.get("publish_time"),
                    "url": art.get("url", ""),
                    "sentiment": art.get("sentiment", 0.0),
                    "impact_level": art.get("impact_level", "low"),
                    "is_policy": art.get("is_policy", False),
                    "related_sectors": json.dumps(
                        art.get("related_sectors", []), ensure_ascii=False
                    ),
                    "related_etf_codes": json.dumps(
                        art.get("related_etf_codes", []),
                        ensure_ascii=False,
                    ),
                    "created_at": datetime.now(),
                }
            )

        df = pd.DataFrame(rows)
        self.conn.execute("""
            INSERT OR REPLACE INTO news_articles
            SELECT id, title, summary, content, source, category,
                   publish_time, url, sentiment, impact_level, is_policy,
                   related_sectors, related_etf_codes, created_at
            FROM df
        """)
        return len(df)

    def save_backtest_scenario(self, row: dict) -> str:
        """保存一次回测方案与指标快照."""
        import json
        import uuid
        from datetime import datetime

        scenario_id = row.get("id") or str(uuid.uuid4())
        params = row.get("params", {})
        if isinstance(params, (dict, list)):
            params = json.dumps(params, ensure_ascii=False)
        df = pd.DataFrame(  # noqa: F841 - DuckDB replacement scan reads this variable.
            [
                {
                    "id": scenario_id,
                    "scenario_name": row.get("scenario_name", ""),
                    "etf_code": row.get("etf_code", ""),
                    "strategy_name": row.get("strategy_name", ""),
                    "params": params or "{}",
                    "start_date": row.get("start_date"),
                    "end_date": row.get("end_date"),
                    "total_return": row.get("total_return", 0.0),
                    "annual_return": row.get("annual_return", 0.0),
                    "max_drawdown": row.get("max_drawdown", 0.0),
                    "sharpe_ratio": row.get("sharpe_ratio", 0.0),
                    "sortino_ratio": row.get("sortino_ratio", 0.0),
                    "calmar_ratio": row.get("calmar_ratio", 0.0),
                    "total_trades": row.get("total_trades", 0),
                    "total_invested": row.get("total_invested", 0.0),
                    "final_value": row.get("final_value", 0.0),
                    "created_at": row.get("created_at") or datetime.now(),
                }
            ]
        )
        self.conn.execute("""
            INSERT OR REPLACE INTO backtest_scenarios (
                id, scenario_name, etf_code, strategy_name, params, start_date, end_date,
                total_return, annual_return, max_drawdown, sharpe_ratio, sortino_ratio,
                calmar_ratio, total_trades, total_invested, final_value, created_at
            )
            SELECT id, scenario_name, etf_code, strategy_name, params, start_date, end_date,
                   total_return, annual_return, max_drawdown, sharpe_ratio, sortino_ratio,
                   calmar_ratio, total_trades, total_invested, final_value, created_at
            FROM df
        """)
        return scenario_id

    def get_backtest_scenarios(self, limit: int = 200) -> pd.DataFrame:
        """查询已保存回测方案."""
        return self.conn.execute(
            "SELECT * FROM backtest_scenarios ORDER BY created_at DESC LIMIT ?",
            [limit],
        ).fetchdf()

    def get_news_articles(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        sector: str | None = None,
        limit: int = 100,
    ) -> pd.DataFrame:
        """查询新闻文章"""
        query = "SELECT * FROM news_articles WHERE 1=1"
        params: list = []

        if start_date:
            query += " AND publish_time >= ?"
            params.append(start_date)
        if end_date:
            query += " AND publish_time <= ?"
            params.append(end_date)
        if sector:
            query += " AND related_sectors LIKE ?"
            params.append(f"%{sector}%")

        query += " ORDER BY publish_time DESC LIMIT ?"
        params.append(limit)
        return self.conn.execute(query, params).fetchdf()

    def upsert_news_event_followup(
        self,
        article_id: str,
        status: str,
        note: str = "",
    ) -> int:
        """插入/更新新闻事件跟踪状态."""
        from datetime import datetime

        df = pd.DataFrame(  # noqa: F841 - DuckDB replacement scan reads this variable.
            [
                {
                    "article_id": article_id,
                    "status": status,
                    "note": note,
                    "updated_at": datetime.now(),
                }
            ]
        )
        self.conn.execute("""
            INSERT OR REPLACE INTO news_event_followups
            SELECT article_id, status, note, updated_at
            FROM df
        """)
        return 1

    def get_news_event_followups(
        self,
        article_ids: list[str] | None = None,
    ) -> pd.DataFrame:
        """查询新闻事件跟踪状态."""
        if not article_ids:
            return self.conn.execute(
                "SELECT * FROM news_event_followups ORDER BY updated_at DESC"
            ).fetchdf()
        placeholders = ", ".join(["?"] * len(article_ids))
        query = (
            "SELECT * FROM news_event_followups "
            f"WHERE article_id IN ({placeholders}) ORDER BY updated_at DESC"
        )
        return self.conn.execute(query, article_ids).fetchdf()

    def upsert_fundamental_data(self, df: pd.DataFrame, index_name: str) -> int:
        """插入/更新基本面数据"""
        if df.empty:
            return 0

        df = df.copy()
        df["index_name"] = index_name

        for col in ["pe", "pb", "dividend_yield", "roe", "pe_percentile", "pb_percentile"]:
            if col not in df.columns:
                df[col] = None
        if "roe_trend" not in df.columns:
            df["roe_trend"] = None

        self.conn.execute("""
            INSERT OR REPLACE INTO fundamental_data
            SELECT index_name, trade_date, pe, pb, dividend_yield, roe,
                   pe_percentile, pb_percentile, roe_trend
            FROM df
        """)
        return len(df)

    def get_fundamental_data(
        self,
        index_name: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """查询基本面数据"""
        query = "SELECT * FROM fundamental_data WHERE index_name = ?"
        params: list = [index_name]

        if start_date:
            query += " AND trade_date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND trade_date <= ?"
            params.append(end_date)

        query += " ORDER BY trade_date"
        return self.conn.execute(query, params).fetchdf()

    def upsert_overseas_earnings_metrics(self, rows: list[dict]) -> int:
        """写入/更新美股季报结构化指标（SEC companyfacts）"""
        if not rows:
            return 0

        from datetime import datetime

        df = pd.DataFrame(rows)
        for col in [
            "ticker",
            "company_name",
            "period_end",
            "fiscal_year",
            "fiscal_period",
            "form",
            "filed_date",
            "revenue_usd",
            "net_income_usd",
            "eps_diluted",
            "revenue_yoy_pct",
            "net_income_yoy_pct",
            "revenue_tag",
            "net_income_tag",
            "eps_tag",
            "updated_at",
        ]:
            if col not in df.columns:
                df[col] = None
        if "updated_at" not in df.columns or df["updated_at"].isna().all():
            df["updated_at"] = datetime.now()

        self.conn.execute("""
            INSERT OR REPLACE INTO overseas_earnings_metrics (
                ticker, company_name, period_end, fiscal_year, fiscal_period, form,
                filed_date, revenue_usd, net_income_usd, eps_diluted,
                revenue_yoy_pct, net_income_yoy_pct, revenue_tag, net_income_tag,
                eps_tag, updated_at
            )
            SELECT ticker, company_name, period_end, fiscal_year, fiscal_period, form,
                   filed_date, revenue_usd, net_income_usd, eps_diluted,
                   revenue_yoy_pct, net_income_yoy_pct, revenue_tag, net_income_tag,
                   eps_tag, updated_at
            FROM df
        """)
        return len(df)

    def upsert_overseas_earnings_analysis(self, rows: list[dict]) -> int:
        """写入/更新季报中文解读"""
        if not rows:
            return 0

        import json
        from datetime import datetime

        out = []
        for r in rows:
            etf = r.get("related_etf_codes", [])
            if isinstance(etf, list):
                etf_s = json.dumps(etf, ensure_ascii=False)
            else:
                etf_s = str(etf)
            out.append(
                {
                    "ticker": r.get("ticker"),
                    "period_end": r.get("period_end"),
                    "summary_zh": (r.get("summary_zh") or "")[:2000],
                    "sentiment": r.get("sentiment", 0.0),
                    "impact_level": r.get("impact_level", "low"),
                    "related_etf_codes": etf_s,
                    "fact_brief": (r.get("fact_brief") or "")[:4000],
                    "analyzed_at": r.get("analyzed_at") or datetime.now(),
                }
            )
        df = pd.DataFrame(out)
        self.conn.execute("""
            INSERT OR REPLACE INTO overseas_earnings_analysis (
                ticker, period_end, summary_zh, sentiment, impact_level,
                related_etf_codes, fact_brief, analyzed_at
            )
            SELECT ticker, period_end, summary_zh, sentiment, impact_level,
                   related_etf_codes, fact_brief, analyzed_at
            FROM df
        """)
        return len(df)

    def get_overseas_earnings_metrics(
        self,
        ticker: str | None = None,
        limit: int = 500,
    ) -> pd.DataFrame:
        if ticker:
            q = (
                "SELECT * FROM overseas_earnings_metrics WHERE ticker = ? "
                "ORDER BY period_end DESC LIMIT ?"
            )
            return self.conn.execute(q, [ticker, limit]).fetchdf()
        return self.conn.execute(
            "SELECT * FROM overseas_earnings_metrics ORDER BY period_end DESC LIMIT ?",
            [limit],
        ).fetchdf()

    def get_overseas_earnings_analysis(
        self,
        ticker: str | None = None,
        limit: int = 200,
    ) -> pd.DataFrame:
        if ticker:
            return self.conn.execute(
                "SELECT * FROM overseas_earnings_analysis WHERE ticker = ? "
                "ORDER BY period_end DESC LIMIT ?",
                [ticker, limit],
            ).fetchdf()
        return self.conn.execute(
            "SELECT * FROM overseas_earnings_analysis ORDER BY analyzed_at DESC LIMIT ?",
            [limit],
        ).fetchdf()

    def upsert_industry_chain_companies(self, rows: list[dict]) -> int:
        """写入/更新产业链企业主数据"""
        if not rows:
            return 0

        import json
        from datetime import datetime

        normalized = []
        for row in rows:
            keywords = row.get("keywords", [])
            if isinstance(keywords, list):
                keywords = json.dumps(keywords, ensure_ascii=False)
            aliases = row.get("aliases", [])
            if isinstance(aliases, list):
                aliases = json.dumps(aliases, ensure_ascii=False)
            normalized.append(
                {
                    "chain_id": row.get("chain_id", ""),
                    "chain_name": row.get("chain_name", ""),
                    "segment_id": row.get("segment_id", ""),
                    "segment_name": row.get("segment_name", ""),
                    "company_code": row.get("company_code", ""),
                    "company_name": row.get("company_name", ""),
                    "role": row.get("role", ""),
                    "keywords": keywords or "[]",
                    "aliases": aliases or "[]",
                    "updated_at": row.get("updated_at") or datetime.now(),
                }
            )

        df = pd.DataFrame(normalized)
        self.conn.execute("""
            INSERT OR REPLACE INTO industry_chain_companies (
                chain_id, chain_name, segment_id, segment_name, company_code,
                company_name, role, keywords, aliases, updated_at
            )
            SELECT chain_id, chain_name, segment_id, segment_name, company_code,
                   company_name, role, keywords, aliases, updated_at
            FROM df
        """)
        return len(df)

    def get_industry_chain_companies(self, chain_id: str | None = None) -> pd.DataFrame:
        """查询产业链企业主数据"""
        query = "SELECT * FROM industry_chain_companies WHERE 1=1"
        params: list = []
        if chain_id:
            query += " AND chain_id = ?"
            params.append(chain_id)
        query += " ORDER BY chain_id, segment_id, company_code"
        return self.conn.execute(query, params).fetchdf()

    def upsert_company_daily(self, df: pd.DataFrame, company_code: str) -> int:
        """插入/更新个股日线数据"""
        if df.empty:
            return 0

        df = df.copy()
        df["company_code"] = company_code
        for col in ["open", "high", "low", "close", "volume", "amount", "pct_change"]:
            if col not in df.columns:
                df[col] = None

        self.conn.execute("""
            INSERT OR REPLACE INTO company_daily
            SELECT company_code, trade_date, open, high, low, close,
                   volume, amount, pct_change
            FROM df
        """)
        return len(df)

    def get_company_daily(
        self,
        company_code: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """查询个股日线"""
        query = "SELECT * FROM company_daily WHERE company_code = ?"
        params: list = [company_code]
        if start_date:
            query += " AND trade_date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND trade_date <= ?"
            params.append(end_date)
        query += " ORDER BY trade_date"
        return self.conn.execute(query, params).fetchdf()

    def upsert_company_fundamentals(self, df: pd.DataFrame, company_code: str) -> int:
        """插入/更新个股财务指标."""
        if df.empty:
            return 0

        df = df.copy()
        df["company_code"] = company_code
        for col in [
            "report_type",
            "revenue",
            "net_profit",
            "roe",
            "revenue_yoy",
            "net_profit_yoy",
            "notice_date",
        ]:
            if col not in df.columns:
                df[col] = None

        self.conn.execute("""
            INSERT OR REPLACE INTO company_fundamentals
            SELECT company_code, report_date, report_type, revenue, net_profit, roe,
                   revenue_yoy, net_profit_yoy, notice_date, CURRENT_TIMESTAMP
            FROM df
        """)
        return len(df)

    def get_company_fundamentals(
        self,
        company_code: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """查询个股财务指标."""
        query = "SELECT * FROM company_fundamentals WHERE company_code = ?"
        params: list = [company_code]
        if start_date:
            query += " AND report_date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND report_date <= ?"
            params.append(end_date)
        query += " ORDER BY report_date"
        return self.conn.execute(query, params).fetchdf()

    def upsert_company_valuation(self, df: pd.DataFrame, company_code: str) -> int:
        """插入/更新个股估值历史."""
        if df.empty:
            return 0

        df = df.copy()
        df["company_code"] = company_code
        for col in ["close", "market_cap", "pe_ttm", "pe_static", "pb"]:
            if col not in df.columns:
                df[col] = None

        self.conn.execute("""
            INSERT OR REPLACE INTO company_valuation
            SELECT company_code, trade_date, close, market_cap, pe_ttm, pe_static, pb,
                   CURRENT_TIMESTAMP
            FROM df
        """)
        return len(df)

    def get_company_valuation(
        self,
        company_code: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """查询个股估值历史."""
        query = "SELECT * FROM company_valuation WHERE company_code = ?"
        params: list = [company_code]
        if start_date:
            query += " AND trade_date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND trade_date <= ?"
            params.append(end_date)
        query += " ORDER BY trade_date"
        return self.conn.execute(query, params).fetchdf()

    def upsert_company_earnings_forecasts(self, df: pd.DataFrame) -> int:
        """插入/更新业绩预告."""
        if df.empty:
            return 0

        df = df.copy()
        for col in [
            "company_name",
            "indicator",
            "forecast_value",
            "change_pct",
            "forecast_type",
            "reason",
            "last_year_value",
        ]:
            if col not in df.columns:
                df[col] = None

        self.conn.execute("""
            INSERT OR REPLACE INTO company_earnings_forecasts
            SELECT company_code, company_name, report_period, indicator, forecast_value,
                   change_pct, forecast_type, reason, last_year_value, announce_date,
                   CURRENT_TIMESTAMP
            FROM df
        """)
        return len(df)

    def get_company_earnings_forecasts(
        self,
        company_code: str | None = None,
        report_period: str | None = None,
        limit: int = 500,
    ) -> pd.DataFrame:
        """查询业绩预告."""
        query = "SELECT * FROM company_earnings_forecasts WHERE 1=1"
        params: list = []
        if company_code:
            query += " AND company_code = ?"
            params.append(company_code)
        if report_period:
            query += " AND report_period = ?"
            params.append(report_period)
        query += " ORDER BY announce_date DESC, report_period DESC LIMIT ?"
        params.append(limit)
        return self.conn.execute(query, params).fetchdf()

    def upsert_company_news_links(self, rows: list[dict]) -> int:
        """写入新闻与产业链企业关联"""
        if not rows:
            return 0

        from datetime import datetime

        df = pd.DataFrame(
            [
                {
                    "article_id": r.get("article_id", ""),
                    "chain_id": r.get("chain_id", ""),
                    "segment_id": r.get("segment_id", ""),
                    "company_code": r.get("company_code", ""),
                    "company_name": r.get("company_name", ""),
                    "match_score": r.get("match_score", 1.0),
                    "created_at": r.get("created_at") or datetime.now(),
                }
                for r in rows
            ]
        )
        self.conn.execute("""
            INSERT OR REPLACE INTO company_news_links (
                article_id, chain_id, segment_id, company_code, company_name,
                match_score, created_at
            )
            SELECT article_id, chain_id, segment_id, company_code, company_name,
                   match_score, created_at
            FROM df
        """)
        return len(df)

    def get_industry_chain_news(
        self,
        chain_id: str,
        segment_id: str | None = None,
        company_code: str | None = None,
        limit: int = 100,
    ) -> pd.DataFrame:
        """查询产业链关联新闻"""
        query = """
            SELECT n.*, l.chain_id, l.segment_id, l.company_code,
                   l.company_name, l.match_score
            FROM company_news_links l
            JOIN news_articles n ON n.id = l.article_id
            WHERE l.chain_id = ?
        """
        params: list = [chain_id]
        if segment_id:
            query += " AND l.segment_id = ?"
            params.append(segment_id)
        if company_code:
            query += " AND l.company_code = ?"
            params.append(company_code)
        query += " ORDER BY n.publish_time DESC LIMIT ?"
        params.append(limit)
        return self.conn.execute(query, params).fetchdf()

    def log_data_update_run(self, row: dict) -> str:
        """记录一次数据更新运行结果"""
        import json
        import uuid
        from datetime import datetime

        run_id = row.get("id") or str(uuid.uuid4())
        details = row.get("details", {})
        if isinstance(details, (dict, list)):
            details = json.dumps(details, ensure_ascii=False)

        df = pd.DataFrame(  # noqa: F841 - DuckDB replacement scan reads this variable.
            [
                {
                    "id": run_id,
                    "task_name": row.get("task_name", ""),
                    "status": row.get("status", "unknown"),
                    "started_at": row.get("started_at") or datetime.now(),
                    "finished_at": row.get("finished_at") or datetime.now(),
                    "duration_seconds": row.get("duration_seconds", 0.0),
                    "success_count": row.get("success_count", 0),
                    "skipped_count": row.get("skipped_count", 0),
                    "failed_count": row.get("failed_count", 0),
                    "rows_written": row.get("rows_written", 0),
                    "details": details or "",
                    "error_message": row.get("error_message", ""),
                }
            ]
        )
        self.conn.execute("""
            INSERT OR REPLACE INTO data_update_runs (
                id, task_name, status, started_at, finished_at, duration_seconds,
                success_count, skipped_count, failed_count, rows_written,
                details, error_message
            )
            SELECT id, task_name, status, started_at, finished_at, duration_seconds,
                   success_count, skipped_count, failed_count, rows_written,
                   details, error_message
            FROM df
        """)
        return run_id

    def get_data_update_runs(
        self,
        task_name: str | None = None,
        limit: int = 100,
    ) -> pd.DataFrame:
        """查询数据更新运行日志"""
        query = "SELECT * FROM data_update_runs WHERE 1=1"
        params: list = []
        if task_name:
            query += " AND task_name = ?"
            params.append(task_name)
        query += " ORDER BY started_at DESC LIMIT ?"
        params.append(limit)
        return self.conn.execute(query, params).fetchdf()

    def upsert_dashboard_task(self, row: dict) -> str:
        """Persist dashboard background task state."""
        import json
        from datetime import datetime

        raw_result = row.get("result")
        result = raw_result
        tags = row.get("tags", [])
        if isinstance(result, (dict, list, tuple)):
            result = json.dumps(result, ensure_ascii=False, default=str)
        elif result is not None:
            result = str(result)
        else:
            result = ""
        if isinstance(tags, (dict, list, tuple)):
            tags = json.dumps(tags, ensure_ascii=False, default=str)
        elif tags is not None:
            tags = str(tags)
        else:
            tags = "[]"

        df = pd.DataFrame(  # noqa: F841 - DuckDB replacement scan reads this variable.
            [
                {
                    "id": row["id"],
                    "name": row.get("name", ""),
                    "status": row.get("status", "queued"),
                    "task_key": row.get("task_key", ""),
                    "task_type": row.get("task_type", "general"),
                    "tags": tags,
                    "created_at": row.get("created_at") or datetime.now(),
                    "started_at": row.get("started_at"),
                    "finished_at": row.get("finished_at"),
                    "result": result,
                    "error": row.get("error", ""),
                    "updated_at": datetime.now(),
                }
            ]
        )
        self.conn.execute("""
            INSERT OR REPLACE INTO dashboard_tasks (
                id, name, status, task_key, task_type, tags, created_at,
                started_at, finished_at, result, error, updated_at
            )
            SELECT id, name, status, task_key, task_type, tags, created_at,
                   started_at, finished_at, result, error, updated_at
            FROM df
        """)
        if result:
            self.upsert_dashboard_task_results(str(row["id"]), raw_result)
        return str(row["id"])

    def _dashboard_task_result_rows(self, task_id: str, result: object) -> list[dict]:
        """Convert a task result into searchable key/value rows."""
        import json

        rows: list[dict] = []

        def add_row(key: str, value: object) -> None:
            if value is None:
                value_type = "null"
                encoded = ""
            elif isinstance(value, bool):
                value_type = "bool"
                encoded = str(value).lower()
            elif isinstance(value, int | float):
                value_type = "number"
                encoded = str(value)
            elif isinstance(value, str):
                value_type = "string"
                encoded = value
            else:
                value_type = type(value).__name__
                encoded = json.dumps(value, ensure_ascii=False, default=str)
            rows.append(
                {
                    "task_id": task_id,
                    "result_key": key,
                    "result_value": encoded,
                    "value_type": value_type,
                }
            )

        def walk(prefix: str, value: object) -> None:
            if isinstance(value, dict):
                if not value:
                    add_row(prefix or "result", {})
                for child_key, child_value in value.items():
                    key = str(child_key)
                    walk(f"{prefix}.{key}" if prefix else key, child_value)
                return
            if isinstance(value, list | tuple):
                add_row(f"{prefix}.__count__" if prefix else "__count__", len(value))
                for idx, item in enumerate(value[:50]):
                    walk(f"{prefix}.{idx}" if prefix else str(idx), item)
                if len(value) > 50:
                    add_row(f"{prefix}.__truncated__" if prefix else "__truncated__", True)
                return
            add_row(prefix or "result", value)

        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                pass
        walk("", result)
        return rows

    def upsert_dashboard_task_results(self, task_id: str, result: object) -> int:
        """Persist flattened task result rows for lightweight querying."""
        rows = self._dashboard_task_result_rows(task_id, result)
        self.conn.execute("DELETE FROM dashboard_task_results WHERE task_id = ?", [task_id])
        if not rows:
            return 0
        df = pd.DataFrame(rows)  # noqa: F841 - DuckDB replacement scan reads this variable.
        self.conn.execute("""
            INSERT OR REPLACE INTO dashboard_task_results (
                task_id, result_key, result_value, value_type
            )
            SELECT task_id, result_key, result_value, value_type
            FROM df
        """)
        return len(rows)

    def get_dashboard_task_results(self, task_id: str) -> pd.DataFrame:
        """Return flattened result rows for one dashboard task."""
        return self.conn.execute(
            """
            SELECT task_id, result_key, result_value, value_type, created_at
            FROM dashboard_task_results
            WHERE task_id = ?
            ORDER BY result_key
            """,
            [task_id],
        ).fetchdf()

    def get_dashboard_tasks(self, limit: int = 50) -> pd.DataFrame:
        """Return persisted dashboard background tasks."""
        return self.conn.execute(
            """
            SELECT *
            FROM dashboard_tasks
            ORDER BY created_at DESC
            LIMIT ?
            """,
            [limit],
        ).fetchdf()

    def get_dashboard_task(self, task_id: str) -> pd.DataFrame:
        """Return one persisted dashboard task by id."""
        return self.conn.execute(
            "SELECT * FROM dashboard_tasks WHERE id = ?",
            [task_id],
        ).fetchdf()

    def mark_orphaned_dashboard_tasks(self) -> int:
        """Mark queued/running dashboard tasks from a previous process as interrupted."""
        count = self.conn.execute(
            "SELECT COUNT(*) FROM dashboard_tasks WHERE status IN ('queued', 'running')"
        ).fetchone()[0]
        self.conn.execute("""
            UPDATE dashboard_tasks
            SET status = 'interrupted',
                finished_at = COALESCE(finished_at, CURRENT_TIMESTAMP),
                error = CASE
                    WHEN error IS NULL OR error = ''
                    THEN '进程重启前任务未完成，已标记为中断'
                    ELSE error
                END,
                updated_at = CURRENT_TIMESTAMP
            WHERE status IN ('queued', 'running')
        """)
        return int(count or 0)

    def delete_finished_dashboard_tasks(self) -> int:
        """Delete successful dashboard tasks and return deleted row count."""
        count = self.conn.execute(
            """
            SELECT COUNT(*)
            FROM dashboard_tasks
            WHERE status = 'success'
            """
        ).fetchone()[0]
        self.conn.execute("DELETE FROM dashboard_tasks WHERE status = 'success'")
        self.conn.execute("""
            DELETE FROM dashboard_task_results
            WHERE task_id NOT IN (SELECT id FROM dashboard_tasks)
        """)
        return int(count or 0)

    def delete_success_dashboard_tasks_older_than(self, retention_days: int) -> int:
        """Delete successful dashboard tasks older than retention_days."""
        from datetime import datetime, timedelta

        cutoff = datetime.now() - timedelta(days=max(retention_days, 0))
        count = self.conn.execute(
            """
            SELECT COUNT(*)
            FROM dashboard_tasks
            WHERE status = 'success'
              AND COALESCE(finished_at, updated_at, created_at) < ?
            """,
            [cutoff],
        ).fetchone()[0]
        self.conn.execute(
            """
            DELETE FROM dashboard_tasks
            WHERE status = 'success'
              AND COALESCE(finished_at, updated_at, created_at) < ?
            """,
            [cutoff],
        )
        self.conn.execute("""
            DELETE FROM dashboard_task_results
            WHERE task_id NOT IN (SELECT id FROM dashboard_tasks)
        """)
        return int(count or 0)

    _ALLOWED_TABLES = {
        "etf_daily",
        "index_valuation",
        "bond_yield",
        "fundamental_data",
        "company_daily",
        "company_valuation",
    }
    _ALLOWED_COLUMNS = {"code", "index_name", "company_code", "1"}

    def get_latest_date(self, table: str, code_column: str, code_value: str) -> str | None:
        """获取某表某条目的最新日期，用于增量更新"""
        if table not in self._ALLOWED_TABLES:
            raise ValueError(f"不允许的表名: {table}")
        if code_column not in self._ALLOWED_COLUMNS:
            raise ValueError(f"不允许的列名: {code_column}")

        if code_column == "1":
            query = f"SELECT MAX(trade_date) FROM {table}"
            result = self.conn.execute(query).fetchone()
        else:
            query = f"SELECT MAX(trade_date) FROM {table} WHERE {code_column} = ?"
            result = self.conn.execute(query, [code_value]).fetchone()

        if result and result[0]:
            return str(result[0])
        return None
