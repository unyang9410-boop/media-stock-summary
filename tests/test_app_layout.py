from __future__ import annotations

from streamlit.testing.v1 import AppTest

from app import _analysis_json, _validate_source_url
from src.models import AnalysisResult


def test_home_screen_renders_main_layout() -> None:
    app = AppTest.from_file("app.py")
    app.run()

    assert not app.exception
    assert "輸入模式" in [radio.label for radio in app.radio]
    assert "網址" in [text_input.label for text_input in app.text_input]
    assert app.button[0].label == "開始分析"
    assert app.button[0].disabled is True
    assert "內容分析模型" in [text_input.label for text_input in app.sidebar.text_input]
    assert "音訊轉錄模型" in [text_input.label for text_input in app.sidebar.text_input]
    assert app.warning


def test_validate_source_url() -> None:
    assert _validate_source_url("youtube", "https://www.youtube.com/watch?v=dQw4w9WgXcQ") is None
    assert _validate_source_url("youtube", "https://youtu.be/dQw4w9WgXcQ") is None
    assert _validate_source_url("podcast", "https://example.com/episode.mp3") is None
    assert "完整" in (_validate_source_url("podcast", "example.com/episode.mp3") or "")
    assert "YouTube" in (_validate_source_url("youtube", "https://example.com/episode.mp3") or "")


def test_analysis_json_preserves_traditional_chinese() -> None:
    result = AnalysisResult.model_validate(
        {
            "summary": {
                "title": "台股供應鏈",
                "key_points": ["重點一"],
                "investment_observations": [],
            },
            "stocks": [],
        }
    )

    payload = _analysis_json(result)

    assert "台股供應鏈" in payload
    assert "\\u53f0" not in payload
