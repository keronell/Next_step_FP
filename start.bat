@echo off
setlocal
cd /d "%~dp0"

echo Starting NextStep Career Matcher...
echo.

where node >nul 2>&1
if errorlevel 1 (
    echo Node.js is not installed or not on PATH.
    echo Install Node.js 18+ from https://nodejs.org/ then run this file again.
    pause
    exit /b 1
)

node start.js
set "EXITCODE=%ERRORLEVEL%"
if not "%EXITCODE%"=="0" (
    echo.
    pause
)
exit /b %EXITCODE%
