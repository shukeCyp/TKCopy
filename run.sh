#!/bin/bash
set -e
cd "$(dirname "$0")"

log() {
    echo "[TKCopy] $1 / $2"
}

# 初始化uv项目并安装依赖
log "同步 Python 依赖" "Syncing Python dependencies"
uv sync

# 编译前端静态文件
log "安装前端依赖" "Installing frontend dependencies"
cd frontend
npm install
log "编译前端静态文件" "Building static frontend"
npm run build
cd ..

# 启动pyWebview应用
log "启动桌面应用" "Starting desktop app"
uv run python tkcopy/main.py
