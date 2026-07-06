$ErrorActionPreference = "Stop"

param(
    [string]$RepoName = "media-stock-summary",
    [switch]$Private
)

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$git = "git"

if (Test-Path "C:\Users\unyang0914\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe") {
    $git = "C:\Users\unyang0914\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe"
}

Set-Location $projectRoot

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Host "找不到 GitHub CLI。請先安裝 gh：https://cli.github.com/"
    exit 1
}

gh auth status | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "尚未登入 GitHub。請先執行：gh auth login"
    exit 1
}

$visibility = "--public"
if ($Private) {
    $visibility = "--private"
}

$remote = & $git remote get-url origin 2>$null
if (-not $remote) {
    gh repo create $RepoName $visibility --source . --remote origin --push
} else {
    & $git push -u origin main
}

$repoUrl = gh repo view --json url --jq .url
Write-Host "GitHub repo 已就緒：$repoUrl"
Write-Host "下一步：到 Render 建立 Blueprint 或 Web Service，連接此 repo，並設定 OPENAI_API_KEY。"

