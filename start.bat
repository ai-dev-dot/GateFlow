@echo off
chcp 65001 >nul 2>&1

echo Cleaning up old processes on port 3000 and 8000...

:: Kill all processes listening on port 3000 and 8000 (with full process tree)
:: Use netstat to find PIDs, then taskkill with /T to kill child processes too
for /f "tokens=5" %%a in ('netstat -ano ^| findstr "LISTENING" ^| findstr ":3000 "') do (
    echo   Killing PID %%a (port 3000)
    taskkill /PID %%a /F /T >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr "LISTENING" ^| findstr ":8000 "') do (
    echo   Killing PID %%a (port 8000)
    taskkill /PID %%a /F /T >nul 2>&1
)

:: Wait for ports to be fully released
timeout /t 2 /nobreak >nul 2>&1

echo Starting services...

if defined WT_SESSION (
    wt new-tab --title "GateFlow Backend"  cmd /k "cd /d D:\APP\GateFlow\backend  && python -m uvicorn app.main:app --reload --port 8000" ^
    ; new-tab --title "GateFlow Frontend" cmd /k "cd /d D:\APP\GateFlow\frontend && npm run dev"
) else (
    start "GateFlow Backend"  cmd /k "cd /d D:\APP\GateFlow\backend  && python -m uvicorn app.main:app --reload --port 8000"
    start "GateFlow Frontend" cmd /k "cd /d D:\APP\GateFlow\frontend && npm run dev"
)
