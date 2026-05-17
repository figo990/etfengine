"""行业政策追踪器：关键词匹配 + 政策来源加权"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from loguru import logger

from src.core.config import load_yaml_config


@dataclass
class PolicyAlert:
    """政策预警条目"""

    title: str
    summary: str
    sector: str
    sentiment: float  # -1 ~ +1
    impact_score: float  # 综合影响分（考虑来源权重）
    source: str
    publish_time: datetime | None = None
    url: str = ""
    matched_keywords: list[str] = field(default_factory=list)


class SectorTracker:
    """行业政策追踪器

    1. 按行业关键词匹配新闻
    2. 政策来源权重加分（国务院/发改委 > 一般媒体）
    3. 生成预警信号
    """

    def __init__(self) -> None:
        config = load_yaml_config("intelligence.yaml")
        self._sectors = config.get("sectors", {})
        self._source_weights = config.get("policy_sources_weight", {})

    def track(self, analyzed_news: list[dict]) -> dict[str, list[PolicyAlert]]:
        """追踪各行业政策动态

        Args:
            analyzed_news: NewsMonitor 输出的分析结果列表

        Returns:
            {sector_name: [PolicyAlert, ...]}
        """
        sector_alerts: dict[str, list[PolicyAlert]] = defaultdict(list)

        for item in analyzed_news:
            if not item.get("is_policy", False) and item.get("impact_level") != "high":
                if item.get("category") != "policy":
                    continue

            sectors = item.get("related_sectors", [])
            if not sectors:
                sectors = self._match_sectors(item.get("title", ""), item.get("content", ""))

            for sector in sectors:
                matched_kw = self._get_matched_keywords(
                    sector,
                    f"{item.get('title', '')} {item.get('content', '')[:200]}",
                )
                source_weight = self._calc_source_weight(
                    item.get("source", ""), item.get("title", "")
                )
                base_sentiment = item.get("sentiment", 0.0)
                impact_score = abs(base_sentiment) * source_weight

                alert = PolicyAlert(
                    title=item.get("title", ""),
                    summary=item.get("summary", ""),
                    sector=sector,
                    sentiment=base_sentiment,
                    impact_score=round(impact_score, 3),
                    source=item.get("source", ""),
                    publish_time=item.get("publish_time"),
                    url=item.get("url", ""),
                    matched_keywords=matched_kw,
                )
                sector_alerts[sector].append(alert)

        for sector in sector_alerts:
            sector_alerts[sector].sort(key=lambda a: a.impact_score, reverse=True)

        logger.info(
            f"[SectorTracker] 追踪到 {sum(len(v) for v in sector_alerts.values())} 条预警, "
            f"涉及 {len(sector_alerts)} 个行业"
        )
        return dict(sector_alerts)

    def _match_sectors(self, title: str, content: str) -> list[str]:
        """关键词匹配行业"""
        text = f"{title} {content[:300]}"
        matched = []
        for sector_name, sector_info in self._sectors.items():
            keywords = sector_info.get("keywords", [])
            if any(kw in text for kw in keywords):
                matched.append(sector_name)
        return matched

    def _get_matched_keywords(self, sector: str, text: str) -> list[str]:
        """获取匹配到的关键词"""
        sector_info = self._sectors.get(sector, {})
        keywords = sector_info.get("keywords", [])
        return [kw for kw in keywords if kw in text]

    def _calc_source_weight(self, source: str, title: str) -> float:
        """根据来源计算权重"""
        weight = 1.0
        for src_name, src_weight in self._source_weights.items():
            if src_name in title or src_name in source:
                weight = max(weight, src_weight)
        return weight

    def get_sector_summary(
        self,
        sector_alerts: dict[str, list[PolicyAlert]],
    ) -> list[dict]:
        """生成各行业政策摘要

        Returns:
            [{sector, alert_count, avg_sentiment, top_alert_title, impact_direction}]
        """
        summaries = []
        for sector, alerts in sector_alerts.items():
            if not alerts:
                continue
            sentiments = [a.sentiment for a in alerts]
            avg_sent = sum(sentiments) / len(sentiments) if sentiments else 0

            direction = "中性"
            if avg_sent > 0.2:
                direction = "利多"
            elif avg_sent < -0.2:
                direction = "利空"

            summaries.append(
                {
                    "sector": sector,
                    "alert_count": len(alerts),
                    "avg_sentiment": round(avg_sent, 3),
                    "top_alert_title": alerts[0].title if alerts else "",
                    "impact_direction": direction,
                }
            )

        summaries.sort(key=lambda x: abs(x["avg_sentiment"]), reverse=True)
        return summaries
