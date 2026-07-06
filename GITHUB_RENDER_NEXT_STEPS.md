# GitHub + Render 上線步驟

目前專案已經是可部署狀態；剩下需要 GitHub 和 Render 帳號授權。

## 1. 登入 GitHub CLI

在 PowerShell 執行：

```powershell
gh auth status
```

若顯示 token invalid，先清掉舊 token：

```powershell
gh auth logout -h github.com
```

再重新登入：

```powershell
gh auth login -h github.com --git-protocol https --web
```

網頁登入建議選項：

- GitHub.com
- HTTPS
- Login with a web browser

登入完成後再次確認：

```powershell
gh auth status
```

## 2. 建立 GitHub repo 並推送

回到專案資料夾後執行：

```powershell
powershell -ExecutionPolicy Bypass -File .\publish_github.ps1 -RepoName media-stock-summary
```

若想建立 private repo：

```powershell
powershell -ExecutionPolicy Bypass -File .\publish_github.ps1 -RepoName media-stock-summary -Private
```

## 3. 在 Render 部署

1. 打開 Render Dashboard。
2. 選擇 New +。
3. 若可用 Blueprint，選 Blueprint 並連接 GitHub repo，Render 會讀取 `render.yaml`。
4. 若建立 Web Service，設定：
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `streamlit run app.py --server.address 0.0.0.0 --server.port $PORT --server.headless true --browser.gatherUsageStats false`
   - Health Check Path: `/_stcore/health`
5. 在 Environment Variables 設定：
   - `OPENAI_API_KEY`
   - `OPENAI_ANALYSIS_MODEL=gpt-4o`
   - `OPENAI_TRANSCRIBE_MODEL=whisper-1`

## 4. 驗證

部署完成後檢查：

```text
https://你的-render網址/_stcore/health
```

回應 HTTP 200 表示服務正常。接著打開 Render 給的公開網址測試 YouTube / Podcast 輸入流程。
