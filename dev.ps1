<#
.SYNOPSIS
    Dev launcher (Windows): starts the FastAPI backend (:8000) and the Vite
    frontend (:3000) in two new PowerShell windows, then opens the browser.
    Close those two windows to stop the servers.
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File dev.ps1
#>

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

# ── Python: prefer backend venv, fall back to system ─────────────────────────
$VenvPython = Join-Path $Root "backend\venv\Scripts\python.exe"
if (Test-Path $VenvPython) {
    $Python = $VenvPython
    Write-Host "Python  : venv ($VenvPython)" -ForegroundColor DarkGray
} else {
    $PythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $PythonCmd) {
        Write-Host ""
        Write-Host "ERROR: Python not found in PATH." -ForegroundColor Red
        Write-Host "Either add Python to PATH, or create a venv first:" -ForegroundColor Yellow
        Write-Host "  cd backend" -ForegroundColor Yellow
        Write-Host "  python -m venv venv" -ForegroundColor Yellow
        Write-Host "  venv\Scripts\pip install -r requirements.txt" -ForegroundColor Yellow
        exit 1
    }
    $Python = $PythonCmd.Source
    Write-Host "Python  : system ($Python)" -ForegroundColor DarkGray
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

# ── Launch backend and frontend each in their own window ─────────────────────
$BackendDir  = Join-Path $Root "backend"
$FrontendDir = Join-Path $Root "frontend"

$BackendCmd = "Set-Location '$BackendDir'; " +
              "Write-Host '--- Backend  http://localhost:8000 ---' -ForegroundColor Cyan; " +
              "& '$Python' -m uvicorn app.main:app --port 8000 --reload"

$FrontendCmd = "Set-Location '$FrontendDir'; " +
               "Write-Host '--- Frontend http://localhost:3000 ---' -ForegroundColor Cyan; " +
               "npm run dev"

$BackendProc  = Start-Process powershell `
    -ArgumentList "-NoExit", "-Command", $BackendCmd `
    -PassThru

$FrontendProc = Start-Process powershell `
    -ArgumentList "-NoExit", "-Command", $FrontendCmd `
    -PassThru

# ── Print URLs and open the browser after Vite has had time to boot ──────────
Write-Host ""
Write-Host "  Backend  ->  http://localhost:8000  (PID $($BackendProc.Id))" -ForegroundColor Green
Write-Host "  Frontend ->  http://localhost:3000  (PID $($FrontendProc.Id))" -ForegroundColor Green
Write-Host ""
Write-Host "  Opening browser in 4 s. Close the two new windows to stop the servers." -ForegroundColor DarkGray
Write-Host ""

Start-Sleep -Seconds 4
Start-Process "http://localhost:3000"
