@echo off
chcp 65001 >nul 2>&1
setlocal

set "ROOT=%~dp0"

echo [1/3] 检查后端 Python 环境...
cd /d "%ROOT%backend"
if not exist "venv\Scripts\python.exe" (
    python -m venv venv
    if errorlevel 1 goto :error
    echo   ^✓ 已创建 venv
) else (
    echo   ^✓ venv 已存在
)

echo [2/3] 安装后端依赖...
call venv\Scripts\activate.bat
pip install -q -r requirements.txt
if errorlevel 1 goto :error
echo   ^✓ 后端依赖装完

echo [3/3] 安装前端依赖...
cd /d "%ROOT%frontend"
if not exist "node_modules" (
    call npm install
    if errorlevel 1 goto :error
)
echo   ^✓ 前端依赖装完

echo.
echo 安装完成。下一步：
echo   1. 确认 backend\.env 已配置（DATABASE_URL 等）
echo   2. 双击 start.bat 启动服务
exit /b 0

:error
echo.
echo 安装失败，请检查 Python / Node.js / 网络是否正常。
exit /b 1
