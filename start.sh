#!/usr/bin/env bash
# GateFlow 一键启动脚本（后端 + 前端）
# 使用方式: bash start.sh

set -e

cd "$(dirname "$0")"

# 清理函数：停止所有子进程
cleanup() {
    echo ""
    echo "正在停止服务..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    wait $BACKEND_PID $FRONTEND_PID 2>/dev/null
    echo "已停止。"
}
trap cleanup EXIT INT TERM

echo "=== 启动后端 (port 8000) ==="
cd backend
python -m uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!
cd ..

echo "=== 启动前端 (port 3000) ==="
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "GateFlow 已启动:"
echo "  前端: http://localhost:3000"
echo "  后端: http://localhost:8000"
echo "  按 Ctrl+C 停止所有服务"
echo ""

wait
