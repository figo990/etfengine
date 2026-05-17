"""外盘科技龙头季报：SEC 结构化采集 + 入库 + 可选 LLM 解读"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from loguru import logger

from src.analysis.earnings_analyzer import attach_yoy_metrics, build_fact_brief_cn
from src.core.config import load_yaml_config
from src.data.providers.us_sec_earnings_provider import UsSecEarningsProvider
from src.data.storage import StorageEngine
from src.intelligence.llm_analyzer import LLMAnalyzer


def _norm_cik(raw: object) -> int | None:
    if raw is None or raw == "" or str(raw).lower() == "null":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


class OverseasEarningsMonitor:
    """按 overseas_earnings.yaml 拉取美股龙头季报指标并写入 DuckDB"""

    def __init__(self) -> None:
        self._cfg = load_yaml_config("overseas_earnings.yaml")

    def run_cycle(self, use_llm: bool | None = None) -> dict[str, Any]:
        if not self._cfg.get("enabled", True):
            logger.info("[Earnings] overseas_earnings.yaml 中 enabled=false，跳过")
            return {"skipped": True, "updated_metrics": 0, "updated_analysis": 0}

        if use_llm is None:
            use_llm = bool(self._cfg.get("llm_digest", True))

        ua = self._cfg.get("sec_user_agent")
        provider = UsSecEarningsProvider(user_agent=ua)
        storage = StorageEngine()
        storage.init_schema()

        watch = self._cfg.get("watchlist") or []
        total_m = 0
        analysis_rows: list[dict] = []

        llm: LLMAnalyzer | None = None
        if use_llm:
            llm = LLMAnalyzer()

        try:
            for item in watch:
                ticker = str(item.get("ticker", "")).strip().upper()
                if not ticker:
                    continue
                name = str(item.get("name") or ticker)
                cik = _norm_cik(item.get("cik"))
                default_etfs = list(item.get("related_etf_codes") or [])

                try:
                    points = provider.fetch_quarterly_metrics(ticker, cik)
                except Exception as e:
                    logger.warning(f"[Earnings] {ticker} SEC 拉取失败: {e}")
                    continue

                if not points:
                    logger.info(f"[Earnings] {ticker} 无季报数据点")
                    continue

                points = points[-28:]
                rows = attach_yoy_metrics(ticker, name, points)
                total_m += storage.upsert_overseas_earnings_metrics(rows)

                latest = max(rows, key=lambda r: r["period_end"])
                brief = build_fact_brief_cn(ticker, name, latest)
                title = (
                    f"{name}({ticker}) {latest['fiscal_year']}{latest['fiscal_period']} 季报解读"
                )

                if llm is not None:
                    try:
                        res = llm.analyze_earnings_digest(title, brief, default_etfs)
                        analysis_rows.append(
                            {
                                "ticker": ticker,
                                "period_end": latest["period_end"],
                                "summary_zh": res.summary,
                                "sentiment": res.sentiment,
                                "impact_level": res.impact_level,
                                "related_etf_codes": res.related_etf_codes or default_etfs,
                                "fact_brief": brief,
                                "analyzed_at": datetime.now(),
                            }
                        )
                    except Exception as e:
                        logger.warning(f"[Earnings] {ticker} LLM 解读失败，使用规则摘要: {e}")
                        analysis_rows.append(
                            {
                                "ticker": ticker,
                                "period_end": latest["period_end"],
                                "summary_zh": brief[:200],
                                "sentiment": 0.0,
                                "impact_level": "low",
                                "related_etf_codes": default_etfs,
                                "fact_brief": brief,
                                "analyzed_at": datetime.now(),
                            }
                        )
                else:
                    analysis_rows.append(
                        {
                            "ticker": ticker,
                            "period_end": latest["period_end"],
                            "summary_zh": brief[:200],
                            "sentiment": 0.0,
                            "impact_level": "low",
                            "related_etf_codes": default_etfs,
                            "fact_brief": brief,
                            "analyzed_at": datetime.now(),
                        }
                    )

            total_a = 0
            if analysis_rows:
                total_a = storage.upsert_overseas_earnings_analysis(analysis_rows)

            logger.info(
                "[Earnings] 完成: metrics_rows={}, analysis_rows={}, watchlist={}",
                total_m,
                total_a,
                len(watch),
            )
            return {
                "skipped": False,
                "updated_metrics": total_m,
                "updated_analysis": total_a,
                "watchlist": len(watch),
            }
        finally:
            storage.close()
