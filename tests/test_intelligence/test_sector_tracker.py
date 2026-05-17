"""行业政策追踪器测试"""

from unittest.mock import patch

from src.intelligence.sector_tracker import PolicyAlert, SectorTracker


class TestSectorTracker:
    def setup_method(self):
        with patch("src.intelligence.sector_tracker.load_yaml_config") as mock_cfg:
            mock_cfg.return_value = {
                "sectors": {
                    "消费": {"keywords": ["消费", "白酒", "食品"], "etf_codes": ["159928"]},
                    "医药": {"keywords": ["医药", "创新药"], "etf_codes": ["512010"]},
                    "半导体": {"keywords": ["芯片", "半导体"], "etf_codes": ["512480"]},
                },
                "policy_sources_weight": {
                    "国务院": 1.5,
                    "发改委": 1.3,
                    "央行": 1.3,
                },
            }
            self.tracker = SectorTracker()

    def test_track_policy_news(self):
        analyzed = [
            {
                "title": "国务院发布促消费措施",
                "content": "消费领域重大政策",
                "source": "cctv",
                "sentiment": 0.8,
                "impact_level": "high",
                "is_policy": True,
                "category": "policy",
                "related_sectors": ["消费"],
                "summary": "促消费政策",
            },
        ]
        alerts = self.tracker.track(analyzed)
        assert "消费" in alerts
        assert len(alerts["消费"]) == 1
        assert alerts["消费"][0].sentiment == 0.8

    def test_track_source_weight(self):
        analyzed = [
            {
                "title": "国务院出台芯片补贴政策",
                "content": "半导体国产替代加速",
                "source": "cctv",
                "sentiment": 0.7,
                "impact_level": "high",
                "is_policy": True,
                "category": "policy",
                "related_sectors": ["半导体"],
                "summary": "芯片补贴",
            },
        ]
        alerts = self.tracker.track(analyzed)
        alert = alerts["半导体"][0]
        assert alert.impact_score > 0.7 * 1.0  # should be boosted by 国务院 weight

    def test_track_skips_low_impact_non_policy(self):
        analyzed = [
            {
                "title": "天气不错",
                "content": "今天晴朗",
                "source": "random",
                "sentiment": 0.1,
                "impact_level": "low",
                "is_policy": False,
                "category": "finance",
                "related_sectors": [],
                "summary": "天气",
            },
        ]
        alerts = self.tracker.track(analyzed)
        total = sum(len(v) for v in alerts.values())
        assert total == 0

    def test_get_sector_summary(self):
        alerts = {
            "消费": [
                PolicyAlert(
                    title="促消费",
                    summary="摘要",
                    sector="消费",
                    sentiment=0.8,
                    impact_score=1.2,
                    source="cctv",
                ),
                PolicyAlert(
                    title="零售",
                    summary="摘要2",
                    sector="消费",
                    sentiment=0.3,
                    impact_score=0.3,
                    source="cls",
                ),
            ],
            "医药": [
                PolicyAlert(
                    title="集采",
                    summary="摘要3",
                    sector="医药",
                    sentiment=-0.5,
                    impact_score=0.7,
                    source="eastmoney",
                ),
            ],
        }
        summaries = self.tracker.get_sector_summary(alerts)
        assert len(summaries) == 2

        sector_names = {s["sector"] for s in summaries}
        assert "消费" in sector_names
        assert "医药" in sector_names

        consumer = next(s for s in summaries if s["sector"] == "消费")
        assert consumer["alert_count"] == 2
        assert consumer["avg_sentiment"] > 0
        assert consumer["impact_direction"] == "利多"

        pharma = next(s for s in summaries if s["sector"] == "医药")
        assert pharma["impact_direction"] == "利空"

    def test_match_sectors_keyword(self):
        matched = self.tracker._match_sectors("白酒行业", "消费数据向好")
        assert "消费" in matched

    def test_calc_source_weight_default(self):
        w = self.tracker._calc_source_weight("cls", "普通新闻")
        assert w == 1.0

    def test_calc_source_weight_policy(self):
        w = self.tracker._calc_source_weight("cctv", "国务院发布政策")
        assert w == 1.5
