"""新闻监控引擎测试"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.data.providers.news_provider import NewsArticle
from src.intelligence.news_monitor import NewsMonitor


class TestNewsMonitorDedup:
    def setup_method(self):
        with patch("src.intelligence.news_monitor.load_yaml_config") as mock_cfg:
            mock_cfg.return_value = {
                "news_monitor": {
                    "dedup_window_hours": 24,
                    "max_news_per_batch": 50,
                    "sources": [],
                    "llm_batch_size": 10,
                },
                "sectors": {
                    "消费": {"keywords": ["消费", "白酒"], "etf_codes": ["159928"]},
                    "医药": {"keywords": ["医药", "创新药"], "etf_codes": ["512010"]},
                },
            }
            self.monitor = NewsMonitor()

    def test_dedup_removes_duplicates(self):
        articles = [
            NewsArticle(title="新闻A", content="内容A"),
            NewsArticle(title="新闻A", content="内容A重复"),
            NewsArticle(title="新闻B", content="内容B"),
        ]
        result = self.monitor._dedup(articles)
        assert len(result) == 2
        titles = {a.title for a in result}
        assert "新闻A" in titles
        assert "新闻B" in titles

    def test_dedup_all_unique(self):
        articles = [
            NewsArticle(title=f"新闻{i}") for i in range(5)
        ]
        result = self.monitor._dedup(articles)
        assert len(result) == 5


class TestNewsMonitorClassify:
    def setup_method(self):
        with patch("src.intelligence.news_monitor.load_yaml_config") as mock_cfg:
            mock_cfg.return_value = {
                "news_monitor": {"dedup_window_hours": 24, "sources": [], "llm_batch_size": 10},
                "sectors": {
                    "消费": {"keywords": ["消费", "白酒", "食品"], "etf_codes": ["159928"]},
                    "医药": {"keywords": ["医药", "创新药", "集采"], "etf_codes": ["512010"]},
                    "半导体": {"keywords": ["芯片", "半导体"], "etf_codes": ["512480"]},
                },
            }
            self.monitor = NewsMonitor()

    def test_classify_matches_sector(self):
        articles = [
            NewsArticle(title="白酒行业复苏", content="消费升级推动高端白酒增长"),
            NewsArticle(title="芯片出口管制", content="半导体行业面临新挑战"),
            NewsArticle(title="天气预报", content="明天多云"),
        ]
        result = self.monitor._classify_sector(articles)
        assert len(result) == 3

        assert "消费" in result[0]["matched_sectors"]
        assert "半导体" in result[1]["matched_sectors"]
        assert len(result[2]["matched_sectors"]) == 0

    def test_classify_multiple_sectors(self):
        articles = [
            NewsArticle(title="消费医药联动", content="消费升级带动创新药需求"),
        ]
        result = self.monitor._classify_sector(articles)
        sectors = result[0]["matched_sectors"]
        assert "消费" in sectors
        assert "医药" in sectors


class TestNewsMonitorHeatmap:
    def setup_method(self):
        with patch("src.intelligence.news_monitor.load_yaml_config") as mock_cfg:
            mock_cfg.return_value = {
                "news_monitor": {"dedup_window_hours": 24, "sources": [], "llm_batch_size": 10},
                "sectors": {},
            }
            self.monitor = NewsMonitor()

    def test_heatmap_basic(self):
        analyzed = [
            {"related_sectors": ["消费"], "sentiment": 0.5, "impact_level": "high"},
            {"related_sectors": ["消费"], "sentiment": 0.3, "impact_level": "low"},
            {"related_sectors": ["医药"], "sentiment": -0.5, "impact_level": "high"},
        ]
        heatmap = self.monitor.get_sector_heatmap(analyzed)
        assert "消费" in heatmap
        assert heatmap["消费"]["count"] == 2
        assert heatmap["消费"]["avg_sentiment"] == pytest.approx(0.4, abs=0.01)
        assert heatmap["消费"]["high_impact_count"] == 1
        assert heatmap["医药"]["count"] == 1

    def test_heatmap_empty(self):
        heatmap = self.monitor.get_sector_heatmap([])
        assert heatmap == {}


class TestNewsMonitorFallback:
    def setup_method(self):
        with patch("src.intelligence.news_monitor.load_yaml_config") as mock_cfg:
            mock_cfg.return_value = {
                "news_monitor": {"dedup_window_hours": 24, "sources": [], "llm_batch_size": 10},
                "sectors": {"消费": {"keywords": ["消费"], "etf_codes": ["159928"]}},
            }
            self.monitor = NewsMonitor()

    def test_no_llm_fallback(self):
        classified = [
            {
                "title": "消费回暖", "content": "消费数据向好",
                "source": "cls", "publish_time": None, "url": "",
                "category": "finance", "matched_sectors": ["消费"],
                "matched_etf_codes": ["159928"],
            },
        ]
        results = self.monitor._no_llm_fallback(classified)
        assert len(results) == 1
        assert results[0]["sentiment"] == 0.0
        assert results[0]["summary"] == "消费回暖"
