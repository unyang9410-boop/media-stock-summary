from __future__ import annotations

import json
from types import SimpleNamespace

from src.analyzer import analyze_transcript
from src.models import AnalysisResult


def test_analyze_transcript_validates_openai_json() -> None:
    payload = {
        "summary": {
            "title": "AI 伺服器供應鏈",
            "key_points": ["討論台股 AI 供應鏈。"],
            "investment_observations": ["市場關注營收成長。"],
        },
        "stocks": [
            {
                "company_name": "台積電",
                "ticker": "2330",
                "market": "TWSE",
                "mention_reason": "逐字稿提到先進製程需求。",
                "aspects": {
                    "business_model": "晶圓代工。",
                    "revenue_structure": "逐字稿未明確提及",
                    "growth_drivers": "AI 晶片需求。",
                    "end_markets": "資料中心。",
                    "customers": "逐字稿未明確提及",
                    "competitive_advantages": "逐字稿未明確提及",
                    "management_guidance": "逐字稿未明確提及",
                    "technical_analysis": "逐字稿未明確提及",
                },
            }
        ],
    }

    class FakeCompletions:
        def create(self, **kwargs: object) -> SimpleNamespace:
            assert kwargs["model"] == "gpt-4o"
            assert kwargs["response_format"]["type"] == "json_schema"
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content=json.dumps(payload, ensure_ascii=False))
                    )
                ]
            )

    fake_client = SimpleNamespace(
        chat=SimpleNamespace(completions=FakeCompletions())
    )

    result = analyze_transcript(fake_client, "逐字稿", "gpt-4o")

    assert isinstance(result, AnalysisResult)
    assert result.stocks[0].ticker == "2330"

