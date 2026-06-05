#!/usr/bin/env bash
# GateFlow 首次安装脚本（装依赖，不启动服务）
# 使用方式: bash setup.sh

set -e

# 切换到脚本所在目录
cd "$(dirname "$0")"
ROOT_DIR=$(pwd)

echo "[1/3] 检查后端 Python 环境..."
cd "$ROOT_DIR/backend"
if [ ! -f "venv/bin/python" ]; then
    python3 -m venv venv
    echo "  ✓ 已创建 venv"
else
    echo "  ✓ venv 已存在"
fi

echo "[2/3] 安装后端依赖..."
./venv/bin/pip install -q -r requirements.txt
echo "  ✓ 后端依赖装完"

echo "[3/3] 安装前端依赖..."
cd "$ROOT_DIR/frontend"
if [ ! -d "node_modules" ]; then
    npm install
fi
echo "  ✓ 前端依赖装完"

echo ""
echo "安装完成。下一步："
echo "  1. 确认 backend/.env 已配置（DATABASE_URL 等）"
echo "  2. 运行 bash start.sh 启动服务"
