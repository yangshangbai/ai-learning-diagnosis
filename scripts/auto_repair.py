#!/usr/bin/env python3
"""
AI学习诊断系统 — 自动错误分析与修复脚本
============================================
功能:
  1. 扫描 error_logs 表中 Repair=False 的错误
  2. 智能分类：程序Bug vs 非程序问题
  3. 非程序问题 → 自动标记 Repair=True
  4. 程序Bug → 分析堆栈，尝试自动修复，或生成修复报告
  5. 输出 JSON 报告供 CI/CD 流程使用

运行: python auto_repair.py [--dry-run] [--auto-fix]
"""

import os
import sys
import json
import re
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent  # /opt/ai-learning
BACKEND_DIR = PROJECT_ROOT / "backend"
REPORT_FILE = PROJECT_ROOT / "logs" / "auto_repair_report.json"
LOCK_FILE = PROJECT_ROOT / "logs" / "auto_repair.lock"

# ---------------------------------------------------------------------------
# 错误分类规则
# ---------------------------------------------------------------------------

# 非程序问题 — 客户端或运维问题，直接标记 Repair=True
NOT_BUG_PATTERNS = {
    "HTTP 401": {
        "patterns": ["invalid token", "无效的认证凭证", "未认证", "not authenticated",
                     "Could not validate", "Token has expired", "401 on"],
        "note": "客户端认证失败（Token缺失/过期/无效），非程序Bug",
    },
    "HTTP 404": {
        "patterns": ["404 on", "Not Found", "not found", "does not exist"],
        "note": "客户端请求了不存在的资源，非程序Bug",
    },
    "HTTP 400": {
        "patterns": ["400 on", "Bad Request", "validation error", "文件类型"],
        "note": "客户端请求参数/数据格式错误，非程序Bug",
    },
    "HTTP 405": {
        "patterns": ["405 on", "Method Not Allowed"],
        "note": "客户端使用了错误的HTTP方法，非程序Bug",
    },
    "HTTP 413": {
        "patterns": ["413 on", "Payload Too Large", "exceeds"],
        "note": "客户端上传文件过大，非程序Bug（可调整Nginx限制）",
    },
    "HTTP 409": {
        "patterns": ["409 on", "Conflict", "不能被删除", "仍有"],
        "note": "业务规则冲突（如FK保护），预期行为，非Bug",
    },
    "HTTP 422": {
        "patterns": ["422 on", "Validation", "min_length", "field required"],
        "note": "请求参数验证失败，客户端数据问题，非程序Bug",
    },
    "HTTP 403": {
        "patterns": ["403 on", "Forbidden", "权限不足", "你没有权限"],
        "note": "权限不足，RBAC正常拒绝，非程序Bug",
    },
}

# 程序Bug — 代码逻辑问题，需要修复
BUG_PATTERNS = {
    "TypeError": {
        "patterns": ["'NoneType' object is not subscriptable",
                     "object is not callable",
                     "can only concatenate str",
                     "not iterable",
                     "is not a function",
                     "cannot read propert",
                     "undefined is not"],
        "severity": "HIGH",
    },
    "AttributeError": {
        "patterns": ["object has no attribute",
                     "has no attribute"],
        "severity": "HIGH",
    },
    "ProgrammingError": {
        "patterns": ["sqlalchemy", "psycopg2", "asyncpg",
                     "syntax error", "column.*does not exist",
                     "relation.*does not exist"],
        "severity": "CRITICAL",
    },
    "IntegrityError": {
        "patterns": ["duplicate key", "violates unique",
                     "violates foreign key", "violates not-null"],
        "severity": "MEDIUM",
    },
    "KeyError": {
        "patterns": ["KeyError"],
        "severity": "MEDIUM",
    },
    "ValueError": {
        "patterns": ["ValueError", "invalid literal"],
        "severity": "MEDIUM",
    },
    "ImportError": {
        "patterns": ["No module named", "ImportError", "ModuleNotFoundError"],
        "severity": "CRITICAL",
    },
}


def is_program_bug(error_type: str, error_message: str) -> tuple[bool, str, str]:
    """
    判断错误是否为程序Bug。
    返回: (is_bug, category, note)
    """
    combined = f"{error_type} {error_message}".lower()

    # 先检查是否匹配程序Bug模式
    for bug_type, config in BUG_PATTERNS.items():
        if bug_type.lower() in combined:
            for pattern in config["patterns"]:
                if pattern.lower() in combined:
                    return True, bug_type, config["severity"]

    # 再检查是否匹配非Bug模式
    for not_bug_type, config in NOT_BUG_PATTERNS.items():
        if not_bug_type.lower() in combined:
            for pattern in config["patterns"]:
                if pattern.lower() in combined:
                    return False, not_bug_type, config["note"]

    # HTTP 5xx 默认视为可能的程序Bug
    if "500" in error_type or "500" in str(error_message)[:10]:
        return True, "HTTP 500", "HIGH"

    # 默认: 无法分类，标记为非Bug（保守策略）
    return False, "UNKNOWN", "无法自动分类，标记为非程序问题（保守策略）"


def parse_stack_trace(stack_trace: str) -> list[dict]:
    """解析堆栈跟踪，提取文件路径和行号。"""
    if not stack_trace:
        return []

    files = []
    # 匹配类似: File "/path/to/file.py", line 42, in function_name
    pattern = re.compile(
        r'File\s+"([^"]+)",\s*line\s+(\d+),\s*in\s+(\S+)'
    )
    for match in pattern.finditer(stack_trace):
        filepath = match.group(1)
        # 只关注项目内的文件
        if "/opt/ai-learning/" in filepath or "backend" in filepath:
            files.append({
                "file": filepath,
                "line": int(match.group(2)),
                "function": match.group(3),
            })

    return files


def analyze_error(row: dict) -> dict:
    """分析单条错误记录。"""
    error_type = row.get("error_type", "")
    error_message = row.get("error_message", "")
    stack_trace = row.get("stack_trace", "")
    endpoint = row.get("endpoint", "")
    method = row.get("method", "")

    is_bug, category, note = is_program_bug(error_type, error_message)
    stack_files = parse_stack_trace(stack_trace)

    result = {
        "id": row["id"],
        "timestamp": str(row.get("timestamp", "")),
        "endpoint": endpoint,
        "method": method,
        "error_type": error_type,
        "error_message": error_message[:300],
        "is_bug": is_bug,
        "category": category,
        "note": note,
        "stack_files": stack_files,
        "auto_fixable": False,
        "fix_action": None,
    }

    # 判断是否可自动修复
    if is_bug and stack_files:
        result["auto_fixable"] = assess_auto_fix(result, stack_files)

    return result


def assess_auto_fix(result: dict, stack_files: list[dict]) -> dict | None:
    """评估是否可以自动修复，返回修复方案。"""
    error_type = result["error_type"]
    error_msg = result["error_message"]

    # --- 可自动修复的模式 ---

    # 1. ImportError / ModuleNotFoundError → 安装依赖
    if error_type in ("ImportError", "ModuleNotFoundError"):
        match = re.search(r"No module named '(\w+)'", error_msg)
        if match:
            module = match.group(1)
            return {
                "type": "pip_install",
                "module": module,
                "command": f"pip install {module}",
                "description": f"安装缺失的Python包: {module}",
            }

    # 2. IntegrityError: duplicate key → 重置序列
    if "IntegrityError" in error_type and "duplicate key" in error_msg.lower():
        # 提取表名
        table_match = re.search(r'relation "(\w+)"', error_msg)
        table = table_match.group(1) if table_match else "unknown"
        return {
            "type": "reset_sequence",
            "table": table,
            "command": f"SELECT setval('{table}_id_seq', (SELECT MAX(id)+1 FROM {table}))",
            "description": f"重置 {table} 表的主键序列",
        }

    # 3. TypeError: 'NoneType' ... not subscriptable → 添加空值检查
    if "NoneType" in error_msg and "subscriptable" in error_msg:
        if stack_files:
            target = stack_files[0]
            return {
                "type": "null_check",
                "file": target["file"],
                "line": target["line"],
                "function": target["function"],
                "description": f"在 {target['function']}() 第{target['line']}行添加空值检查",
            }

    # 4. AttributeError: has no attribute → 可能缺少导入或属性拼写错误
    if "AttributeError" in error_type:
        match = re.search(r"has no attribute '(\w+)'", error_msg)
        if match and stack_files:
            attr = match.group(1)
            target = stack_files[0]
            return {
                "type": "attribute_error",
                "file": target["file"],
                "line": target["line"],
                "missing_attr": attr,
                "description": f"对象缺少属性 '{attr}'，需检查 {target['file']}:{target['line']}",
            }

    return None


def generate_repair_summary(analyses: list[dict]) -> dict:
    """生成修复汇总报告。"""
    total = len(analyses)
    bugs = [a for a in analyses if a["is_bug"]]
    non_bugs = [a for a in analyses if not a["is_bug"]]
    auto_fixable = [a for a in analyses if a.get("auto_fixable")]

    return {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "total_errors": total,
        "program_bugs": len(bugs),
        "non_program_issues": len(non_bugs),
        "auto_fixable": len(auto_fixable),
        "bugs_detail": bugs,
        "non_bugs_detail": [{"id": a["id"], "note": a["note"]} for a in non_bugs],
        "fix_suggestions": [
            {"id": a["id"], "fix": a.get("fix_action")}
            for a in auto_fixable
        ],
    }


# ---------------------------------------------------------------------------
# 数据库操作
# ---------------------------------------------------------------------------

async def fetch_unrepaired_errors():
    """从数据库获取所有 Repair=False 的错误。"""
    import os
    # 确保环境变量已加载
    from dotenv import load_dotenv
    load_dotenv(BACKEND_DIR / ".env")

    # 将项目路径加入 sys.path
    sys.path.insert(0, str(BACKEND_DIR))

    from database import async_session_factory
    from models.error_log import ErrorLog
    from sqlalchemy import select

    async with async_session_factory() as session:
        result = await session.execute(
            select(ErrorLog).where(ErrorLog.repair == False).order_by(ErrorLog.id)
        )
        rows = result.scalars().all()

        data = []
        for row in rows:
            data.append({
                "id": row.id,
                "timestamp": row.timestamp,
                "endpoint": row.endpoint,
                "method": row.method,
                "error_type": row.error_type,
                "error_message": row.error_message,
                "status_code": row.status_code,
                "stack_trace": row.stack_trace,
                "source": row.source,
            })
        return data


async def mark_repaired(session, error_id: int, note: str, repaired_by: str = "auto_repair"):
    """标记错误为已修复。"""
    from sqlalchemy import update
    from models.error_log import ErrorLog

    await session.execute(
        update(ErrorLog)
        .where(ErrorLog.id == error_id)
        .values(
            repair=True,
            repair_note=note,
            repaired_at=datetime.now(timezone.utc),
            repaired_by=repaired_by,
        )
    )


async def apply_repairs(errors_data: list[dict], analyses: list[dict], dry_run: bool = False):
    """应用修复：标记非Bug为已修复，记录Bug信息。"""
    import os
    from dotenv import load_dotenv
    load_dotenv(BACKEND_DIR / ".env")

    sys.path.insert(0, str(BACKEND_DIR))
    from database import async_session_factory
    from models.error_log import ErrorLog
    from sqlalchemy import select, update

    marked = 0
    async with async_session_factory() as session:
        for analysis in analyses:
            if analysis["is_bug"]:
                # 程序Bug：记录但不自动标记修复
                # 如果有自动修复方案，在日志中注明
                if analysis.get("auto_fixable"):
                    note = f"[待修复] {analysis['category']}: {analysis['fix_action']['description']}"
                else:
                    note = f"[待人工修复] {analysis['category']}: 需手动排查 {analysis['error_message'][:100]}"
                # Bug 暂不标记 repair=True，留给人工确认
                if not dry_run:
                    await session.execute(
                        update(ErrorLog)
                        .where(ErrorLog.id == analysis["id"])
                        .values(repair_note=note)
                    )
            else:
                # 非程序问题：直接标记 Repair=True
                if not dry_run:
                    await mark_repaired(session, analysis["id"], analysis["note"])
                marked += 1

        if not dry_run:
            await session.commit()

    return marked


# ---------------------------------------------------------------------------
# 自动代码修复
# ---------------------------------------------------------------------------

def apply_code_fix(fix_action: dict) -> bool:
    """对单个文件应用代码修复。返回是否成功。"""
    fix_type = fix_action.get("type", "")
    target_file = fix_action.get("file", "")

    if not target_file or not os.path.exists(target_file):
        print(f"  [WARN] 目标文件不存在: {target_file}")
        return False

    if fix_type == "null_check":
        return _apply_null_check_fix(fix_action)

    if fix_type == "pip_install":
        return _apply_pip_install(fix_action)

    print(f"  [INFO] 修复类型 '{fix_type}' 暂不支持自动修复")
    return False


def _apply_null_check_fix(fix_action: dict) -> bool:
    """添加空值检查。"""
    target_file = fix_action["file"]
    target_line = fix_action["line"]
    function_name = fix_action.get("function", "")

    try:
        with open(target_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if target_line > len(lines):
            return False

        # 获取目标行的缩进
        target = lines[target_line - 1]
        indent = len(target) - len(target.lstrip())
        indent_str = " " * indent

        # 提取目标行中的变量名（简单的启发式方法）
        var_match = re.search(r'(\w+)\[', target)
        var_name = var_match.group(1) if var_match else "data"

        # 插入空值检查
        guard_line = f'{indent_str}if {var_name} is None:\n'
        return_line = f'{indent_str}    return None  # auto-repair: null guard\n'

        lines.insert(target_line - 1, return_line)
        lines.insert(target_line - 1, guard_line)

        with open(target_file, "w", encoding="utf-8") as f:
            f.writelines(lines)

        print(f"  [FIXED] {target_file}:{target_line} — 添加空值检查")
        return True
    except Exception as e:
        print(f"  [ERROR] 修复失败: {e}")
        return False


def _apply_pip_install(fix_action: dict) -> bool:
    """安装缺失的 Python 包。"""
    import subprocess
    module = fix_action.get("module", "")
    venv_pip = str(BACKEND_DIR / "venv" / "bin" / "pip")

    try:
        result = subprocess.run(
            [venv_pip, "install", module],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            print(f"  [FIXED] pip install {module} — 成功")
            return True
        else:
            print(f"  [ERROR] pip install {module} — 失败: {result.stderr[:200]}")
            return False
    except Exception as e:
        print(f"  [ERROR] pip install 异常: {e}")
        return False


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main():
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description="AI学习诊断系统自动错误修复")
    parser.add_argument("--dry-run", action="store_true", help="仅分析，不实际修改")
    parser.add_argument("--auto-fix", action="store_true", help="尝试自动修复代码Bug")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    args = parser.parse_args()

    # 防止并发运行
    if LOCK_FILE.exists():
        print("[SKIP] 上一次修复任务仍在运行中 (lock file exists)")
        return

    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOCK_FILE.touch()

    try:
        print("=" * 60)
        print(f"  AI学习诊断系统 — 自动错误修复")
        print(f"  运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  模式: {'DRY-RUN (仅分析)' if args.dry_run else 'LIVE (执行修复)'}")
        print("=" * 60)

        # 1. 获取未修复错误
        print("\n[1/4] 查询未修复错误...")
        errors = asyncio.run(fetch_unrepaired_errors())
        print(f"  发现 {len(errors)} 条 Repair=False 的错误")

        if not errors:
            print("  ✅ 没有需要修复的错误")
            LOCK_FILE.unlink()
            return

        # 2. 分析每条错误
        print("\n[2/4] 智能分类错误...")
        analyses = []
        bug_count = 0
        non_bug_count = 0

        for err in errors:
            analysis = analyze_error(err)
            analyses.append(analysis)

            if args.verbose:
                flag = "🐛 BUG" if analysis["is_bug"] else "✅ OK"
                print(f"  [{flag}] #{analysis['id']} {analysis['error_type']}: "
                      f"{analysis['error_message'][:80]}")

            if analysis["is_bug"]:
                bug_count += 1
            else:
                non_bug_count += 1

        print(f"  程序Bug: {bug_count} 条")
        print(f"  非程序问题: {non_bug_count} 条 (将自动标记为已修复)")

        # 3. 尝试自动修复
        if args.auto_fix:
            print("\n[3/4] 尝试自动修复程序Bug...")
            fixed = 0
            for analysis in analyses:
                if analysis.get("auto_fixable") and analysis.get("fix_action"):
                    fix = analysis["fix_action"]
                    print(f"  → #{analysis['id']} {fix['description']}")
                    if not args.dry_run:
                        success = apply_code_fix(fix)
                        if success:
                            fixed += 1
            print(f"  自动修复: {fixed} 处")
        else:
            print("\n[3/4] 跳过自动修复 (使用 --auto-fix 启用)")

        # 4. 应用标记修复
        print("\n[4/4] 更新数据库修复标记...")
        if args.dry_run:
            print(f"  [DRY-RUN] 将标记 {non_bug_count} 条为非Bug已修复")
        else:
            marked = asyncio.run(apply_repairs(errors, analyses, dry_run=False))
            print(f"  已标记 {marked} 条为非程序问题 (Repair=True)")

        # 生成报告
        summary = generate_repair_summary(analyses)
        REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(REPORT_FILE, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"\n📄 报告已保存: {REPORT_FILE}")

        # 摘要
        print("\n" + "=" * 60)
        print(f"  处理完成!")
        print(f"  ✅ 自动标记修复: {non_bug_count} 条")
        if args.auto_fix:
            auto = len([a for a in analyses if a.get("auto_fixable")])
            print(f"  🔧 可自动修复: {auto} 条")
        print(f"  ⚠️  待人工处理: {bug_count} 条")
        print(f"  📄 详细报告: {REPORT_FILE}")
        print("=" * 60)

    except Exception as e:
        print(f"\n[FATAL] 脚本执行错误: {e}")
        traceback.print_exc()
    finally:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()


if __name__ == "__main__":
    main()
