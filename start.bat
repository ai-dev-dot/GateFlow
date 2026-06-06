@echo off
chcp 65001 >nul 2>&1

echo Cleaning up old processes on port 8000...

:: Kill all processes listening on port 8000 (with full process tree)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr "LISTENING" ^| findstr ":8000 "') do (
    echo   Killing PID %%a (port 8000)
    taskkill /PID %%a /F /T >nul 2>&1
)

:: Wait for port to be fully released
timeout /t 2 /nobreak >nul 2>&1

echo Starting GateFlow...
cd /d D:\APP\GateFlow
python -m uvicorn app.main:app --reload --port 8000
