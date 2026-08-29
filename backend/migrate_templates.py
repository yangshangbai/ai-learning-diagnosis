#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""模板功能增量迁移（幂等，不删库不重建）。

本脚本为「试卷模板 & 答题卡模板」功能一次性/多次可重复执行的迁移：
  1. paper_templates 表：CREATE TABLE IF NOT EXISTS（新增）
  2. answer_sheet_templates 表：ALTER TABLE ... ADD COLUMN IF NOT EXISTS（补 6 列）

用法（在本 backend/ 目录下执行，自动读取 .env 的 DATABASE_URL）：
    venv/Scripts/python.exe migrate_templates.py
    venv/Scripts/python.exe migrate_templates.py --check   # 只校验列是否齐全，不执行 DDL

PostgreSQL 语法（生产/本地飞牛 PG 同结构）；不 drop 任何表、不动已有数据。
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import inspect, text  # noqa: E402

from app.core.db import engine  # noqa: E402

# paper_templates 建表（与 app/models/paper.py PaperTemplate 对应）
_CREATE_PAPER_TEMPLATES = """
CREATE TABLE IF NOT EXISTS paper_templates (
  id          SERIAL PRIMARY KEY,
  paper_id    INTEGER NOT NULL UNIQUE REFERENCES papers(id) ON DELETE CASCADE,
  file_name   VARCHAR(255),
  file_type   VARCHAR(20) DEFAULT 'docx',
  file_size   INTEGER DEFAULT 0,
  file_path   VARCHAR(500),
  layout_config JSON,
  source      VARCHAR(20) DEFAULT 'auto',
  updated_by  INTEGER,
  created_at  TIMESTAMPTZ DEFAULT now(),
  updated_at  TIMESTAMPTZ DEFAULT now()
);
"""

# answer_sheet_templates 增量补列（不重建表）
_ALTER_SHEET_COLUMNS = [
    ("file_name", "VARCHAR(255)"),
    ("file_type", "VARCHAR(20) DEFAULT 'docx'"),
    ("file_size", "INTEGER DEFAULT 0"),
    ("file_path", "VARCHAR(500)"),
    ("source", "VARCHAR(20) DEFAULT 'auto'"),
    ("updated_at", "TIMESTAMPTZ DEFAULT now()"),
]

_SHEET_EXPECTED = [c[0] for c in _ALTER_SHEET_COLUMNS] + ["id", "paper_id", "layout_config", "created_at"]


def _sheet_existing_cols() -> set:
    insp = inspect(engine)
    if not insp.has_table("answer_sheet_templates"):
        return set()
    return {c["name"] for c in insp.get_columns("answer_sheet_templates")}


def migrate() -> dict:
    result = {"paper_templates_created": False, "sheet_columns_added": []}
    with engine.begin() as conn:
        conn.execute(text(_CREATE_PAPER_TEMPLATES))
        result["paper_templates_created"] = True

        if inspect(conn).has_table("answer_sheet_templates"):
            existing = _sheet_existing_cols()
            for col, ddl in _ALTER_SHEET_COLUMNS:
                if col not in existing:
                    conn.execute(text(f'ALTER TABLE answer_sheet_templates ADD COLUMN IF NOT EXISTS {col} {ddl}'))
                    result["sheet_columns_added"].append(col)
                    existing.add(col)
    return result


def check() -> dict:
    """只校验，不执行 DDL。返回列齐全情况。"""
    insp = inspect(engine)
    report = {
        "paper_templates_exists": insp.has_table("paper_templates"),
        "answer_sheet_templates_exists": insp.has_table("answer_sheet_templates"),
        "answer_sheet_templates_missing": [],
    }
    if report["answer_sheet_templates_exists"]:
        cols = {c["name"] for c in insp.get_columns("answer_sheet_templates")}
        report["answer_sheet_templates_missing"] = [c for c in _SHEET_EXPECTED if c not in cols]
    return report


def main():
    ap = argparse.ArgumentParser(description="试卷/答题卡模板增量迁移（幂等）")
    ap.add_argument("--check", action="store_true", help="只校验列是否齐全，不执行 DDL")
    args = ap.parse_args()

    if args.check:
        rep = check()
        print("[CHECK] paper_templates 表存在:", rep["paper_templates_exists"])
        print("[CHECK] answer_sheet_templates 表存在:", rep["answer_sheet_templates_exists"])
        print("[CHECK] answer_sheet_templates 缺失列:", rep["answer_sheet_templates_missing"] or "（无，全部齐全）")
        if rep["paper_templates_exists"] and not rep["answer_sheet_templates_missing"]:
            print("[CHECK] 迁移已就绪")
        else:
            print("[CHECK] 需要执行迁移（去掉 --check 运行）")
        sys.exit(0 if (rep["paper_templates_exists"] and not rep["answer_sheet_templates_missing"]) else 1)

    res = migrate()
    print("[MIGRATE] paper_templates 建表完成:", res["paper_templates_created"])
    if res["sheet_columns_added"]:
        print("[MIGRATE] answer_sheet_templates 补列:", res["sheet_columns_added"])
    else:
        print("[MIGRATE] answer_sheet_templates 列已齐全，无需补列（幂等跳过）")
    # 复核
    rep = check()
    assert rep["paper_templates_exists"], "paper_templates 建表失败"
    assert not rep["answer_sheet_templates_missing"], f"仍有缺失列: {rep['answer_sheet_templates_missing']}"
    print("[MIGRATE] 校验通过：全部列就绪")


if __name__ == "__main__":
    main()
