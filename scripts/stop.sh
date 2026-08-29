#!/bin/bash
# AI学习诊断系统 - 停止脚本 (Linux/Mac)

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "停止AI学习诊断系统..."

# Stop backend
if [ -f "$PROJECT_DIR/.backend.pid" ]; then
    PID=$(cat "$PROJECT_DIR/.backend.pid")
    if kill -0 $PID 2>/dev/null; then
        kill $PID 2>/dev/null
        echo "  后端已停止 (PID: $PID)"
    fi
    rm "$PROJECT_DIR/.backend.pid"
fi

# Kill any remaining uvicorn processes
pkill -f "uvicorn main:app" 2>/dev/null || true

# Stop frontend
if [ -f "$PROJECT_DIR/.frontend.pid" ]; then
    PID=$(cat "$PROJECT_DIR/.frontend.pid")
    if kill -0 $PID 2>/dev/null; then
        kill $PID 2>/dev/null
        echo "  前端已停止 (PID: $PID)"
    fi
    rm "$PROJECT_DIR/.frontend.pid"
fi

# Kill any remaining vite processes
pkill -f "vite" 2>/dev/null || true

echo "  系统已停止"
