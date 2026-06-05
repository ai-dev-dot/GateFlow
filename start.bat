@echo off
chcp 65001 >nul 2>&1

echo Cleaning up old processes on port 3000 and 8000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3000 "') do taskkill /PID %%a /F >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000 "') do taskkill /PID %%a /F >nul 2>&1

if defined WT_SESSION (
    wt new-tab --title "GateFlow Backend"  cmd /k "cd /d D:\APP\GateFlow\backend  && python -m uvicorn app.main:app --reload --port 8000" ^
    ; new-tab --title "GateFlow Frontend" cmd /k "cd /d D:\APP\GateFlow\frontend && npm run dev"
) else (
    start "GateFlow Backend"  cmd /k "cd /d D:\APP\GateFlow\backend  && python -m uvicorn app.main:app --reload --port 8000"
    start "GateFlow Frontend" cmd /k "cd /d D:\APP\GateFlow\frontend && npm run dev"
)
