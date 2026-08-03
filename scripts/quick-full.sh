#!/bin/bash
# ============================================================
# 全栈快速部署 - 前后端都变更时使用
# 调用: bash scripts/quick-full.sh
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

SSH_KEY="$PROJECT_DIR/YunServerMG.pem"
SSH_USER="ubuntu"; SSH_HOST="175.178.29.97"
REMOTE_DIR="/opt/ai-learning"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

echo -e "${BLUE}🚀 全栈部署 → ${SSH_USER}@${SSH_HOST}${NC}"

# 1. Sync
echo -e "${YELLOW}[1/4] 同步代码...${NC}"
cd "$PROJECT_DIR"

echo "  后端..."
tar czf - --exclude='__pycache__' --exclude='*.pyc' --exclude='venv' \
    --exclude='.env' --exclude='uploads' --exclude='*.db' --exclude='*.db-journal' \
    backend | ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SSH_USER@$SSH_HOST" \
    "cd $REMOTE_DIR && tar xzf - --overwrite 2>/dev/null || tar xzf -"

echo "  前端..."
tar czf - --exclude='node_modules' --exclude='dist' frontend | \
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SSH_USER@$SSH_HOST" \
    "cd $REMOTE_DIR && tar xzf - --overwrite 2>/dev/null || tar xzf -"

echo -e "${GREEN}  ✓ 同步完成${NC}"

# 2. Deps + Build
echo -e "${YELLOW}[2/4] 安装依赖+构建...${NC}"
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SSH_USER@$SSH_HOST" \
    "cd $REMOTE_DIR && \
     /opt/ai-learning/backend/venv/bin/pip install -q -r backend/requirements.txt && \
     cd frontend && npm install --silent && npm run build && \
     echo '  ✓ 构建完成'"

# 3. Restart
echo -e "${YELLOW}[3/4] 重启后端...${NC}"
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SSH_USER@$SSH_HOST" \
    "sudo systemctl reload ai-learning 2>/dev/null || sudo systemctl restart ai-learning; \
     sleep 3; sudo systemctl is-active --quiet ai-learning && echo '  ✓ 后端OK'"

# 4. Nginx
echo -e "${YELLOW}[4/4] 重载Nginx...${NC}"
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SSH_USER@$SSH_HOST" \
    "sudo nginx -t >/dev/null 2>&1 && sudo systemctl reload nginx && echo '  ✓ Nginx OK'"

echo -e "${GREEN}✅ 全栈部署完成 — http://${SSH_HOST}${NC}"
