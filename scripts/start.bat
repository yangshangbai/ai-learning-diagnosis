@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

set "PROJECT_DIR=%~dp0.."
set "BACKEND_DIR=%PROJECT_DIR%\backend"
set "FRONTEND_DIR=%PROJECT_DIR%\frontend"

echo ==========================================
echo   AI学习诊断系统 - 启动中...
echo ==========================================

REM Create uploads directory
if not exist "%BACKEND_DIR%\uploads" mkdir "%BACKEND_DIR%\uploads"

REM Install Python dependencies
echo [1/3] 检查Python依赖...
cd /d "%BACKEND_DIR%"
if not exist "venv" (
    python -m venv venv
)
call venv\Scripts\activate.bat
pip install -q -r requirements.txt

REM Start backend
echo [2/3] 启动后端服务 (端口 8000)...
start "AI-Backend" cmd /c "cd /d %BACKEND_DIR% && venv\Scripts\python.exe main.py"

REM Wait for backend
timeout /t 3 /nobreak >nul

REM Start frontend
echo [3/3] 启动前端开发服务器 (端口 5173)...
cd /d "%FRONTEND_DIR%"
if not exist "node_modules" (
    call npm install
)
start "AI-Frontend" cmd /c "cd /d %FRONTEND_DIR% && npm run dev"

echo.
echo ==========================================
echo   系统启动完成!
echo   后端: http://localhost:8000
echo   前端: http://localhost:5173
echo   API文档: http://localhost:8000/docs
echo ==========================================
echo   停止系统: 关闭弹出的命令行窗口
echo   或运行: scripts\stop.bat
echo.

pause
