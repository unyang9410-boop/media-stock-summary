# 影音總結與台股萃取 Streamlit App

這是一個 Python/Streamlit 網站，支援 Podcast 網址、節目連結或直接音檔網址，並使用 OpenAI 產生繁體中文摘要與台股優先的股票分析。

## 功能

- Podcast 網址或節目連結：可貼 Apple Podcasts 節目/單集頁、Podcast RSS、含音訊播放器的單集頁或直接音檔 URL；系統會解析音訊連結後，用 `requests` 讀取音訊 bytes，透過 `io.BytesIO` 送 OpenAI 音訊轉錄。
- AI 分析：使用 GPT 模型產生重點摘要、投資觀察、股票清單與八大面向分析。
- 台股優先：股票名稱與代號辨識以台股為優先，但保留其他明確提及市場。
- 網址驗證：接受完整 Podcast 網址、Apple Podcasts 節目/單集頁、RSS、節目連結或直接音檔 URL。
- 匯出結果：分析完成後可下載 JSON，方便後續存檔或串接其他流程。

## 安裝

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

編輯 `.env`：

```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_ANALYSIS_MODEL=gpt-4o
OPENAI_TRANSCRIBE_MODEL=whisper-1
```

## 本機執行

最簡單的方式是直接雙擊：

```text
start_app.bat
```

它會在背景啟動 Streamlit，並自動開啟：

```text
http://127.0.0.1:8501
```

如果想在終端機中查看完整錯誤訊息，使用：

```powershell
powershell -ExecutionPolicy Bypass -File .\run_app.ps1
```

## 架設成網站

專案已包含部署檔案：

- `render.yaml`：Render Web Service 部署設定。
- `Dockerfile`：容器化部署。
- `Procfile`：支援 Procfile 的平台使用。
- `DEPLOYMENT.md`：部署步驟。
- `GITHUB_RENDER_NEXT_STEPS.md`：GitHub + Render 上線流程。
- `publish_github.ps1`：GitHub CLI 登入後的一鍵建立 repo / push 腳本。

若 `gh auth status` 顯示 token invalid，請先執行 `gh auth logout -h github.com`，再執行 `gh auth login -h github.com --git-protocol https --web`。

部署時請在平台後台設定環境變數：

```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_ANALYSIS_MODEL=gpt-4o
OPENAI_TRANSCRIBE_MODEL=whisper-1
```

雲端平台的啟動指令必須使用 `0.0.0.0` 和平台提供的 `$PORT`：

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port $PORT --server.headless true
```

詳細部署方式請看 `DEPLOYMENT.md`。

## 測試

```powershell
pytest
```

## 注意事項

- Podcast 音訊目前不設定應用層大小上限，長音訊可能造成記憶體壓力或 OpenAI API 限制錯誤。
- 線上版暫不開放 YouTube 影片輸入。YouTube 字幕 API 在雲端環境容易遇到 IP 封鎖或影片無字幕限制，無法保證穩定可用。
- AI 分析會要求模型不要補充逐字稿以外的資訊；缺失面向會標示「逐字稿未明確提及」。
- 不要把 `.env` 或 API key 上傳到公開 repo。
