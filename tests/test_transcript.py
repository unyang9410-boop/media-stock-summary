from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.transcript import (
    TranscriptError,
    download_audio_to_memory,
    fetch_youtube_transcript,
    parse_youtube_video_id,
    resolve_podcast_audio_url,
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


def test_download_audio_to_memory_accepts_audio_extension_without_content_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponse:
        headers = {}
        content = b"audio-bytes"

        def raise_for_status(self) -> None:
            return None

    monkeypatch.setattr("src.transcript.requests.get", lambda *args, **kwargs: FakeResponse())

    audio_file = download_audio_to_memory("https://example.com/episode.m4a")

    assert audio_file.read() == b"audio-bytes"
    assert audio_file.name == "episode.m4a"


def test_download_audio_to_memory_resolves_html_episode_page(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = {
        "https://example.com/episode": SimpleNamespace(
            url="https://example.com/episode",
            headers={"Content-Type": "text/html; charset=utf-8"},
            content=b'<html><head><meta property="og:audio" content="/media/episode.mp3"></head></html>',
            raise_for_status=lambda: None,
        ),
        "https://example.com/media/episode.mp3": SimpleNamespace(
            url="https://example.com/media/episode.mp3",
            headers={"Content-Type": "audio/mpeg"},
            content=b"audio-from-page",
            raise_for_status=lambda: None,
        ),
    }
    calls = []

    def fake_get(url: str, stream: bool, timeout: int) -> SimpleNamespace:
        calls.append((url, stream, timeout))
        return responses[url]

    monkeypatch.setattr("src.transcript.requests.get", fake_get)

    audio_file = download_audio_to_memory("https://example.com/episode")

    assert [call[0] for call in calls] == [
        "https://example.com/episode",
        "https://example.com/media/episode.mp3",
    ]
    assert audio_file.read() == b"audio-from-page"
    assert audio_file.name == "episode.mp3"


def test_download_audio_to_memory_resolves_rss_enclosure(monkeypatch: pytest.MonkeyPatch) -> None:
    rss = b"""
    <rss>
      <channel>
        <item>
          <enclosure url="https://cdn.example.com/show.m4a" type="audio/mp4" />
        </item>
      </channel>
    </rss>
    """
    responses = {
        "https://example.com/feed.xml": SimpleNamespace(
            url="https://example.com/feed.xml",
            headers={"Content-Type": "application/rss+xml"},
            content=rss,
            raise_for_status=lambda: None,
        ),
        "https://cdn.example.com/show.m4a": SimpleNamespace(
            url="https://cdn.example.com/show.m4a",
            headers={"Content-Type": "audio/mp4"},
            content=b"rss-audio",
            raise_for_status=lambda: None,
        ),
    }

    monkeypatch.setattr("src.transcript.requests.get", lambda url, **kwargs: responses[url])

    audio_file = download_audio_to_memory("https://example.com/feed.xml")

    assert audio_file.read() == b"rss-audio"
    assert audio_file.name == "show.m4a"


def test_resolve_podcast_audio_url_supports_apple_podcasts_show(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_get(url: str, **kwargs: object) -> SimpleNamespace:
        assert url == "https://itunes.apple.com/lookup"
        assert kwargs["params"] == {"id": "1500839292", "entity": "podcastEpisode", "limit": 20}

        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {
                "results": [
                    {"kind": "podcast", "feedUrl": "https://example.com/feed.xml"},
                    {
                        "kind": "podcast-episode",
                        "trackId": 1001,
                        "episodeUrl": "https://cdn.example.com/latest.mp3",
                    },
                ]
            },
        )

    monkeypatch.setattr("src.transcript.requests.get", fake_get)

    audio_url = resolve_podcast_audio_url(
        "https://podcasts.apple.com/tw/podcast/gooaye/id1500839292",
        b"<html></html>",
        "text/html",
    )

    assert audio_url == "https://cdn.example.com/latest.mp3"


def test_resolve_podcast_audio_url_supports_apple_podcasts_episode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_get(url: str, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {
                "results": [
                    {
                        "kind": "podcast-episode",
                        "trackId": 1001,
                        "episodeUrl": "https://cdn.example.com/latest.mp3",
                    },
                    {
                        "kind": "podcast-episode",
                        "trackId": 1002,
                        "episodeUrl": "https://cdn.example.com/chosen.mp3",
                    },
                ]
            },
        )

    monkeypatch.setattr("src.transcript.requests.get", fake_get)

    audio_url = resolve_podcast_audio_url(
        "https://podcasts.apple.com/tw/podcast/gooaye/id1500839292?i=1002",
        b"<html></html>",
        "text/html",
    )

    assert audio_url == "https://cdn.example.com/chosen.mp3"


def test_download_audio_to_memory_rejects_page_without_audio(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        url = "https://example.com/not-audio"
        headers = {"Content-Type": "text/html"}
        content = b"<html></html>"

        def raise_for_status(self) -> None:
            return None

    monkeypatch.setattr("src.transcript.requests.get", lambda *args, **kwargs: FakeResponse())

    with pytest.raises(TranscriptError, match="找不到可用"):
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
