#!/bin/bash
# AI学习诊断系统 - 启动脚本 (Linux/Mac)
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"

echo "=========================================="
echo "  AI学习诊断系统 - 启动中..."
echo "=========================================="

# Create required directories
mkdir -p "$BACKEND_DIR/uploads"

# Install Python dependencies
echo "[1/3] 检查Python依赖..."
cd "$BACKEND_DIR"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null
pip install -q -r requirements.txt

# Start backend
echo "[2/3] 启动后端服务 (端口 8000)..."
python main.py &
BACKEND_PID=$!
echo "  后端 PID: $BACKEND_PID"
echo $BACKEND_PID > "$PROJECT_DIR/.backend.pid"

# Wait for backend
sleep 2

# Start frontend
echo "[3/3] 启动前端开发服务器 (端口 5173)..."
cd "$FRONTEND_DIR"
if [ ! -d "node_modules" ]; then
    npm install
fi
npm run dev &
FRONTEND_PID=$!
echo "  前端 PID: $FRONTEND_PID"
echo $FRONTEND_PID > "$PROJECT_DIR/.frontend.pid"

echo ""
echo "=========================================="
echo "  系统启动完成!"
echo "  后端: http://localhost:8000"
echo "  前端: http://localhost:5173"
echo "  API文档: http://localhost:8000/docs"
echo "=========================================="
echo "  停止系统: ./scripts/stop.sh"
echo ""

# Wait for processes
wait
