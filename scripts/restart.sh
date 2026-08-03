#!/bin/bash
# AI学习诊断系统 - 重启脚本 (Linux/Mac)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
bash "$SCRIPT_DIR/stop.sh"
sleep 2
bash "$SCRIPT_DIR/start.sh"
