#!/bin/bash
# ============================================================
# 快速同步 - 仅后端代码变更
# 调用: bash scripts/quick-sync.sh
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

SSH_KEY="$PROJECT_DIR/YunServerMG.pem"
SSH_USER="ubuntu"; SSH_HOST="175.178.29.97"
REMOTE_DIR="/opt/ai-learning"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

echo -e "${BLUE}⚡ 快速同步 (后端) → ${SSH_USER}@${SSH_HOST}${NC}"

# 1. Sync backend + demo 前端代码文件 + root configs via tar+ssh
#    (demo 仅同步代码文件 index.html/api-bridge.js；images 数据量大不随包)
echo -e "${YELLOW}[1/3] 同步后端+demo前端+配置...${NC}"
cd "$PROJECT_DIR"
tar czf - --exclude='__pycache__' --exclude='*.pyc' --exclude='venv' \
    --exclude='.env' --exclude='uploads' --exclude='*.db' --exclude='*.db-journal' \
    backend frontend/demo/index.html frontend/demo/api-bridge.js AGENTS.md | \
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SSH_USER@$SSH_HOST" \
    "cd $REMOTE_DIR && tar xzf - --overwrite 2>/dev/null || tar xzf -"
echo -e "${GREEN}  ✓ 同步完成${NC}"

# 2. Pip install
echo -e "${YELLOW}[2/3] 更新Python依赖...${NC}"
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SSH_USER@$SSH_HOST" \
    "/opt/ai-learning/backend/venv/bin/pip install -q -r /opt/ai-learning/backend/requirements.txt && echo '  ✓ 依赖OK'"

# 3. Graceful restart
echo -e "${YELLOW}[3/3] 重载Gunicorn...${NC}"
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SSH_USER@$SSH_HOST" << 'REMOTE'
    if sudo systemctl reload ai-learning 2>/dev/null; then
        echo "  ✓ Graceful reload"
    else
        sudo systemctl restart ai-learning
        sleep 3
    fi
    sudo systemctl is-active --quiet ai-learning && echo "  ✓ 服务运行中" || {
        echo "  ✗ 启动失败!"
        sudo journalctl -u ai-learning -n 10 --no-pager
        exit 1
    }
REMOTE

echo -e "${GREEN}✅ 后端快速同步完成${NC}"
