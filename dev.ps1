<#
.SYNOPSIS
    Dev launcher (Windows): starts the microservices stack (docker compose,
    gateway on :8000) and the Vite frontend (:3000) in a new PowerShell window,
    then opens the browser. Close the frontend window and run
    `docker compose stop` to stop everything.
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File dev.ps1
#>

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

# ── Docker: the backend is the compose stack now ─────────────────────────────
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker is not running - start Docker Desktop first." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path (Join-Path $Root ".env"))) {
    Write-Host "ERROR: missing repo-root .env (compose secrets). Create it first:" -ForegroundColor Red
    Write-Host "  copy .env.example .env   # then set APP_API_TOKEN" -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path (Join-Path $Root "data\jobs\chroma"))) {
    Write-Host "WARNING: data\jobs\chroma missing - matching will serve 503s (SPA uses offline estimates)." -ForegroundColor Yellow
    Write-Host "Build it with: backend\venv\Scripts\python data\scripts\build_rag.py" -ForegroundColor Yellow
}

# ── Frontend deps: install once if node_modules is missing ───────────────────
$NodeModules = Join-Path $Root "frontend\node_modules"
if (-not (Test-Path $NodeModules)) {
    Write-Host "npm install (first run)..." -ForegroundColor Yellow
    Push-Location (Join-Path $Root "frontend")
    npm install
    $npmExit = $LASTEXITCODE
    Pop-Location
    if ($npmExit -ne 0) {
        Write-Host "ERROR: npm install failed (exit $npmExit)." -ForegroundColor Red
        exit 1
    }
}

# ── Backend: bring up the whole stack ────────────────────────────────────────
Push-Location $Root
docker compose up -d --build
$composeExit = $LASTEXITCODE
Pop-Location
if ($composeExit -ne 0) {
    Write-Host "ERROR: docker compose up failed (exit $composeExit)." -ForegroundColor Red
    exit 1
}

# ── Frontend in its own window ───────────────────────────────────────────────
$FrontendDir = Join-Path $Root "frontend"
$FrontendCmd = "Set-Location '$FrontendDir'; " +
               "Write-Host '--- Frontend http://localhost:3000 ---' -ForegroundColor Cyan; " +
               "npm run dev"

$FrontendProc = Start-Process powershell `
    -ArgumentList "-NoExit", "-Command", $FrontendCmd `
    -PassThru

# ── Print URLs and open the browser after Vite has had time to boot ──────────
Write-Host ""
Write-Host "  Backend  ->  http://localhost:8000  (gateway; 'docker compose ps' for services)" -ForegroundColor Green
Write-Host "  Frontend ->  http://localhost:3000  (PID $($FrontendProc.Id))" -ForegroundColor Green
Write-Host ""
Write-Host "  Opening browser in 4 s. Close the frontend window and run 'docker compose stop' to shut down." -ForegroundColor DarkGray
Write-Host ""

Start-Sleep -Seconds 4
Start-Process "http://localhost:3000"
