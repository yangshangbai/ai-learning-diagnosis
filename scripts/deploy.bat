@echo off
REM ============================================================
REM AI学习诊断系统 - Windows 部署脚本
REM 功能: 本地代码 → 云端同步 → 构建 → 服务重启
REM ============================================================

setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0
set PROJECT_DIR=%SCRIPT_DIR%..
set SSH_KEY=%PROJECT_DIR%\YunServerMG.pem
set SSH_USER=ubuntu
set SSH_HOST=175.178.29.97
set REMOTE_DIR=/opt/ai-learning

echo =========================================
echo   AI学习诊断系统 - 云端部署
echo   %SSH_USER%@%SSH_HOST%:%REMOTE_DIR%
echo =========================================

REM ── Step 1: 代码同步 ───────────────────────────────────────
echo.
echo [1/4] 同步代码到云端...

REM 后端同步
echo   同步 backend...
rsync -avz --delete --progress ^
    --exclude "__pycache__" --exclude "*.pyc" --exclude "venv/" ^
    --exclude ".env" --exclude "uploads/" --exclude "*.db" --exclude "*.db-journal" ^
    -e "ssh -i %SSH_KEY% -o StrictHostKeyChecking=no" ^
    "%PROJECT_DIR%/backend/" "%SSH_USER%@%SSH_HOST%:%REMOTE_DIR%/backend/"

REM 前端同步
echo   同步 frontend...
rsync -avz --delete --progress ^
    --exclude "node_modules/" --exclude "dist/" ^
    -e "ssh -i %SSH_KEY% -o StrictHostKeyChecking=no" ^
    "%PROJECT_DIR%/frontend/" "%SSH_USER%@%SSH_HOST%:%REMOTE_DIR%/frontend/"

REM 同步脚本和文档
echo   同步 scripts/docs...
rsync -avz --progress ^
    -e "ssh -i %SSH_KEY% -o StrictHostKeyChecking=no" ^
    "%PROJECT_DIR%/scripts/" "%SSH_USER%@%SSH_HOST%:%REMOTE_DIR%/scripts/"
rsync -avz --progress ^
    -e "ssh -i %SSH_KEY% -o StrictHostKeyChecking=no" ^
    "%PROJECT_DIR%/CHANGELOG.md" "%PROJECT_DIR%/README.md" ^
    "%SSH_USER%@%SSH_HOST%:%REMOTE_DIR%/"
echo   [完成] 代码同步完成

REM ── Step 2: 依赖安装 ───────────────────────────────────────
echo.
echo [2/4] 云端安装依赖...
ssh -i "%SSH_KEY%" -o StrictHostKeyChecking=no %SSH_USER%@%SSH_HOST% ^
    "/opt/ai-learning/backend/venv/bin/pip install -q -r /opt/ai-learning/backend/requirements.txt && cd /opt/ai-learning/frontend && npm install --silent"
echo   [完成] 依赖安装完成

REM ── Step 3: 前端构建 ───────────────────────────────────────
echo.
echo [3/4] 构建前端...
ssh -i "%SSH_KEY%" -o StrictHostKeyChecking=no %SSH_USER%@%SSH_HOST% ^
    "cd /opt/ai-learning/frontend && npm run build"
echo   [完成] 前端构建完成

REM ── Step 4: 服务重启 ───────────────────────────────────────
echo.
echo [4/4] 重启服务...
ssh -i "%SSH_KEY%" -o StrictHostKeyChecking=no %SSH_USER%@%SSH_HOST% ^
    "sudo systemctl reload ai-learning 2>/dev/null || sudo systemctl restart ai-learning && sleep 3 && sudo systemctl is-active ai-learning && sudo nginx -t && sudo systemctl reload nginx"
echo   [完成] 服务重启完成

echo.
echo =========================================
echo   ✅ 部署完成!
echo   HTTP:  http://%SSH_HOST%
echo   API:   http://%SSH_HOST%/api/docs
echo =========================================
pause
