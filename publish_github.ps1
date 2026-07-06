param(
    [string]$RepoName = "media-stock-summary",
    [switch]$Private
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$git = "git"

if (Test-Path "C:\Users\unyang0914\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe") {
    $git = "C:\Users\unyang0914\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe"
}

Set-Location $projectRoot

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Host "GitHub CLI was not found. Install gh first: https://cli.github.com/"
    exit 1
}

gh auth status
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "GitHub CLI auth is not ready. If the cached token is invalid, run:"
    Write-Host "  gh auth logout -h github.com"
    Write-Host "  gh auth login -h github.com --git-protocol https --web"
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
Write-Host "GitHub repo is ready: $repoUrl"
Write-Host "Next: create a Render Blueprint or Web Service, connect this repo, and set OPENAI_API_KEY."
