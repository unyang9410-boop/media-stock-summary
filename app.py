from __future__ import annotations

import html
import json
import os
from urllib.parse import urlparse

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

from src.analyzer import analyze_transcript
from src.models import AnalysisResult, MentionedStock, SourceType, TranscriptResult
from src.transcript import TranscriptError, fetch_transcript


load_dotenv()

DEFAULT_ANALYSIS_MODEL = "gpt-4o"
DEFAULT_TRANSCRIBE_MODEL = "whisper-1"
YOUTUBE_LABEL = "YouTube 影片網址"
PODCAST_LABEL = "Podcast 網址或節目連結"


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --app-bg: #fffaf3;
            --surface: #ffffff;
            --surface-soft: #fff8ef;
            --text: #26332f;
            --muted: #66736f;
            --border: #eadfd2;
            --accent: #df7058;
            --accent-soft: #ffe2d8;
            --accent-deep: #a84f3f;
            --success-soft: #e9f7ef;
            --shadow: 0 18px 42px rgba(92, 65, 38, .08);
        }

        .stApp {
            background:
                radial-gradient(circle at top left, rgba(255, 226, 216, .66), transparent 28rem),
                radial-gradient(circle at bottom right, rgba(236, 248, 238, .7), transparent 24rem),
                linear-gradient(180deg, #fffaf3 0%, #fff7ee 52%, #fffaf3 100%);
            color: var(--text);
        }

        .block-container {
            max-width: 1120px;
            padding-top: 2rem;
            padding-bottom: 3.5rem;
        }

        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #fff2e4 0%, #fff9f1 100%);
            border-right: 1px solid var(--border);
        }

        section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3,
        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] p {
            color: var(--text) !important;
        }

        .app-hero {
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1.5rem 1.6rem;
            background:
                linear-gradient(135deg, rgba(255, 255, 255, .96), rgba(255, 248, 239, .96)),
                radial-gradient(circle at right top, rgba(255, 226, 216, .95), transparent 16rem);
            box-shadow: var(--shadow);
            margin-bottom: 1.1rem;
        }

        .app-hero h1 {
            color: var(--text);
            font-size: 2rem;
            font-weight: 760;
            line-height: 1.2;
            margin: 0 0 .45rem 0;
            letter-spacing: 0;
        }

        .app-hero p {
            color: var(--muted);
            margin: 0;
            line-height: 1.7;
            font-size: 1.02rem;
            max-width: 58rem;
        }

        .feature-row {
            display: flex;
            flex-wrap: wrap;
            gap: .5rem;
            margin-top: 1rem;
        }

        .feature-pill {
            border: 1px solid rgba(223, 112, 88, .24);
            background: rgba(255, 226, 216, .72);
            color: #7a3f32;
            border-radius: 999px;
            padding: .38rem .7rem;
            font-size: .9rem;
            font-weight: 680;
        }

        .section-title {
            font-size: 1rem;
            font-weight: 760;
            color: var(--text);
            margin: .15rem 0 .7rem 0;
        }

        .source-note {
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: .8rem .9rem;
            background: var(--surface-soft);
            color: var(--muted);
            line-height: 1.6;
            margin-top: .5rem;
        }

        .stat-card {
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: .85rem .95rem;
            background: rgba(255, 255, 255, .86);
        }

        .stat-label {
            color: var(--muted);
            font-size: .82rem;
            font-weight: 680;
            margin-bottom: .16rem;
        }

        .stat-value {
            color: var(--text);
            font-size: 1.22rem;
            font-weight: 760;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-color: var(--border);
            background: rgba(255, 255, 255, .78);
            box-shadow: 0 12px 32px rgba(92, 65, 38, .06);
        }

        div[data-testid="stTextInput"] input,
        div[data-testid="stTextArea"] textarea {
            background: #ffffff;
            border: 1px solid var(--border);
            color: var(--text);
            border-radius: 8px;
        }

        div[data-testid="stTextInput"] input:focus,
        div[data-testid="stTextArea"] textarea:focus {
            border-color: var(--accent);
            box-shadow: 0 0 0 3px rgba(223, 112, 88, .15);
        }

        div[data-testid="stTextArea"] textarea {
            font-family: "Consolas", "Menlo", monospace;
            line-height: 1.55;
        }

        div[data-testid="stRadio"] label,
        div[data-testid="stTextInput"] label,
        div[data-testid="stTextArea"] label {
            color: var(--text) !important;
            font-weight: 650;
        }

        .stButton button,
        .stDownloadButton button {
            border-radius: 8px;
            border: 1px solid rgba(223, 112, 88, .2);
            font-weight: 700;
        }

        .stButton button[kind="primary"] {
            background: var(--accent);
            color: #ffffff;
            border-color: var(--accent);
        }

        .stButton button[kind="primary"]:hover {
            background: #cf634e;
            border-color: #cf634e;
        }

        .stButton button:disabled,
        .stButton button[disabled],
        .stDownloadButton button:disabled,
        .stDownloadButton button[disabled] {
            background: #eadfd2 !important;
            border-color: #ded2c4 !important;
            color: #92857a !important;
            cursor: not-allowed !important;
            opacity: .72 !important;
            box-shadow: none !important;
        }

        .summary-box {
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1.05rem 1.15rem;
            background: var(--surface);
            box-shadow: 0 10px 24px rgba(92, 65, 38, .05);
            margin-bottom: 1rem;
        }

        .summary-box h2 {
            color: var(--text);
            font-size: 1.35rem;
            line-height: 1.35;
            margin: 0;
        }

        .aspect-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: .75rem;
            margin-top: .9rem;
        }

        .aspect-item {
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: .85rem .95rem;
            background: var(--surface);
            min-height: 6.4rem;
        }

        .aspect-label {
            font-size: .84rem;
            font-weight: 760;
            color: #7a4a3d;
            margin-bottom: .35rem;
        }

        .aspect-text {
            color: var(--text);
            line-height: 1.6;
            font-size: .95rem;
        }

        .stock-meta {
            color: var(--muted);
            line-height: 1.6;
            margin-bottom: .15rem;
        }

        div[data-testid="stExpander"] {
            border-color: var(--border);
            background: rgba(255, 255, 255, .82);
            border-radius: 8px;
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: .35rem;
        }

        .stTabs [data-baseweb="tab"] {
            border-radius: 8px;
            color: var(--muted);
            background: rgba(255, 255, 255, .64);
            border: 1px solid var(--border);
            padding: .45rem .85rem;
        }

        .stTabs [aria-selected="true"] {
            color: var(--accent-deep);
            background: var(--accent-soft);
            border-color: rgba(223, 112, 88, .3);
        }

        @media (max-width: 720px) {
            .block-container {
                padding-left: 1rem;
                padding-right: 1rem;
            }

            .app-hero {
                padding: 1rem;
            }

            .app-hero h1 {
                font-size: 1.55rem;
            }

            .aspect-grid {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _get_openai_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("找不到 OPENAI_API_KEY。請先在 .env 或環境變數中設定 OpenAI API key。")
    return OpenAI(api_key=api_key)


def _source_type_from_label(source_label: str) -> SourceType:
    return "youtube" if source_label.startswith("YouTube") else "podcast"


def _source_copy(source_type: SourceType) -> tuple[str, str, str]:
    if source_type == "youtube":
        return (
            "YouTube 影片網址",
            "https://www.youtube.com/watch?v=...",
            "系統會讀取影片內建字幕；若影片沒有字幕，會回報明確錯誤，不會改下載影片音訊。",
        )
    return (
        "Podcast 網址或節目連結",
        "https://example.com/episode 或 https://example.com/episode.mp3",
        "可貼上 Podcast 單集頁、RSS enclosure 或直接音檔 URL；系統會先解析音訊連結，再讀入記憶體並送 OpenAI 轉錄。",
    )


def _validate_source_url(source_type: SourceType, url: str) -> str | None:
    stripped_url = url.strip()
    if not stripped_url:
        return "請先貼上 YouTube 影片、Podcast 網址或節目連結。"

    parsed = urlparse(stripped_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return "請輸入完整的 http 或 https 網址。"

    host = parsed.netloc.lower()
    if source_type == "youtube" and "youtube.com" not in host and "youtu.be" not in host:
        return "YouTube 模式請貼上 youtube.com 或 youtu.be 網址。"

    return None


def _analysis_json(result: AnalysisResult) -> str:
    return json.dumps(result.model_dump(), ensure_ascii=False, indent=2)


def _render_hero() -> None:
    st.markdown(
        """
        <div class="app-hero">
            <h1>影音總結與台股萃取</h1>
            <p>貼上 YouTube 影片、Podcast 網址或節目連結，系統會取得逐字稿、產生繁體中文摘要，並整理逐字稿中提到的股票與八大分析面向。</p>
            <div class="feature-row">
                <span class="feature-pill">YouTube 字幕解析</span>
                <span class="feature-pill">Podcast 網址轉錄</span>
                <span class="feature-pill">台股優先萃取</span>
                <span class="feature-pill">八大面向分析</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_stats(analysis_result: AnalysisResult, transcript_result: TranscriptResult) -> None:
    source_name = "YouTube" if transcript_result.source_type == "youtube" else "Podcast"
    stat_items = [
        ("來源", source_name),
        ("逐字稿字數", f"{len(transcript_result.text):,}"),
        ("股票數", f"{len(analysis_result.stocks):,}"),
    ]
    columns = st.columns(len(stat_items), gap="medium")
    for column, (label, value) in zip(columns, stat_items):
        with column:
            st.markdown(
                f"""
                <div class="stat-card">
                    <div class="stat-label">{html.escape(label)}</div>
                    <div class="stat-value">{html.escape(value)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _render_summary(result: AnalysisResult) -> None:
    st.markdown(
        f"""
        <div class="summary-box">
            <h2>{html.escape(result.summary.title)}</h2>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns((1.2, 1), gap="large")
    with left:
        st.markdown('<div class="section-title">重點總結</div>', unsafe_allow_html=True)
        for point in result.summary.key_points:
            st.markdown(f"- {point}")

    with right:
        st.markdown('<div class="section-title">投資相關觀察</div>', unsafe_allow_html=True)
        if result.summary.investment_observations:
            for observation in result.summary.investment_observations:
                st.markdown(f"- {observation}")
        else:
            st.info("逐字稿未明確提及投資觀察。")


def _render_aspect_grid(stock: MentionedStock) -> None:
    aspects = [
        ("商業模式", stock.aspects.business_model),
        ("營收結構", stock.aspects.revenue_structure),
        ("成長動能", stock.aspects.growth_drivers),
        ("終端市場", stock.aspects.end_markets),
        ("客戶", stock.aspects.customers),
        ("競爭優勢", stock.aspects.competitive_advantages),
        ("管理層指引", stock.aspects.management_guidance),
        ("技術分析", stock.aspects.technical_analysis),
    ]
    cells = "\n".join(
        f"""
        <div class="aspect-item">
            <div class="aspect-label">{html.escape(label)}</div>
            <div class="aspect-text">{html.escape(text)}</div>
        </div>
        """
        for label, text in aspects
    )
    st.markdown(f'<div class="aspect-grid">{cells}</div>', unsafe_allow_html=True)


def _render_stocks(result: AnalysisResult) -> None:
    if not result.stocks:
        st.info("逐字稿未明確提及股票。")
        return

    st.caption(f"共萃取 {len(result.stocks)} 檔股票。股票代號未知時會顯示 unknown。")

    for stock in result.stocks:
        title = f"{stock.company_name} ({stock.ticker}) - {stock.market}"
        with st.expander(title, expanded=True):
            st.markdown(
                f"""
                <div class="stock-meta"><strong>提及脈絡：</strong>{html.escape(stock.mention_reason)}</div>
                """,
                unsafe_allow_html=True,
            )
            _render_aspect_grid(stock)


def _render_transcript(transcript_result: TranscriptResult) -> None:
    source_name = "YouTube 字幕" if transcript_result.source_type == "youtube" else "Podcast 轉錄"
    st.caption(f"來源類型：{source_name}")
    st.caption(f"來源網址：{transcript_result.source_url}")
    st.text_area("逐字稿內容", transcript_result.text, height=360)


def _render_export(result: AnalysisResult) -> None:
    payload = _analysis_json(result)
    st.download_button(
        "下載分析 JSON",
        data=payload.encode("utf-8"),
        file_name="media_stock_analysis.json",
        mime="application/json",
        use_container_width=True,
    )
    st.code(payload, language="json")


def _render_results(analysis_result: AnalysisResult, transcript_result: TranscriptResult) -> None:
    st.markdown('<div class="section-title">分析結果</div>', unsafe_allow_html=True)
    _render_stats(analysis_result, transcript_result)
    st.write("")

    summary_tab, stocks_tab, transcript_tab, export_tab = st.tabs(["總結", "股票分析", "逐字稿", "匯出"])
    with summary_tab:
        _render_summary(analysis_result)
    with stocks_tab:
        _render_stocks(analysis_result)
    with transcript_tab:
        _render_transcript(transcript_result)
    with export_tab:
        _render_export(analysis_result)


def main() -> None:
    st.set_page_config(page_title="影音總結與台股萃取", layout="wide")
    _inject_styles()
    _render_hero()

    with st.container(border=True):
        st.markdown('<div class="section-title">輸入來源</div>', unsafe_allow_html=True)
        mode_col, url_col = st.columns((1, 2.4), gap="large")
        with mode_col:
            source_label = st.radio(
                "輸入模式",
                (YOUTUBE_LABEL, PODCAST_LABEL),
            )
        source_type = _source_type_from_label(source_label)
        source_title, placeholder, source_note = _source_copy(source_type)

        with url_col:
            url = st.text_input("網址", placeholder=placeholder)
            st.markdown(
                f"""
                <div class="source-note">
                    <strong>{html.escape(source_title)}</strong><br />
                    {html.escape(source_note)}
                </div>
                """,
                unsafe_allow_html=True,
            )

        submitted = st.button("開始分析", type="primary", use_container_width=True)

    with st.sidebar:
        st.header("模型設定")
        analysis_model = st.text_input(
            "內容分析模型",
            value=os.getenv("OPENAI_ANALYSIS_MODEL", DEFAULT_ANALYSIS_MODEL),
        )
        transcribe_model = st.text_input(
            "音訊轉錄模型",
            value=os.getenv("OPENAI_TRANSCRIBE_MODEL", DEFAULT_TRANSCRIBE_MODEL),
        )
        st.divider()
        if os.getenv("OPENAI_API_KEY"):
            st.success("OpenAI API key 已設定。")
        else:
            st.warning("尚未設定 OPENAI_API_KEY。部署網站時請在平台環境變數加入。")
        st.caption("預設以繁體中文輸出，股票辨識以台股優先。")

    if submitted:
        validation_error = _validate_source_url(source_type, url)
        if validation_error:
            st.error(validation_error)
            return

        try:
            client = _get_openai_client()

            with st.status("處理中", expanded=True) as status:
                st.write("取得逐字稿...")
                transcript_result = fetch_transcript(source_type, url.strip(), client, transcribe_model)

                st.write("呼叫 GPT 分析內容與股票...")
                analysis_result = analyze_transcript(client, transcript_result.text, analysis_model)

                status.update(label="分析完成", state="complete")

            _render_results(analysis_result, transcript_result)
        except TranscriptError as exc:
            st.error(str(exc))
        except RuntimeError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"未預期錯誤：{exc}")


if __name__ == "__main__":
    main()
