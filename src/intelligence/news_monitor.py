"""新闻监控引擎：采集 + 去重 + LLM分析 + 存储"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import datetime, timedelta

from loguru import logger

from src.core.config import load_yaml_config
from src.data.providers.news_provider import NewsArticle, NewsProvider
from src.intelligence.llm_analyzer import LLMAnalyzer


class NewsMonitor:
    """新闻监控引擎

    1. 从多个源采集新闻
    2. 标题哈希去重
    3. 关键词匹配分类到行业
    4. LLM 分析打分
    5. 存储结果
    """

    def __init__(self) -> None:
        self._config = load_yaml_config("intelligence.yaml")
        self._monitor_config = self._config.get("news_monitor", {})
        self._provider = NewsProvider()
        self._llm = LLMAnalyzer()
        self._seen_hashes: dict[str, datetime] = {}
        self._dedup_window = timedelta(hours=self._monitor_config.get("dedup_window_hours", 24))

    def run_cycle(self, use_llm: bool = True) -> list[dict]:
        """执行一轮采集-分析流程

        Returns:
            list of analyzed news dicts ready for storage
        """
        # 1. 采集
        sources = self._monitor_config.get("sources", ["eastmoney", "cls"])
        max_per_batch = self._monitor_config.get("max_news_per_batch", 50)
        raw_articles = self._provider.fetch_all(sources, max_per_source=max_per_batch)
        logger.info(f"[Monitor] 本轮采集 {len(raw_articles)} 条原始新闻")

        # 2. 去重
        unique = self._dedup(raw_articles)
        logger.info(f"[Monitor] 去重后 {len(unique)} 条")

        if not unique:
            return []

        # 3. 关键词分类
        classified = self._classify_sector(unique)

        # 4. LLM 分析
        if use_llm:
            results = self._llm_analyze(classified)
        else:
            results = self._no_llm_fallback(classified)

        logger.info(f"[Monitor] 分析完成 {len(results)} 条")
        return results

    def _dedup(self, articles: list[NewsArticle]) -> list[NewsArticle]:
        """基于标题哈希去重"""
        now = datetime.now()
        # 清理过期哈希
        expired = [h for h, t in self._seen_hashes.items() if now - t > self._dedup_window]
        for h in expired:
            del self._seen_hashes[h]

        unique = []
        for art in articles:
            h = hashlib.md5(art.title.encode("utf-8")).hexdigest()
            if h not in self._seen_hashes:
                self._seen_hashes[h] = now
                unique.append(art)

        return unique

    def _classify_sector(self, articles: list[NewsArticle]) -> list[dict]:
        """关键词匹配分行业"""
        sectors_config = self._config.get("sectors", {})
        results = []

        for art in articles:
            text = f"{art.title} {art.content[:200]}"
            matched_sectors: list[str] = []
            matched_etf_codes: list[str] = []

            for sector_name, sector_info in sectors_config.items():
                keywords = sector_info.get("keywords", [])
                if any(kw in text for kw in keywords):
                    matched_sectors.append(sector_name)
                    matched_etf_codes.extend(sector_info.get("etf_codes", []))

            results.append(
                {
                    "title": art.title,
                    "content": art.content,
                    "source": art.source,
                    "publish_time": art.publish_time,
                    "url": art.url,
                    "category": art.category,
                    "matched_sectors": matched_sectors,
                    "matched_etf_codes": list(set(matched_etf_codes)),
                }
            )

        return results

    def _llm_analyze(self, classified: list[dict]) -> list[dict]:
        """LLM 批量分析"""
        batch_size = self._monitor_config.get("llm_batch_size", 10)
        all_results = []

        for i in range(0, len(classified), batch_size):
            batch = classified[i : i + batch_size]
            try:
                analysis = self._llm.analyze_batch(batch)
                for item, result in zip(batch, analysis):
                    merged = {**item}
                    merged["summary"] = result.summary
                    merged["sentiment"] = result.sentiment
                    merged["impact_level"] = result.impact_level
                    merged["is_policy"] = result.is_policy
                    # LLM 识别的行业与关键词匹配取并集
                    all_sectors = list(set(item["matched_sectors"] + result.related_sectors))
                    all_etfs = list(set(item["matched_etf_codes"] + result.related_etf_codes))
                    merged["related_sectors"] = all_sectors
                    merged["related_etf_codes"] = all_etfs
                    all_results.append(merged)
            except Exception as e:
                logger.error(f"[Monitor] LLM 批次分析失败: {e}")
                all_results.extend(self._no_llm_fallback(batch))

        return all_results

    def _no_llm_fallback(self, classified: list[dict]) -> list[dict]:
        """无 LLM 时的回退：只做关键词分类"""
        results = []
        for item in classified:
            item["summary"] = item["title"][:50]
            item["sentiment"] = 0.0
            item["impact_level"] = "low"
            item["is_policy"] = item.get("category") == "policy"
            item["related_sectors"] = item.get("matched_sectors", [])
            item["related_etf_codes"] = item.get("matched_etf_codes", [])
            results.append(item)
        return results

    def get_sector_heatmap(self, analyzed: list[dict]) -> dict[str, dict]:
        """按行业汇总情绪热力数据

        Returns:
            {sector: {count, avg_sentiment, high_impact_count}}
        """
        sector_stats: dict[str, dict] = defaultdict(
            lambda: {"count": 0, "total_sentiment": 0.0, "high_impact": 0}
        )

        for item in analyzed:
            for sector in item.get("related_sectors", []):
                stats = sector_stats[sector]
                stats["count"] += 1
                stats["total_sentiment"] += item.get("sentiment", 0)
                if item.get("impact_level") == "high":
                    stats["high_impact"] += 1

        result = {}
        for sector, stats in sector_stats.items():
            count = stats["count"]
            result[sector] = {
                "count": count,
                "avg_sentiment": round(stats["total_sentiment"] / count, 3) if count else 0,
                "high_impact_count": stats["high_impact"],
            }
        return result
