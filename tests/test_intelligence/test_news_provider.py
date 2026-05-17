"""新闻数据源测试"""

from datetime import datetime

from src.data.providers.news_provider import NewsArticle, NewsProvider


class TestNewsArticle:
    def test_dataclass_creation(self):
        art = NewsArticle(
            title="测试新闻标题",
            content="测试内容",
            source="eastmoney",
            publish_time=datetime(2025, 5, 10, 15, 30),
            category="finance",
        )
        assert art.title == "测试新闻标题"
        assert art.source == "eastmoney"
        assert art.publish_time == datetime(2025, 5, 10, 15, 30)

    def test_default_values(self):
        art = NewsArticle(title="仅标题")
        assert art.content == ""
        assert art.url == ""
        assert art.raw_data == {}


class TestNewsProvider:
    def setup_method(self):
        self.provider = NewsProvider()

    def test_parse_time_none(self):
        assert self.provider._parse_time(None) is None

    def test_parse_time_standard(self):
        result = self.provider._parse_time("2025-05-10 15:30:00")
        assert result == datetime(2025, 5, 10, 15, 30)

    def test_parse_time_date_only(self):
        result = self.provider._parse_time("2025-05-10")
        assert result == datetime(2025, 5, 10)

    def test_parse_time_compact(self):
        result = self.provider._parse_time("20250510")
        assert result == datetime(2025, 5, 10)

    def test_parse_time_invalid(self):
        result = self.provider._parse_time("not_a_date")
        assert result is None

    def test_fetch_all_returns_list(self):
        result = self.provider.fetch_all(sources=[], max_per_source=0)
        assert isinstance(result, list)
