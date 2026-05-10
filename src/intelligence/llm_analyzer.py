"""LLM 智能分析器：新闻摘要、情绪打分、影响评级"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from loguru import logger

from src.core.config import load_yaml_config


@dataclass
class NewsAnalysisResult:
    """LLM 新闻分析结果"""
    title: str
    summary: str                    # 1-2句摘要
    sentiment: float                # -1(利空) ~ 0(中性) ~ +1(利多)
    impact_level: str               # high | medium | low
    related_sectors: list[str]      # 关联行业
    related_etf_codes: list[str]    # 关联ETF代码
    is_policy: bool                 # 是否政策类新闻
    raw_response: str = ""


ANALYSIS_PROMPT = """你是一位专业的A股ETF投资分析师。请分析以下财经新闻，返回JSON格式结果。

新闻标题: {title}
新闻内容: {content}

请返回严格的JSON（不要markdown包裹），格式如下：
{{
    "summary": "一句话摘要（不超过50字）",
    "sentiment": 0.0,
    "impact_level": "low",
    "related_sectors": [],
    "related_etf_codes": [],
    "is_policy": false
}}

字段说明：
- summary: 一句话核心信息
- sentiment: -1.0(重大利空) 到 +1.0(重大利多)，0为中性
- impact_level: "high"(重大影响)/"medium"(一般影响)/"low"(影响较小)
- related_sectors: 受影响的行业，如["消费","医药"]
- related_etf_codes: 受影响的ETF代码，如["510300","512010"]
- is_policy: 是否为政策法规类新闻"""


BATCH_PROMPT = """你是专业的A股ETF投资分析师。请逐条分析以下新闻，为每条返回JSON。

{news_list}

请返回一个JSON数组，每条新闻一个对象，格式同上。只返回JSON数组，不要其他内容。"""


class LLMAnalyzer:
    """基于 LLM 的新闻智能分析器

    使用 DeepSeek/通义等 API（兼容 OpenAI SDK 格式）
    """

    def __init__(self) -> None:
        intel_config = load_yaml_config("intelligence.yaml")
        self._llm_config = intel_config.get("llm", {})
        self._client = None

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client

        try:
            from openai import OpenAI
        except ImportError:
            raise RuntimeError(
                "需要安装 openai 包: pip install openai"
            )

        api_key_env = self._llm_config.get("api_key_env", "DEEPSEEK_API_KEY")
        api_key = os.environ.get(api_key_env, "")
        if not api_key:
            raise ValueError(
                f"未设置环境变量 {api_key_env}，请设置 LLM API Key"
            )

        base_url = self._llm_config.get("base_url", "https://api.deepseek.com")
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        return self._client

    def analyze_single(self, title: str, content: str) -> NewsAnalysisResult:
        """分析单条新闻"""
        prompt = ANALYSIS_PROMPT.format(
            title=title,
            content=content[:1000],  # 截断过长内容
        )

        raw = self._call_llm(prompt)
        return self._parse_result(title, raw)

    def analyze_batch(self, articles: list[dict]) -> list[NewsAnalysisResult]:
        """批量分析新闻（更经济）"""
        if not articles:
            return []

        news_lines = []
        for i, art in enumerate(articles):
            news_lines.append(
                f"[{i+1}] 标题: {art['title']}\n内容: {art.get('content', '')[:300]}"
            )
        news_text = "\n\n".join(news_lines)

        prompt = BATCH_PROMPT.format(news_list=news_text)
        raw = self._call_llm(prompt)

        results = []
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                for i, item in enumerate(parsed):
                    title = articles[i]["title"] if i < len(articles) else ""
                    results.append(self._dict_to_result(title, item, raw))
            else:
                # 单条返回
                results.append(self._dict_to_result(articles[0]["title"], parsed, raw))
        except json.JSONDecodeError:
            logger.warning(f"LLM 批量分析返回非JSON: {raw[:200]}")
            for art in articles:
                results.append(NewsAnalysisResult(
                    title=art["title"],
                    summary=art["title"],
                    sentiment=0.0,
                    impact_level="low",
                    related_sectors=[],
                    related_etf_codes=[],
                    is_policy=False,
                    raw_response=raw,
                ))

        return results

    def _call_llm(self, prompt: str) -> str:
        """调用 LLM API"""
        client = self._get_client()
        model = self._llm_config.get("model", "deepseek-chat")
        max_tokens = self._llm_config.get("max_tokens", 500)
        temperature = self._llm_config.get("temperature", 0.1)

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            return "{}"

    def _parse_result(self, title: str, raw: str) -> NewsAnalysisResult:
        """解析单条 LLM 响应"""
        try:
            # 去除可能的 markdown 包裹
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                cleaned = "\n".join(lines[1:-1])

            data = json.loads(cleaned)
            return self._dict_to_result(title, data, raw)
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"LLM 解析失败 ({title}): {e}")
            return NewsAnalysisResult(
                title=title,
                summary=title,
                sentiment=0.0,
                impact_level="low",
                related_sectors=[],
                related_etf_codes=[],
                is_policy=False,
                raw_response=raw,
            )

    def _dict_to_result(self, title: str, data: dict, raw: str) -> NewsAnalysisResult:
        return NewsAnalysisResult(
            title=title,
            summary=str(data.get("summary", title))[:100],
            sentiment=float(data.get("sentiment", 0.0)),
            impact_level=str(data.get("impact_level", "low")),
            related_sectors=list(data.get("related_sectors", [])),
            related_etf_codes=list(data.get("related_etf_codes", [])),
            is_policy=bool(data.get("is_policy", False)),
            raw_response=raw,
        )
