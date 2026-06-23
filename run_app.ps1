$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "找不到 .venv。請先執行："
    Write-Host "python -m venv .venv"
    Write-Host ".\.venv\Scripts\python.exe -m pip install -r requirements.txt"
    exit 1
}

Set-Location $projectRoot
& $python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true --browser.gatherUsageStats false @args

