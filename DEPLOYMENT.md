# 架設網站部署指南

這個專案是 Streamlit 網站。部署時重點是讓平台從外部連進來，因此啟動命令必須使用：

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port $PORT --server.headless true
```

本機啟動腳本仍使用 `127.0.0.1`，但雲端部署不可使用 `127.0.0.1`。

## 必要環境變數

請在部署平台後台設定：

```env
OPENAI_API_KEY=你的 OpenAI API key
OPENAI_ANALYSIS_MODEL=gpt-4o
OPENAI_TRANSCRIBE_MODEL=whisper-1
```

不要把 `.env` 上傳到公開 repo。

## 健康檢查

部署完成後可檢查：

```text
https://你的網站網址/_stcore/health
```

若回應 HTTP 200，代表 Streamlit 服務已啟動。

## Render 部署

1. 將專案推到 GitHub。
2. 在 Render 建立新的 Web Service，連到該 GitHub repo。
3. Render 若偵測到 `render.yaml`，可直接套用。
4. 在 Environment Variables 加上 `OPENAI_API_KEY`。
5. 部署完成後，Render 會提供公開網址。

## Docker 部署

建置：

```bash
docker build -t media-stock-summary .
```

執行：

```bash
docker run --rm -p 8501:8501 --env-file .env media-stock-summary
```

打開：

```text
http://127.0.0.1:8501
```

## 其他平台

有支援 `Procfile` 的平台可使用：

```Procfile
web: streamlit run app.py --server.address=0.0.0.0 --server.port=${PORT:-8501} --server.headless=true --browser.gatherUsageStats=false
```
