$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$url = "http://127.0.0.1:8501"

if (-not (Test-Path $python)) {
    Write-Host "Missing .venv. Run these commands first:"
    Write-Host "python -m venv .venv"
    Write-Host ".\.venv\Scripts\python.exe -m pip install -r requirements.txt"
    exit 1
}

$existing = Get-NetTCPConnection -LocalPort 8501 -ErrorAction SilentlyContinue |
    Where-Object { $_.State -eq "Listen" -or $_.State -eq "Established" }

if (-not $existing) {
    Start-Process `
        -FilePath $python `
        -ArgumentList @(
            "-m", "streamlit", "run", "app.py",
            "--server.address", "127.0.0.1",
            "--server.port", "8501",
            "--server.headless", "true",
            "--browser.gatherUsageStats", "false"
        ) `
        -WorkingDirectory $projectRoot `
        -WindowStyle Hidden
}

for ($i = 0; $i -lt 30; $i++) {
    try {
        $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2
        if ($response.StatusCode -eq 200) {
            Write-Host "Streamlit is running: $url"
            Start-Process $url
            exit 0
        }
    } catch {
        Start-Sleep -Seconds 1
    }
}

Write-Host "Streamlit startup timed out. Run .\run_app.ps1 to see the detailed error."
exit 1
