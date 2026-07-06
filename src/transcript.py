from __future__ import annotations

import io
import mimetypes
import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from openai import OpenAI
from youtube_transcript_api import NoTranscriptFound, TranscriptsDisabled, YouTubeTranscriptApi

from src.models import SourceType, TranscriptResult


YOUTUBE_LANGUAGE_PRIORITY = ("zh-Hant", "zh-TW", "zh", "zh-Hans", "en")
DEFAULT_HTTP_TIMEOUT = 60
APPLE_LOOKUP_URL = "https://itunes.apple.com/lookup"
AUDIO_EXTENSIONS = (".mp3", ".m4a", ".aac", ".wav", ".ogg", ".oga", ".flac", ".webm", ".mp4")
AUDIO_META_KEYS = {
    "audio",
    "og:audio",
    "og:audio:url",
    "og:audio:secure_url",
    "twitter:player:stream",
}


class TranscriptError(RuntimeError):
    """Raised when a transcript cannot be fetched or generated."""


class PodcastAudioLinkParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.candidates: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.lower(): value for key, value in attrs if value}
        tag_name = tag.lower()

        if tag_name == "meta":
            meta_key = (
                attributes.get("property")
                or attributes.get("name")
                or attributes.get("itemprop")
                or ""
            ).lower()
            if meta_key in AUDIO_META_KEYS:
                self._add_candidate(attributes.get("content"))

        if tag_name in {"audio", "source"}:
            self._add_candidate(attributes.get("src"))

        if tag_name == "a":
            href = attributes.get("href")
            if href and _looks_like_audio_url(href):
                self._add_candidate(href)

        if tag_name == "link":
            rel = attributes.get("rel", "").lower()
            content_type = attributes.get("type", "").lower()
            if ("enclosure" in rel or content_type.startswith("audio/")) and attributes.get("href"):
                self._add_candidate(attributes.get("href"))

    def _add_candidate(self, value: str | None) -> None:
        if not value:
            return
        resolved = urljoin(self.base_url, value.strip())
        if resolved and resolved not in self.candidates:
            self.candidates.append(resolved)


def _is_audio_content_type(content_type: str) -> bool:
    normalized = content_type.split(";")[0].strip().lower()
    return (
        normalized.startswith("audio/")
        or normalized in {"application/octet-stream", "video/mp4"}
        or "mpeg" in normalized
    )


def _looks_like_audio_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.path.lower().endswith(AUDIO_EXTENSIONS)


def _extract_audio_url_from_xml(content: bytes, base_url: str) -> str | None:
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return None

    for element in root.iter():
        tag_name = element.tag.rsplit("}", 1)[-1].lower()
        url = element.attrib.get("url") or element.attrib.get("href")
        content_type = element.attrib.get("type", "")
        if not url:
            continue
        if tag_name in {"enclosure", "content"} and (
            content_type.startswith("audio/") or _looks_like_audio_url(url)
        ):
            return urljoin(base_url, url)

    return None


def _extract_audio_url_from_html(content: bytes, base_url: str) -> str | None:
    parser = PodcastAudioLinkParser(base_url)
    parser.feed(content.decode("utf-8", errors="ignore"))
    return parser.candidates[0] if parser.candidates else None


def _apple_podcast_ids(url: str) -> tuple[str | None, str | None]:
    parsed = urlparse(url)
    if not parsed.netloc.lower().endswith("podcasts.apple.com"):
        return None, None

    collection_match = re.search(r"/id(\d+)", parsed.path)
    collection_id = collection_match.group(1) if collection_match else None
    episode_id = parse_qs(parsed.query).get("i", [None])[0]
    return collection_id, episode_id


def _resolve_apple_podcast_audio_url(url: str, timeout: int) -> str | None:
    collection_id, episode_id = _apple_podcast_ids(url)
    if not collection_id:
        return None

    try:
        response = requests.get(
            APPLE_LOOKUP_URL,
            params={"id": collection_id, "entity": "podcastEpisode", "limit": 20},
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
    except (ValueError, requests.RequestException) as exc:
        raise TranscriptError(f"Apple Podcasts 連結解析失敗：{exc}") from exc

    episodes = [
        item
        for item in payload.get("results", [])
        if item.get("kind") == "podcast-episode" and item.get("episodeUrl")
    ]
    if episode_id:
        for episode in episodes:
            if str(episode.get("trackId")) == episode_id:
                return str(episode["episodeUrl"])
        raise TranscriptError("找不到這個 Apple Podcasts 單集的音訊連結。請改貼該節目的 RSS 或直接音檔 URL。")

    if episodes:
        return str(episodes[0]["episodeUrl"])

    for item in payload.get("results", []):
        feed_url = item.get("feedUrl")
        if feed_url:
            return str(feed_url)

    raise TranscriptError("找不到這個 Apple Podcasts 節目的 RSS 或音訊連結。")


def resolve_podcast_audio_url(url: str, content: bytes, content_type: str, timeout: int = DEFAULT_HTTP_TIMEOUT) -> str:
    apple_audio_url = _resolve_apple_podcast_audio_url(url, timeout)
    if apple_audio_url:
        return apple_audio_url

    base_url = url
    xml_audio_url = _extract_audio_url_from_xml(content, base_url)
    if xml_audio_url:
        return xml_audio_url

    html_audio_url = _extract_audio_url_from_html(content, base_url)
    if html_audio_url:
        return html_audio_url

    type_hint = f"（Content-Type: {content_type}）" if content_type else ""
    raise TranscriptError(f"找不到可用的 Podcast 音訊連結{type_hint}。請貼上含音訊播放器的單集頁、RSS enclosure，或直接音檔 URL。")


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
    is_probably_audio = _is_audio_content_type(content_type) or (
        not content_type and _looks_like_audio_url(url)
    )
    if not is_probably_audio:
        resolved_url = resolve_podcast_audio_url(
            getattr(response, "url", url),
            response.content,
            content_type,
            timeout=timeout,
        )
        if resolved_url.strip() == url.strip():
            raise TranscriptError("Podcast 節目頁解析到原始網址，無法取得直接音訊檔。")
        return download_audio_to_memory(resolved_url, timeout=timeout)

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
