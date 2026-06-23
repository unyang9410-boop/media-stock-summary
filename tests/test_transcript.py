from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.transcript import (
    TranscriptError,
    download_audio_to_memory,
    fetch_youtube_transcript,
    parse_youtube_video_id,
    transcribe_audio_file,
)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ],
)
def test_parse_youtube_video_id(url: str, expected: str) -> None:
    assert parse_youtube_video_id(url) == expected


def test_parse_youtube_video_id_rejects_invalid_url() -> None:
    with pytest.raises(TranscriptError):
        parse_youtube_video_id("https://example.com/video")


def test_fetch_youtube_transcript_uses_current_api(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {}

    class FakeTranscriptApi:
        def fetch(self, video_id: str, languages: list[str]) -> list[SimpleNamespace]:
            calls["video_id"] = video_id
            calls["languages"] = languages
            return [
                SimpleNamespace(text="第一段字幕"),
                SimpleNamespace(text="第二段字幕"),
            ]

    monkeypatch.setattr("src.transcript.YouTubeTranscriptApi", FakeTranscriptApi)

    result = fetch_youtube_transcript("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    assert result.source_type == "youtube"
    assert result.text == "第一段字幕\n第二段字幕"
    assert calls["video_id"] == "dQw4w9WgXcQ"
    assert calls["languages"][0] == "zh-Hant"


def test_download_audio_to_memory_success(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        headers = {"Content-Type": "audio/mpeg"}
        content = b"audio-bytes"

        def raise_for_status(self) -> None:
            return None

    def fake_get(url: str, stream: bool, timeout: int) -> FakeResponse:
        assert stream is True
        assert timeout == 60
        return FakeResponse()

    monkeypatch.setattr("src.transcript.requests.get", fake_get)

    audio_file = download_audio_to_memory("https://example.com/episode.mp3")

    assert audio_file.read() == b"audio-bytes"
    assert audio_file.name == "episode.mp3"


def test_download_audio_to_memory_rejects_non_audio(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        headers = {"Content-Type": "text/html"}
        content = b"<html></html>"

        def raise_for_status(self) -> None:
            return None

    monkeypatch.setattr("src.transcript.requests.get", lambda *args, **kwargs: FakeResponse())

    with pytest.raises(TranscriptError, match="不是音訊格式"):
        download_audio_to_memory("https://example.com/not-audio")


def test_transcribe_audio_file_uses_openai_client() -> None:
    calls = {}

    class FakeTranscriptions:
        def create(self, model: str, file: object) -> SimpleNamespace:
            calls["model"] = model
            calls["file"] = file
            return SimpleNamespace(text="逐字稿內容")

    fake_client = SimpleNamespace(audio=SimpleNamespace(transcriptions=FakeTranscriptions()))
    audio_file = SimpleNamespace(name="episode.mp3")

    text = transcribe_audio_file(fake_client, audio_file, "whisper-1")

    assert text == "逐字稿內容"
    assert calls == {"model": "whisper-1", "file": audio_file}

