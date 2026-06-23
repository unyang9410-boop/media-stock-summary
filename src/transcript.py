from __future__ import annotations

import io
import mimetypes
import re
from urllib.parse import parse_qs, urlparse

import requests
from openai import OpenAI
from youtube_transcript_api import NoTranscriptFound, TranscriptsDisabled, YouTubeTranscriptApi

from src.models import SourceType, TranscriptResult


YOUTUBE_LANGUAGE_PRIORITY = ("zh-Hant", "zh-TW", "zh", "zh-Hans", "en")
DEFAULT_HTTP_TIMEOUT = 60


class TranscriptError(RuntimeError):
    """Raised when a transcript cannot be fetched or generated."""


def parse_youtube_video_id(url: str) -> str:
    parsed = urlparse(url.strip())
    host = parsed.netloc.lower()

    if host.endswith("youtu.be"):
        video_id = parsed.path.strip("/").split("/")[0]
    elif "youtube.com" in host:
        if parsed.path.startswith("/shorts/") or parsed.path.startswith("/embed/"):
            video_id = parsed.path.strip("/").split("/")[1]
        else:
            video_id = parse_qs(parsed.query).get("v", [""])[0]
    else:
        video_id = ""

    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id or ""):
        raise TranscriptError("無法從 YouTube 網址解析影片 ID。")

    return video_id


def fetch_youtube_transcript(url: str) -> TranscriptResult:
    video_id = parse_youtube_video_id(url)

    try:
        transcript = YouTubeTranscriptApi().fetch(
            video_id,
            languages=list(YOUTUBE_LANGUAGE_PRIORITY),
        )
    except (NoTranscriptFound, TranscriptsDisabled) as exc:
        raise TranscriptError("此 YouTube 影片沒有可用字幕，無法產生逐字稿。") from exc
    except Exception as exc:  # pragma: no cover - library raises several transport errors
        raise TranscriptError(f"YouTube 字幕讀取失敗：{exc}") from exc

    text = "\n".join(item.text.strip() for item in transcript if item.text)
    if not text:
        raise TranscriptError("YouTube 字幕內容為空。")

    return TranscriptResult(source_type="youtube", source_url=url, text=text)


def _filename_from_url(url: str, content_type: str | None) -> str:
    path_name = urlparse(url).path.rsplit("/", 1)[-1]
    if path_name and "." in path_name:
        return path_name

    extension = mimetypes.guess_extension((content_type or "").split(";")[0].strip()) or ".mp3"
    return f"podcast{extension}"


def download_audio_to_memory(url: str, timeout: int = DEFAULT_HTTP_TIMEOUT) -> io.BytesIO:
    try:
        response = requests.get(url, stream=True, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise TranscriptError(f"Podcast 音檔下載失敗：{exc}") from exc

    content_type = response.headers.get("Content-Type", "")
    if content_type and not (
        content_type.startswith("audio/")
        or "octet-stream" in content_type
        or "mpeg" in content_type
    ):
        raise TranscriptError(f"Podcast URL 回傳的內容不是音訊格式：{content_type}")

    audio_file = io.BytesIO(response.content)
    audio_file.name = _filename_from_url(url, content_type)
    audio_file.seek(0)
    return audio_file


def transcribe_audio_file(client: OpenAI, audio_file: io.BytesIO, model: str) -> str:
    try:
        result = client.audio.transcriptions.create(
            model=model,
            file=audio_file,
        )
    except Exception as exc:  # pragma: no cover - OpenAI SDK exceptions vary by version
        raise TranscriptError(f"OpenAI 音訊轉錄失敗：{exc}") from exc

    text = getattr(result, "text", None)
    if text is None and isinstance(result, dict):
        text = result.get("text")

    if not text:
        raise TranscriptError("OpenAI 音訊轉錄結果為空。")

    return text


def transcribe_podcast_url(url: str, client: OpenAI, model: str) -> TranscriptResult:
    audio_file = download_audio_to_memory(url)
    text = transcribe_audio_file(client, audio_file, model)
    return TranscriptResult(source_type="podcast", source_url=url, text=text)


def fetch_transcript(source_type: SourceType, url: str, client: OpenAI, transcribe_model: str) -> TranscriptResult:
    if source_type == "youtube":
        return fetch_youtube_transcript(url)
    if source_type == "podcast":
        return transcribe_podcast_url(url, client, transcribe_model)
    raise TranscriptError("不支援的輸入模式。")
