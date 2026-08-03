#!/bin/bash
# ==============================================================================
# 版本号自动递增 — 每次 auto-repair 时调用
# 用法: bash bump_version.sh [major|minor|patch]
# 默认: patch (1.1.0 → 1.1.1)
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VERSION_FILE="$SCRIPT_DIR/../VERSION"
MAIN_FILE="$SCRIPT_DIR/../backend/main.py"
BUMP_TYPE="${1:-patch}"

# 读取当前版本
CURRENT=$(cat "$VERSION_FILE" 2>/dev/null | tr -d '[:space:]')
if [ -z "$CURRENT" ]; then
    echo "ERROR: VERSION file not found or empty"
    exit 1
fi

# 解析 semver
IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT"

# 递增
case "$BUMP_TYPE" in
    major) MAJOR=$((MAJOR + 1)); MINOR=0; PATCH=0 ;;
    minor) MINOR=$((MINOR + 1)); PATCH=0 ;;
    patch|*) PATCH=$((PATCH + 1)) ;;
esac

NEW_VERSION="${MAJOR}.${MINOR}.${PATCH}"
echo "$CURRENT → $NEW_VERSION ($BUMP_TYPE)"

# 写入 VERSION 文件
echo "$NEW_VERSION" > "$VERSION_FILE"
echo "VERSION file updated: $NEW_VERSION"

# 不直接改 main.py 代码（main.py 已经从 VERSION 文件读取）
# 只需要确保 VERSION 文件被 git 追踪即可

echo "Version bumped successfully"
