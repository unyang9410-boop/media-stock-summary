from __future__ import annotations

import json

from openai import OpenAI
from pydantic import ValidationError

from src.models import AnalysisResult


ANALYSIS_SYSTEM_PROMPT = """
你是繁體中文投資研究助理。請閱讀影音逐字稿，產生內容摘要並萃取提到的股票。

規則：
1. 全部輸出使用繁體中文。
2. 股票辨識以台股優先，若內容明確提及美股或其他市場也要列出。
3. 股票代號未知時填入 unknown，不要猜測。
4. 八大面向若逐字稿沒有明確資訊，填入「逐字稿未明確提及」。
5. 不要使用逐字稿以外的資訊補完公司基本面。
6. 只回傳符合指定 JSON schema 的 JSON，不要 Markdown。
""".strip()


def _analysis_user_prompt(transcript: str) -> str:
    return f"""
請分析以下逐字稿，輸出 JSON。

逐字稿：
{transcript}
""".strip()


def _extract_message_content(response: object) -> str:
    choices = getattr(response, "choices", None)
    if not choices and isinstance(response, dict):
        choices = response.get("choices")

    if not choices:
        raise ValueError("OpenAI 回應缺少 choices。")

    message = choices[0].message if hasattr(choices[0], "message") else choices[0]["message"]
    content = message.content if hasattr(message, "content") else message.get("content")

    if not content:
        raise ValueError("OpenAI 回應內容為空。")

    return content


def analyze_transcript(client: OpenAI, transcript: str, model: str) -> AnalysisResult:
    schema = AnalysisResult.model_json_schema()

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
                {"role": "user", "content": _analysis_user_prompt(transcript)},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "media_stock_analysis",
                    "schema": schema,
                },
            },
        )
        raw_content = _extract_message_content(response)
        payload = json.loads(raw_content)
        return AnalysisResult.model_validate(payload)
    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        raise RuntimeError(f"AI 分析結果格式不正確：{exc}") from exc
    except Exception as exc:  # pragma: no cover - OpenAI SDK exceptions vary by version
        raise RuntimeError(f"OpenAI 內容分析失敗：{exc}") from exc

