"""产业链洞察：配置驱动的产业链企业、新闻与趋势聚合"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd

from src.core.config import get_industry_chain_config
from src.data.storage import StorageEngine


@dataclass(frozen=True)
class IndustryChainCompany:
    """产业链企业主数据"""

    chain_id: str
    chain_name: str
    segment_id: str
    segment_name: str
    company_code: str
    company_name: str
    role: str
    aliases: tuple[str, ...]
    keywords: tuple[str, ...]


class IndustryChainAnalyzer:
    """产业链分析器

    以 `config/industry_chains.yaml` 为主数据，聚合本地新闻、ETF行情、
    估值和企业行情，形成 Streamlit/API 可复用的产业链快照。
    """

    def __init__(self, storage: StorageEngine | None = None) -> None:
        self.storage = storage or StorageEngine()
        self.config = get_industry_chain_config().get("industry_chains", {})

    def list_chains(self) -> list[dict[str, Any]]:
        """列出已配置产业链"""
        return [
            {
                "chain_id": chain_id,
                "name": chain.get("name", chain_id),
                "description": chain.get("description", ""),
                "etf_codes": chain.get("etf_codes", []),
                "index_names": chain.get("index_names", []),
                "segment_count": len(chain.get("segments", {})),
                "company_count": sum(
                    len(segment.get("companies", []))
                    for segment in chain.get("segments", {}).values()
                ),
            }
            for chain_id, chain in self.config.items()
        ]

    def get_chain_config(self, chain_id: str) -> dict[str, Any]:
        """读取单个产业链配置"""
        if chain_id not in self.config:
            raise KeyError(f"未配置产业链: {chain_id}")
        return self.config[chain_id]

    def flatten_companies(self, chain_id: str | None = None) -> list[IndustryChainCompany]:
        """将 YAML 图谱摊平成企业列表"""
        chains = {chain_id: self.get_chain_config(chain_id)} if chain_id else self.config
        rows: list[IndustryChainCompany] = []

        for cid, chain in chains.items():
            chain_name = chain.get("name", cid)
            for segment_id, segment in chain.get("segments", {}).items():
                segment_name = segment.get("name", segment_id)
                for company in segment.get("companies", []):
                    aliases = tuple(company.get("aliases", []))
                    company_keywords = tuple(company.get("keywords", []))
                    keywords = tuple(
                        dict.fromkeys(
                            (
                                company.get("role", ""),
                                *company_keywords,
                            )
                        )
                    )
                    rows.append(
                        IndustryChainCompany(
                            chain_id=cid,
                            chain_name=chain_name,
                            segment_id=segment_id,
                            segment_name=segment_name,
                            company_code=str(company.get("code", "")),
                            company_name=str(company.get("name", "")),
                            role=str(company.get("role", "")),
                            aliases=aliases,
                            keywords=keywords,
                        )
                    )
        return rows

    def sync_company_master(self, chain_id: str | None = None) -> int:
        """把配置中的产业链企业同步到数据库"""
        rows = [
            {
                "chain_id": item.chain_id,
                "chain_name": item.chain_name,
                "segment_id": item.segment_id,
                "segment_name": item.segment_name,
                "company_code": item.company_code,
                "company_name": item.company_name,
                "role": item.role,
                "aliases": list(item.aliases),
                "keywords": list(item.keywords),
            }
            for item in self.flatten_companies(chain_id)
        ]
        return self.storage.upsert_industry_chain_companies(rows)

    def link_news(self, chain_id: str, limit: int = 500) -> int:
        """按关键词将已有新闻关联到产业链企业/环节"""
        chain = self.get_chain_config(chain_id)
        companies = self.flatten_companies(chain_id)
        news = self.storage.get_news_articles(limit=limit)
        if news.empty:
            return 0

        links = []
        for _, article in news.iterrows():
            title = str(article.get("title", ""))
            summary = str(article.get("summary", ""))
            content = str(article.get("content", ""))
            text = f"{title} {summary} {content[:500]}"
            article_id = str(article.get("id") or self._article_id(title))
            for segment_id, segment in chain.get("segments", {}).items():
                segment_score = self._segment_match_score(text, segment)
                if segment_score > 0:
                    links.append(
                        {
                            "article_id": article_id,
                            "chain_id": chain_id,
                            "segment_id": segment_id,
                            "company_code": "",
                            "company_name": "",
                            "match_score": segment_score,
                        }
                    )
            for company in companies:
                score = self._match_score(text, company)
                if score > 0:
                    links.append(
                        {
                            "article_id": article_id,
                            "chain_id": company.chain_id,
                            "segment_id": company.segment_id,
                            "company_code": company.company_code,
                            "company_name": company.company_name,
                            "match_score": score,
                        }
                    )

        return self.storage.upsert_company_news_links(links)

    def link_all_news(self, limit: int = 500) -> dict[str, int]:
        """刷新全部已配置产业链的新闻关联"""
        return {chain_id: self.link_news(chain_id, limit=limit) for chain_id in self.config}

    def build_snapshot(self, chain_id: str, link_news: bool = True) -> dict[str, Any]:
        """生成单个产业链的全景快照"""
        chain = self.get_chain_config(chain_id)
        self.sync_company_master(chain_id)
        if link_news:
            self.link_news(chain_id)

        companies = self.flatten_companies(chain_id)
        news_links = self.storage.get_industry_chain_news(chain_id, limit=300)
        news_unique = self._unique_news(news_links)
        company_trends = self._build_company_trends(companies, news_links)
        segment_summary = self._build_segment_summary(chain, companies, news_links)
        etf_summary = self._build_etf_summary(chain.get("etf_codes", []))
        index_summary = self._build_index_summary(chain.get("index_names", []))
        data_quality = self._build_data_quality(company_trends, etf_summary, index_summary)

        avg_sentiment = self._avg(news_unique, "sentiment")
        high_impact = (
            int((news_unique.get("impact_level") == "high").sum()) if not news_unique.empty else 0
        )

        return {
            "chain_id": chain_id,
            "name": chain.get("name", chain_id),
            "description": chain.get("description", ""),
            "trend_keywords": chain.get("trend_keywords", []),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "overview": {
                "company_count": len(companies),
                "segment_count": len(chain.get("segments", {})),
                "news_count": int(len(news_unique)),
                "high_impact_news_count": high_impact,
                "avg_sentiment": round(avg_sentiment, 3),
                "trend_label": self._trend_label(avg_sentiment, high_impact, len(news_unique)),
            },
            "segments": segment_summary,
            "companies": company_trends,
            "etfs": etf_summary,
            "indices": index_summary,
            "data_quality": data_quality,
            "news": self._news_records(news_unique.head(50)),
            "analysis": self._rule_based_analysis(
                chain, segment_summary, avg_sentiment, high_impact
            ),
        }

    def compare_chains(self, chain_ids: list[str]) -> pd.DataFrame:
        """生成多个产业链的横向对比表"""
        rows = []
        for chain_id in chain_ids:
            snapshot = self.build_snapshot(chain_id)
            overview = snapshot["overview"]
            rows.append(
                {
                    "chain_id": chain_id,
                    "产业链": snapshot["name"],
                    "企业数": overview["company_count"],
                    "环节数": overview["segment_count"],
                    "相关新闻": overview["news_count"],
                    "高影响新闻": overview["high_impact_news_count"],
                    "平均情绪": overview["avg_sentiment"],
                    "趋势": overview["trend_label"],
                }
            )
        return pd.DataFrame(rows)

    def _unique_news(self, news: pd.DataFrame) -> pd.DataFrame:
        if news.empty:
            return news
        unique_key = "id" if "id" in news.columns else "title"
        return news.drop_duplicates(subset=[unique_key]).copy()

    def _build_data_quality(
        self,
        companies: list[dict[str, Any]],
        etfs: list[dict[str, Any]],
        indices: list[dict[str, Any]],
    ) -> dict[str, Any]:
        missing_company_prices = [
            item["company_name"] for item in companies if not item.get("latest_date")
        ]
        missing_etfs = [item["code"] for item in etfs if not item.get("latest_date")]
        missing_indices = [
            item["index_name"]
            for item in indices
            if item.get("pe") is None and item.get("pb") is None
        ]
        missing_company_fundamentals = [
            item["company_name"] for item in companies if not item.get("latest_report_date")
        ]
        missing_company_valuations = [
            item["company_name"] for item in companies if not item.get("valuation_date")
        ]
        latest_dates = [
            item.get("latest_date", "") for item in [*companies, *etfs] if item.get("latest_date")
        ]
        report_dates = [
            item.get("latest_report_date", "")
            for item in companies
            if item.get("latest_report_date")
        ]
        forecast_count = sum(int(item.get("earnings_forecast_count", 0)) for item in companies)
        return {
            "company_price_coverage": round(1 - len(missing_company_prices) / len(companies), 3)
            if companies
            else 0,
            "company_fundamental_coverage": round(
                1 - len(missing_company_fundamentals) / len(companies), 3
            )
            if companies
            else 0,
            "company_valuation_coverage": round(
                1 - len(missing_company_valuations) / len(companies), 3
            )
            if companies
            else 0,
            "missing_company_prices": missing_company_prices,
            "missing_company_fundamentals": missing_company_fundamentals,
            "missing_company_valuations": missing_company_valuations,
            "missing_etfs": missing_etfs,
            "missing_indices": missing_indices,
            "latest_market_date": max(latest_dates) if latest_dates else "",
            "latest_report_date": max(report_dates) if report_dates else "",
            "earnings_forecast_count": forecast_count,
        }

    def _build_company_trends(
        self,
        companies: list[IndustryChainCompany],
        news: pd.DataFrame,
    ) -> list[dict[str, Any]]:
        rows = []
        for company in companies:
            daily = self.storage.get_company_daily(company.company_code)
            fundamentals = self.storage.get_company_fundamentals(company.company_code)
            valuation = self.storage.get_company_valuation(company.company_code)
            forecasts = self.storage.get_company_earnings_forecasts(
                company_code=company.company_code,
                limit=20,
            )
            trend = self._calc_price_trend(daily)
            quality = self._latest_fundamental_record(fundamentals)
            valuation_snapshot = self._latest_valuation_record(valuation)
            latest_forecast = self._latest_forecast_record(forecasts)
            company_news = (
                news[news["company_code"] == company.company_code]
                if not news.empty and "company_code" in news.columns
                else pd.DataFrame()
            )
            rows.append(
                {
                    "chain_id": company.chain_id,
                    "segment_id": company.segment_id,
                    "segment_name": company.segment_name,
                    "company_code": company.company_code,
                    "company_name": company.company_name,
                    "role": company.role,
                    "aliases": list(company.aliases),
                    "news_count": int(len(company_news)),
                    "avg_sentiment": round(self._avg(company_news, "sentiment"), 3),
                    **quality,
                    **valuation_snapshot,
                    **latest_forecast,
                    **trend,
                }
            )
        return rows

    def _build_segment_summary(
        self,
        chain: dict[str, Any],
        companies: list[IndustryChainCompany],
        news: pd.DataFrame,
    ) -> list[dict[str, Any]]:
        rows = []
        for segment_id, segment in chain.get("segments", {}).items():
            segment_news = (
                news[news["segment_id"] == segment_id]
                if not news.empty and "segment_id" in news.columns
                else pd.DataFrame()
            )
            segment_news = self._unique_news(segment_news)
            segment_companies = [c for c in companies if c.segment_id == segment_id]
            rows.append(
                {
                    "segment_id": segment_id,
                    "segment_name": segment.get("name", segment_id),
                    "keywords": segment.get("keywords", []),
                    "company_count": len(segment_companies),
                    "news_count": int(len(segment_news)),
                    "high_impact_news_count": int(
                        (segment_news.get("impact_level") == "high").sum()
                    )
                    if not segment_news.empty
                    else 0,
                    "avg_sentiment": round(self._avg(segment_news, "sentiment"), 3),
                    "companies": [
                        {
                            "company_code": c.company_code,
                            "company_name": c.company_name,
                            "role": c.role,
                            "aliases": list(c.aliases),
                        }
                        for c in segment_companies
                    ],
                }
            )
        return rows

    def _build_etf_summary(self, etf_codes: list[str]) -> list[dict[str, Any]]:
        rows = []
        for code in etf_codes:
            daily = self.storage.get_etf_daily(code)
            rows.append({"code": code, **self._calc_price_trend(daily)})
        return rows

    def _build_index_summary(self, index_names: list[str]) -> list[dict[str, Any]]:
        rows = []
        for index_name in index_names:
            val = self.storage.get_index_valuation(index_name)
            if val.empty:
                rows.append(
                    {
                        "index_name": index_name,
                        "pe": None,
                        "pb": None,
                        "pe_percentile": None,
                    }
                )
                continue
            latest = val.iloc[-1]
            rows.append(
                {
                    "index_name": index_name,
                    "trade_date": str(latest.get("trade_date", "")),
                    "pe": self._safe_float(latest.get("pe")),
                    "pb": self._safe_float(latest.get("pb")),
                    "dividend_yield": self._safe_float(latest.get("dividend_yield")),
                    "pe_percentile": self._safe_float(latest.get("pe_percentile")),
                    "pb_percentile": self._safe_float(latest.get("pb_percentile")),
                }
            )
        return rows

    def _calc_price_trend(self, df: pd.DataFrame) -> dict[str, Any]:
        if df.empty or "close" not in df.columns:
            return {
                "latest_date": "",
                "latest_close": None,
                "return_5d": None,
                "return_20d": None,
                "return_60d": None,
            }

        data = df.dropna(subset=["close"]).sort_values("trade_date")
        if data.empty:
            return {
                "latest_date": "",
                "latest_close": None,
                "return_5d": None,
                "return_20d": None,
                "return_60d": None,
            }

        latest = data.iloc[-1]
        return {
            "latest_date": str(latest.get("trade_date", "")),
            "latest_close": self._safe_float(latest.get("close")),
            "return_5d": self._period_return(data, 5),
            "return_20d": self._period_return(data, 20),
            "return_60d": self._period_return(data, 60),
        }

    def _period_return(self, df: pd.DataFrame, periods: int) -> float | None:
        if len(df) <= periods:
            return None
        now = df["close"].iloc[-1]
        prev = df["close"].iloc[-periods - 1]
        if pd.isna(now) or pd.isna(prev) or prev == 0:
            return None
        return round((float(now) / float(prev) - 1) * 100, 2)

    def _latest_fundamental_record(self, df: pd.DataFrame) -> dict[str, Any]:
        if df.empty:
            return {
                "latest_report_date": "",
                "latest_report_type": "",
                "revenue": None,
                "net_profit": None,
                "roe": None,
                "revenue_yoy": None,
                "net_profit_yoy": None,
            }
        latest = df.sort_values("report_date").iloc[-1]
        return {
            "latest_report_date": str(latest.get("report_date", "")),
            "latest_report_type": latest.get("report_type", ""),
            "revenue": self._safe_float(latest.get("revenue")),
            "net_profit": self._safe_float(latest.get("net_profit")),
            "roe": self._safe_float(latest.get("roe")),
            "revenue_yoy": self._safe_float(latest.get("revenue_yoy")),
            "net_profit_yoy": self._safe_float(latest.get("net_profit_yoy")),
        }

    def _latest_valuation_record(self, df: pd.DataFrame) -> dict[str, Any]:
        if df.empty:
            return {
                "valuation_date": "",
                "market_cap": None,
                "pe_ttm": None,
                "pe_static": None,
                "pb": None,
            }
        latest = df.sort_values("trade_date").iloc[-1]
        return {
            "valuation_date": str(latest.get("trade_date", "")),
            "market_cap": self._safe_float(latest.get("market_cap")),
            "pe_ttm": self._safe_float(latest.get("pe_ttm")),
            "pe_static": self._safe_float(latest.get("pe_static")),
            "pb": self._safe_float(latest.get("pb")),
        }

    def _latest_forecast_record(self, df: pd.DataFrame) -> dict[str, Any]:
        if df.empty:
            return {
                "earnings_forecast_count": 0,
                "latest_forecast_period": "",
                "latest_forecast_type": "",
                "latest_forecast_change_pct": None,
            }
        latest = df.sort_values(["announce_date", "report_period"]).iloc[-1]
        return {
            "earnings_forecast_count": int(len(df)),
            "latest_forecast_period": str(latest.get("report_period", "")),
            "latest_forecast_type": latest.get("forecast_type", ""),
            "latest_forecast_change_pct": self._safe_float(latest.get("change_pct")),
        }

    def _news_records(self, news: pd.DataFrame) -> list[dict[str, Any]]:
        if news.empty:
            return []
        records = []
        for _, row in news.iterrows():
            records.append(
                {
                    "title": row.get("title", ""),
                    "summary": row.get("summary", ""),
                    "source": row.get("source", ""),
                    "publish_time": str(row.get("publish_time", "")),
                    "url": row.get("url", ""),
                    "sentiment": self._safe_float(row.get("sentiment")),
                    "impact_level": row.get("impact_level", "low"),
                    "is_policy": bool(row.get("is_policy", False)),
                    "segment_id": row.get("segment_id", ""),
                    "company_code": row.get("company_code", ""),
                    "company_name": row.get("company_name", ""),
                }
            )
        return records

    def _rule_based_analysis(
        self,
        chain: dict[str, Any],
        segments: list[dict[str, Any]],
        avg_sentiment: float,
        high_impact: int,
    ) -> dict[str, str]:
        hot_segments = sorted(
            segments,
            key=lambda item: (item["news_count"], abs(item["avg_sentiment"])),
            reverse=True,
        )
        hot_text = "、".join(s["segment_name"] for s in hot_segments[:2] if s["news_count"] > 0)
        if not hot_text:
            hot_text = "暂无明显集中环节"

        if avg_sentiment > 0.25:
            direction = "资讯情绪偏积极，适合继续跟踪政策、订单和业绩兑现。"
        elif avg_sentiment < -0.25:
            direction = "资讯情绪偏谨慎，需要关注估值回撤、订单不及预期或政策节奏变化。"
        else:
            direction = "资讯情绪整体中性，当前更适合用企业趋势和重大新闻做结构筛选。"

        return {
            "status": f"{chain.get('name', '该产业链')}当前关注点集中在{hot_text}。",
            "trend": direction,
            "risk": "高影响新闻较多" if high_impact >= 3 else "暂未出现密集高影响新闻",
        }

    def _match_score(self, text: str, company: IndustryChainCompany) -> float:
        score = 0.0
        if company.company_name and company.company_name in text:
            score += 1.0
        for alias in company.aliases:
            if alias and alias in text:
                score += 0.8
        for keyword in company.keywords:
            if keyword and keyword in text:
                score += 0.2
        return round(min(score, 2.0), 3)

    def _segment_match_score(self, text: str, segment: dict[str, Any]) -> float:
        score = 0.0
        for keyword in segment.get("keywords", []):
            if keyword and keyword in text:
                score += 0.25
        return round(min(score, 1.0), 3)

    def _trend_label(self, avg_sentiment: float, high_impact: int, news_count: int) -> str:
        if news_count == 0:
            return "待观察"
        if avg_sentiment > 0.35 and high_impact > 0:
            return "升温"
        if avg_sentiment < -0.25 and high_impact > 0:
            return "承压"
        if news_count >= 10:
            return "活跃"
        return "平稳"

    def _avg(self, df: pd.DataFrame, column: str) -> float:
        if df.empty or column not in df.columns:
            return 0.0
        value = pd.to_numeric(df[column], errors="coerce").mean()
        return 0.0 if pd.isna(value) else float(value)

    def _safe_float(self, value: Any) -> float | None:
        try:
            if pd.isna(value):
                return None
            return round(float(value), 4)
        except (TypeError, ValueError):
            return None

    def _article_id(self, title: str) -> str:
        return hashlib.md5(title.encode("utf-8")).hexdigest()[:16]


def dataframe_from_records(records: list[dict[str, Any]]) -> pd.DataFrame:
    """面向 Dashboard 的轻量转换，保证空数据也有 DataFrame。"""
    return pd.DataFrame(records)
