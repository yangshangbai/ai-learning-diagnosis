#!/bin/bash
# ============================================================
# AI学习诊断系统 - 一键部署脚本
# 功能: 本地代码 → 云端同步 → 构建 → 服务重启
# 兼容: Git Bash (Windows) / Linux / Mac
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# ── 配置 ───────────────────────────────────────────────────
SSH_KEY="$PROJECT_DIR/YunServerMG.pem"
SSH_USER="ubuntu"
SSH_HOST="175.178.29.97"
REMOTE_DIR="/opt/ai-learning"

# ── 颜色 ───────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

echo -e "${BLUE}=========================================${NC}"
echo -e "${BLUE}  AI学习诊断系统 - 云端部署${NC}"
echo -e "${BLUE}  ${SSH_USER}@${SSH_HOST}:${REMOTE_DIR}${NC}"
echo -e "${BLUE}=========================================${NC}"

# ── 参数处理 ────────────────────────────────────────────────
SYNC_ONLY=false; RESTART_ONLY=false; SKIP_BUILD=false; SKIP_DEPS=false
for arg in "$@"; do
    case $arg in
        --sync-only) SYNC_ONLY=true ;;
        --restart-only) RESTART_ONLY=true ;;
        --skip-build) SKIP_BUILD=true ;;
        --skip-deps) SKIP_DEPS=true ;;
        -h|--help)
            echo "用法: $0 [选项]"
            echo "  --sync-only      仅同步代码"
            echo "  --restart-only   仅重启服务"
            echo "  --skip-build     跳过前端构建"
            echo "  --skip-deps      跳过依赖安装"
            exit 0 ;;
    esac
done

# ── 通用函数: 通过tar+ssh传输目录 ────────────────────────────
sync_dir() {
    local src="$1" dst="$2" desc="$3"
    echo -e "  ${YELLOW}同步 $desc...${NC}"
    cd "$(dirname "$src")"
    tar czf - "$(basename "$src")" | \
        ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SSH_USER@$SSH_HOST" \
        "cd $(dirname "$dst") && tar xzf - --overwrite 2>/dev/null || tar xzf -"
    echo -e "  ${GREEN}✓ $desc${NC}"
}

# ── 检查SSH连通性 ───────────────────────────────────────────
check_ssh() {
    if ! ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -o ConnectTimeout=5 -o BatchMode=yes "$SSH_USER@$SSH_HOST" "echo ok" &>/dev/null; then
        echo -e "${RED}[错误] 无法连接 ${SSH_HOST}${NC}"
        exit 1
    fi
}

# ── Step 1: 代码同步 ───────────────────────────────────────
if [ "$RESTART_ONLY" = false ]; then
    echo -e "\n${YELLOW}[1/4] 同步代码到云端...${NC}"
    check_ssh

    # 后端 (排除 venv, __pycache__, uploads, .env, *.db)
    cd "$PROJECT_DIR"
    echo "  打包 backend..."
    tar czf - --exclude='__pycache__' --exclude='*.pyc' --exclude='venv' \
        --exclude='.env' --exclude='uploads' --exclude='*.db' --exclude='*.db-journal' \
        backend | \
        ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SSH_USER@$SSH_HOST" \
        "cd $REMOTE_DIR && tar xzf - --overwrite 2>/dev/null || tar xzf -"
    echo -e "  ${GREEN}✓ backend${NC}"

    # 前端 (排除 node_modules, dist)
    echo "  打包 frontend..."
    tar czf - --exclude='node_modules' --exclude='dist' frontend | \
        ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SSH_USER@$SSH_HOST" \
        "cd $REMOTE_DIR && tar xzf - --overwrite 2>/dev/null || tar xzf -"
    echo -e "  ${GREEN}✓ frontend${NC}"

    # 脚本和文档
    echo "  同步 scripts + docs..."
    tar czf - scripts AGENTS.md CHANGELOG.md README.md cloud_migration.md 2>/dev/null | \
        ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SSH_USER@$SSH_HOST" \
        "cd $REMOTE_DIR && tar xzf - --overwrite 2>/dev/null || tar xzf -"
    echo -e "  ${GREEN}✓ scripts/docs${NC}"

    echo -e "${GREEN}[完成] 代码同步完成${NC}"
else
    echo -e "${YELLOW}[1/4] 跳过代码同步 (--restart-only)${NC}"
fi

[ "$SYNC_ONLY" = true ] && { echo -e "\n${GREEN}部署完成 (仅同步模式)${NC}"; exit 0; }

# ── Step 2: 依赖安装 ───────────────────────────────────────
echo -e "\n${YELLOW}[2/4] 云端安装依赖...${NC}"
if [ "$SKIP_DEPS" = false ]; then
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SSH_USER@$SSH_HOST" \
        "cd $REMOTE_DIR && \
         /opt/ai-learning/backend/venv/bin/pip install -q -r backend/requirements.txt 2>&1 | tail -1 && \
         echo '  ✓ Python依赖OK' && \
         cd frontend && npm install --silent 2>&1 | tail -1 && \
         echo '  ✓ Node依赖OK'"
    echo -e "${GREEN}[完成] 依赖安装完成${NC}"
else
    echo -e "${YELLOW}[2/4] 跳过依赖安装${NC}"
fi

# ── Step 3: 前端构建 ───────────────────────────────────────
echo -e "\n${YELLOW}[3/4] 构建前端...${NC}"
if [ "$SKIP_BUILD" = false ]; then
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SSH_USER@$SSH_HOST" \
        "cd $REMOTE_DIR/frontend && npm run build 2>&1 | tail -5 && \
         echo \"  ✓ 构建完成: \$(du -sh dist/ | cut -f1)\""
    echo -e "${GREEN}[完成] 前端构建完成${NC}"
else
    echo -e "${YELLOW}[3/4] 跳过前端构建${NC}"
fi

# ── Step 4: 服务重启 ───────────────────────────────────────
echo -e "\n${YELLOW}[4/4] 重启服务...${NC}"
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SSH_USER@$SSH_HOST" << 'REMOTE_RESTART'
    # Graceful reload gunicorn
    if sudo systemctl reload ai-learning 2>/dev/null; then
        echo "  ✓ Gunicorn graceful reload"
    else
        echo "  Reload不支持, 执行restart..."
        sudo systemctl restart ai-learning
        sleep 3
    fi

    # 验证后端
    if sudo systemctl is-active --quiet ai-learning; then
        echo "  ✓ 后端服务运行中"
    else
        echo "  ❌ 后端启动失败!"
        sudo journalctl -u ai-learning -n 10 --no-pager
        exit 1
    fi

    # 重载Nginx
    sudo nginx -t >/dev/null 2>&1 && sudo systemctl reload nginx
    echo "  ✓ Nginx 已重载"

    echo ""
    echo "  监听端口:"
    ss -tlnp 2>/dev/null | grep -E '8001|80|443' || netstat -tlnp 2>/dev/null | grep -E '8001|80|443'
REMOTE_RESTART

echo -e "\n${GREEN}=========================================${NC}"
echo -e "${GREEN}  ✅ 部署完成!${NC}"
echo -e "${GREEN}  HTTP:  http://${SSH_HOST}${NC}"
echo -e "${GREEN}  HTTPS: https://${SSH_HOST}${NC}"
echo -e "${GREEN}  API:   http://${SSH_HOST}/api/docs${NC}"
echo -e "${GREEN}=========================================${NC}"
