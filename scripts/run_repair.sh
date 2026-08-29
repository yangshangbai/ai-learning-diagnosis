#!/bin/bash
# ==============================================================================
# AI学习诊断系统 — 自动修复包装脚本
# ==============================================================================
# 由 cron 定时调用，执行:
#   1. 错误分析 + 自动标记非Bug
#   2. 程序Bug自动修复 (可选)
#   3. Git 提交变更 + 推送到远程
#   4. 代码同步回本地开发机
#   5. 必要时重启服务
#
# Cron 配置 (crontab -e):
#   0  8 * * * /opt/ai-learning/scripts/run_repair.sh >> /opt/ai-learning/logs/repair_cron.log 2>&1
#   0 11 * * * /opt/ai-learning/scripts/run_repair.sh >> /opt/ai-learning/logs/repair_cron.log 2>&1
#   0 17 * * * /opt/ai-learning/scripts/run_repair.sh >> /opt/ai-learning/logs/repair_cron.log 2>&1
#   0 22 * * * /opt/ai-learning/scripts/run_repair.sh >> /opt/ai-learning/logs/repair_cron.log 2>&1
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_DIR/backend"
LOG_DIR="$PROJECT_DIR/logs"
REPORT_FILE="$LOG_DIR/auto_repair_report.json"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# 日志函数
log() { echo "[$TIMESTAMP] $*"; }

log "=========================================="
log "  自动修复任务开始"
log "=========================================="

# ---- 1. 激活虚拟环境并运行分析 ----
log "[1/4] 运行错误分析脚本..."
cd "$BACKEND_DIR"
source venv/bin/activate
export $(cat .env | xargs)

python3 "$SCRIPT_DIR/auto_repair.py" --auto-fix -v 2>&1 | while IFS= read -r line; do
    log "  $line"
done

ANALYSIS_EXIT="${PIPESTATUS[0]}"
if [ "$ANALYSIS_EXIT" -ne 0 ]; then
    log "[WARN] 分析脚本退出码: $ANALYSIS_EXIT"
fi

# ---- 2. 检查是否有代码变更需要提交 ----
log ""
log "[2/4] 检查代码变更..."

cd "$PROJECT_DIR"

# 初始化 Git（如果尚未初始化）
if [ ! -d ".git" ]; then
    log "  初始化 Git 仓库..."
    git init
    git config user.email "auto-repair@ai-learning.local"
    git config user.name "Auto Repair Bot"

    # 创建 .gitignore
    cat > .gitignore << 'GITIGNORE'
__pycache__/
*.pyc
*.pyo
venv/
node_modules/
dist/
*.db
uploads/*
logs/*.log
logs/*.pid
.env
.env.db
.gitignore
GITIGNORE

    git add -A
    git commit -m "chore: initial commit by auto-repair system"
    log "  Git 仓库已初始化"
fi

# 检测变更
CHANGED=$(git status --porcelain | wc -l)
if [ "$CHANGED" -gt 0 ]; then
    log "  发现 $CHANGED 个文件变更"

    # 读取报告获取变更摘要
    if [ -f "$REPORT_FILE" ]; then
        FIX_COUNT=$(python3 -c "import json; d=json.load(open('$REPORT_FILE')); print(d.get('auto_fixable',0))" 2>/dev/null || echo "0")
    else
        FIX_COUNT="?"
    fi

    git add -A
    git commit -m "fix(auto-repair): $TIMESTAMP — $FIX_COUNT fixes applied

$(python3 -c "
import json
try:
    d = json.load(open('$REPORT_FILE'))
    for s in d.get('fix_suggestions', [])[:5]:
        fix = s.get('fix', {})
        if fix:
            print(f'  - #{s[\"id\"]} {fix.get(\"description\", \"unknown\")}')
except: pass
" 2>/dev/null)"

    log "  已提交: $(git log -1 --oneline)"

    # ---- 3. 同步到本地开发机 ----
    log ""
    log "[3/4] 同步代码到本地开发机..."

    # 方式1: 如果配置了 LOCAL_SYNC 环境变量，通过 SCP 推送
    if [ -n "$LOCAL_SYNC_TARGET" ]; then
        log "  SCP 同步到: $LOCAL_SYNC_TARGET"
        # 打包变更文件并推送
        git diff --name-only HEAD~1 HEAD > /tmp/changed_files.txt
        tar czf /tmp/repair_sync.tar.gz -T /tmp/changed_files.txt 2>/dev/null || true
        scp /tmp/repair_sync.tar.gz "$LOCAL_SYNC_TARGET:/tmp/" 2>/dev/null && \
            log "  同步包已发送" || log "  [WARN] SCP 同步失败"
    else
        log "  [INFO] 未配置 LOCAL_SYNC_TARGET，跳过本地同步"
        log "  变更文件列表:"
        git diff --name-only HEAD~1 HEAD 2>/dev/null | while read -r f; do
            log "    $f"
        done
    fi

    # ---- 4. 重启服务（如果后端代码有变更） ----
    log ""
    log "[4/4] 检查是否需要重启服务..."

    BACKEND_CHANGED=$(git diff --name-only HEAD~1 HEAD 2>/dev/null | grep -c '^backend/' || true)
    if [ "$BACKEND_CHANGED" -gt 0 ]; then
        log "  后端代码有变更 ($BACKEND_CHANGED 个文件)，重启服务..."
        sudo systemctl restart ai-learning
        sleep 3
        if sudo systemctl is-active --quiet ai-learning; then
            log "  ✅ 服务重启成功"
        else
            log "  ❌ 服务重启失败！请检查: sudo systemctl status ai-learning"
        fi
    else
        log "  后端代码无变更，无需重启"
    fi

else
    log "  无代码变更"
    log "[3/4] 跳过同步 (无变更)"
    log "[4/4] 跳过重启 (无变更)"
fi

# ---- 完成 ----
log ""
log "=========================================="
log "  自动修复任务完成"
log "  📄 报告: $REPORT_FILE"
log "=========================================="

exit 0
