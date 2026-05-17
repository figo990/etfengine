"""LLM 分析器测试（不依赖真实 API 调用）"""

import json

from src.intelligence.llm_analyzer import LLMAnalyzer, NewsAnalysisResult


class TestNewsAnalysisResult:
    def test_dataclass_creation(self):
        result = NewsAnalysisResult(
            title="测试",
            summary="摘要",
            sentiment=0.5,
            impact_level="high",
            related_sectors=["消费"],
            related_etf_codes=["159928"],
            is_policy=True,
        )
        assert result.sentiment == 0.5
        assert result.impact_level == "high"
        assert "消费" in result.related_sectors


class TestLLMAnalyzerParsing:
    """测试 LLM 响应解析逻辑（不调用真实 API）"""

    def setup_method(self):
        self.analyzer = LLMAnalyzer()

    def test_parse_valid_json(self):
        raw = json.dumps(
            {
                "summary": "测试摘要",
                "sentiment": 0.6,
                "impact_level": "high",
                "related_sectors": ["半导体"],
                "related_etf_codes": ["512480"],
                "is_policy": False,
            }
        )
        result = self.analyzer._parse_result("标题", raw)
        assert result.summary == "测试摘要"
        assert result.sentiment == 0.6
        assert result.impact_level == "high"
        assert "半导体" in result.related_sectors

    def test_parse_markdown_wrapped_json(self):
        raw = """```json
{"summary": "包裹摘要", "sentiment": -0.3, "impact_level": "medium",
 "related_sectors": [], "related_etf_codes": [], "is_policy": true}
```"""
        result = self.analyzer._parse_result("标题2", raw)
        assert result.summary == "包裹摘要"
        assert result.sentiment == -0.3
        assert result.is_policy is True

    def test_parse_invalid_json_fallback(self):
        result = self.analyzer._parse_result("标题3", "this is not json")
        assert result.title == "标题3"
        assert result.summary == "标题3"
        assert result.sentiment == 0.0
        assert result.impact_level == "low"

    def test_dict_to_result(self):
        data = {
            "summary": "dict摘要",
            "sentiment": 0.1,
            "impact_level": "low",
            "related_sectors": ["新能源", "军工"],
            "related_etf_codes": ["516160"],
            "is_policy": False,
        }
        result = self.analyzer._dict_to_result("test", data, "raw")
        assert result.summary == "dict摘要"
        assert len(result.related_sectors) == 2

    def test_dict_to_result_missing_fields(self):
        result = self.analyzer._dict_to_result("test", {}, "raw")
        assert result.title == "test"
        assert result.sentiment == 0.0
        assert result.related_sectors == []
