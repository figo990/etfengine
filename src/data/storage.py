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
        if db_path is not None:
            self._db_path = db_path
        else:
            cfg = settings().database
            self._db_path = cfg.path
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn: duckdb.DuckDBPyConnection | None = None

    @property
    def conn(self) -> duckdb.DuckDBPyConnection:
        if self._conn is None:
            self._conn = duckdb.connect(self._db_path)
        return self._conn

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
                inception_date DATE
            )
        """)

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

        logger.info("数据库表结构初始化完成")

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
            rows.append({
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
                "related_sectors": json.dumps(art.get("related_sectors", []), ensure_ascii=False),
                "related_etf_codes": json.dumps(art.get("related_etf_codes", []), ensure_ascii=False),
                "created_at": datetime.now(),
            })

        df = pd.DataFrame(rows)
        self.conn.execute("""
            INSERT OR REPLACE INTO news_articles
            SELECT id, title, summary, content, source, category,
                   publish_time, url, sentiment, impact_level, is_policy,
                   related_sectors, related_etf_codes, created_at
            FROM df
        """)
        return len(df)

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

    def get_latest_date(self, table: str, code_column: str, code_value: str) -> str | None:
        """获取某表某条目的最新日期，用于增量更新"""
        query = f"SELECT MAX(trade_date) FROM {table} WHERE {code_column} = ?"
        result = self.conn.execute(query, [code_value]).fetchone()
        if result and result[0]:
            return str(result[0])
        return None
